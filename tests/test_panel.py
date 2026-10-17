"""Optional GTK integration tests; skip cleanly on headless/venv-only hosts."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
try:
    import aimlab_panel as panel
    GTK_AVAILABLE = bool(panel.Gtk.init_check()[0])
except (ImportError,ValueError):
    GTK_AVAILABLE = False


@unittest.skipUnless(GTK_AVAILABLE,'System Python, GTK3 and a graphical session are required')
class PanelTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=patch.object(panel,'ROOT',Path(self.temp.name))
        self.root.start()
        self.window=panel.Panel()

    def tearDown(self):
        panel.GLib.source_remove(self.window.poll_source)
        self.window.log.close()
        self.window.destroy()
        self.root.stop()
        self.temp.cleanup()

    def test_video_mode_routes_start_to_calibration(self):
        self.window.fields['mode'].set_active_id('video-calibration')
        self.window.poll()
        self.assertFalse(self.window.fields['radius'].get_sensitive())
        self.window.save()
        self.assertEqual(panel.load_settings()['mode'],'video-calibration')
        with patch.object(self.window,'video_calibration') as start:
            self.window.train()
            start.assert_called_once()

    def test_video_completion_restores_training(self):
        self.window.fields['mode'].set_active_id('gridshot')
        self.window.fields['mode'].set_active_id('video-calibration')
        self.window.video_running = True
        process = Mock()
        process.poll.return_value = 0
        self.window.children['projector'] = process
        self.window.poll()
        self.assertFalse(self.window.video_running)
        self.assertEqual(self.window.fields['mode'].get_active_id(),'gridshot')
        self.assertEqual(panel.load_settings()['mode'],'gridshot')

    def test_pending_training_waits_for_camera(self):
        self.window.pending = ['--mode','classic']
        process = Mock()
        process.poll.return_value = None
        self.window.children['camera'] = process
        with patch.object(self.window,'state',return_value={}),patch.object(self.window,'spawn') as spawn:
            self.window.poll()
            spawn.assert_not_called()
            self.assertIsNotNone(self.window.pending)
        state = dict(calibrated=True,minimum=180,delta=45,laser_color='green')
        with patch.object(self.window,'state',return_value=state),patch.object(self.window,'spawn') as spawn:
            self.window.poll()
            spawn.assert_called_once()
            self.assertIsNone(self.window.pending)
        self.window.children.clear()

    def test_mode_defaults_and_control_sensitivity(self):
        for name,radius,count in [('gridshot',70,3),('sixshot',30,6),('multishot',55,5),('spidershot',70,1),('trap-spidershot',70,1),('classic',70,1)]:
            self.window.fields['mode'].set_active_id(name)
            self.window.poll()
            self.assertEqual(self.window.fields['radius'].get_value_as_int(),radius)
            self.assertEqual(self.window.fields['active_targets'].get_value_as_int(),count)
            self.assertEqual(self.window.fields['duration'].get_sensitive(),name!='classic')
            self.assertEqual(self.window.fields['targets'].get_sensitive(),name=='classic')
            self.assertEqual(self.window.fields['active_targets'].get_sensitive(),name not in ('classic','spidershot','trap-spidershot'))

    def test_mouse_start_does_not_require_camera(self):
        self.window.fields['input_method'].set_active_id('mouse')
        self.window.fields['mode'].set_active_id('sixshot')
        self.assertIsNotNone(self.window.fields['screen'].get_active_id())
        with patch.object(self.window,'spawn') as spawn:
            self.window.train()
            self.window.poll()
            self.assertEqual(spawn.call_args.args[:2],('training','aimlab_training.py'))
            args=spawn.call_args.args[2]
            self.assertIn('--mouse-test',args)
            self.assertIn('sixshot',args)
            self.assertIn('--active-targets',args)

    def test_trap_mode_keeps_selected_side_appearance(self):
        self.window.fields['input_method'].set_active_id('mouse')
        self.window.fields['target_style'].set_active_id('black')
        self.window.fields['mode'].set_active_id('trap-spidershot')
        self.window.poll()
        self.assertEqual(self.window.fields['target_style'].get_active_id(),'black')
        self.assertFalse(self.window.fields['active_targets'].get_sensitive())
        with patch.object(self.window,'spawn') as spawn:
            self.window.train()
            self.window.poll()
            args=spawn.call_args.args[2]
            self.assertEqual(args[args.index('--mode')+1],'trap-spidershot')
            self.assertEqual(args[args.index('--target-style')+1],'black')

    def test_target_style_is_saved_and_sent_to_training(self):
        self.assertEqual(self.window.fields['target_style'].get_active_id(),'orange')
        self.window.fields['input_method'].set_active_id('mouse')
        for style in ('orange','black','orange-black','classic'):
            self.window.fields['target_style'].set_active_id(style)
            with patch.object(self.window,'spawn') as spawn:
                self.window.train()
                self.window.poll()
                args=spawn.call_args.args[2]
                self.assertEqual(args[args.index('--target-style')+1],style)
            self.assertEqual(panel.load_settings()['target_style'],style)

    def test_save_new_and_load_old_settings(self):
        self.window.fields['mode'].set_active_id('multishot')
        self.window.fields['duration'].set_active_id('120')
        self.window.save()
        values=panel.load_settings()
        self.assertEqual((values['mode'],values['duration'],values['active_targets']),('multishot',120,5))
        (panel.ROOT/'aimlab_settings.json').write_text(json.dumps({'radius':90,'targets':12}))
        values=panel.load_settings()
        self.assertEqual((values['mode'],values['radius'],values['targets']),('classic',90,12))


if __name__=='__main__':
    unittest.main()
