"""Offline Polish DAJ commands; microphone and recognizer live in a separate process."""
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

MODEL = Path(__file__).resolve().parent/'models/vosk-model-small-pl-0.22'


def command_from_result(result, stream_start):
    if result.get('text','').strip().casefold() != 'daj':
        return None
    words = result.get('result',[])
    if len(words)!=1 or words[0].get('word')!='daj' or words[0].get('conf',0)<.75:
        return None
    return stream_start+float(words[0]['start'])


def check_voice_available(model=MODEL):
    if not Path(model,'am/final.mdl').exists():
        raise RuntimeError('Brak polskiego modelu głosowego. Uruchom install_voice.sh.')
    if not shutil.which('parec'):
        raise RuntimeError('Brak parec (pakiet pulseaudio-utils) do odczytu mikrofonu.')
    import importlib.util
    if importlib.util.find_spec('vosk') is None:
        raise RuntimeError('Brak Vosk w .venv. Uruchom install_voice.sh.')


class VoiceInput:
    def __init__(self, model=MODEL, source=None):
        check_voice_available(model)
        self.events = queue.Queue(maxsize=8)
        self.error = None
        self.ready = False
        args = [sys.executable,str(Path(__file__).resolve()),'--worker',str(model)]
        if source:
            args.append(source)
        self.process = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=None,text=True,bufsize=1)
        self.thread = threading.Thread(target=self._receive,daemon=True)
        self.thread.start()

    def _receive(self):
        try:
            for line in self.process.stdout:
                data = json.loads(line)
                if 'error' in data:
                    self.error = data['error']
                elif data.get('ready'):
                    self.ready = True
                elif 'stamp' in data:
                    try:
                        self.events.put_nowait(float(data['stamp']))
                    except queue.Full:
                        pass
        except (ValueError,OSError) as error:
            self.error = str(error)
        finally:
            if self.error is None:
                self.error = 'Rozpoznawanie głosu zostało zatrzymane. Sprawdź mikrofon.'

    def read(self):
        events = []
        while True:
            try:
                events.append(self.events.get_nowait())
            except queue.Empty:
                return events

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.thread.join(timeout=1)
        self.process.stdout.close()


def worker(model, source=None):
    import signal
    import os
    import ctypes
    if sys.platform.startswith('linux'):
        ctypes.CDLL(None).prctl(1,signal.SIGTERM)
        if os.getppid() == 1:
            return
    from vosk import Model, KaldiRecognizer, SetLogLevel
    SetLogLevel(-1)
    recognizer = KaldiRecognizer(Model(model),16000,json.dumps(['daj','[unk]']))
    recognizer.SetWords(True)
    args = ['parec','--raw','--format=s16le','--rate=16000','--channels=1','--latency-msec=40']
    if source:
        args += ['--device',source]
    microphone = subprocess.Popen(args,stdout=subprocess.PIPE)
    def stop(*_):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    start = time.monotonic()
    print(json.dumps({'ready':True}),flush=True)
    last = -float('inf')
    try:
        while True:
            audio = microphone.stdout.read(3200)
            if not audio:
                raise RuntimeError('Brak danych mikrofonu. Sprawdź wybrane wejście dźwięku.')
            if recognizer.AcceptWaveform(audio):
                stamp = command_from_result(json.loads(recognizer.Result()),start)
                if stamp is not None and stamp-last>=.8:
                    print(json.dumps({'stamp':stamp}),flush=True)
                    last = stamp
    finally:
        microphone.terminate()
        try:
            microphone.wait(timeout=1)
        except subprocess.TimeoutExpired:
            microphone.kill()
            microphone.wait()
        microphone.stdout.close()


if __name__ == '__main__':
    try:
        worker(sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None)
    except Exception as error:
        print(json.dumps({'error':str(error)}),flush=True)
        sys.exit(1)
