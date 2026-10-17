"""Camera mask overlay and independent projector reference measurements."""
import cv2
import numpy as np


def mask_overlay(frame, mask):
    result = frame.copy()
    selected = mask != 0
    result[selected] = (frame[selected].astype(np.float32) * .35 +
                        np.array([255, 0, 255]) * .65).astype(np.uint8)
    return result


class CalibrationCheck:
    def __init__(self, width, height):
        self.width, self.height = width, height
        self.references = [(round(u * (width-1)), round(v * (height-1)))
                           for v in (.15, .5, .85) for u in (.15, .5, .85)]
        self.samples = []

    @property
    def reference(self):
        return self.references[len(self.samples)] if len(self.samples) < len(self.references) else None

    def record(self, matrix, camera_point):
        if self.reference is None:
            return None
        uv = cv2.perspectiveTransform(np.float32([[camera_point]]), matrix)[0, 0]
        actual = uv * [self.width-1, self.height-1]
        dx, dy = actual - self.reference
        sample = (len(self.samples)+1, *self.reference, *camera_point,
                  float(dx), float(dy), float(np.hypot(dx, dy)))
        self.samples.append(sample)
        return sample

    def summary(self):
        if not self.samples:
            return 'Click the projected cross in CAMERA view (laser off)'
        errors = np.array([s[-1] for s in self.samples])
        last = self.samples[-1]
        return (f'{len(errors)}/9 dx={last[-3]:+.1f} dy={last[-2]:+.1f}px | '
                f'RMS={np.sqrt(np.mean(errors**2)):.1f}px max={errors.max():.1f}px')

    def draw(self, background):
        result = background.copy()
        if self.reference is not None:
            x, y = self.reference
            cv2.drawMarker(result, (x,y), (0,0,0), cv2.MARKER_CROSS, 46, 7)
            cv2.drawMarker(result, (x,y), (255,255,255), cv2.MARKER_CROSS, 42, 2)
        cv2.putText(result, f'Calibration check {min(len(self.samples)+1,9)}/9',
                    (25,45), cv2.FONT_HERSHEY_SIMPLEX, .8, (255,255,255), 2)
        return result
