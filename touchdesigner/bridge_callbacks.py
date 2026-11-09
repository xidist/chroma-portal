"""Paste into a Script TOP's callbacks DAT. Requires only TD's NumPy and stdlib.

Call stop() before editing/reloading this DAT or removing the component. The
worker never calls any TouchDesigner API. onCook copies the latest RGB and
stores its matching uniforms for the downstream GLSL TOP.
"""
import json
import struct
import threading
import time
import urllib.request
import numpy as np

URL = 'http://127.0.0.1:8765/frame'
_thread = None
_stop = threading.Event()
_latest = None
_lock = threading.Lock()


def decode_frame(packet):
    if len(packet) < 4:
        raise ValueError('Short packet')
    n = struct.unpack('!I', packet[:4])[0]
    if n > 16384 or len(packet) < 4 + n:
        raise ValueError('Invalid header')
    header = json.loads(packet[4:4 + n])
    w, h = int(header['width']), int(header['height'])
    if header['version'] != 1 or not (1 <= w <= 4096 and 1 <= h <= 4096):
        raise ValueError('Unsupported frame')
    pixels = packet[4 + n:]
    if len(pixels) != w * h * 3:
        raise ValueError('Incorrect RGB byte count')
    controls = header['controls']
    for key in ('uCorners01', 'uCorners23', 'uLook', 'uControl'):
        a = np.asarray(controls[key], dtype=float)
        if a.shape != (4,) or not np.isfinite(a).all():
            raise ValueError('Invalid uniform')
    return np.frombuffer(pixels, np.uint8).reshape(h, w, 3), controls, int(header['frame_id'])


def _receive():
    global _latest
    last_id = None
    while not _stop.is_set():
        started = time.monotonic()
        try:
            with urllib.request.urlopen(URL, timeout=.5) as response:
                packet = response.read(64 * 1024 * 1024)
            rgb, controls, frame_id = decode_frame(packet)
            if frame_id != last_id:
                with _lock:
                    _latest = (rgb, controls, time.monotonic())
                last_id = frame_id
        except Exception:
            # Keep last frame; onCook fades the effect when frames stop arriving.
            last_id = None
        _stop.wait(max(.001, 1 / 30 - (time.monotonic() - started)))


def start():
    global _thread
    if _thread is None or not _thread.is_alive():
        _stop.clear()
        _thread = threading.Thread(target=_receive, daemon=True)
        _thread.start()


def stop():
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=1)
        _thread = None


def onSetupParameters(scriptOp):
    pass


def onPulse(par):
    pass


def onCook(scriptOp):
    # Makes the callback time-dependent so it continues to cook while viewed.
    _ = absTime.frame
    start()
    with _lock:
        latest = _latest
    if latest is None:
        scriptOp.copyNumpyArray(np.zeros((240, 320, 3), np.uint8))
        scriptOp.store('uControl', [0, 3, 1, 1.5])
        return
    rgb, controls, received = latest
    age = time.monotonic() - received
    values = {key: list(value) for key, value in controls.items()}
    values['uControl'][0] *= max(0.0, min(1.0, 1.0 - (age - .25) / .30))
    # TD reads texture arrays bottom-up. This is the only image y-flip.
    scriptOp.copyNumpyArray(np.ascontiguousarray(rgb[::-1]))
    for key, value in values.items():
        scriptOp.store(key, value)


def uniform(name, component):
    """Called by GLSL TOP parameter expressions after its input cooks."""
    defaults = {'uCorners01': [.25, .7, .75, .7],
                'uCorners23': [.75, .3, .25, .3],
                'uLook': [0, 0, 8, 1.3], 'uControl': [0, 3, 1, 1.5]}
    return op('portal_frame').fetch(name, defaults[name])[component]
