"""Pure settings migration; importable without GTK or camera dependencies."""
from aimlab_game_modes import MODES

# Keep settings independent of OpenCV, NumPy and native SVG rendering.
TARGET_STYLES = ('orange','black','orange-black','classic')

DEFAULTS = {'camera':'/dev/video2','color':'green','minimum':180,'delta':45,'targets':10,
            'radius':70,'mode':'classic','duration':60,'active_targets':1,'input_method':'laser','target_style':'orange'}


def migrate_settings(data):
    values = dict(DEFAULTS)
    if not isinstance(data,dict):
        return values
    if isinstance(data.get('camera'),str):
        values['camera'] = data['camera']
    for key,choices in [('color',('green','red')),('mode',MODES),('input_method',('laser','mouse')),('target_style',TARGET_STYLES)]:
        if isinstance(data.get(key),str) and data[key] in choices:
            values[key] = data[key]
    preset = MODES.get(values['mode'],MODES['classic'])
    values.update(radius=preset.radius,active_targets=preset.count)
    for key,low,high in [('minimum',0,255),('delta',0,255),('targets',1,100),('radius',5,300),('active_targets',1,24)]:
        if type(data.get(key)) is int and low <= data[key] <= high:
            values[key] = data[key]
    if type(data.get('duration')) is int and data['duration'] in (30,60,120):
        values['duration'] = data['duration']
    if values['mode'] in ('classic','spidershot','trap-spidershot','video-calibration'):
        values['active_targets'] = 1
    return values
