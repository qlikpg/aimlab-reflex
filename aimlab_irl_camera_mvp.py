#!/usr/bin/env python3
"""Linux camera MVP: red/green laser detection and projector calibration."""
import argparse
import csv
import json
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from aimlab_diagnostics import mask_overlay, CalibrationCheck
from aimlab_calibration_markers import draw_quarter_target
from aimlab_laser_test import inspect_detection, DetectionCounter, draw_diagnostic


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera', default='0', help='Camera index or /dev/video path')
    p.add_argument('--width', type=int, default=1280)
    p.add_argument('--height', type=int, default=720)
    p.add_argument('--laser-color', choices=('red', 'green'), default='green')
    p.add_argument('--red-min', type=int, default=210)
    p.add_argument('--red-delta', type=int, default=65)
    p.add_argument('--green-min', type=int, default=210)
    p.add_argument('--green-delta', type=int, default=65)
    p.add_argument('--laser-test', action='store_true', help='Explain detection at a clicked camera point, without recording shots')
    p.add_argument('--show-mask', action='store_true', help='Open laser mask with sensitivity controls')
    p.add_argument('--check-calibration', action='store_true')
    p.add_argument('--projector-width', type=int, default=1920)
    p.add_argument('--projector-height', type=int, default=1080)
    p.add_argument('--screen-x', type=int, default=1920)
    p.add_argument('--screen-y', type=int, default=0)
    p.add_argument('--start-calibration', action='store_true')
    p.add_argument('--status-file', type=Path, help='Live state for the desktop panel')
    p.add_argument('--min-area', type=int, default=2)
    p.add_argument('--max-area', type=int, default=1500)
    p.add_argument('--release-ms', type=int, default=150,
                   help='Laser must disappear for this long before another hit')
    p.add_argument('--output', type=Path, default=Path('aimlab_hits.csv'))
    p.add_argument('--calibration', type=Path, default=Path('aimlab_calibration.json'))
    a = p.parse_args()
    if not all(0 <= value <= 255 for value in (a.red_min, a.red_delta, a.green_min, a.green_delta)):
        p.error('Color thresholds must be between 0 and 255')
    if min(a.width, a.height, a.min_area) <= 0 or a.max_area < a.min_area or a.release_ms < 0:
        p.error('Invalid dimensions, area limits, or release time')
    if min(a.projector_width, a.projector_height) < 2:
        p.error('Invalid projector dimensions')
    return a


def homography(points):
    src = np.asarray(points, dtype=np.float32)
    if src.shape != (4, 2) or not np.isfinite(src).all():
        raise ValueError('Four finite corner coordinates required')
    contour = src.reshape(-1, 1, 2)
    if not cv2.isContourConvex(contour) or abs(cv2.contourArea(contour)) < 100:
        raise ValueError('Corners must form a convex quadrilateral of sufficient size')
    return cv2.getPerspectiveTransform(src, np.float32([[0, 0], [1, 0], [1, 1], [0, 1]]))


def detect(frame, a):
    b, g, r = cv2.split(frame.astype(np.int16))
    if a.laser_color == 'green':
        channel, other, minimum, delta = g, r, a.green_min, a.green_delta
    else:
        channel, other, minimum, delta = r, g, a.red_min, a.red_delta
    mask = ((channel >= minimum) & (channel - other >= delta) & (channel - b >= delta)).astype(np.uint8) * 255
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    candidates = [i for i in range(1, count) if a.min_area <= stats[i, cv2.CC_STAT_AREA] <= a.max_area]
    if not candidates:
        return mask, None
    # Prefer the brightest component in the selected channel; area breaks ties.
    best = max(candidates, key=lambda i: (float(channel[labels == i].mean()), stats[i, cv2.CC_STAT_AREA]))
    return mask, tuple(float(v) for v in centers[best])


