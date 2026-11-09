"""Optional loopback bridge: one matching RGB frame and control packet per reply."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import struct
import threading
import numpy as np


def encode_frame(rgb, controls, frame_id):
    height, width, channels = rgb.shape
    if channels != 3 or rgb.dtype != np.uint8:
        raise ValueError('Expected H x W x 3 uint8 RGB')
    header = json.dumps({'version': 1, 'width': width, 'height': height,
                         'frame_id': int(frame_id), 'controls': controls}, allow_nan=False).encode()
    return struct.pack('!I', len(header)) + header + np.ascontiguousarray(rgb).tobytes()


class FrameBridge:
    def __init__(self, port=8765):
        self.packet = None
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != '/frame':
                    self.send_error(404)
                    return
                packet = bridge.packet
                if packet is None:
                    self.send_error(503, 'Waiting for a camera frame')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(len(packet)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                try:
                    self.wfile.write(packet)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def publish(self, rgb, controls, frame_id):
        self.packet = encode_frame(rgb, controls, frame_id)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
