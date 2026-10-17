import struct
import unittest
from unittest.mock import patch
try:
    import aimlab_camera_controls as controls
    AVAILABLE = bool(controls.Gtk.init_check()[0])
except (ImportError,ValueError):
    AVAILABLE = False


@unittest.skipUnless(AVAILABLE,'GTK system interpreter required')
class CameraControlsTests(unittest.TestCase):
    def test_open_reads_controls_without_writing_values(self):
        calls = []
        def ioctl(fd,request,data):
            calls.append(request)
            identifier = struct.unpack_from('I',data)[0]
            if identifier != 0x980900:
                raise OSError('unsupported')
            if request == controls.QUERY:
                return struct.pack('II32siiiiIII',identifier,1,b'Brightness',-64,64,1,0,0,0,0)
            if request == controls.GET:
                return struct.pack('Ii',identifier,5)
            return data
        with patch.object(controls.os,'open',return_value=123),patch.object(controls.os,'close') as close,patch.object(controls.fcntl,'ioctl',side_effect=ioctl):
            window = controls.CameraControls('/dev/video0')
            self.assertEqual(window.widgets[0x980900][0].get_value_as_int(),5)
            self.assertNotIn(controls.SET,calls)
            window.widgets[0x980900][0].set_value(6)
            self.assertIn(controls.SET,calls)
            window.destroy()
            close.assert_called_once_with(123)

    def test_camera_listing_excludes_metadata_interface(self):
        for capabilities,expected in ((1,True),(0x800000,False)):
            raw = bytearray(104)
            struct.pack_into('II',raw,84,0x80000000,capabilities)
            with patch.object(controls.os,'open',return_value=123),patch.object(controls.os,'close'),patch.object(controls.fcntl,'ioctl',return_value=bytes(raw)):
                self.assertEqual(controls.is_capture_device('/dev/video1'),expected)
