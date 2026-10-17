import unittest
from types import SimpleNamespace
import numpy as np
from aimlab_irl_camera_mvp import detect
from aimlab_laser_test import inspect_detection,DetectionCounter


class LaserTestTests(unittest.TestCase):
    def setUp(self):
        self.args = SimpleNamespace(laser_color='green',green_min=180,green_delta=45,
                                    red_min=180,red_delta=45,min_area=2,max_area=1500)

    def inspect(self,frame,point=(50,50)):
        mask,spot = detect(frame,self.args)
        return inspect_detection(frame,mask,spot,self.args,point,radius=12)

    def test_detects_selected_point_and_handles_red(self):
        frame = np.zeros((100,100,3),np.uint8)
        frame[49:52,49:52] = (20,240,20)
        self.assertTrue(self.inspect(frame)['detected'])
        self.args.laser_color = 'red'
        frame[49:52,49:52] = (20,20,240)
        self.assertTrue(self.inspect(frame)['detected'])

    def test_reports_brightness_color_and_area_failures(self):
        frame = np.zeros((100,100,3),np.uint8)
        frame[49:52,49:52] = (20,100,20)
        self.assertIn('Jasnosc',self.inspect(frame)['reason'])
        frame[49:52,49:52] = (255,255,255)
        self.assertIn('przewaga',self.inspect(frame)['reason'])
        frame[:] = 0
        frame[50,50] = (20,240,20)
        self.assertIn('Rozmiar',self.inspect(frame)['reason'])

    def test_other_point_is_not_a_detection_in_selected_region(self):
        frame = np.zeros((100,100,3),np.uint8)
        frame[8:11,8:11] = (20,240,20)
        report = self.inspect(frame)
        self.assertFalse(report['detected'])
        self.assertTrue(report['other_detected'])
        self.assertFalse(self.inspect(frame,None)['selected'])

    def test_continuous_light_counts_once_after_release(self):
        counter = DetectionCounter()
        counter.update(False,0)
        counter.update(False,.2)
        counter.update(True,.21)
        counter.update(True,.4)
        self.assertEqual(counter.count,1)
        counter.update(False,.5)
        counter.update(False,.7)
        counter.update(True,.71)
        self.assertEqual(counter.count,2)
