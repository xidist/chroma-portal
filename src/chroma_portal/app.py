"""Webcam entry point. No camera frames are saved or sent to an internet service."""
import argparse
from pathlib import Path
import time
import cv2
import numpy as np
from .core import PortalState, anchors_from_hands
from .render import composite


def synthetic_frame(width=640, height=360):
    y, x = np.mgrid[0:height, 0:width]
    frame = np.stack((x / width * 255, y / height * 255,
                      (np.sin(x / 35) * .5 + .5) * 255), axis=-1).astype(np.uint8)
    cv2.circle(frame, (width // 2, height // 2), height // 4, (180, 180, 180), -1)
    cv2.putText(frame, 'CHROMA PORTAL', (24, 46), cv2.FONT_HERSHEY_SIMPLEX,
                .8, (235, 235, 235), 2, cv2.LINE_AA)
    return frame


def demo(path):
    state = PortalState()
    state.update(np.array([[.2, .25], [.82, .18], [.75, .8], [.28, .72]]), 0)
    state.opacity = 1
    out = composite(synthetic_frame(), state, 2.5)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), cv2.cvtColor(out, cv2.COLOR_RGB2BGR)):
        raise RuntimeError(f'Could not save {path}')
    print(f'Synthetic render saved to {path}; this is not a webcam recording.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--model', default='models/hand_landmarker.task')
    parser.add_argument('--width', type=int, default=640)
    parser.add_argument('--height', type=int, default=480)
    parser.add_argument('--no-mirror', action='store_true')
    parser.add_argument('--no-preview', action='store_true')
    parser.add_argument('--bridge', action='store_true', help='Send matching RGB/controls to TouchDesigner on localhost')
    parser.add_argument('--bridge-port', type=int, default=8765)
    parser.add_argument('--osc', action='store_true', help='Also send controls to localhost UDP 8000')
    parser.add_argument('--osc-port', type=int, default=8000)
    parser.add_argument('--demo', metavar='PNG', help='Render a synthetic example without camera or model')
    args = parser.parse_args()
    if args.demo:
        demo(args.demo)
        return
    if args.width < 16 or args.height < 16:
        parser.error('Camera dimensions must be at least 16 pixels')
    if not Path(args.model).is_file():
        parser.error('Model missing. Run: python tools/download_model.py')

    import mediapipe as mp
    from .bridge import FrameBridge
    from pythonosc.udp_client import SimpleUDPClient
    from pythonosc.osc_bundle_builder import OscBundleBuilder, IMMEDIATELY
    from pythonosc.osc_message_builder import OscMessageBuilder

    def send_controls(client, controls):
        if client is None:
            return
        bundle = OscBundleBuilder(IMMEDIATELY)
        for name, values in controls.items():
            message = OscMessageBuilder(address='/portal/' + name)
            for value in values:
                message.add_arg(float(value))
            bundle.add_content(message.build())
        client.send(bundle.build())

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=args.model),
        running_mode=mp.tasks.vision.RunningMode.VIDEO, num_hands=2,
        min_hand_detection_confidence=.6, min_hand_presence_confidence=.6,
        min_tracking_confidence=.6)
    camera = cv2.VideoCapture(args.camera)
    bridge = None
    client = SimpleUDPClient('127.0.0.1', args.osc_port) if args.osc else None
    try:
        if not camera.isOpened():
            raise RuntimeError('Camera unavailable. Close other camera apps or try --camera 1.')
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
        if args.bridge:
            bridge = FrameBridge(args.bridge_port)
            print(f'TouchDesigner bridge: http://127.0.0.1:{args.bridge_port}/frame')
        state = PortalState()
        start = time.monotonic()
        previous_ms = -1
        frame_id = 0
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as tracker:
            print('Show both hands with thumb/index tips apart. Q or Escape quits; Ctrl+C also quits.')
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError('Camera frame read failed; bridge clients will fade on timeout.')
                if not args.no_mirror:
                    frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                seconds = time.monotonic() - start
                timestamp_ms = max(previous_ms + 1, int(seconds * 1000))
                previous_ms = timestamp_ms
                result = tracker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), timestamp_ms)
                hands = [np.array([[p.x, p.y] for p in h]) for h in result.hand_landmarks]
                target = anchors_from_hands(hands)
                state.update(target, time.monotonic() - start)
                controls = state.controls(seconds)
                send_controls(client, controls)
                if bridge:
                    bridge.publish(rgb, controls, frame_id)
                frame_id += 1
                if not args.no_preview:
                    output = composite(rgb, state, seconds)
                    if target is not None:
                        for x, y in state.points:
                            cv2.circle(output, (int(x * (output.shape[1] - 1)), int(y * (output.shape[0] - 1))), 5, (80, 255, 130), -1)
                    cv2.imshow('Chroma Portal - Q to quit', cv2.cvtColor(output, cv2.COLOR_RGB2BGR))
                    if cv2.waitKey(1) & 0xff in (27, ord('q')):
                        break
    except KeyboardInterrupt:
        pass
    finally:
        # A final transparent OSC state handles graceful exits; receivers should
        # additionally implement their own heartbeat timeout for a killed process.
        send_controls(client, PortalState().controls(0))
        camera.release()
        if bridge:
            bridge.close()
        if not args.no_preview:
            cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
