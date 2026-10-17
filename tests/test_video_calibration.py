import unittest
import cv2
import numpy as np
from aimlab_video_calibration import locate, fit_correction
from aimlab_calibration_markers import draw_quarter_target


class VideoCalibrationTests(unittest.TestCase):
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
