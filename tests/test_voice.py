import unittest
from aimlab_game_modes import Config,Game
from aimlab_voice import command_from_result


class VoiceTests(unittest.TestCase):
    def test_waits_for_daj_and_does_not_queue_while_target_is_active(self):
        game = Game(Config(mode='voice',classic_total=2))
        game.start(10)
        self.assertFalse(game.targets)
        self.assertFalse(game.activate_voice(9,11))
        self.assertTrue(game.activate_voice(11,12))
        self.assertFalse(game.activate_voice(12,13))
        game.presented(12)
        target = game.targets[0]
        shot=game.fire(13,target.x/1919,target.y/1079,13)
        self.assertEqual(shot.result,'hit')
        self.assertFalse(game.targets)
        self.assertFalse(game.activate_voice(12.5,14))
        game.tick(100)
        self.assertEqual(game.state,'running')
        self.assertTrue(game.activate_voice(100,101))
        game.presented(101)
        target=game.targets[0]
        game.fire(102,target.x/1919,target.y/1079,102)
        self.assertEqual(game.state,'finished')
        self.assertFalse(game.activate_voice(103,104))
        game.start(200)
        self.assertFalse(game.targets)
        self.assertFalse(game.activate_voice(199,201))

    def test_exact_command_with_confidence(self):
        result=dict(text='daj',result=[dict(word='daj',conf=.95,start=1.2)])
        self.assertEqual(command_from_result(result,100),101.2)
        for text in ('','dalej','daj mi','[unk]'):
            self.assertIsNone(command_from_result(dict(result,text=text),100))
        result['result'][0]['conf']=.5
        self.assertIsNone(command_from_result(result,100))
