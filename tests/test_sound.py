import unittest
import wave
from pathlib import Path
from unittest.mock import patch,Mock
from aimlab_sound import HitSound


class SoundTests(unittest.TestCase):
    def test_bell_is_prepared_once_and_playback_is_async(self):
        with patch('aimlab_sound.shutil.which',return_value='/usr/bin/paplay'),patch('aimlab_sound.subprocess.Popen') as spawn:
            process = Mock()
            process.poll.return_value = None
            spawn.return_value = process
            sound = HitSound()
            path = Path(sound.command[-1])
            with wave.open(str(path),'rb') as wav:
                self.assertEqual(wav.getframerate(),44100)
                self.assertLess(wav.getnframes()/wav.getframerate(),.2)
            sound.play()
            spawn.assert_called_once()
            process.wait.assert_not_called()
            sound.close()
            self.assertFalse(path.exists())

    def test_disabled_and_missing_player_are_silent(self):
        with patch('aimlab_sound.shutil.which',return_value=None),patch('aimlab_sound.subprocess.Popen') as spawn:
            for enabled in (False,True):
                sound = HitSound(enabled)
                sound.play()
                sound.close()
            spawn.assert_not_called()
