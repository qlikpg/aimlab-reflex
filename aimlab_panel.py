#!/usr/bin/env python3
"""Native Linux control panel; workers run in the local virtual environment."""
import fcntl
import json
import shutil
import subprocess
import time
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, GLib, Gtk

from aimlab_game_modes import Config, Game, MODES
from aimlab_settings import DEFAULTS, migrate_settings
from aimlab_calibration_report import format_report
from aimlab_camera_controls import CameraControls, is_capture_device

ROOT = Path(__file__).resolve().parent


def load_settings():
    try:
        return migrate_settings(json.loads((ROOT/'aimlab_settings.json').read_text()))
    except (OSError, ValueError):
        return dict(DEFAULTS)


class Panel(Gtk.Window):
    def __init__(self):
        super().__init__(title='AimLab IRL — panel treningu')
        self.set_default_size(860, 840)
        self.set_border_width(24)
        self.connect('delete-event', self.close)
        self.children = {}
        self.stopping = {}
        self.closing = False
        self.pending = None
        self.training_input = 'laser'
        self.last_training_mode = 'classic'
        self.calibration_stage = None
        self.calibration_report = ROOT/'aimlab_calibration_report.json'
        self.calibration_dialog = None
        self.camera_controls = None
        self.calibration_draft = ROOT/f'.calibration_draft_{time.time_ns()}.json'
        self.state_path = ROOT/f'.camera_status_{time.time_ns()}.json'
        self.log = (ROOT/'aimlab_panel.log').open('a')
        self.settings = load_settings()
        self.message = ''
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.add(box)
        title = Gtk.Label(xalign=0)
        title.set_markup('<span size="xx-large" weight="bold">AimLab IRL</span>')
        box.pack_start(title, False, False, 0)
        grid = Gtk.Grid(column_spacing=18, row_spacing=10)
        box.pack_start(grid, False, False, 0)
        self.fields = {}
        for row, (key, label) in enumerate([('camera','Kamera'), ('screen','Ekran rzutnika'), ('color','Kolor lasera'), ('minimum','Minimalna jasność'), ('delta','Przewaga koloru'), ('mode','Tryb treningu'), ('target_style','Wygląd celu'), ('duration','Czas sesji (sekundy)'), ('active_targets','Aktywne cele jednocześnie'), ('targets','Cele do ukończenia Classic'), ('radius','Promień celu (px przy 1920×1080)'), ('input_method','Sterowanie')]):
            if key in ('camera', 'screen', 'color', 'mode', 'duration', 'input_method', 'target_style'):
                field = Gtk.ComboBoxText()
            else:
                low, high = (1,100) if key == 'targets' else ((1,24) if key == 'active_targets' else ((5,300) if key == 'radius' else (0,255)))
                field = Gtk.SpinButton.new_with_range(low, high, 1)
                field.set_value(self.settings[key])
            field.set_hexpand(True)
            grid.attach(Gtk.Label(label=label, xalign=0), 0, row, 1, 1)
            grid.attach(field, 1, row, 1, 1)
            self.fields[key] = field
        self.fields['color'].append('green','Zielony')
        self.fields['color'].append('red','Czerwony')
        self.fields['color'].set_active_id(self.settings['color'])
        for key, choices in [('mode', [(key,mode.name) for key,mode in MODES.items()]),
                             ('duration', [(str(n),str(n)) for n in (30,60,120)]),
                             ('target_style', [('orange','Pomarańczowy'),('black','Czarny'),('orange-black','Pomarańczowo-czarny'),('classic','Klasyczny — niebieskie koło')]),
                             ('input_method', [('laser','Kamera i laser'),('mouse','Test myszą — bez kamery')])]:
            for value,label in choices:
                self.fields[key].append(value,label)
            self.fields[key].set_active_id(str(self.settings[key]))
        self.fields['mode'].connect('changed',self.mode_changed)
        self.fields['input_method'].connect('changed',self.input_changed)
        self.buttons = []
        for labels in [[('Odśwież urządzenia',self.refresh), ('Zapisz ustawienia',self.save), ('Ustawienia kamery',self.show_camera_controls)], [('Podgląd i maska',self.preview), ('Kalibracja',self.calibrate), ('Pomiar błędu',self.check_calibration)], [('Start treningu',self.train), ('STOP',self.stop)]]:
            row = Gtk.Box(spacing=8)
            box.pack_start(row, False, False, 0)
            for label, callback in labels:
                button = Gtk.Button(label=label)
                button.connect('clicked',self.action,callback)
                row.pack_start(button, True, True, 0)
                if label not in ('STOP','Ustawienia kamery'):
                    self.buttons.append(button)
        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        box.pack_start(self.status, False, False, 0)
        note = Gtk.Label(xalign=0, label='Kalibracja: kliknij w podglądzie kamery cztery zewnętrzne rogi ramki:\nlewy górny → prawy górny → prawy dolny → lewy dolny.\nPotwierdź wskazane rogi w panelu, aby przejść do tarcz laserowych.\n\nUstawienia z panelu obowiązują po ponownym uruchomieniu kamery.\nSuwaki maski działają na żywo; „Zapisz ustawienia” zachowa ich wartości.\nOdstępy i wiek celu obejmują opóźnienia sprzętu. Gaś laser między strzałami.\nPrzy czerwonym laserze wybierz czarny cel, jeśli pomarańczowy zakłóca detekcję.')
        note.set_line_wrap(True)
        box.pack_start(note, False, False, 0)
        self.refresh()
        self.poll_source = GLib.timeout_add(250, self.poll)

    def action(self, button, callback):
        try:
            callback()
        except (OSError, RuntimeError, ValueError) as error:
            self.message = str(error)

    def running(self, name):
        return name in self.children and self.children[name].poll() is None

    def refresh(self):
        previous = self.fields['camera'].get_active_id() or self.settings['camera']
        self.fields['camera'].remove_all()
        cameras = []
        for path in sorted(Path('/sys/class/video4linux').glob('video*')):
            device = '/dev/'+path.name
            if Path(device).exists() and is_capture_device(device):
                name = (path/'name').read_text().strip()
                cameras.append((device,name))
                self.fields['camera'].append(device,f'{name} ({device})')
        selected = previous if previous in [c[0] for c in cameras] else next((c[0] for c in cameras if 'trust' in c[1].lower()), None)
        if selected:
            self.fields['camera'].set_active_id(selected)
        self.fields['screen'].remove_all()
        display = Gdk.Display.get_default()
        self.screens = []
        for i in range(display.get_n_monitors()):
            monitor = display.get_monitor(i)
            g = monitor.get_geometry()
            self.screens.append((g.width,g.height,g.x,g.y))
            self.fields['screen'].append(str(i),f'{monitor.get_model() or "Ekran"} — {g.width}×{g.height} ({g.x},{g.y})')
            if monitor != display.get_primary_monitor():
                self.fields['screen'].set_active_id(str(i))
        self.input_changed()
        self.message = ('Wybierz kamerę. ' if not selected else '') + ('Brak rzutnika — podłącz HDMI i kliknij Odśwież.' if len(self.screens)<2 else 'Gotowe do podglądu i kalibracji.')

    def mode_changed(self, *_):
        mode = self.fields['mode'].get_active_id()
        if mode:
            self.last_training_mode = mode
            self.fields['radius'].set_value(MODES[mode].radius)
            self.fields['active_targets'].set_value(MODES[mode].count)
            self.fields['duration'].set_active_id('60')
            self.fields['targets'].set_value(10)

    def input_changed(self, *_):
        if self.fields['input_method'].get_active_id() == 'mouse' and self.fields['screen'].get_active_id() is None:
            if self.screens:
                self.fields['screen'].set_active_id('0')

    def state(self):
        try:
            data = json.loads(self.state_path.read_text())
            if self.running('camera') and 0 <= time.monotonic()-data['monotonic_s'] < 2:
                return data
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return {}

    def save(self):
        a = dict(DEFAULTS)
        for key, field in self.fields.items():
            if key != 'screen':
                a[key] = (int(field.get_active_id()) if key == 'duration' else
                          field.get_active_id() if key in ('camera','color','mode','input_method','target_style') else field.get_value_as_int())
        if not a['camera']:
            a['camera'] = self.settings['camera']
        state = self.state()
        if state:
            a.update(minimum=state['minimum'], delta=state['delta'], color=state['laser_color'])
            for key in ('minimum','delta'):
                self.fields[key].set_value(a[key])
        target = ROOT/'aimlab_settings.json'
        temp = target.with_suffix('.tmp')
        temp.write_text(json.dumps(a,indent=2))
        temp.replace(target)
        self.settings = migrate_settings(a)
        self.message = 'Ustawienia zapisane na następne uruchomienia.'

    def spawn(self, name, script, args):
        if self.running(name) or name in self.stopping:
            raise RuntimeError('Poczekaj na zatrzymanie poprzedniego procesu.')
        python = ROOT/'.venv/bin/python'
        if not python.exists():
            raise RuntimeError('Brak środowiska projektu. Uruchom instalator.')
        self.children[name] = subprocess.Popen([str(python),'-u',str(ROOT/script),*args],cwd=ROOT,stdout=self.log,stderr=self.log)

    def start_camera(self, calibration=False, extra_args=None):
        if self.running('camera'):
            if calibration or extra_args:
                raise RuntimeError('Kliknij STOP, potem Kalibracja — rogi będą gotowe do wskazania.')
            return
        camera = self.fields['camera'].get_active_id()
        if not camera or not Path(camera).exists():
            raise RuntimeError('Podłącz kamerę i wybierz ją na liście.')
        self.save()
        a = self.settings
        args = ['--camera',camera,'--laser-color',a['color'],f'--{a["color"]}-min',str(a['minimum']),f'--{a["color"]}-delta',str(a['delta']),'--show-mask','--status-file',str(self.state_path)]
        if calibration:
            args.append('--start-calibration')
        args.extend(extra_args or [])
        self.spawn('camera','aimlab_irl_camera_mvp.py',args)

    def screen_args(self):
        selection = self.fields['screen'].get_active_id()
        if selection is None:
            raise RuntimeError('Podłącz rzutnik, odśwież urządzenia i wybierz jego ekran.')
        i = int(selection)
        display = Gdk.Display.get_default()
        if i >= display.get_n_monitors():
            raise RuntimeError('Układ ekranów zmienił się. Odśwież urządzenia.')
        g = display.get_monitor(i).get_geometry()
        if (g.width,g.height,g.x,g.y) != self.screens[i]:
            raise RuntimeError('Układ ekranów zmienił się. Odśwież urządzenia.')
        w,h,x,y = self.screens[i]
        return ['--width',str(w),'--height',str(h),'--screen-x',str(x),'--screen-y',str(y)]

    def show_camera_controls(self, parent=None):
        camera = self.fields['camera'].get_active_id()
        if not camera or not is_capture_device(camera):
            raise RuntimeError('Wybierz podłączoną kamerę z obrazem, nie interfejs pomocniczy.')
        parent = parent or self.calibration_dialog or self
        if self.camera_controls is not None:
            if self.camera_controls.device == camera:
                self.camera_controls.set_transient_for(parent)
                self.camera_controls.set_modal(parent.get_modal())
                self.camera_controls.present()
                return
            self.camera_controls.destroy()
        controls = CameraControls(camera,parent)
        self.camera_controls = controls
        controls.connect('destroy',lambda window:setattr(self,'camera_controls',None))
        controls.show_all()
        controls.present()

    def preview(self):
        self.start_camera()
        self.message = 'Podgląd uruchomiony. Maska ma suwaki czułości.'

    def video_calibration(self):
        if any(self.running(name) for name in ('camera','training','projector')):
            raise RuntimeError('Kliknij STOP przed kalibracją wideo.')
        camera = self.fields['camera'].get_active_id()
        if not camera or not Path(camera).exists():
            raise RuntimeError('Podłącz i wybierz kamerę.')
        args = self.screen_args()
        self.save()
        a = self.settings
        self.calibration_report.unlink(missing_ok=True)
        self.spawn('projector','aimlab_video_calibration.py',['--camera',camera,'--report-file',str(self.calibration_report),*args,'--laser-color',a['color'],f'--{a["color"]}-min',str(a['minimum']),f'--{a["color"]}-delta',str(a['delta'])])
        self.video_running = True
        self.message = 'Kalibracja wideo: strzelaj w środek tarczy. Następny cel po impulsie. Gaś laser między strzałami; nie ruszaj kamerą. Nagranie zostanie usunięte; wynik w aimlab_panel.log.'

    def show_calibration_report(self, code, expected=False):
        try:
            report = json.loads(self.calibration_report.read_text(encoding='utf-8'))
            if not isinstance(report,dict):
                raise ValueError('Nieprawidłowy raport')
            if code != 0 and report.get('status') in ('applied','unchanged'):
                report['status'] = 'failed'
        except (OSError,ValueError):
            report = dict(status='cancelled' if expected else 'failed',
                          message='Proces nie dostarczył pełnego raportu. Szczegóły w aimlab_panel.log.')
        self.message = format_report(report)
        if expected:
            return
        success = report.get('status') in ('applied','unchanged')
        dialog = Gtk.MessageDialog(transient_for=self,modal=True,
                                   message_type=Gtk.MessageType.INFO if success else Gtk.MessageType.WARNING,
                                   buttons=Gtk.ButtonsType.OK,text='Raport kalibracji')
        dialog.format_secondary_text(self.message)
        dialog.connect('response',lambda window,response:window.destroy())
        dialog.show_all()
        dialog.present()

    def check_calibration(self):
        if any(self.running(name) for name in ('camera','training','projector')):
            raise RuntimeError('Kliknij STOP przed pomiarem błędu.')
        args = self.screen_args()
        args[0] = '--projector-width'
        args[2] = '--projector-height'
        self.start_camera(extra_args=['--check-calibration', *args])
        self.message = 'Laser wyłączony: klikaj środek tarczy w oknie AimLab IRL. Wynik w pikselach rzutnika; N powtarza pomiar.'

    def calibrate(self):
        self.screen_args()  # Validate selected output before stopping anything.
        camera = self.fields['camera'].get_active_id()
        if not camera or not Path(camera).exists():
            raise RuntimeError('Podłącz i wybierz kamerę.')
        self.stop()
        self.calibration_stage = 'mouse-start'
        self.message = 'Kalibracja: przygotowuję wskazywanie czterech rogów myszą…'

    def confirm_mouse_calibration(self):
        self.calibration_stage = 'confirm'
        dialog = Gtk.MessageDialog(transient_for=self, modal=True,
                                   message_type=Gtk.MessageType.QUESTION,
                                   text='Czy potwierdzasz kalibrację myszą?')
        dialog.format_secondary_text('Sprawdź cztery wskazane rogi w podglądzie kamery. '
                                     'Po potwierdzeniu uruchomi się etap laserowy. '
                                     'Możesz też powtórzyć wskazywanie rogów.')
        dialog.add_buttons('Ustawienia kamery',1001,'Anuluj',Gtk.ResponseType.CANCEL,
                           'Powtórz',Gtk.ResponseType.REJECT,
                           'Potwierdź i przejdź do lasera',Gtk.ResponseType.ACCEPT)
        dialog.connect('response',self.mouse_calibration_response)
        self.calibration_dialog = dialog
        dialog.show_all()
        dialog.present()
        self.message = 'Potwierdź kalibrację myszą w oknie dialogowym.'

    def mouse_calibration_response(self, dialog, response):
        if response == 1001:
            try:
                self.show_camera_controls(dialog)
            except (OSError,RuntimeError) as error:
                dialog.format_secondary_text(str(error))
            return
        if self.camera_controls is not None:
            self.camera_controls.destroy()
        self.calibration_dialog = None
        dialog.destroy()
        if response == Gtk.ResponseType.ACCEPT:
            try:
                data = json.loads(self.calibration_draft.read_text())
                if (len(data['points']) != 4 or len(data['frame_size']) != 2
                        or data['camera'] != self.fields['camera'].get_active_id()):
                    raise ValueError('Nieprawidłowy szkic kalibracji.')
                destination = ROOT/'aimlab_calibration.json'
                if destination.exists():
                    shutil.copy2(destination,ROOT/'aimlab_calibration.previous.json')
                temporary = destination.with_suffix('.tmp')
                temporary.write_text(json.dumps(data),encoding='utf-8')
                temporary.replace(destination)
                self.calibration_stage = 'laser-start'
                self.message = 'Potwierdzono rogi. Przygotowuję kalibrację laserową…'
            except (OSError,ValueError,KeyError) as error:
                self.stop()
                self.message = f'Nie zapisano kalibracji: {error}'
                return
        elif response == Gtk.ResponseType.REJECT:
            self.calibration_stage = 'mouse-start'
            self.message = 'Powtórz wskazywanie czterech rogów.'
        else:
            self.stop()
            self.message = 'Kalibracja anulowana. Nie zatwierdzono nowych rogów.'
            return
        for name in list(self.children):
            self.stop_one(name)

    def advance_calibration(self, state):
        stage = self.calibration_stage
        if stage in ('mouse-start','laser-start') and not self.children and not self.stopping:
            try:
                if stage == 'mouse-start':
                    self.calibration_draft.unlink(missing_ok=True)
                    self.state_path.unlink(missing_ok=True)
                    self.start_camera(True,extra_args=['--calibration',str(self.calibration_draft)])
                    self.spawn('projector','projector_calibration.py',self.screen_args())
                    self.calibration_stage = 'mouse'
                    self.message = 'Etap 1/2: wskaż cztery zewnętrzne rogi ramki myszą.'
                else:
                    self.video_calibration()
                    self.calibration_stage = 'laser'
                    self.message = 'Etap 2/2: strzelaj w środki tarcz. Pudła nie zmieniają celu.'
            except (OSError,RuntimeError,ValueError) as error:
                self.stop()
                self.message = str(error)
        elif stage == 'mouse' and state.get('calibrated') and self.calibration_draft.exists():
            self.confirm_mouse_calibration()
        elif stage in ('mouse','confirm') and (not self.running('camera') or not self.running('projector')):
            self.stop()
            self.message = 'Kalibracja przerwana przed potwierdzeniem rogów.'

    def train(self):
        if self.running('training'):
            return
        args = self.screen_args()
        mouse = self.fields['input_method'].get_active_id() == 'mouse'
        if not mouse:
            if not self.running('camera'):
                self.start_camera()
            elif not self.state().get('calibrated'):
                raise RuntimeError('Kamera wymaga kalibracji lub jeszcze się uruchamia. Poczekaj na status gotowa.')
        mode = self.fields['mode'].get_active_id()
        radius = self.fields['radius'].get_value_as_int()
        count = self.fields['active_targets'].get_value_as_int() if mode not in ('classic','spidershot','trap-spidershot') else 1
        w,h = self.screens[int(self.fields['screen'].get_active_id())][:2]
        duration = int(self.fields['duration'].get_active_id())
        try:
            Game(Config(mode=mode,width=w,height=h,radius=radius,active_count=count,duration=duration,
                        classic_total=self.fields['targets'].get_value_as_int()))
        except ValueError as error:
            raise RuntimeError('Nie można rozmieścić celów. Zmniejsz promień lub liczbę celów albo zwiększ ekran. '+str(error)) from error
        self.save()
        self.stop_one('projector')
        self.training_input = 'mouse' if mouse else 'laser'
        self.pending = args+['--mode',mode,'--target-style',self.fields['target_style'].get_active_id(),'--duration',str(duration),'--active-targets',str(count),
                             '--targets',str(self.fields['targets'].get_value_as_int()),'--radius',str(radius)]
        if mouse:
            self.pending.append('--mouse-test')
        self.message = 'Przygotowuję trening…'

    def stop_one(self,name):
        if self.running(name) and name not in self.stopping:
            self.children[name].terminate()
            self.stopping[name] = time.monotonic()

    def stop(self):
        self.calibration_stage = None
        if self.calibration_dialog is not None:
            dialog,self.calibration_dialog = self.calibration_dialog,None
            dialog.destroy()
        self.calibration_draft.unlink(missing_ok=True)
        self.pending = None
        for name in list(self.children):
            self.stop_one(name)
        self.message = 'Zatrzymano. Wyniki i kalibracja są zachowane.'

    def poll(self):
        for name,process in list(self.children.items()):
            code = process.poll()
            if code is not None:
                expected = name in self.stopping
                self.stopping.pop(name,None)
                del self.children[name]
                if code and not expected:
                    self.message = f'Błąd procesu {name}. Szczegóły w aimlab_panel.log.'
                if name == 'projector' and getattr(self,'video_running',False):
                    self.video_running = False
                    self.calibration_stage = None
                    self.calibration_draft.unlink(missing_ok=True)
                    self.save()
                    self.show_calibration_report(code,expected)
                if name == 'camera':
                    if self.training_input != 'mouse':
                        self.stop_one('training')
                    self.stop_one('projector')
                    if self.training_input != 'mouse':
                        self.pending = None
            elif name in self.stopping and time.monotonic()-self.stopping[name] > 2:
                process.kill()
        state = self.state()
        self.advance_calibration(state)
        if self.running('training') and self.training_input != 'mouse' and not state.get('calibrated'):
            self.stop_one('training')
            self.message = 'Trening zatrzymany: brak gotowej kamery lub kalibracji.'
        if self.pending and not self.running('projector') and 'projector' not in self.stopping:
            if self.training_input == 'mouse' or state.get('calibrated'):
                try:
                    self.spawn('training','aimlab_training.py',self.pending)
                    self.message = ('Test myszą: klikaj cele.' if self.training_input == 'mouse' else 'Trening trwa. Celuj w cele i gaś laser między strzałami.')
                except (OSError, RuntimeError) as error:
                    self.message = str(error)
                self.pending = None
            elif self.running('camera') and state and not state.get('calibrated'):
                self.pending = None
                self.message = 'Brak poprawnej kalibracji kamery. Wykonaj kalibrację czterech rogów.'
        camera = 'wyłączona' if not self.running('camera') else ('uruchamianie…' if not state else ('gotowa' if state.get('calibrated') else 'wymaga kalibracji'))
        self.status.set_text(f'Kamera: {camera} | Trening: {"włączony" if self.running("training") else "wyłączony"}\n{self.message.splitlines()[0] if self.message else ""}')
        for widget in self.buttons:
            widget.set_sensitive(not self.stopping and not self.pending and not getattr(self,'video_running',False) and not self.calibration_stage)
        for key,field in self.fields.items():
            hardware = key in ('camera','color','minimum','delta')
            enabled = not self.stopping and not self.pending and not self.running('training') and not getattr(self,'video_running',False) and not self.calibration_stage
            if hardware and self.running('camera'):
                enabled = False
            mode = self.fields['mode'].get_active_id()
            if key == 'duration' and mode == 'classic':
                enabled = False
            if key == 'targets' and mode != 'classic':
                enabled = False
            if key == 'active_targets' and mode in ('classic','spidershot','trap-spidershot'):
                enabled = False
            field.set_sensitive(enabled)
        if self.closing and not self.children:
            self.state_path.unlink(missing_ok=True)
            self.log.close()
            self.destroy()
            Gtk.main_quit()
            return False
        return True

    def close(self,*_):
        self.closing = True
        self.stop()
        return True


def main():
    with (ROOT/'.aimlab_panel.lock').open('w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            dialog = Gtk.MessageDialog(message_type=Gtk.MessageType.INFO,buttons=Gtk.ButtonsType.OK,text='Panel AimLab IRL jest już uruchomiony.')
            dialog.run()
            dialog.destroy()
            return
        window = Panel()
        window.show_all()
        Gtk.main()


if __name__ == '__main__':
    main()