def main():
    a = arguments()
    source = int(a.camera) if a.camera.isdigit() else a.camera
    camera = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not camera.isOpened():
        camera.release()
        raise SystemExit(f'Cannot open camera {a.camera}. Check /dev/video*, permissions and other camera apps.')
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, a.width)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, a.height)
    camera.set(cv2.CAP_PROP_FPS, 30)
    points, matrix, calibrating, show_mask = [], None, False, a.show_mask
    shape = None
    armed, absent_since = True, None
    start = time.monotonic()
    frames = 0
    last_status = 0
    last_hit = 'No hits yet'
    check = CalibrationCheck(a.projector_width, a.projector_height) if a.check_calibration else None
    raw_mask = False
    test_point = None
    test_report = None
    test_counter = DetectionCounter()
    if check:
        from aimlab_training import load_background
        background = load_background(Path(__file__).parent/'assets/meadow.png', check.width, check.height)
        cv2.namedWindow('Calibration check', cv2.WINDOW_NORMAL)
        cv2.moveWindow('Calibration check', a.screen_x, a.screen_y)
        cv2.setWindowProperty('Calibration check', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        check_image = check.draw(background)

    def open_mask():
        cv2.namedWindow('Laser mask', cv2.WINDOW_AUTOSIZE)
        color = a.laser_color
        cv2.createTrackbar('Brightness min', 'Laser mask', getattr(a, color + '_min'), 255,
                          lambda value: setattr(a, color + '_min', value))
        cv2.createTrackbar('Color difference', 'Laser mask', getattr(a, color + '_delta'), 255,
                          lambda value: setattr(a, color + '_delta', value))

    def click(event, x, y, flags, userdata):
        nonlocal matrix, calibrating, points, check_image, test_point, test_counter
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if a.laser_test:
            test_point = (x,y)
            test_counter = DetectionCounter()
            return
        if check and not calibrating:
            if matrix is not None:
                sample = check.record(matrix, (x,y))
                if sample:
                    path = a.output.parent/'aimlab_calibration_check.csv'
                    exists = path.exists() and path.stat().st_size > 0
                    with path.open('a', newline='', encoding='utf-8') as report:
                        writer = csv.writer(report)
                        if not exists:
                            writer.writerow(['utc','point','expected_x','expected_y','camera_x','camera_y','dx_px','dy_px','error_px'])
                        writer.writerow([datetime.now(timezone.utc).isoformat(), *sample])
                    check_image = check.draw(background)
                    print(check.summary(), flush=True)
            return
        if not calibrating:
            return
        points.append((x, y))
        if len(points) == 4:
            try:
                matrix = homography(points)
                a.calibration.parent.mkdir(parents=True, exist_ok=True)
                a.calibration.write_text(json.dumps({'points': points, 'frame_size': shape, 'camera': a.camera}), encoding='utf-8')
                calibrating = False
                print('Calibration saved:', a.calibration)
            except (ValueError, OSError) as error:
                print('Calibration failed:', error)
                matrix, points = None, []

    try:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        with a.output.open('a', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            if stream.tell() == 0:
                writer.writerow(['utc', 'monotonic_s', 'pixel_x', 'pixel_y', 'u', 'v'])
                stream.flush()
            cv2.namedWindow('AimLab IRL', cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback('AimLab IRL', click)
            if show_mask:
                open_mask()
            print(f'Laser: {a.laser_color}; min={getattr(a, a.laser_color + "_min")}; delta={getattr(a, a.laser_color + "_delta")}', flush=True)
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError('Camera stopped delivering frames')
                if shape is None:
                    shape = [frame.shape[1], frame.shape[0]]
                    print(f'Camera: {shape[0]}x{shape[1]}; CSV: {a.output}')
                    if a.calibration.exists():
                        try:
                            saved = json.loads(a.calibration.read_text(encoding='utf-8'))
                            if saved['frame_size'] != shape:
                                raise ValueError('Camera resolution changed; press C to recalibrate')
                            if saved.get('camera', '/dev/video2') != a.camera:
                                raise ValueError('Camera changed; press C to recalibrate')
                            matrix = homography(saved['points'])
                            points = saved['points']
                        except (ValueError, KeyError, TypeError, OSError) as error:
                            print('Calibration ignored:', error)
                    if a.start_calibration:
                        points, matrix, calibrating, armed = [], None, True, False
                now = time.monotonic()
                if a.status_file and now - last_status >= .25:
                    state = {'monotonic_s': now, 'calibrated': matrix is not None and not calibrating and not a.laser_test,
                             'laser_test': a.laser_test, 'detection_test': test_report,
                             'calibrating': calibrating, 'camera': a.camera, 'frame_size': shape,
                             'laser_color': a.laser_color,
                             'minimum': getattr(a, a.laser_color + '_min'),
                             'delta': getattr(a, a.laser_color + '_delta')}
                    temporary = a.status_file.with_suffix('.tmp')
                    temporary.write_text(json.dumps(state), encoding='utf-8')
                    temporary.replace(a.status_file)
                    last_status = now
                frames += 1
                mask, spot = detect(frame, a)
                overlay = mask_overlay(frame, mask) if show_mask else None
                if a.laser_test:
                    test_report = inspect_detection(frame,mask,spot,a,test_point)
                    test_counter.update(test_report['detected'],now,a.release_ms)
                    test_report['pulse_count'] = test_counter.count
                if spot is None:
                    if absent_since is None:
                        absent_since = now
                    if (now - absent_since) * 1000 >= a.release_ms:
                        armed = True
                else:
                    absent_since = None
                    x, y = spot
                    cv2.circle(frame, (round(x), round(y)), 10, (0, 255, 0), 2)
                    if armed and matrix is not None and not calibrating and not a.laser_test:
                        u, v = cv2.perspectiveTransform(np.float32([[spot]]), matrix)[0, 0]
                        if 0 <= u <= 1 and 0 <= v <= 1:
                            writer.writerow([datetime.now(timezone.utc).isoformat(), f'{now:.6f}', f'{x:.2f}', f'{y:.2f}', f'{u:.6f}', f'{v:.6f}'])
                            stream.flush()
                            last_hit = f'Hit: u={u:.3f} v={v:.3f}'
                            print(last_hit)
                        armed = False
                if points:
                    cv2.polylines(frame, [np.int32(points)], len(points) == 4, (255, 180, 0), 2)
                    for i, point in enumerate(points):
                        draw_quarter_target(frame, point, 12)
                status = f'Click corner {len(points)+1}: TL TR BR BL' if calibrating else ('Calibrated' if matrix is not None else 'Press C to calibrate')
                status += f' | Laser: {a.laser_color}'
                status += f' | min={getattr(a, a.laser_color + "_min")} delta={getattr(a, a.laser_color + "_delta")}'
                for i, line in enumerate([status, last_hit, 'C calibrate | R reset | M mask | S screenshot | I info | Q quit']):
                    cv2.putText(frame, line, (12, 28 + i * 26), cv2.FONT_HERSHEY_SIMPLEX, .55, (0, 255, 255), 1)
                if check:
                    cv2.putText(frame, check.summary() if matrix is not None else 'No calibration - close check and calibrate first', (12,110), cv2.FONT_HERSHEY_SIMPLEX, .5, (255,255,255), 1)
                    cv2.imshow('Calibration check', check_image)
                if a.laser_test:
                    draw_diagnostic(frame,test_report,test_counter,now)
                cv2.imshow('AimLab IRL', frame)
                if show_mask:
                    cv2.putText(overlay, 'B: binary / overlay | magenta: mask', (12,28), cv2.FONT_HERSHEY_SIMPLEX, .6, (255,255,255), 1)
                    cv2.imshow('Laser mask', mask if raw_mask else overlay)
                key = cv2.waitKey(1) & 0xff
                if key in (27, ord('q')) or cv2.getWindowProperty('AimLab IRL', cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord('b'):
                    raw_mask = not raw_mask
                elif key == ord('n') and a.laser_test:
                    test_counter = DetectionCounter()
                elif key == ord('n') and check:
                    check.samples.clear()
                    check_image = check.draw(background)
                elif key == ord('c') and not a.laser_test:
                    points, matrix, calibrating, armed = [], None, True, False
                elif key == ord('r') and not a.laser_test:
                    points, matrix, calibrating = [], None, False
                    a.calibration.unlink(missing_ok=True)
                elif key == ord('m'):
                    show_mask = not show_mask
                    if show_mask:
                        open_mask()
                    else:
                        cv2.destroyWindow('Laser mask')
                elif key == ord('s'):
                    path = a.output.parent / f'aimlab_{time.time_ns()}.png'
                    if not cv2.imwrite(str(path), frame):
                        raise OSError(f'Could not save {path}')
                    print('Saved:', path)
                elif key == ord('i'):
                    print(f'Measured FPS: {frames / max(now-start, .001):.1f}; size: {shape}; calibrated: {matrix is not None}; laser={a.laser_color}; min={getattr(a, a.laser_color + "_min")}; delta={getattr(a, a.laser_color + "_delta")}')
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if a.status_file:
            a.status_file.unlink(missing_ok=True)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
