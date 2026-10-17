import unittest
from aimlab_calibration_report import format_report


class CalibrationReportTests(unittest.TestCase):
    def test_success_reports_measurements_and_cleanup(self):
        metrics = dict(rms_before_px=12,rms_after_px=2,max_before_px=20,
                       max_after_px=4,shift_x_px=-3,shift_y_px=5,max_shift_px=11)
        result = format_report(dict(status='applied',hits=25,misses=3,retries=2,
                                   duration_s=65,metrics=metrics,video_removed=True))
        for text in ('pomyślnie','25/25','pudła: 3','ponowienia obrazu: 2',
                     '12.00 → po: 2.00','X -3.00, Y +5.00','Nagranie usunięte.'):
            self.assertIn(text,result)

    def test_missing_or_failed_report_never_claims_success(self):
        for status in ('failed','cancelled','unknown'):
            result = format_report(dict(status=status))
            self.assertNotIn('pomyślnie',result)
            self.assertIn('Brak potwierdzenia zwolnienia nagrania',result)
