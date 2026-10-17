"""High-contrast, achromatic calibration markers."""
import cv2


def draw_quarter_target(image, center, radius=22):
    """Draw four alternating black/white sectors and an exact center cross."""
    x, y = map(round, center)
    radius = max(6, round(radius))
    cv2.circle(image, (x,y), radius+2, (255,255,255), -1, cv2.LINE_AA)
    for start in (0,90,180,270):
        color = (255,255,255) if start in (0,180) else (0,0,0)
        cv2.ellipse(image, (x,y), (radius,radius), 0, start, start+90,
                    color, -1, cv2.LINE_AA)
    cv2.circle(image, (x,y), radius, (0,0,0), 1, cv2.LINE_AA)
    cv2.drawMarker(image, (x,y), (255,255,255), cv2.MARKER_CROSS,
                   radius*2, 3, cv2.LINE_AA)
    cv2.drawMarker(image, (x,y), (0,0,0), cv2.MARKER_CROSS,
                   radius*2, 1, cv2.LINE_AA)
    if 0 <= y < image.shape[0] and 0 <= x < image.shape[1]:
        image[y, x] = 0
