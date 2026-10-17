import unittest
import numpy as np
from aimlab_diagnostics import CalibrationCheck, mask_overlay
from aimlab_irl_camera_mvp import homography


class DiagnosticsTests(unittest.TestCase):
    def test_overlay_preserves_background_and_inputs(self):
        frame = np.full((3,4,3), 80, np.uint8)
        mask = np.zeros((3,4), np.uint8)
        mask[1,2] = 255
        result = mask_overlay(frame, mask)
        np.testing.assert_array_equal(result[0], frame[0])
        self.assertGreater(int(result[1,2,0]), 80)
        self.assertLess(int(result[1,2,1]), 80)
        self.assertTrue((frame == 80).all())
        self.assertEqual(np.count_nonzero(mask), 1)

    def test_independent_reference_error(self):
        check = CalibrationCheck(1001,501)
        matrix = homography([(0,0),(1000,0),(1000,500),(0,500)])
        x,y = check.reference
        sample = check.record(matrix, (x+3,y+4))
        self.assertAlmostEqual(sample[-3],3,places=3)
        self.assertAlmostEqual(sample[-2],4,places=3)
        self.assertAlmostEqual(sample[-1],5,places=3)
        self.assertIn('RMS=5.0px',check.summary())
        while check.reference is not None:
            check.record(matrix,check.reference)
        self.assertIsNone(check.record(matrix,(0,0)))
        self.assertEqual(len(check.samples),9)
        check.samples.clear()
        self.assertEqual(check.reference,(150,75))

    def test_reference_matches_rendered_center(self):
        check = CalibrationCheck(1001,501)
        result = check.draw(np.zeros((501,1001,3),np.uint8))
        x,y = check.reference
        self.assertTrue((result[y,x] == 255).all())
