"""Exercise complete training sessions with the real engine and simulated mouse input."""
import contextlib
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import aimlab_training as training
from aimlab_game_modes import Game,MODES


class LoopTests(unittest.TestCase):
    def test_every_mode_mouse_hits_end_and_restart(self):
        for mode in MODES:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as directory:
                clock=[0.]
                games=[]
                callback=[]
                restarts=[0]
                frames=[0]
                def factory(config, **kwargs):
                    game=Game(config, **kwargs)
                    games.append(game)
                    return game
                def wait_key(delay):
                    frames[0]+=1
                    self.assertLess(frames[0],250,'Training loop failed to complete')
                    game=games[-1]
                    if game.state=='finished':
                        if restarts[0]==0:
                            restarts[0]+=1
                            return ord(' ')
                        return ord('q')
                    if game.state=='running' and game.targets:
                        target=game.targets[0]
                        if target.activated_at is not None:
                            callback[0](cv2.EVENT_LBUTTONDOWN,round(target.x),round(target.y),0,None)
                    clock[0]+=1 if game.state=='idle' else .05
                    return -1
                args=['aimlab_training.py','--mode',mode,'--mouse-test','--duration','.5','--targets','2',
                      '--width','960','--height','540','--hits',str(Path(directory)/'no_camera_needed.csv')]
                with patch.object(training.sys,'argv',args),patch.object(training,'Game',side_effect=factory), \
                     patch.object(training.time,'monotonic',side_effect=lambda:clock[0]), \
                     patch.object(cv2,'namedWindow'),patch.object(cv2,'moveWindow'), \
                     patch.object(cv2,'setWindowProperty'),patch.object(cv2,'imshow'), \
                     patch.object(cv2,'getWindowProperty',return_value=1),patch.object(cv2,'destroyAllWindows'), \
                     patch.object(cv2,'setMouseCallback',side_effect=lambda name,fn:callback.append(fn)), \
                     patch.object(cv2,'waitKey',side_effect=wait_key),contextlib.redirect_stdout(io.StringIO()):
                    training.main()
                result=next(Path(directory).glob('aimlab_training_*.csv'))
                with result.open() as stream:
                    rows=list(csv.DictReader(stream))
                summaries=[r for r in rows if r['event_type']=='summary']
                shots=[r for r in rows if r['event_type']=='shot']
                self.assertEqual(len(summaries),2)
                self.assertEqual(len({r['session_id'] for r in summaries}),2)
                self.assertTrue(all(r['result']=='finished' for r in summaries))
                self.assertTrue(shots)
                self.assertTrue(all(r['source']=='mouse' for r in shots))
                self.assertTrue(all(int(r['hits'])>0 for r in summaries))
                if mode=='classic':
                    self.assertTrue(all(int(r['hits'])==2 for r in summaries))


if __name__=='__main__':
    unittest.main()
