#!/usr/bin/env python3
"""Projected target practice using new laser events from the camera CSV."""
import argparse
import csv
import math
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

DEFAULT_BACKGROUND = Path(__file__).resolve().parent / 'assets' / 'meadow.png'


def load_background(path, width, height):
    """Fit with a centered crop, preserving the photo's proportions."""
    picture = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if picture is None:
        raise ValueError(f'Cannot read training background: {path}')
    scale = max(width / picture.shape[1], height / picture.shape[0])
    resized = cv2.resize(picture, (max(width, math.ceil(picture.shape[1]*scale)),
                                    max(height, math.ceil(picture.shape[0]*scale))),
                         interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    x = (resized.shape[1]-width)//2
    y = (resized.shape[0]-height)//2
    return resized[y:y+height, x:x+width].copy()


def draw_target(image, target, radius):
    # Dark outer rim stays visible against bright clouds and the white inner rim.
    cv2.circle(image, target, radius+4, (15, 15, 15), -1)
    cv2.circle(image, target, radius, (220, 0, 0), -1)
    cv2.circle(image, target, radius, (255, 255, 255), 3)
    cv2.drawMarker(image, target, (255, 255, 255), cv2.MARKER_CROSS, 22, 2)


class HitReader:
    """Ignore historical hits and hold partial writes until a complete line arrives."""
    def __init__(self, path):
        self.stream = path.open('r', encoding='utf-8', newline='')
        self.stream.seek(0, 2)
        self.pending = ''

    def read(self):
        self.pending += self.stream.read()
        lines = self.pending.split('\n')
        self.pending = lines.pop()
        events = []
        for line in lines:
            try:
                row = next(csv.reader([line]))
                stamp, u, v = float(row[1]), float(row[4]), float(row[5])
                if all(math.isfinite(x) for x in (stamp, u, v)) and 0 <= u <= 1 and 0 <= v <= 1:
                    events.append((stamp, u, v))
            except (ValueError, IndexError, StopIteration):
                continue
        return events

    def close(self):
        self.stream.close()


def inside_target(u, v, target, width, height, radius):
    x, y = u * (width - 1), v * (height - 1)
    return math.hypot(x - target[0], y - target[1]) <= radius


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hits', type=Path, default=Path('aimlab_hits.csv'))
    p.add_argument('--width', type=int, default=1920)
    p.add_argument('--height', type=int, default=1080)
    p.add_argument('--screen-x', type=int, default=1920)
    p.add_argument('--screen-y', type=int, default=0)
    p.add_argument('--radius', type=int, default=70)
    p.add_argument('--targets', type=int, default=10)
    p.add_argument('--background', type=Path, default=DEFAULT_BACKGROUND)
    p.add_argument('--plain-background', action='store_true', help='Use the original dark background')
    a = p.parse_args()
    margin = a.radius + 40
    if (a.targets < 1 or a.radius < 5 or a.width < 4*a.radius+40
            or a.height < max(160, margin) + margin + 80):
        p.error('Invalid target count, radius, or screen dimensions')
    if not a.hits.exists():
        p.error('Start the calibrated camera application first')
    return a


def main():
    a = arguments()
    try:
        background = (np.full((a.height, a.width, 3), 20, dtype=np.uint8) if a.plain_background
                      else load_background(a.background, a.width, a.height))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    reader = HitReader(a.hits)
    name = 'AimLab IRL - Training'
    cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    cv2.moveWindow(name, a.screen_x, a.screen_y)
    cv2.setWindowProperty(name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    output = a.hits.parent / f'aimlab_training_{time.time_ns()}.csv'
    with output.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['session', 'utc', 'target', 'result', 'u', 'v', 'target_u', 'target_v', 'approx_reaction_ms'])
        stream.flush()
        session, hits, misses = 1, 0, 0
        reactions = []
        target, shown_at = None, None
        ready_at = time.monotonic() + 3
        feedback, feedback_until = '', 0
        print('Training started. Results:', output, flush=True)
        try:
            while True:
                now = time.monotonic()
                for stamp, u, v in reader.read():
                    # A hit belongs to a target only after that target was presented.
                    if shown_at is None or stamp < shown_at or stamp > now:
                        continue
                    success = inside_target(u, v, target, a.width, a.height, a.radius)
                    reaction = (stamp - shown_at) * 1000
                    writer.writerow([session, datetime.now(timezone.utc).isoformat(), hits + 1,
                                     'hit' if success else 'miss', u, v,
                                     target[0]/(a.width-1), target[1]/(a.height-1), f'{reaction:.1f}'])
                    stream.flush()
                    if success:
                        hits += 1
                        reactions.append(reaction)
                        feedback = f'HIT! {reaction:.0f} ms (approx.)'
                        target, shown_at = None, None
                        ready_at = now + .6
                        print(f'Target {hits}/{a.targets}: hit, approx. {reaction:.0f} ms', flush=True)
                    else:
                        misses += 1
                        feedback = 'MISS - try again'
                    feedback_until = now + .6
                image = background.copy()
                # Shade only the status strips; keep the landscape unchanged elsewhere.
                image[:120] = (image[:120].astype(np.float32)*.3).astype(np.uint8)
                image[-80:] = (image[-80:].astype(np.float32)*.3).astype(np.uint8)
                cv2.putText(image, f'AimLab IRL | Targets: {hits}/{a.targets} | Misses: {misses}',
                            (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(image, 'Q / Esc: exit | SPACE: restart | Release laser between shots',
                            (40, a.height-35), cv2.FONT_HERSHEY_SIMPLEX, .8, (180, 180, 180), 1)
                new_target = False
                if hits >= a.targets:
                    image[160:-100] = (image[160:-100].astype(np.float32)*.3).astype(np.uint8)
                    mean = sum(reactions) / len(reactions)
                    accuracy = 100*hits/(hits+misses)
                    lines = ['SESSION COMPLETE', f'Accuracy: {accuracy:.0f}% | Mean: {mean:.0f} ms (approx.)',
                             'SPACE: new session', 'Timing includes camera and display latency']
                    for i, line in enumerate(lines):
                        cv2.putText(image, line, (a.width//6, a.height//2-80+i*65),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
                elif now >= ready_at:
                    if target is None:
                        margin = a.radius + 40
                        target = (random.randint(margin, a.width-margin-1),
                                  random.randint(max(160, margin), a.height-margin-80))
                        new_target = True
                    draw_target(image, target, a.radius)
                elif now < feedback_until:
                    cv2.rectangle(image, (a.width//4-15, a.height//2-60),
                                  (min(a.width-1, a.width//4+850), a.height//2+20), (20, 20, 20), -1)
                    cv2.putText(image, feedback, (a.width//4, a.height//2),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 255), 3)
                else:
                    cv2.rectangle(image, (a.width//3-15, a.height//2-70),
                                  (min(a.width-1, a.width//3+550), a.height//2+20), (20, 20, 20), -1)
                    cv2.putText(image, f'Start in {math.ceil(ready_at-now)}', (a.width//3, a.height//2),
                                cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
                if shown_at is not None and now < feedback_until:
                    cv2.putText(image, feedback, (40, 105), cv2.FONT_HERSHEY_SIMPLEX, .8, (0, 255, 255), 2)
                cv2.imshow(name, image)
                key = cv2.waitKey(10) & 0xff
                if new_target:
                    shown_at = time.monotonic()
                if key in (27, ord('q')) or cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key == ord(' '):
                    session += 1
                    hits, misses, reactions = 0, 0, []
                    target, shown_at = None, None
                    ready_at = time.monotonic() + 3
                    feedback_until = 0
        finally:
            reader.close()
            cv2.destroyAllWindows()
            print('Results saved:', output, flush=True)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    main()
