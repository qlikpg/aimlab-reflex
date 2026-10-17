#!/usr/bin/env python3
"""Plain full-screen projector field for comparing laser detection."""
import argparse
import signal
import sys
from pathlib import Path
import cv2
from aimlab_training import make_background


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--width',type=int,default=1920)
    parser.add_argument('--height',type=int,default=1080)
    parser.add_argument('--screen-x',type=int,default=1920)
    parser.add_argument('--screen-y',type=int,default=0)
    parser.add_argument('--background-style',choices=('meadow','black','white'),default='meadow')
    a = parser.parse_args()
    if min(a.width,a.height)<2:
        parser.error('Invalid display dimensions')
    image = make_background(a.background_style,Path(__file__).parent/'assets/meadow.png',a.width,a.height)
    name = 'AimLab - Laser test background'
    cv2.namedWindow(name,cv2.WINDOW_NORMAL)
    cv2.moveWindow(name,a.screen_x,a.screen_y)
    cv2.setWindowProperty(name,cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
    try:
        while True:
            cv2.imshow(name,image)
            if cv2.waitKey(50)&255 in (27,ord('q')) or cv2.getWindowProperty(name,cv2.WND_PROP_VISIBLE)<1:
                break
    finally:
        cv2.destroyAllWindows()


if __name__ == '__main__':
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(0))
    main()
