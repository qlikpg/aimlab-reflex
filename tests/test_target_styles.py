import math
import random
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
from aimlab_game_modes import Game,Config,Target,MODES
from aimlab_target_styles import TargetAppearance,TargetAssetError,rasterize_svg_rgba,ASSET_DIR,ALPHA_THRESHOLD,draw_classic
from aimlab_settings import migrate_settings
from aimlab_training import render_frame


class TargetStyleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.styles = {name:TargetAppearance(name) for name in ('orange','black','orange-black','classic')}

    def test_rgba_loading_transparency_and_antialiasing(self):
        for name in ('orange','black','orange_black'):
            with self.subTest(name=name):
                rgba=rasterize_svg_rgba(ASSET_DIR/f'clay_target_{name}.svg',512)
                self.assertEqual(rgba.shape,(256,512,4))
                self.assertEqual(int(rgba[0,0,3]),0)
                self.assertEqual(int(rgba[132,256,3]),255)
                self.assertTrue(np.any((rgba[:,:,3]>0)&(rgba[:,:,3]<255)))
                if name=='orange':
                    self.assertGreater(int(rgba[132,256,0]),int(rgba[132,256,2])+100)
                if name=='black':
                    self.assertLess(int(rgba[132,256,:3].max()),100)

    def test_same_geometry_for_all_variants(self):
        reference=self.styles['orange'].prepare(70).alpha
        for name in ('black','orange-black'):
            self.assertTrue(np.array_equal(reference,self.styles[name].prepare(70).alpha))

    def test_preserves_ellipse_and_radius_is_half_width(self):
        for radius in (3,15,30,55,70,70.5,140):
            sprite=self.styles['orange'].prepare(radius)
            self.assertEqual(sprite.width,round(radius*2))
            self.assertLess(sprite.height,sprite.width*.4)
            ratio=self.styles['orange'].rgba.shape[0]/self.styles['orange'].rgba.shape[1]
            self.assertLessEqual(abs(sprite.height-sprite.width*ratio),.5)

    def test_pixel_exact_mask_alignment_including_fractional_centers(self):
        appearance=self.styles['orange']
        for center in ((160,100),(160.5,100.5),(161.2,101.8)):
            target=Target(1,*center,30)
            sprite=appearance.prepare(target.radius)
            left,top=sprite.origin(target)
            image=np.full((220,320,3),80,np.uint8)
            original=image.copy()
            appearance.draw(image,target)
            patch=image[top:top+sprite.height,left:left+sprite.width]
            self.assertTrue(np.array_equal(patch[sprite.alpha==0],original[top:top+sprite.height,left:left+sprite.width][sprite.alpha==0]))
            for row in range(sprite.height):
                for col in range(sprite.width):
                    self.assertEqual(appearance.contains(target,left+col,top+row),bool(sprite.alpha[row,col]>=ALPHA_THRESHOLD))
            self.assertFalse(appearance.contains(target,left,top))
            self.assertFalse(appearance.contains(target,left-1,top+sprite.height//2))
            self.assertFalse(appearance.contains(target,left+sprite.width,top+sprite.height//2))

    def test_bgr_colors_and_transparent_composition(self):
        images={}
        for name in ('orange','black','orange-black'):
            image=np.full((240,400,3),(40,100,160),np.uint8)
            target=Target(1,200,120,70)
            self.styles[name].draw(image,target)
            images[name]=image
            self.assertTrue(np.array_equal(image[0,0],(40,100,160)))
        b,g,r=[int(c) for c in images['orange'][120,200]]
        self.assertGreater(r,b+100,'Orange must not become blue in OpenCV')
        self.assertLess(int(images['black'][120,200].max()),100)
        self.assertFalse(np.array_equal(images['orange'],images['orange-black']))

    def test_offscreen_clipping_does_not_change_hit_origin(self):
        appearance=self.styles['orange']
        target=Target(1,0,0,30)
        sprite=appearance.prepare(30)
        left,top=sprite.origin(target)
        image=np.zeros((40,40,3),np.uint8)
        appearance.draw(image,target)
        for y in range(min(40,top+sprite.height)):
            for x in range(min(40,left+sprite.width)):
                self.assertEqual(appearance.contains(target,x,y),bool(sprite.mask[y-top,x-left]))

    def test_cache_and_no_svg_work_during_frames(self):
        with patch('aimlab_target_styles.rasterize_svg_rgba',wraps=rasterize_svg_rgba) as rasterize:
            appearance=TargetAppearance('orange')
            self.assertEqual(rasterize.call_count,1)
            target=Target(1,160,100,70)
            prepared=appearance.prepare(70)
            with patch('aimlab_target_styles.cv2.resize',side_effect=AssertionError('No per-frame resize')):
                for _ in range(100):
                    appearance.draw(np.zeros((240,400,3),np.uint8),target)
                    self.assertTrue(appearance.contains(target,160,100))
                    self.assertIs(appearance.prepare(70),prepared)
            self.assertEqual(rasterize.call_count,1)
            for radius in range(10,30):
                appearance.prepare(radius)
            self.assertLessEqual(len(appearance.cache),8)

    def test_missing_or_invalid_svg(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(TargetAssetError,'SVG'):
                TargetAppearance('orange',Path(d))
            appearance=TargetAppearance('orange',Path(d),fallback=True)
            self.assertEqual(appearance.style,'classic')
            self.assertIn('SVG',appearance.warning)
            target=Target(1,100,100,30)
            self.assertTrue(appearance.contains(target,100,100))
            self.assertFalse(appearance.contains(target,131,100))
            (Path(d)/'clay_target_orange.svg').write_text('<broken>')
            self.assertEqual(TargetAppearance('orange',Path(d),fallback=True).style,'classic')

    def test_classic_pixels_and_circle_unchanged(self):
        target=Target(1,100,100,30)
        old=np.zeros((240,320,3),np.uint8)
        cv2.circle(old,(100,100),34,(15,15,15),-1)
        cv2.circle(old,(100,100),30,(220,0,0),-1)
        cv2.circle(old,(100,100),30,(255,255,255),3)
        cv2.drawMarker(old,(100,100),(255,255,255),cv2.MARKER_CROSS,22,2)
        new=np.zeros_like(old)
        self.styles['classic'].draw(new,target)
        self.assertTrue(np.array_equal(old,new))
        self.assertTrue(self.styles['classic'].contains(target,130,100))
        self.assertFalse(self.styles['classic'].contains(target,130.1,100))

    def test_all_modes_use_silhouette_and_preserve_it_on_restart(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                appearance=self.styles['orange']
                game=Game(Config(mode=mode),random.Random(4),appearance.contains)
                game.start(10)
                if mode == 'voice':
                    game.activate_voice(10,10)
                game.presented(10.1)
                target=game.targets[0]
                sprite=appearance.prepare(target.radius)
                left,top=sprite.origin(target)
                miss=game.fire(11,left/1919,top/1079,11)
                self.assertEqual(miss.result,'miss')
                hit=game.fire(12,target.x/1919,target.y/1079,12)
                self.assertEqual(hit.result,'hit')
                frame=render_frame(np.full((1080,1920,3),80,np.uint8),game,12,10,appearance=appearance)
                self.assertEqual(frame.shape,(1080,1920,3))
                game.start(20)
                self.assertEqual(game.hit_test,appearance.contains)

    def test_style_settings_migration(self):
        self.assertEqual(migrate_settings({'radius':85})['target_style'],'orange')
        self.assertEqual(migrate_settings({'target_style':'black'})['target_style'],'black')
        self.assertEqual(migrate_settings({'target_style':'wrong'})['target_style'],'orange')


if __name__=='__main__':
    unittest.main()
