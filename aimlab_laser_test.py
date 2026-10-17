"""Explain the existing laser detector without changing its thresholds or decisions."""
import cv2
import numpy as np


def inspect_detection(frame, mask, spot, args, point, radius=35):
    if point is None:
        return dict(selected=False,detected=False,reason='Kliknij punkt w podgladzie kamery')
    h,w = mask.shape
    x,y = point
    x0,x1 = max(0,x-radius),min(w,x+radius+1)
    y0,y1 = max(0,y-radius),min(h,y+radius+1)
    if x1<=x0 or y1<=y0:
        return dict(selected=False,detected=False,reason='Punkt poza obrazem')
    pixels = frame[y0:y1,x0:x1].astype(np.int16)
    b,g,r = cv2.split(pixels)
    channel,other = (g,r) if args.laser_color == 'green' else (r,g)
    contrast = np.minimum(channel-other,channel-b)
    py,px = np.unravel_index(np.argmax(contrast+channel/256),contrast.shape)
    brightness,delta = int(channel[py,px]),int(contrast[py,px])
    minimum = getattr(args,args.laser_color+'_min')
    required_delta = getattr(args,args.laser_color+'_delta')
    detected = spot is not None and x0<=spot[0]<x1 and y0<=spot[1]<y1
    reasons = []
    if not detected:
        if brightness<minimum:
            reasons.append('Jasnosc ponizej progu')
        if delta<required_delta:
            reasons.append('Za mala przewaga koloru / przeswietlenie')
        if not reasons:
            reasons.append('Rozmiar plamki poza limitem lub detektor wybral inny punkt')
    return dict(selected=True,detected=bool(detected),reason='WYKRYTO' if detected else '; '.join(reasons),
                brightness=brightness,minimum=minimum,delta=delta,required_delta=required_delta,
                roi=[x0,y0,x1,y1],bgr=[int(v) for v in pixels[py,px]],
                masked_pixels=int(np.count_nonzero(mask[y0:y1,x0:x1])),
                other_detected=bool(spot is not None and not detected))


class DetectionCounter:
    def __init__(self):
        self.count = 0
        self.armed = False
        self.absent_since = None
        self.last_detection = None

    def update(self, detected, now, release_ms=150):
        if not detected:
            if self.absent_since is None:
                self.absent_since = now
            if (now-self.absent_since)*1000>=release_ms:
                self.armed = True
        else:
            self.last_detection = now
            self.absent_since = None
            if self.armed:
                self.count += 1
                self.armed = False


def draw_diagnostic(frame, report, counter, now):
    if report['selected']:
        x0,y0,x1,y1 = report['roi']
        cv2.rectangle(frame,(x0,y0),(x1-1,y1-1),(255,255,255),1)
    lines = ['TEST LASERA: kliknij miejsce strzalu; N zeruje licznik; Q konczy',
             'WYKRYTO W PUNKCIE' if report['detected'] else 'NIE WYKRYTO W PUNKCIE',report['reason']]
    if report['selected']:
        lines += [f"Jasnosc {report['brightness']}/255 (min {report['minimum']}) | przewaga koloru {report['delta']} (min {report['required_delta']})",
                  f"BGR {report['bgr']} | piksele maski w polu: {report['masked_pixels']}"]
    age = '-' if counter.last_detection is None else f'{now-counter.last_detection:.1f}s temu'
    lines += [f'Impulsy po zwolnieniu: {counter.count} | ostatnie wykrycie: {age}',
              'Progi: suwaki w Laser mask. Zgas laser na 150 ms miedzy impulsami.']
    cv2.rectangle(frame,(0,0),(frame.shape[1]-1,22+len(lines)*24),(20,20,20),-1)
    for index,line in enumerate(lines):
        cv2.putText(frame,line,(10,24+index*24),cv2.FONT_HERSHEY_SIMPLEX,.52,(255,255,255),1)
