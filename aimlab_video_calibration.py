#!/usr/bin/env python3
"""Sequential, camera-observed calibration; temporary video is always removed."""
import argparse
import json
import os
import shutil
import signal
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np
from aimlab_calibration_markers import draw_quarter_target
from aimlab_training import load_background
from aimlab_irl_camera_mvp import detect


def locate(before, after):
    difference = cv2.absdiff(before, after).max(axis=2)
    mask = (difference > max(25, float(np.percentile(difference, 99.5))*.5)).astype(np.uint8)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(mask)
    candidates = [i for i in range(1,count) if 30 <= stats[i,4] <= mask.size*.03]
    if not candidates:
        raise ValueError('Nie wykryto tarczy. Sprawdź widoczność projekcji i nieruchomość kamery.')
    best = max(candidates, key=lambda i: stats[i,4])
    if len(candidates)>1 and sorted([stats[i,4] for i in candidates])[-2] > stats[best,4]*.6:
        raise ValueError('Niejednoznaczny obraz tarczy. Usuń ruch i zmiany oświetlenia.')
    # Bounding-box center is independent of the alternating sector brightness.
    x,y,w,h,_ = stats[best]
    return x+(w-1)/2, y+(h-1)/2


def target_region(before, after, expected=None):
    """Find the visible target independently of the old calibration and laser aim."""
    # Remove a global exposure/color shift before measuring the changed target.
    delta = after.astype(np.int16)-before.astype(np.int16)
    offset = np.median(delta[::8,::8],axis=(0,1))
    difference = np.abs(delta-offset).max(axis=2)
    mask = (difference > max(25, float(np.percentile(difference,99.5))*.5)).astype(np.uint8)
    if expected is not None:
        mask[expected == 0] = 0
    count,labels,stats,_ = cv2.connectedComponentsWithStats(mask)
    candidates = [i for i in range(1,count) if 30 <= stats[i,4] <= mask.size*.03]
    if not candidates:
        raise ValueError('Nie widać tarczy w kamerze; kalibracja bez zmian.')
    best = max(candidates,key=lambda i:stats[i,4])
    if expected is None and sum(stats[i,4] > stats[best,4]*.6 for i in candidates) > 1:
        # Separate quarters of one marker may form separate components.
        for i in candidates:
            if i != best and stats[i,4] > stats[best,4]*.6:
                separation = np.linalg.norm(np.array(stats[i,:2])-stats[best,:2])
                if separation > max(stats[best,2:4])*2+12:
                    raise ValueError('Niejednoznaczny obraz tarczy; ponów pomiar.')
    selected = np.isin(labels,candidates) if expected is not None else labels == best
    pixels = cv2.findNonZero(selected.astype(np.uint8))
    region = np.zeros_like(mask)
    cv2.fillConvexPoly(region,cv2.convexHull(pixels),255)
    x,y,w,h = cv2.boundingRect(pixels)
    return (x+(w-1)/2,y+(h-1)/2),region


def expected_target_region(matrix, point, radius, width, height, frame_size):
    # Search near the target predicted by the explicitly confirmed mouse calibration.
    polygon = [(point[0]+np.cos(t)*radius*2,point[1]+np.sin(t)*radius*2)
               for t in np.linspace(0,2*np.pi,48,endpoint=False)]
    uv = np.float32(polygon)/[width-1,height-1]
    camera = cv2.perspectiveTransform(np.float32([uv]),np.linalg.inv(matrix))[0]
    mask = np.zeros((frame_size[1],frame_size[0]),np.uint8)
    cv2.fillConvexPoly(mask,np.int32(np.round(camera)),255)
    return mask


def central_hit(region, spot):
    if spot is None:
        return False
    x,y = map(round,spot)
    if not (0 <= y < region.shape[0] and 0 <= x < region.shape[1]):
        return False
    distance = cv2.distanceTransform(region,cv2.DIST_L2,5)
    return bool(distance.max() > 0 and distance[y,x] >= distance.max()*.45)


