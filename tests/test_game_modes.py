import math
import random
import unittest
from aimlab_game_modes import Config, Game, MODES, Target
from aimlab_settings import migrate_settings


class GameTests(unittest.TestCase):
    def game(self, mode='gridshot', **kwargs):
        game = Game(Config(mode=mode,**kwargs),random.Random(12))
        game.start(100.)
        game.presented(100.01)
        return game

    def shoot(self, game, target=None, stamp=101.):
        target = target or game.targets[0]
        return game.fire(stamp,target.x/(game.config.width-1),target.y/(game.config.height-1),stamp+.001)

    def test_mode_defaults_and_scaled_radius(self):
        for mode,expected in [('classic',1),('gridshot',3),('sixshot',6),('multishot',5),('spidershot',1)]:
            with self.subTest(mode=mode):
                g = self.game(mode,width=1280,height=720)
                self.assertEqual(len(g.targets),expected)
                self.assertAlmostEqual(g.radius,MODES[mode].radius*2/3)

    def test_bounds_and_nonoverlap_over_many_replacements(self):
        for mode in ('gridshot','sixshot','multishot'):
            for w,h in [(1920,1080),(1280,720),(800,600)]:
                g = self.game(mode,width=w,height=h)
                for i in range(150):
                    left,right,top,bottom = g.bounds
                    for t in g.targets:
                        self.assertTrue(left<=t.x<=right and top<=t.y<=bottom)
                        self.assertTrue(t.x-t.radius>=0 and t.x+t.radius<w)
                        self.assertTrue(t.y-t.radius>=0 and t.y+t.radius<h)
                    for a in g.targets:
                        for b in g.targets:
                            if a.id != b.id:
                                self.assertGreater(math.hypot(a.x-b.x,a.y-b.y),a.radius+b.radius)
                    old = g.targets[0]
                    shot = self.shoot(g,stamp=100.1+i*.1)
                    self.assertEqual(shot.result,'hit')
                    self.assertFalse(old.active)
                    self.assertEqual(len(g.targets),MODES[mode].count)
                    self.assertTrue(all(t.id != old.id for t in g.targets))
                    g.presented(100.11+i*.1)

    def test_geometry_error_instead_of_loop(self):
        with self.assertRaisesRegex(ValueError,'space|targets'):
            Game(Config(mode='sixshot',radius=450))

    def test_custom_active_count(self):
        self.assertEqual(len(self.game('multishot',active_count=8).targets),8)
        with self.assertRaises(ValueError):
            self.game('spidershot',active_count=2)

    def test_miss_does_not_replace(self):
        g = self.game()
        ids = [t.id for t in g.targets]
        shot = g.fire(101,0,0,101)
        self.assertEqual(shot.result,'miss')
        self.assertEqual(g.misses,1)
        self.assertEqual([t.id for t in g.targets],ids)

    def test_circle_edge_and_nearest_overlap_single_hit(self):
        g = self.game()
        t = g.targets[0]
        shot = g.fire(101,(t.x+t.radius)/(g.config.width-1),t.y/(g.config.height-1),101)
        self.assertEqual(shot.result,'hit')
        g.targets = [Target(50,500,500,70,101),Target(51,510,500,70,101)]
        shot = g.fire(102,509/1919,500/1079,102)
        self.assertEqual(shot.target.id,51)
        self.assertEqual(g.hits,2)

    def test_duplicate_and_out_of_order_pulse(self):
        g = self.game()
        self.shoot(g,stamp=101)
        self.assertIsNone(self.shoot(g,stamp=101))
        self.assertIsNone(self.shoot(g,stamp=100.5))
        self.assertEqual(g.hits,1)

    def test_unpresented_target_and_old_event(self):
        g = self.game()
        self.shoot(g,stamp=101)
        t = g.targets[-1]
        self.assertIsNone(self.shoot(g,t,101.01))
        g.presented(101.1)
        self.assertIsNone(self.shoot(g,t,101.05))
        self.assertEqual(g.misses,0)
        self.assertEqual(self.shoot(g,t,101.2).result,'hit')

    def test_before_start_and_after_deadline(self):
        g = self.game(duration=30)
        self.assertIsNone(self.shoot(g,stamp=99))
        self.assertIsNone(self.shoot(g,stamp=130))
        self.assertEqual(g.state,'finished')
        self.assertEqual(g.metrics(200)['duration_s'],30)
        self.assertIsNone(self.shoot(g,stamp=131))
        self.assertEqual(g.hits,0)

    def test_reset_discards_old_session(self):
        g = self.game('spidershot')
        self.shoot(g,stamp=101)
        g.start(200)
        self.assertEqual((g.hits,g.misses,g.cycles),(0,0,0))
        self.assertEqual(g.targets[0].role,'center')
        self.assertIsNone(g.targets[0].activated_at)
        self.assertIsNone(self.shoot(g,stamp=102))
        self.assertEqual(g.metrics(200)['mean_hit_interval_ms'],None)

    def test_classic_ten_targets_and_delay(self):
        g = self.game('classic')
        for i in range(10):
            stamp = 101+i*2
            self.assertEqual(self.shoot(g,stamp=stamp).result,'hit')
            self.assertEqual(len(g.targets),0)
            if i<9:
                self.assertEqual(g.state,'running')
                g.tick(stamp+.5)
                self.assertFalse(g.targets)
                g.tick(stamp+.7)
                self.assertEqual(len(g.targets),1)
                g.presented(stamp+.8)
        self.assertEqual(g.state,'finished')
        self.assertEqual(g.hits,10)

    def test_spider_center_side_return_cycle_metrics(self):
        g = self.game('spidershot')
        self.assertEqual((g.targets[0].x,g.targets[0].y),g.center)
        self.shoot(g,stamp=101)
        self.assertEqual(g.targets[0].role,'side')
        self.assertEqual(g.cycles,0)
        g.presented(101.1)
        self.shoot(g,stamp=102.5)
        self.assertEqual(g.targets[0].role,'center')
        self.assertEqual(g.cycles,0)
        g.presented(102.6)
        self.shoot(g,stamp=104.5)
        m = g.metrics(104.5)
        self.assertEqual(g.cycles,1)
        self.assertEqual(m['mean_center_to_side_ms'],1500)
        self.assertEqual(m['mean_return_to_center_ms'],2000)
        self.assertEqual(m['mean_hit_interval_ms'],1750)

    def test_spider_varies_directions_and_distances(self):
        g = self.game('spidershot')
        points = set()
        for i in range(30):
            self.shoot(g,stamp=101+i)
            if g.targets[0].role=='side':
                points.add((g.targets[0].x,g.targets[0].y))
            g.presented(101.1+i)
        self.assertGreater(len(points),5)
        self.assertTrue(any(x<g.center[0] for x,y in points))
        self.assertTrue(any(x>g.center[0] for x,y in points))
        self.assertGreater(len({round(math.dist(p,g.center)) for p in points}),3)

    def test_metric_definitions(self):
        g = self.game()
        self.shoot(g,stamp=101)
        g.fire(102,0,0,102)
        g.presented(102.1)
        self.shoot(g,stamp=103)
        g.finish(104)
        m = g.metrics(900)
        self.assertEqual(m['hits'],2)
        self.assertEqual(m['misses'],1)
        self.assertAlmostEqual(m['accuracy_percent'],200/3)
        self.assertEqual(m['hits_per_second'],.5)
        self.assertEqual(m['mean_hit_interval_ms'],2000)

    def test_invalid_event_does_not_count(self):
        g = self.game()
        for stamp,u,v,now in [(101,float('nan'),.5,101),(101,2,.5,101),(102,.5,.5,101)]:
            self.assertIsNone(g.fire(stamp,u,v,now))
        self.assertEqual((g.hits,g.misses),(0,0))


class SettingsTests(unittest.TestCase):
    def test_legacy_settings(self):
        a = migrate_settings({'camera':'/dev/video2','radius':85,'targets':12,'minimum':180,'delta':45})
        self.assertEqual((a['mode'],a['radius'],a['targets']),('classic',85,12))
        self.assertEqual((a['duration'],a['active_targets'],a['input_method']),(60,1,'laser'))

    def test_mode_defaults_and_saved_overrides(self):
        a = migrate_settings({'mode':'sixshot'})
        self.assertEqual((a['radius'],a['active_targets']),(30,6))
        b = migrate_settings({'mode':'sixshot','radius':60,'active_targets':8,'duration':120,'input_method':'mouse'})
        self.assertEqual((b['radius'],b['active_targets'],b['duration'],b['input_method']),(60,8,120,'mouse'))

    def test_invalid_settings(self):
        for raw in (None,[],{}, {'mode':[]}, {'mode':'wrong','radius':False,'active_targets':-1,'duration':32}):
            self.assertEqual(migrate_settings(raw)['mode'],'classic')
        self.assertEqual(migrate_settings({'mode':'spidershot','active_targets':8})['active_targets'],1)


if __name__ == '__main__':
    unittest.main()
