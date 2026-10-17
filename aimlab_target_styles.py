"""Shared target drawing/hit geometry; SVG rasterized once using Mint's native libraries."""
from collections import OrderedDict
import ctypes as C
import ctypes.util
from dataclasses import dataclass
from functools import lru_cache
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import cv2
import numpy as np

STYLES = {
    'orange': ('Pomarańczowy', 'clay_target_orange.svg'),
    'black': ('Czarny', 'clay_target_black.svg'),
    'orange-black': ('Pomarańczowo-czarny', 'clay_target_orange_black.svg'),
    'classic': ('Klasyczny — niebieskie koło', None),
}
ASSET_DIR = Path(__file__).resolve().parent/'assets'/'targets'
ALPHA_THRESHOLD = 32  # Include visible antialiasing, exclude almost transparent edge fringes.


class TargetAssetError(ValueError):
    pass


class _Rectangle(C.Structure):
    _fields_ = [('x',C.c_double),('y',C.c_double),('width',C.c_double),('height',C.c_double)]


class _GError(C.Structure):
    _fields_ = [('domain',C.c_uint),('code',C.c_int),('message',C.c_char_p)]


@lru_cache(maxsize=1)
def _libraries():
    """Only the system shared libraries; no GTK typelib or pip dependency needed."""
    try:
        libraries = []
        for name in ('rsvg-2','cairo','gobject-2.0','glib-2.0'):
            location = ctypes.util.find_library(name)
            if not location:
                raise OSError(f'Missing {name}')
            libraries.append(C.CDLL(location))
        rsvg,cairo,gobject,glib = libraries
        def bind(lib,name,args,result):
            function = getattr(lib,name)
            function.argtypes,function.restype = args,result
        ptr = C.c_void_p
        bind(rsvg,'rsvg_handle_new_from_file',[C.c_char_p,C.POINTER(ptr)],ptr)
        bind(rsvg,'rsvg_handle_render_document',[ptr,ptr,C.POINTER(_Rectangle),C.POINTER(ptr)],C.c_int)
        bind(cairo,'cairo_image_surface_create',[C.c_int,C.c_int,C.c_int],ptr)
        bind(cairo,'cairo_surface_status',[ptr],C.c_int)
        bind(cairo,'cairo_create',[ptr],ptr)
        bind(cairo,'cairo_status',[ptr],C.c_int)
        bind(cairo,'cairo_set_antialias',[ptr,C.c_int],None)
        bind(cairo,'cairo_surface_flush',[ptr],None)
        bind(cairo,'cairo_image_surface_get_data',[ptr],C.POINTER(C.c_ubyte))
        bind(cairo,'cairo_image_surface_get_stride',[ptr],C.c_int)
        bind(cairo,'cairo_destroy',[ptr],None)
        bind(cairo,'cairo_surface_destroy',[ptr],None)
        bind(gobject,'g_object_unref',[ptr],None)
        bind(glib,'g_error_free',[ptr],None)
        return libraries
    except (OSError,AttributeError) as error:
        raise TargetAssetError('Brak obsługi SVG. Zainstaluj librsvg2-2 i libcairo2 albo wybierz klasyczny cel.') from error


