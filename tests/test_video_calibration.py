import unittest
import cv2
import numpy as np
from aimlab_video_calibration import locate, fit_correction, PulseGate, target_region, central_hit, expected_target_region
from aimlab_calibration_markers import draw_quarter_target


class VideoCalibrationTests(unittest.TestCase):
    def test_waits_for_fresh_pulse(self):
        gate = PulseGate()
        self.assertFalse(gate.update((10,10),0))
        self.assertFalse(gate.update(None,.1))
        self.assertFalse(gate.update(None,.3))
        self.assertTrue(gate.update((10,10),.31))
        self.assertFalse(gate.update((10,10),.4))
        self.assertFalse(PulseGate().update((10,10),.5))

    def test_hit_must_be_in_observed_target_center(self):
        base = np.full((720,1280,3),100,np.uint8)
        image = base.copy()
        draw_quarter_target(image,(600,400),40)
        center,region = target_region(base,image)
        self.assertTrue(central_hit(region,(606,404)))
        self.assertFalse(central_hit(region,(630,430)))
        self.assertFalse(central_hit(region,(800,600)))
        self.assertFalse(central_hit(region,(-10,400)))
        self.assertLess(abs(center[0]-600),2)
        self.assertLess(abs(center[1]-400),2)

    def test_confirmed_calibration_excludes_other_changes(self):
        from aimlab_irl_camera_mvp import homography
        base = np.full((720,1280,3),80,np.uint8)
        after = np.full_like(base,90)  # Global exposure changed during projector transition.
        draw_quarter_target(after,(600,400),40)
        draw_quarter_target(after,(100,100),40)  # Equally large distractor.
        matrix = homography([(0,0),(1279,0),(1279,719),(0,719)])
        expected = expected_target_region(matrix,(600,400),40,1280,720,(1280,720))
        center,region = target_region(base,after,expected)
        self.assertLess(abs(center[0]-600),2)
        self.assertLess(abs(center[1]-400),2)
        self.assertTrue(central_hit(region,(600,400)))
        self.assertFalse(central_hit(region,(100,100)))

    def test_marker_center(self):
        base = np.full((720,1280,3),100,np.uint8)
        image = base.copy()
        draw_quarter_target(image,(600,400),40)
        x,y = locate(base,image)
        self.assertLess(abs(x-600),2)
        self.assertLess(abs(y-400),2)

    def test_fit_with_independent_points(self):
        refs = [(u,v) for v in (100,300,500,700,900) for u in (100,300,500,700,900)]
        camera = [(x*.8+20,y*.6+30) for x,y in refs]
        corners,errors = fit_correction(camera,refs,1001,1001)
        self.assertLess(max(errors),.01)
        np.testing.assert_allclose(corners[0],[20,30],atol=.01)
        camera[0] = (900,900)
        with self.assertRaises(ValueError):
            fit_correction(camera,refs,1001,1001)

    def test_no_visible_marker_rejected(self):
        image = np.zeros((720,1280,3),np.uint8)
        with self.assertRaises(ValueError):
            locate(image,image)
