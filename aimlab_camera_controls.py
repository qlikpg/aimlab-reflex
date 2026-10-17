"""Native V4L2 controls shared with the GTK training/calibration panel."""
import fcntl
import os
import struct
import gi
gi.require_version('Gtk','3.0')
from gi.repository import Gtk, GLib

QUERY = 0xc0445624
GET = 0xc008561b
SET = 0xc008561c
NAMES = {0x980900:'Jasność',0x980901:'Kontrast',0x98090c:'Automatyczny balans bieli',
         0x98091a:'Temperatura bieli (K)',0x9a0901:'Tryb ekspozycji',
         0x9a0902:'Czas ekspozycji (0,1 ms)',0x9a0903:'Automatyczna zmiana FPS',
         0x9a090a:'Ostrość ręczna',0x9a090c:'Autofokus',0x980918:'Częstotliwość oświetlenia'}


def is_capture_device(device):
    try:
        fd = os.open(str(device),os.O_RDONLY|os.O_NONBLOCK)
        try:
            raw = fcntl.ioctl(fd,0x80685600,bytes(104))
            caps,device_caps = struct.unpack_from('II',raw,84)
            return bool((device_caps if caps & 0x80000000 else caps) & (1|0x1000))
        finally:
            os.close(fd)
    except OSError:
        return False


class CameraControls(Gtk.Window):
    def __init__(self, device, parent=None):
        super().__init__(title=f'Ustawienia kamery — {device}',transient_for=parent)
        self.fd = os.open(str(device),os.O_RDWR|os.O_NONBLOCK)
        self.device = str(device)
        self.widgets = {}
        self.refreshing = False
        self.source = None
        self.set_default_size(640,520)
        self.set_border_width(20)
        self.set_destroy_with_parent(True)
        self.set_modal(bool(parent and parent.get_modal()))
        self.connect('destroy',self.cleanup)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12)
        self.add(box)
        note = Gtk.Label(xalign=0,label='Ustawienia działają na żywo, bez zatrzymywania podglądu.\n'
                        'Otwarcie okna nie zmienia wartości. Wybierz ręczną ekspozycję,\n'
                        'aby zmienić jej czas (100 = 10 ms). Zbyt krótki czas może gubić impulsy.\n'
                        'Po zmianie ostrości powtórz kalibrację rogów.')
        note.set_line_wrap(True)
        box.pack_start(note,False,False,0)
        grid = Gtk.Grid(column_spacing=18,row_spacing=12)
        box.pack_start(grid,False,False,0)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        box.pack_start(self.status,False,False,0)
        for identifier,title in NAMES.items():
            try:
                info = self.query(identifier)
                kind = info[1]
                if info[7] & 1:
                    continue
                if kind == 3:
                    widget = Gtk.ComboBoxText()
                    for index in range(info[3],info[4]+1):
                        try:
                            raw = fcntl.ioctl(self.fd,0xc02c5625,struct.pack('II32sI',identifier,index,b'',0))
                            text = struct.unpack('II32sI',raw)[2].split(b'\0')[0].decode(errors='replace')
                            if identifier == 0x9a0901:
                                text = {1:'Ręczna',3:'Automatyczna'}.get(index,text)
                            widget.append(str(index),text)
                        except OSError:
                            pass
                    event = 'changed'
                elif kind == 2:
                    widget = Gtk.CheckButton(label='Włączone')
                    event = 'toggled'
                elif kind == 1:
                    widget = Gtk.SpinButton.new_with_range(info[3],info[4],max(1,info[5]))
                    event = 'value-changed'
                else:
                    continue
                row = len(self.widgets)
                grid.attach(Gtk.Label(label=title,xalign=0),0,row,1,1)
                grid.attach(widget,1,row,1,1)
                self.widgets[identifier] = (widget,kind)
                widget.connect(event,self.changed,identifier,kind)
            except OSError:
                continue
        self.refresh()
        if not self.widgets:
            self.status.set_text('Kamera nie udostępnia obsługiwanych ustawień.')
        self.source = GLib.timeout_add(1000,self.refresh)

    def query(self, identifier):
        return struct.unpack('II32siiiiIII',fcntl.ioctl(self.fd,QUERY,
                             struct.pack('II32siiiiIII',identifier,0,b'',0,0,0,0,0,0,0)))

    def changed(self, widget, identifier, kind):
        if self.refreshing:
            return
        try:
            value = (int(widget.get_active_id()) if kind == 3 else
                     int(widget.get_active()) if kind == 2 else widget.get_value_as_int())
            fcntl.ioctl(self.fd,SET,struct.pack('Ii',identifier,value))
            self.status.set_text('Zapisano w kamerze: '+NAMES[identifier])
        except (OSError,TypeError,ValueError) as error:
            self.status.set_text('Nie można ustawić wartości: '+str(error))
        self.refresh()

    def refresh(self):
        self.refreshing = True
        try:
            for identifier,(widget,kind) in self.widgets.items():
                info = self.query(identifier)
                value = struct.unpack('Ii',fcntl.ioctl(self.fd,GET,struct.pack('Ii',identifier,0)))[1]
                widget.set_sensitive(not info[7] & (1|4|16))
                if kind == 3:
                    widget.set_active_id(str(value))
                elif kind == 2:
                    widget.set_active(bool(value))
                else:
                    widget.set_value(value)
        except OSError as error:
            self.status.set_text('Błąd odczytu kamery: '+str(error))
        finally:
            self.refreshing = False
        return True

    def cleanup(self, *_):
        if self.source is not None:
            GLib.source_remove(self.source)
            self.source = None
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
