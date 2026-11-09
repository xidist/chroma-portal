"""Download Google's official Hand Landmarker model; never auto-run at import."""
from pathlib import Path
import hashlib
import urllib.request

URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'

if __name__ == '__main__':
    target = Path(__file__).resolve().parents[1] / 'models' / 'hand_landmarker.task'
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        print(f'Already present: {target}')
    else:
        temporary = target.with_suffix('.download')
        try:
            with urllib.request.urlopen(URL, timeout=60) as response:
                temporary.write_bytes(response.read())
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        print(f'Downloaded: {target}')
    print('SHA256:', hashlib.sha256(target.read_bytes()).hexdigest())
