import random
import unittest
import numpy as np
from aimlab_game_modes import Config,Game
from aimlab_settings import migrate_settings
from aimlab_target_styles import TargetAppearance
from aimlab_training import load_background,DEFAULT_BACKGROUND,render_frame


class TrapSpidershotTests(unittest.TestCase):
    def game(self,style='orange',**kwargs):
        appearance=TargetAppearance(style)
        game=Game(Config(mode='trap-spidershot',**kwargs),random.Random(7),appearance.contains)
        game.start(10)
        game.presented(10.1)
        return game,appearance

    def shoot(self,game,stamp):
        target=game.targets[0]
        return game.fire(stamp,target.x/(game.config.width-1),target.y/(game.config.height-1),stamp)

    def test_base_center_x_and_bottom_tangency_for_screen_sizes(self):
        for width,height in [(1920,1080),(1280,720),(800,600)]:
            for radius in (30,70,85):
                with self.subTest(width=width,height=height,radius=radius):
                    game,appearance=self.game(width=width,height=height,radius=radius)
                    target=game.targets[0]
                    self.assertEqual(target.role,'center')
                    self.assertEqual(target.style,'classic')
                    self.assertEqual(target.x,(width-1)/2)
                    self.assertAlmostEqual(target.y+target.radius,height-1)
                    self.assertTrue(appearance.contains(target,target.x,height-1))
                    self.assertFalse(appearance.contains(target,target.x,height))
                    image=np.zeros((height,width,3),np.uint8)
                    appearance.draw(image,target)
                    self.assertTrue(np.any(image[-1]))

    def test_base_blue_and_circular_while_side_uses_selected_svg(self):
        for style in ('orange','black','orange-black','classic'):
            with self.subTest(style=style):
                game,appearance=self.game(style)
                center=game.targets[0]
                image=np.zeros((1080,1920,3),np.uint8)
                appearance.draw(image,center)
                # Off the white cross, the center is the original blue fill.
                self.assertTrue(np.array_equal(image[round(center.y)+15,round(center.x)+15],(220,0,0)))
                self.assertTrue(appearance.contains(center,center.x,center.y-.75*center.radius))
                self.assertEqual(self.shoot(game,11).result,'hit')
                side=game.targets[0]
                self.assertEqual(side.role,'side')
                self.assertIsNone(side.style)
                self.assertTrue(appearance.contains(side,side.x,side.y))
                if style!='classic':
                    self.assertFalse(appearance.contains(side,side.x,side.y-.75*side.radius))

    def test_alternation_metrics_single_active_target_and_reset(self):
        game,appearance=self.game()
        positions=set()
        base=game.center
        for i in range(20):
            target=game.targets[0]
            self.assertEqual(len(game.targets),1)
            self.assertEqual(target.role,'center' if i%2==0 else 'side')
            if target.role=='center':
                self.assertEqual((target.x,target.y),base)
                self.assertEqual(target.style,'classic')
            else:
                positions.add((target.x,target.y))
                self.assertLess(target.y,base[1])
            self.assertEqual(self.shoot(game,11+i).result,'hit')
            game.presented(11.1+i)
        self.assertGreater(len(positions),5)
        self.assertEqual(game.cycles,9)
        self.assertEqual(game.metrics(31)['mean_center_to_side_ms'],1000)
        self.assertEqual(game.metrics(31)['mean_return_to_center_ms'],1000)
        game.start(40)
        self.assertEqual(game.targets[0].style,'classic')
        self.assertEqual((game.hits,game.misses,game.cycles),(0,0,0))

    def test_bad_active_count_and_settings(self):
        with self.assertRaises(ValueError):
            self.game(active_count=2)
        values=migrate_settings({'mode':'trap-spidershot','active_targets':6,'target_style':'black'})
        self.assertEqual((values['active_targets'],values['target_style']),(1,'black'))

    def test_timer_and_unchanged_classic_spidershot_center(self):
        game,appearance=self.game(duration=30)
        game.tick(40)
        self.assertEqual(game.state,'finished')
        self.assertIsNone(self.shoot(game,41))
        original=Game(Config(mode='spidershot'))
        original.start(10)
        self.assertEqual(original.center,(959.5,539.5))
        self.assertIsNone(original.targets[0].style)

    def test_renderer_keeps_bottom_center_visible(self):
        game,appearance=self.game()
        base=load_background(DEFAULT_BACKGROUND,1920,1080)
        frame=render_frame(base,game,11,10,appearance=appearance)
        self.assertTrue(np.array_equal(frame[1030,975],(220,0,0)))
        self.assertFalse(np.array_equal(frame[-1,960],base[-1,960]))


if __name__=='__main__':
    unittest.main()
