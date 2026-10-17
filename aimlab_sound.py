"""Short synthesized hit bell using Linux audio tools, without blocking playback."""
import math
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path


class HitSound:
    def __init__(self, enabled=True):
        self.processes = []
        self.directory = None
        self.command = None
        if not enabled:
            return
        player = shutil.which('paplay') or shutil.which('aplay')
        if player is None:
            print('Dźwięk trafienia niedostępny: brak paplay/aplay.',flush=True)
            return
        self.directory = tempfile.TemporaryDirectory(prefix='aimlab-hit-')
        path = Path(self.directory.name)/'bell.wav'
        rate = 44100
        duration = .16
        samples = bytearray()
        for index in range(round(rate*duration)):
            t = index/rate
            envelope = min(1,t/.003)*math.exp(-t*28)*min(1,(duration-t)/.012)
            tone = (math.sin(2*math.pi*1320*t)+.35*math.sin(2*math.pi*2640*t))
            samples.extend(struct.pack('<h',round(7500*envelope*tone)))
        with wave.open(str(path),'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(rate)
            output.writeframes(samples)
        self.command = [player,str(path)] if Path(player).name == 'paplay' else [player,'-q',str(path)]

    def play(self):
        if self.command is None:
            return
        self.processes = [process for process in self.processes if process.poll() is None]
        if len(self.processes) >= 8:
            return  # Never build up a delayed queue of old hit sounds.
        try:
            self.processes.append(subprocess.Popen(self.command,stdin=subprocess.DEVNULL,
                                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL))
        except OSError:
            self.command = None
            print('Nie można odtworzyć dźwięku trafienia; trening trwa dalej.',flush=True)

    def close(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        self.processes.clear()
        if self.directory:
            self.directory.cleanup()
