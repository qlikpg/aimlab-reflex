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

    def test_entire_target_is_in_upper_half(self):
        import random
        for width,height in ((1920,1080),(960,540),(320,240)):
            game = Game(Config(mode='voice',width=width,height=height),random.Random(8))
            game.start(0)
            for index in range(50):
                self.assertTrue(game.activate_voice(index*2,index*2))
                target=game.targets[0]
                self.assertLess(target.y+target.radius+6,height/2)
                self.assertGreaterEqual(target.y-target.radius,0)
                game.presented(index*2+.1)
                game.fire(index*2+1,target.x/(width-1),target.y/(height-1),index*2+1)
                if game.state=='finished':
                    game.start(index*2+1)

    def test_blue_guide_has_exact_height_and_thickness(self):
        import numpy as np
        from aimlab_training import draw_voice_guide
        image=np.zeros((1080,1920,3),np.uint8)
        draw_voice_guide(image,70)
        ys,xs=np.where(image[:,:,0]==255)
        self.assertEqual(ys.min(),945)
        self.assertEqual(ys.max(),1079)
        self.assertEqual(xs.max()-xs.min()+1,18)
        self.assertEqual((xs.min()+xs.max())/2,959.5)
        self.assertEqual(image[:,:,1:].sum(),0)

    def test_exact_command_with_confidence(self):
        result=dict(text='daj',result=[dict(word='daj',conf=.95,start=1.2)])
        self.assertEqual(command_from_result(result,100),101.2)
        for text in ('','dalej','daj mi','[unk]'):
            self.assertIsNone(command_from_result(dict(result,text=text),100))
        result['result'][0]['conf']=.5
        self.assertIsNone(command_from_result(result,100))
