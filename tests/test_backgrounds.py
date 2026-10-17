import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from aimlab_training import make_background
from aimlab_settings import migrate_settings


class BackgroundTests(unittest.TestCase):
    def test_solid_fields_are_exact_and_need_no_asset(self):
        for style,value in (('black',0),('white',255)):
            image = make_background(style,Path('/missing.png'),320,240)
            self.assertEqual(image.shape,(240,320,3))
            self.assertEqual(image.dtype,np.uint8)
            self.assertTrue((image == value).all())

    def test_meadow_reuses_existing_loader(self):
        with patch('aimlab_training.load_background',return_value='loaded') as loader:
            self.assertEqual(make_background('meadow',Path('meadow.png'),320,240),'loaded')
            loader.assert_called_once_with(Path('meadow.png'),320,240)

    def test_old_settings_default_to_meadow(self):
        self.assertEqual(migrate_settings({})['background_style'],'meadow')
        self.assertEqual(migrate_settings({'background_style':'white'})['background_style'],'white')
        self.assertEqual(migrate_settings({'background_style':'invalid'})['background_style'],'meadow')
