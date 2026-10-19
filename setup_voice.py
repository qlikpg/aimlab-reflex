"""Download the official Polish offline model once; remove the temporary archive."""
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def install():
    root = Path(__file__).resolve().parent/'models'
    if (root/'vosk-model-small-pl-0.22/am/final.mdl').exists():
        print('Polski model jest już zainstalowany.')
        return
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='aimlab-voice-model-') as directory:
        archive = Path(directory)/'model.zip'
        urllib.request.urlretrieve('https://alphacephei.com/vosk/models/vosk-model-small-pl-0.22.zip',archive)
        with zipfile.ZipFile(archive) as package:
            for member in package.infolist():
                if not (root/member.filename).resolve().is_relative_to(root.resolve()):
                    raise ValueError('Invalid model archive path')
            package.extractall(root)
    print('Polski model DAJ zainstalowany.')


if __name__ == '__main__':
    install()
