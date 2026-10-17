import csv
import random
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from aimlab_game_modes import Config,Game,MODES
from aimlab_training import HitReader, MouseInput, Results, LEGACY_COLUMNS, RESULT_COLUMNS, read_results, render_frame, load_background, DEFAULT_BACKGROUND


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'hits.csv'
        self.path.write_text('utc,monotonic_s,pixel_x,pixel_y,u,v\nold,10,0,0,.5,.5\n')
        self.reader = HitReader(self.path)

    def tearDown(self):
        self.reader.close()
        self.temp.cleanup()

    def append(self,text):
        with self.path.open('a') as stream:
            stream.write(text)

    def test_tail_and_partial_lines(self):
        self.assertEqual(self.reader.read(),[])
        self.append('new,20,0,0,.3,')
        self.assertEqual(self.reader.read(),[])
        self.append('.4\nnew,21,0,0,.5,.6\n')
        self.assertEqual(self.reader.read(),[(20,.3,.4),(21,.5,.6)])

    def test_partial_previous_session(self):
        self.append('old,22,0,0,.4,')
        self.reader.read()
        self.reader.reset()
        self.append('.5\nnew,30,0,0,.5,.6\n')
        self.assertEqual(self.reader.read(),[(30,.5,.6)])

    def test_rotation_ignores_old_content(self):
        replacement=self.path.with_suffix('.new')
        replacement.write_text('old,11,0,0,.5,.5\n')
        replacement.replace(self.path)
        self.assertEqual(self.reader.read(),[])
        self.assertEqual(self.reader.generation,1)
        self.append('new,25,0,0,.4,.6\n')
        self.assertEqual(self.reader.read(),[(25,.4,.6)])

    def test_truncation_and_same_inode_rewrite(self):
        self.path.write_text('old,12,0,0,.5,.5\n')
        self.assertEqual(self.reader.read(),[])
        self.assertEqual(self.reader.generation,1)
        self.path.write_text('rewritten,13,0,0,.5,.5\n'*20)
        self.assertEqual(self.reader.read(),[])
        self.assertEqual(self.reader.generation,2)

    def test_missing_file_then_reappears(self):
        self.path.unlink()
        self.assertEqual(self.reader.read(),[])
        self.path.write_text('old,10,0,0,.5,.5\n')
        self.assertEqual(self.reader.read(),[])
        self.assertEqual(self.reader.generation,1)

    def test_invalid_rows(self):
        self.append('utc,monotonic_s,pixel_x,pixel_y,u,v\nbad\nx,40,0,0,nan,.5\nx,41,0,0,1.2,.5\nx,42,0,0,.2,.4\n')
        self.assertEqual(self.reader.read(),[(42,.2,.4)])


class RenderingAndInputTests(unittest.TestCase):
    def test_mouse_uses_same_engine(self):
        game=Game(Config(mode='sixshot'),random.Random(5))
        game.start(100)
        game.presented(100.1)
        target=game.targets[0]
        mouse=MouseInput(1920,1080)
        with patch('aimlab_training.time.monotonic',return_value=101):
            mouse.callback(cv2.EVENT_LBUTTONDOWN,round(target.x),round(target.y),None,None)
            mouse.callback(cv2.EVENT_MOUSEMOVE,0,0,None,None)
        events=mouse.read()
        self.assertEqual(len(events),1)
        shot=game.fire(*events[0],now=101,source='mouse')
        self.assertEqual((shot.result,shot.source),('hit','mouse'))
        self.assertEqual(mouse.read(),[])

    def test_all_modes_render_without_camera_or_projector(self):
        for mode in MODES:
            game=Game(Config(mode=mode,width=1280,height=720),random.Random(1))
            base=load_background(DEFAULT_BACKGROUND,1280,720)
            before=base.copy()
            game.start(10)
            frame=render_frame(base,game,10,10)
            self.assertEqual(frame.shape,(720,1280,3))
            self.assertFalse(np.array_equal(frame,base))
            self.assertTrue(np.array_equal(base,before))
            game.finish(11)
            self.assertEqual(render_frame(base,game,11,10).shape,frame.shape)

    def test_legacy_results_can_be_read(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'legacy.csv'
            with path.open('w',newline='') as f:
                writer=csv.writer(f)
                writer.writerow(LEGACY_COLUMNS)
                writer.writerow([1,'2026-10-14T19:00:00Z',1,'hit',.2,.4,.2,.4,500])
            row=list(read_results(path))[0]
            self.assertEqual(row['mode_id'],'classic')
            self.assertEqual(row['schema_version'],'1')
            self.assertEqual(row['target_age_ms'],'500')
            self.assertEqual(row['mean_hit_interval_ms'],'')

    def test_new_results_keep_legacy_prefix_and_summary(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'results.csv'
            game=Game(Config(mode='gridshot'),random.Random(1))
            game.start(10)
            game.presented(10.1)
            t=game.targets[0]
            shot=game.fire(11,t.x/1919,t.y/1079,11,source='mouse')
            writer=Results(path)
            writer.write(game,1,'session-id',11,shot)
            game.finish(12)
            writer.write(game,1,'session-id',12)
            writer.close()
            with path.open() as f:
                reader=csv.DictReader(f)
                rows=list(reader)
                self.assertEqual(reader.fieldnames[:len(LEGACY_COLUMNS)],LEGACY_COLUMNS)
                self.assertEqual(reader.fieldnames,RESULT_COLUMNS)
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[0]['source'],'mouse')
            self.assertEqual(rows[0]['mode_id'],'gridshot')
            self.assertEqual(rows[0]['error_px'],'0.0')
            self.assertEqual(rows[1]['event_type'],'summary')
            self.assertEqual(rows[1]['duration_s'],'2')


if __name__=='__main__':
    unittest.main()