def rasterize_svg_rgba(path, raster_width=2048):
    """Return straight-alpha RGBA. Respect Cairo's native endian/premultiplied ARGB32."""
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
        view = [float(n) for n in root.attrib['viewBox'].replace(',',' ').split()]
        ratio = view[3]/view[2]
        if len(view)!=4 or not math.isfinite(ratio) or not 0 < ratio <= 4:
            raise ValueError('Invalid viewBox')
    except (OSError,ET.ParseError,KeyError,IndexError,ValueError,ZeroDivisionError) as error:
        raise TargetAssetError(f'Nie można wczytać SVG: {path}. Wybierz klasyczny cel lub przywróć plik.') from error
    width,height = raster_width,max(1,round(raster_width*ratio))
    rsvg,cairo,gobject,glib = _libraries()
    error = C.c_void_p()
    handle = surface = context = None
    def failure(message):
        detail = ''
        if error.value:
            detail = C.cast(error,C.POINTER(_GError)).contents.message.decode('utf-8',errors='replace')
            glib.g_error_free(error)
            error.value = None
        return TargetAssetError(f'{message}: {path}. {detail}')
    try:
        handle = rsvg.rsvg_handle_new_from_file(str(path.resolve()).encode(),C.byref(error))
        if not handle:
            raise failure('Błąd ładowania SVG')
        surface = cairo.cairo_image_surface_create(0,width,height)  # CAIRO_FORMAT_ARGB32
        if cairo.cairo_surface_status(surface):
            raise failure('Błąd pamięci obrazu SVG')
        context = cairo.cairo_create(surface)
        if cairo.cairo_status(context):
            raise failure('Błąd kontekstu SVG')
        cairo.cairo_set_antialias(context,6)  # CAIRO_ANTIALIAS_BEST
        viewport = _Rectangle(0,0,width,height)
        if not rsvg.rsvg_handle_render_document(handle,context,C.byref(viewport),C.byref(error)):
            raise failure('Błąd renderowania SVG')
        cairo.cairo_surface_flush(surface)
        stride = cairo.cairo_image_surface_get_stride(surface)
        pixels = np.ctypeslib.as_array(cairo.cairo_image_surface_get_data(surface),shape=(height,stride))
        native = pixels[:,:width*4].reshape(height,width,4)
        # Cairo's uint32 ARGB layout is BGRA bytes on little-endian systems.
        rgba = native[:,:,[2,1,0,3] if sys.byteorder=='little' else [1,2,3,0]].copy()
        alpha = rgba[:,:,3:4].astype(np.uint32)
        straight = (rgba[:,:,:3].astype(np.uint32)*255 + alpha//2)//np.maximum(alpha,1)
        rgba[:,:,:3] = np.minimum(straight,255).astype(np.uint8)
        return rgba
    finally:
        if error.value:
            glib.g_error_free(error)
        if context:
            cairo.cairo_destroy(context)
        if surface:
            cairo.cairo_surface_destroy(surface)
        if handle:
            gobject.g_object_unref(handle)


def draw_classic(image, target):
    center = (round(target.x),round(target.y))
    radius = round(target.radius)
    cv2.circle(image,center,radius+4,(15,15,15),-1)
    cv2.circle(image,center,radius,(220,0,0),-1)
    cv2.circle(image,center,radius,(255,255,255),3)
    cv2.drawMarker(image,center,(255,255,255),cv2.MARKER_CROSS,22,2)


@dataclass(frozen=True)
class Sprite:
    premultiplied_bgr: np.ndarray
    alpha: np.ndarray
    inverse_alpha: np.ndarray
    mask: np.ndarray

    @property
    def width(self): return self.alpha.shape[1]

    @property
    def height(self): return self.alpha.shape[0]

    def origin(self,target):
        return round(target.x-(self.width-1)/2),round(target.y-(self.height-1)/2)


class TargetAppearance:
    """One appearance owns both drawing and collision at exactly the same pixel origin."""
    def __init__(self,style='orange',asset_dir=ASSET_DIR,fallback=False):
        if style not in STYLES:
            raise ValueError(f'Unknown target style: {style}')
        self.requested_style = self.style = style
        self.warning = ''
        self.cache = OrderedDict()
        self.rgba = None
        self.base = None
        if style == 'classic':
            return
        try:
            rgba = rasterize_svg_rgba(Path(asset_dir)/STYLES[style][1])
            ys,xs = np.nonzero(rgba[:,:,3])
            if not len(xs):
                raise TargetAssetError('SVG jest całkowicie przezroczysty.')
            # Remove transparent viewBox padding so radius controls silhouette half-width.
            self.rgba = rgba[ys.min():ys.max()+1,xs.min():xs.max()+1].copy()
            self.base = self.rgba[:,:,[2,1,0,3]].astype(np.float32)
            self.base[:,:,:3] *= self.base[:,:,3:4]/255
        except TargetAssetError as error:
            if not fallback:
                raise
            self.style = 'classic'
            self.warning = str(error)

    def prepare(self,radius):
        if self.style == 'classic':
            return None
        if not math.isfinite(radius) or radius<=0:
            raise ValueError('Target radius must be positive and finite')
        width = max(2,round(2*radius))
        if width in self.cache:
            self.cache.move_to_end(width)
            return self.cache[width]
        height = max(1,round(width*self.base.shape[0]/self.base.shape[1]))
        interpolation = cv2.INTER_AREA if width <= self.base.shape[1] else cv2.INTER_LINEAR
        # Scale premultiplied colors, preventing dark fringes at transparent boundaries.
        resized = cv2.resize(self.base,(width,height),interpolation=interpolation)
        alpha = np.clip(np.rint(resized[:,:,3]),0,255).astype(np.uint8)
        color = resized[:,:,:3] * (alpha.astype(np.float32)/np.maximum(resized[:,:,3],1e-6))[:,:,None]
        sprite = Sprite(color,alpha,(1-alpha.astype(np.float32)/255)[:,:,None],alpha>=ALPHA_THRESHOLD)
        self.cache[width] = sprite
        if len(self.cache)>8:
            self.cache.popitem(last=False)
        return sprite

    def draw(self,image,target):
        if self.style == 'classic' or target.style == 'classic':
            draw_classic(image,target)
            return
        sprite = self.prepare(target.radius)
        left,top = sprite.origin(target)
        x0,y0 = max(0,left),max(0,top)
        x1,y1 = min(image.shape[1],left+sprite.width),min(image.shape[0],top+sprite.height)
        if x1<=x0 or y1<=y0:
            return
        sx,sy = x0-left,y0-top
        color = sprite.premultiplied_bgr[sy:sy+y1-y0,sx:sx+x1-x0]
        inverse = sprite.inverse_alpha[sy:sy+y1-y0,sx:sx+x1-x0]
        destination = image[y0:y1,x0:x1]
        blended = color+destination*inverse
        destination[:] = np.clip(np.rint(blended),0,255).astype(np.uint8)

    def contains(self,target,x,y):
        if self.style == 'classic' or target.style == 'classic':
            return math.hypot(x-target.x,y-target.y) <= target.radius+1e-7
        sprite = self.prepare(target.radius)
        left,top = sprite.origin(target)
        column,row = math.floor(x-left+.5),math.floor(y-top+.5)
        return (0<=column<sprite.width and 0<=row<sprite.height and bool(sprite.mask[row,column]))
