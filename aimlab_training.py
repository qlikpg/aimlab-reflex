#!/usr/bin/env python3
"""Projected target practice using new laser events from the camera CSV."""
import argparse
import csv
import math
import signal
import sys
import time
import os
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np

from aimlab_game_modes import Config, Game, MODES, Target
from aimlab_target_styles import TargetAppearance, STYLES, draw_classic

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
    # Compatibility wrapper for the original circular renderer.
    draw_classic(image,Target(0,target[0],target[1],radius))


class HitReader:
    """Tail only fresh complete lines; discard content after rotation/truncation."""
    def __init__(self, path):
        self.path = Path(path)
        self.generation = 0
        self.stream = None
        self.reset()

    def reset(self):
        if self.stream:
            self.stream.close()
        self.stream = self.path.open('rb')
        info = os.fstat(self.stream.fileno())
        self.identity = (info.st_dev, info.st_ino)
        self.stream.seek(0, 2)
        self.pending = b''
        self._anchor()

    def _anchor(self):
        self.position = self.stream.tell()
        self.stream.seek(max(0,self.position-64))
        self.anchor = self.stream.read(self.position-self.stream.tell())
        self.stream.seek(self.position)

    def read(self):
        try:
            info = self.path.stat()
        except FileNotFoundError:
            return []
        changed = (info.st_dev,info.st_ino) != self.identity or info.st_size < self.position
        if not changed:
            self.stream.seek(max(0,self.position-64))
            changed = self.stream.read(len(self.anchor)) != self.anchor
            self.stream.seek(self.position)
        if changed:
            self.reset()
            self.generation += 1
            return []
        data = self.pending + self.stream.read()
        self._anchor()
        lines = data.split(b'\n')
        self.pending = lines.pop()
        # A valid camera row is small. Do not let a corrupt partial line grow forever.
        if len(self.pending) > 65536:
            self.pending = b''
        events = []
        for line in lines:
            try:
                row = next(csv.reader([line.decode('utf-8')]))
                stamp,u,v = float(row[1]),float(row[4]),float(row[5])
                if all(math.isfinite(x) for x in (stamp,u,v)) and 0 <= u <= 1 and 0 <= v <= 1:
                    events.append((stamp,u,v))
            except (ValueError, IndexError, StopIteration, UnicodeError):
                continue
        return events

    def close(self):
        self.stream.close()


def inside_target(u, v, target, width, height, radius):
    return math.hypot(u*(width-1)-target[0], v*(height-1)-target[1]) <= radius+1e-7


