#!/usr/bin/env python3
"""White calibration pattern on the selected projector."""
import argparse
import signal
import sys
import cv2
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width',type=int,default=1920)
    parser.add_argument('--height',type=int,default=1080)
    parser.add_argument('--screen-x',type=int,default=1920)
    parser.add_argument('--screen-y',type=int,default=0)
    args = parser.parse_args()
    w,h = args.width,args.height
    if w < 320 or h < 240:
        parser.error('Screen too small')
    image = np.full((h,w,3),35,dtype=np.uint8)
    cv2.rectangle(image,(0,0),(w-1,h-1),(255,255,255),10)
    for number,(x,y) in enumerate([(25,25),(w-26,25),(w-26,h-26),(25,h-26)],1):
        cv2.drawMarker(image,(x,y),(255,255,255),cv2.MARKER_CROSS,40,3)
        cv2.putText(image,str(number),(65 if x<w/2 else w-110,105 if y<h/2 else h-70),cv2.FONT_HERSHEY_SIMPLEX,2,(255,255,255),4)
    scale = min(w/1920,h/1080)
    for text,y in [('AimLab IRL - CALIBRATION',.45),('Click outer corners in camera: 1 > 2 > 3 > 4',.55)]:
        cv2.putText(image,text,(int(w*.12),int(h*y)),cv2.FONT_HERSHEY_SIMPLEX,max(.4,scale*1.3),(255,255,255),2)
    name = 'Projector calibration'
    cv2.namedWindow(name,cv2.WINDOW_NORMAL)
    cv2.moveWindow(name,args.screen_x,args.screen_y)
    cv2.setWindowProperty(name,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
    try:
        while True:
            cv2.imshow(name,image)
            if cv2.waitKey(30)&0xff in (27,ord('q')) or cv2.getWindowProperty(name,cv2.WND_PROP_VISIBLE)<1:
                break
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM,lambda *_: sys.exit(0))
    main()