def fit_correction(camera_points, references, width, height):
    src = np.float32(camera_points)
    dst = np.float32(references)
    holdout = np.array([i % 5 == i // 5 for i in range(25)])
    matrix, inliers = cv2.findHomography(src[~holdout],dst[~holdout],cv2.RANSAC,5)
    if matrix is None or inliers is None or inliers.sum() < 18:
        raise ValueError('Za mało zgodnych punktów. Kalibracja nie została zmieniona.')
    projected = cv2.perspectiveTransform(src[holdout,None,:],matrix)[:,0,:]
    errors = np.linalg.norm(projected-dst[holdout],axis=1)
    if not np.isfinite(errors).all() or np.sqrt(np.mean(errors**2))>8 or errors.max()>15:
        raise ValueError('Błąd kontroli przekracza 8 px RMS / 15 px max. Kalibracja bez zmian.')
    normalized = np.diag([1/(width-1),1/(height-1),1.]) @ matrix
    corners = cv2.perspectiveTransform(np.float32([[[0,0],[1,0],[1,1],[0,1]]]),
                                         np.linalg.inv(normalized))[0]
    from aimlab_irl_camera_mvp import homography
    homography(corners)  # Validate geometry using the existing calibration rules.
    return corners.tolist(), errors.tolist()


class PulseGate:
    """A new target requires 150 ms darkness before accepting one pulse."""
    def __init__(self):
        self.absent_since = None
        self.armed = False

    def update(self, spot, now):
        if spot is None:
            if self.absent_since is None:
                self.absent_since = now
            if now-self.absent_since >= .150:
                self.armed = True
            return False
        self.absent_since = None
        if self.armed:
            self.armed = False
            return True
        return False


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--camera',required=True)
    p.add_argument('--width',type=int,default=1920)
    p.add_argument('--height',type=int,default=1080)
    p.add_argument('--screen-x',type=int,default=1920)
    p.add_argument('--screen-y',type=int,default=0)
    p.add_argument('--calibration',type=Path,default=Path('aimlab_calibration.json'))
    p.add_argument('--laser-color', choices=('green','red'), default='green')
    p.add_argument('--green-min', type=int, default=180)
    p.add_argument('--green-delta', type=int, default=45)
    p.add_argument('--red-min', type=int, default=210)
    p.add_argument('--red-delta', type=int, default=65)
    p.add_argument('--min-area', type=int, default=2)
    p.add_argument('--max-area', type=int, default=1500)
    a = p.parse_args()
    if min(a.width,a.height)<240:
        p.error('Nieprawidłowy rozmiar ekranu')
    cap = cv2.VideoCapture(int(a.camera) if a.camera.isdigit() else a.camera,cv2.CAP_V4L2)
    writer = None
    recording_fd = None
    name = 'AimLab IRL - Video calibration'
    # RAM-backed temporary storage: no recording survives reboot; finally deletes it immediately.
    if not Path('/dev/shm').is_dir() or shutil.disk_usage('/dev/shm').free < 100*1024**2:
        cap.release()
        raise SystemExit('Brak 100 MB wolnej pamięci /dev/shm na nagranie tymczasowe.')
    try:
        with tempfile.TemporaryDirectory(prefix='aimlab-video-',dir='/dev/shm') as temporary:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT,720)
            if not cap.isOpened():
                raise ValueError('Nie można otworzyć kamery.')
            ok,frame = cap.read()
            if not ok:
                raise ValueError('Brak obrazu kamery.')
            size = (frame.shape[1],frame.shape[0])
            path = str(Path(temporary)/'capture.avi')
            writer = cv2.VideoWriter(path,cv2.VideoWriter_fourcc(*'MJPG'),10,size)
            if not writer.isOpened():
                raise ValueError('Nie można uruchomić nagrania MJPG.')
            recording_fd = os.open(path,os.O_RDONLY)
            os.unlink(path)  # Anonymous inode: even SIGKILL cannot leave a video behind.
            base = load_background(Path(__file__).parent/'assets/meadow.png',a.width,a.height)
            refs = [(round(u*(a.width-1)),round(v*(a.height-1)))
                    for v in (.1,.3,.5,.7,.9) for u in (.1,.3,.5,.7,.9)]
            cv2.namedWindow(name,cv2.WINDOW_NORMAL)
            cv2.moveWindow(name,a.screen_x,a.screen_y)
            cv2.setWindowProperty(name,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
            from aimlab_irl_camera_mvp import homography
            saved = json.loads(a.calibration.read_text(encoding='utf-8'))
            if saved.get('camera','/dev/video2') != a.camera or saved['frame_size'] != list(size):
                raise ValueError('Kamera lub rozdzielczość różni się od potwierdzonej kalibracji.')
            initial_matrix = homography(saved['points'])
            measured_centers, regions = [], []
            for index,point in enumerate(refs):
                image = base.copy()
                cv2.putText(image,f'{index+1}/25 - shoot CENTER; release laser between shots',
                            (25,round(a.height*.17)),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
                def capture_reference(display):
                    cv2.imshow(name,display)
                    started = time.monotonic()
                    frames = []
                    while len(frames)<3:
                        key = cv2.waitKey(10)&255
                        if key in (27,ord('q')) or cv2.getWindowProperty(name,cv2.WND_PROP_VISIBLE)<1:
                            raise InterruptedError('Pomiar przerwany; nagranie usunięte.')
                        ok,current = cap.read()
                        if not ok:
                            raise ValueError('Brak obrazu kamery.')
                        _,laser = detect(current,a)
                        if time.monotonic()-started > .8 and laser is None:
                            frames.append(current)
                    return np.median(frames,axis=0).astype(np.uint8)
                target_radius = max(22,round(a.width/1920*40))
                expected = expected_target_region(initial_matrix,point,target_radius,
                                                  a.width,a.height,size)
                while True:
                    before = capture_reference(image)
                    target_image = image.copy()
                    draw_quarter_target(target_image,point,target_radius)
                    after = capture_reference(target_image)
                    try:
                        center,region = target_region(before,after,expected)
                        break
                    except ValueError as error:
                        print(f'Punkt {index+1}: {error} Ponawiam, zgas laser.',flush=True)
                        # Keep the window open; cancellation is handled by capture_reference.
                        notice = image.copy()
                        cv2.putText(notice,'Target unclear - laser OFF; retrying...',
                                    (25,round(a.height*.22)),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
                        capture_reference(notice)
                image = target_image
                cv2.imshow(name,image)
                gate = PulseGate()
                shown = time.monotonic()
                while True:
                    key = cv2.waitKey(10)&255
                    if key in (27,ord('q')) or cv2.getWindowProperty(name,cv2.WND_PROP_VISIBLE)<1:
                        raise InterruptedError('Pomiar przerwany; nagranie usunięte.')
                    ok,frame = cap.read()
                    if not ok:
                        raise ValueError('Utracono obraz kamery.')
                    now = time.monotonic()
                    _,spot = detect(frame,a)
                    # Discard buffered/pre-presentation pulses and require a fresh release.
                    if now-shown < .8:
                        continue
                    if gate.update(spot,now):
                        if not central_hit(region,spot):
                            feedback = image.copy()
                            cv2.putText(feedback,'MISS - aim at target center; try again',
                                        (25,round(a.height*.22)),cv2.FONT_HERSHEY_SIMPLEX,.7,(255,255,255),2)
                            cv2.imshow(name,feedback)
                            print(f'Pudlo {index+1}/25 - ponow strzal',flush=True)
                            continue
                        measured_centers.append(center)
                        regions.append(region)
                        if shutil.disk_usage('/dev/shm').free < 20*1024**2:
                            raise ValueError('Brak pamięci; kalibracja bez zmian.')
                        writer.write(frame)
                        break
                print(f'Hit {index+1}/25',flush=True)
            writer.release()
            writer = None
            video = cv2.VideoCapture(f'/proc/self/fd/{recording_fd}')
            points = []
            try:
                for _ in refs:
                    ok,frame = video.read()
                    if not ok:
                        raise ValueError('Niepełne nagranie; kalibracja bez zmian.')
                    _,spot = detect(frame,a)
                    if not central_hit(regions[len(points)],spot):
                        raise ValueError('Niepotwierdzony hit w nagraniu; kalibracja bez zmian.')
                    # Use the observed target center, never assume the user hit its exact center.
                    points.append(measured_centers[len(points)])
            finally:
                video.release()
            corners,errors = fit_correction(points,refs,a.width,a.height)
            report = {'points':corners,'frame_size':list(size),'camera':a.camera,
                      'video_check_errors_px':errors,'video_calibrated_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
            if a.calibration.exists():
                previous = json.loads(a.calibration.read_text(encoding='utf-8'))
                if previous.get('camera', '/dev/video2') == a.camera and previous.get('frame_size') == list(size):
                    from aimlab_irl_camera_mvp import homography
                    old_matrix = homography(previous['points'])
                    held = [i for i in range(25) if i%5 == i//5]
                    old_uv = cv2.perspectiveTransform(np.float32([[points[i] for i in held]]),old_matrix)[0]
                    old_errors = np.linalg.norm(old_uv*[a.width-1,a.height-1]-np.array([refs[i] for i in held]),axis=1)
                    if np.mean(old_errors**2) <= np.mean(np.square(errors)):
                        print('Poprzednia kalibracja jest co najmniej równie dokładna; zachowana. Nagranie usunięte.',flush=True)
                        return
                shutil.copy2(a.calibration,a.calibration.with_suffix('.previous.json'))
            pending = a.calibration.with_suffix('.tmp')
            pending.write_text(json.dumps(report,indent=2),encoding='utf-8')
            pending.replace(a.calibration)
            print(f'Korekta zapisana. Kontrola RMS={np.sqrt(np.mean(np.square(errors))):.2f}px; nagranie usunięte.',flush=True)
    finally:
        if writer is not None:
            writer.release()
        cap.release()
        if recording_fd is not None:
            os.close(recording_fd)
        cv2.destroyAllWindows()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM,lambda *_: sys.exit(0))
    try:
        main()
    except (ValueError,InterruptedError) as error:
        print(str(error),file=sys.stderr,flush=True)
        sys.exit(1)