class MouseInput:
    def __init__(self, width, height):
        self.width,self.height = width,height
        self.events = deque()

    def callback(self, event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN and 0 <= x < self.width and 0 <= y < self.height:
            self.events.append((time.monotonic(),x/(self.width-1),y/(self.height-1)))

    def read(self):
        events = list(self.events)
        self.events.clear()
        return events


LEGACY_COLUMNS = ['session','utc','target','result','u','v','target_u','target_v','approx_reaction_ms']
METRIC_COLUMNS = ['duration_s','hits','misses','accuracy_percent','hits_per_second',
                  'mean_hit_interval_ms','mean_target_age_ms','mean_center_to_side_ms','mean_return_to_center_ms','full_cycles']
RESULT_COLUMNS = LEGACY_COLUMNS + ['schema_version','mode_id','mode_name','session_id','event_type','source',
                                  'target_id','target_x','target_y','target_radius_px','shot_x','shot_y',
                                  'error_px','target_age_ms'] + METRIC_COLUMNS


def read_results(path):
    """Normalize historical Classic CSVs and v2 files without inventing missing metrics."""
    with Path(path).open(newline='',encoding='utf-8') as stream:
        for original in csv.DictReader(stream):
            row = dict.fromkeys(RESULT_COLUMNS,'')
            row.update(original)
            if not original.get('schema_version'):
                row.update(schema_version='1',mode_id='classic',mode_name='Classic',event_type='shot',
                           session_id=f'legacy-{Path(path).stem}-{original.get("session", "")}',
                           target_id=original.get('target',''),target_age_ms=original.get('approx_reaction_ms',''),source='laser')
            yield row


class Results:
    def __init__(self, path):
        self.stream = Path(path).open('w',newline='',encoding='utf-8')
        self.writer = csv.DictWriter(self.stream,fieldnames=RESULT_COLUMNS)
        self.writer.writeheader()
        self.stream.flush()

    def write(self, game, ordinal, session_id, now, shot=None, reason='finished'):
        row = {'session':ordinal, 'utc':datetime.now(timezone.utc).isoformat(),
               'schema_version':2,'mode_id':game.config.mode,'mode_name':game.mode.name,
               'session_id':session_id,'event_type':'shot' if shot else 'summary',
               'result':shot.result if shot else reason, **game.metrics(now)}
        if shot:
            t = shot.target
            row.update(target=t.id,u=shot.x/(game.config.width-1),v=shot.y/(game.config.height-1),
                       target_u=t.x/(game.config.width-1),target_v=t.y/(game.config.height-1),
                       approx_reaction_ms=shot.target_age_ms, target_id=t.id,target_x=t.x,target_y=t.y,
                       target_radius_px=t.radius,shot_x=shot.x,shot_y=shot.y,error_px=shot.error_px,
                       target_age_ms=shot.target_age_ms,source=shot.source)
        self.writer.writerow({key: '' if value is None else value for key,value in row.items()})
        self.stream.flush()

    def close(self):
        self.stream.close()


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--hits',type=Path,default=Path('aimlab_hits.csv'))
    p.add_argument('--width',type=int,default=1920)
    p.add_argument('--height',type=int,default=1080)
    p.add_argument('--screen-x',type=int,default=1920)
    p.add_argument('--screen-y',type=int,default=0)
    p.add_argument('--radius',type=float,default=None,help='Radius at reference 1920x1080; scales with screen')
    p.add_argument('--targets',type=int,default=10,help='Classic completion count')
    p.add_argument('--mode',choices=tuple(MODES),default='classic')
    p.add_argument('--target-style',choices=tuple(STYLES),default='orange')
    p.add_argument('--duration',type=float,default=60)
    p.add_argument('--active-targets',type=int,default=None)
    p.add_argument('--mouse-test',action='store_true')
    p.add_argument('--background',type=Path,default=DEFAULT_BACKGROUND)
    p.add_argument('--plain-background',action='store_true')
    a = p.parse_args()
    try:
        Game(config_from_args(a))
    except ValueError as error:
        p.error(str(error))
    if not a.mouse_test and not a.hits.exists():
        p.error('Start the calibrated camera first, or use --mouse-test')
    return a


def config_from_args(a):
    return Config(mode=a.mode,width=a.width,height=a.height,duration=a.duration,radius=a.radius,
                  active_count=a.active_targets,classic_total=a.targets)


def render_frame(base, game, now, ready_at, feedback='', finished_reason='finished', appearance=None):
    image = base.copy()
    h,w = image.shape[:2]
    scale = max(.4,min(w/1920,h/1080))
    metrics = game.metrics(now)
    if appearance is not None and appearance.warning:
        feedback = (feedback+' | ' if feedback else '')+'SVG unavailable - classic targets'
    def text(line,x,y,size=1,color=(255,255,255)):
        cv2.putText(image,line,(int(x),int(y)),cv2.FONT_HERSHEY_SIMPLEX,size*scale,color,max(1,round(2*scale)))
    remaining = game.remaining(now)
    clock = f'{remaining:.1f}s' if remaining is not None else f'{game.hits}/{game.config.classic_total}'
    text(f'{game.mode.name} | {clock} | Hits: {game.hits} | Misses: {game.misses} | Accuracy: {metrics["accuracy_percent"]:.1f}%',20*scale,45*scale)
    footer_y = 110*scale if game.config.mode == 'trap-spidershot' else h-24*scale
    text('Q / Esc: exit | SPACE: restart | Release laser between shots',20*scale,footer_y,.65 if game.config.mode == 'trap-spidershot' else .75)
    if game.state == 'running':
        for target in game.targets:
            if target.active:
                if appearance is None:
                    draw_target(image,(round(target.x),round(target.y)),round(target.radius))
                else:
                    appearance.draw(image,target)
        if feedback:
            text(feedback,20*scale,85*scale,.75)
    elif game.state == 'finished':
        top,bottom = int(h*.24),int(h*.83)
        image[top:bottom] = image[top:bottom]//4
        def number(value): return '--' if value is None else f'{value:.0f}'
        lines = [f'SESSION: {finished_reason}', f'Hits: {game.hits} | Misses: {game.misses} | Accuracy: {metrics["accuracy_percent"]:.1f}%',
                 f'Duration: {metrics["duration_s"]:.1f}s | Hits/s: {metrics["hits_per_second"]:.2f}',
                 f'Mean hit interval: {number(metrics["mean_hit_interval_ms"])} ms']
        if game.config.mode in ('spidershot','trap-spidershot'):
            lines += [f'Center > side: {number(metrics["mean_center_to_side_ms"])} ms | Return: {number(metrics["mean_return_to_center_ms"])} ms',f'Full cycles: {game.cycles}']
        lines += ['SPACE: new session','Intervals include camera and projector latency']
        for i,line in enumerate(lines):
            text(line,w*.12,h*.31+i*52*scale,.95)
    else:
        line = f'Start in {max(1,math.ceil(ready_at-now))}'
        cv2.rectangle(image,(int(w*.3),int(h*.42)),(int(w*.75),int(h*.55)),(20,20,20),-1)
        text(line,w*.33,h*.51,1.8)
    return image


def main():
    a = arguments()
    config = config_from_args(a)
    try:
        base = (np.full((a.height,a.width,3),20,dtype=np.uint8) if a.plain_background
                else load_background(a.background,a.width,a.height))
    except ValueError as error:
        raise SystemExit(str(error)) from error
    scale = min(a.width/1920,a.height/1080)
    # Precompute static HUD shading once, not on every frame.
    top,bottom = max(60,round(120*scale)),max(38,round(80*scale))
    base[:top] = (base[:top].astype(np.float32)*.3).astype(np.uint8)
    if a.mode != 'trap-spidershot':
        base[-bottom:] = (base[-bottom:].astype(np.float32)*.3).astype(np.uint8)
    reader = None if a.mouse_test else HitReader(a.hits)
    mouse = MouseInput(a.width,a.height)
    appearance = TargetAppearance(a.target_style,fallback=True)
    game = Game(config,hit_test=appearance.contains)
    appearance.prepare(game.radius)
    if appearance.warning:
        print('UWAGA: '+appearance.warning+' Używam klasycznego celu.',flush=True)
    name = 'AimLab IRL - Training'
    output = a.hits.parent/f'aimlab_training_{time.time_ns()}.csv'
    output.parent.mkdir(parents=True,exist_ok=True)
    results = Results(output)
    ordinal,session_id = 1,uuid.uuid4().hex
    ready_at = time.monotonic()+3
    summary_written = False
    reason = 'finished'
    feedback,feedback_until = '',0
    cv2.namedWindow(name,cv2.WINDOW_NORMAL)
    cv2.moveWindow(name,a.screen_x,a.screen_y)
    cv2.setWindowProperty(name,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
    if a.mouse_test:
        cv2.setMouseCallback(name,mouse.callback)
    print(f'{game.mode.name} started. Input: {"mouse" if a.mouse_test else "laser"}. Results: {output}',flush=True)
    try:
        while True:
            frame_start = time.monotonic()
            if game.state == 'idle' and frame_start >= ready_at:
                if reader:
                    reader.reset()  # Drop every pre-countdown/previous-session row and partial line.
                mouse.read()
                game.start(time.monotonic())
            game.tick(frame_start)
            if reader:
                generation = reader.generation
                events = reader.read()
                if reader.generation != generation and game.state == 'running':
                    game.finish(frame_start)
                    reason = 'stream changed - restart required'
            else:
                events = mouse.read()
            for stamp,u,v in events:
                shot = game.fire(stamp,u,v,time.monotonic(),source='mouse' if a.mouse_test else 'laser')
                if shot:
                    results.write(game,ordinal,session_id,time.monotonic(),shot)
                    feedback = 'HIT' if shot.result == 'hit' else 'MISS'
                    feedback_until = frame_start+.5
            now = time.monotonic()
            game.tick(now)
            if game.state == 'finished' and not summary_written:
                results.write(game,ordinal,session_id,now,reason=reason)
                summary_written = True
            cv2.imshow(name,render_frame(base,game,now,ready_at,feedback if now<feedback_until else '',reason,appearance))
            delay = max(1,round((frame_start+1/30-time.monotonic())*1000))
            key = cv2.waitKey(delay)&0xff
            game.presented(time.monotonic())
            if key in (27,ord('q')) or cv2.getWindowProperty(name,cv2.WND_PROP_VISIBLE)<1:
                break
            if key == ord(' '):
                if game.state == 'running':
                    game.finish(time.monotonic())
                if game.started_at is not None and not summary_written:
                    results.write(game,ordinal,session_id,time.monotonic(),reason='restarted')
                game = Game(config,hit_test=appearance.contains)
                ordinal += 1
                session_id = uuid.uuid4().hex
                ready_at = time.monotonic()+3
                summary_written = False
                reason = 'finished'
                feedback_until = 0
                mouse.read()
                if reader:
                    reader.reset()
    finally:
        if game.started_at is not None and not summary_written:
            game.finish(time.monotonic())
            results.write(game,ordinal,session_id,time.monotonic(),reason='stopped')
        results.close()
        if reader:
            reader.close()
        cv2.destroyAllWindows()
        print('Results saved:',output,flush=True)


if __name__ == '__main__':
    signal.signal(signal.SIGTERM,lambda *_: sys.exit(0))
    main()
