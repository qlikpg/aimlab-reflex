import unittest
from types import SimpleNamespace
import numpy as np
from aimlab_irl_camera_mvp import detect


class LocalContrastTests(unittest.TestCase):
    def args(self, **kwargs):
        values = dict(laser_color='green',green_min=30,green_delta=1,
                      red_min=30,red_delta=1,min_area=2,max_area=1500,local_contrast=8)
        values.update(kwargs)
        return SimpleNamespace(**values)

    def test_finds_small_laser_on_different_background_brightness(self):
        for brightness in (5,30,100,180):
            with self.subTest(brightness=brightness):
                frame = np.full((160,200,3),brightness,np.uint8)
                frame[78:81,98:101] = (brightness,min(255,brightness+50),brightness)
                mask,spot = detect(frame,self.args())
                self.assertIsNotNone(spot)
                np.testing.assert_allclose(spot,[99,79],atol=.1)

    def test_suppresses_uniform_green_cast_without_laser(self):
        frame = np.full((160,200,3),(30,35,30),np.uint8)
        mask,spot = detect(frame,self.args())
        self.assertIsNone(spot)
        self.assertEqual(np.count_nonzero(mask),0)

    def test_calibrated_region_excludes_stronger_outside_light(self):
        frame = np.zeros((160,200,3),np.uint8)
        frame[20:23,20:23] = (0,255,0)
        frame[78:81,98:101] = (20,100,20)
        mask,spot = detect(frame,self.args(detection_polygon=[(50,50),(150,50),(150,130),(50,130)]))
        np.testing.assert_allclose(spot,[99,79],atol=.1)
        self.assertEqual(mask[21,21],0)

    def test_zero_keeps_legacy_brightness_choice(self):
        frame = np.zeros((160,200,3),np.uint8)
        frame[20:23,20:23] = (0,255,0)
        frame[78:81,98:101] = (20,100,20)
        _,spot = detect(frame,self.args(local_contrast=0))
        np.testing.assert_allclose(spot,[21,21],atol=.1)

    def test_does_not_claim_detection_of_white_saturated_laser(self):
        frame = np.full((160,200,3),255,np.uint8)
        _,spot = detect(frame,self.args())
        self.assertIsNone(spot)
