import importlib.util
from pathlib import Path
import unittest
import urllib.request
import numpy as np
from chroma_portal.core import PortalState, anchors_from_hands, valid_quad
from chroma_portal.render import composite, portal_mask
from chroma_portal.bridge import FrameBridge, encode_frame

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('td_bridge', ROOT / 'touchdesigner/bridge_callbacks.py')
td = importlib.util.module_from_spec(spec)
spec.loader.exec_module(td)
QUAD = np.array([[.2, .2], [.8, .2], [.8, .8], [.2, .8]])


class PortalTests(unittest.TestCase):
    def test_crossing_and_degenerate_shapes_are_hidden(self):
        self.assertTrue(valid_quad(QUAD))
        self.assertTrue(valid_quad(QUAD[::-1]))
        for p in [QUAD[[0, 2, 1, 3]], np.zeros((4, 2)), QUAD * np.nan,
                  np.array([[.2, .2], [.8, .2], [.3, .3], [.2, .8]]), QUAD + 1]:
            self.assertFalse(valid_quad(p))
            self.assertEqual(float(portal_mask((80, 100), p).sum()), 0)

    def test_detector_order_does_not_swap_anchors(self):
        left = np.tile([.2, .5], (21, 1))
        right = np.tile([.8, .5], (21, 1))
        left[8], left[4], right[8], right[4] = QUAD[0], QUAD[3], QUAD[1], QUAD[2]
        np.testing.assert_array_equal(anchors_from_hands([left, right]), QUAD)
        np.testing.assert_array_equal(anchors_from_hands([right, left]), QUAD)
        self.assertIsNone(anchors_from_hands([left]))

    def test_tracking_loss_fades_and_reacquisition_is_valid(self):
        state = PortalState()
        for t in np.linspace(0, 1, 31):
            state.update(QUAD, t)
        self.assertGreater(state.opacity, .99)
        state.update(None, 1.2)
        self.assertTrue(0 < state.opacity < .99)
        state.update(None, 3)
        self.assertEqual(state.opacity, 0)
        shifted = QUAD + np.array([.05, 0])
        state.update(shifted, 3.1)
        np.testing.assert_allclose(state.points, shifted)

    def test_smoothing_is_time_based(self):
        outcomes = []
        for rate in [30, 60]:
            s = PortalState()
            s.update(QUAD, 0)
            for t in np.linspace(0, .2, int(rate * .2) + 1)[1:]:
                s.update(QUAD + [.1, 0], t)
            outcomes.append(s.points)
        np.testing.assert_allclose(outcomes[0], outcomes[1], atol=1e-7)

    def test_background_is_exact_and_effect_changes_inside(self):
        rgb = np.full((80, 100, 3), [120, 80, 60], dtype=np.uint8)
        state = PortalState(points=QUAD.copy(), opacity=1)
        output = composite(rgb, state, 2)
        mask = portal_mask(rgb.shape, QUAD)
        np.testing.assert_array_equal(output[mask == 0], rgb[mask == 0])
        self.assertFalse(np.array_equal(output[40, 50], rgb[40, 50]))
        state.opacity = 0
        np.testing.assert_array_equal(composite(rgb, state, 2), rgb)

    def test_uniform_coordinates_and_bridge_roundtrip(self):
        s = PortalState(points=QUAD.copy(), opacity=1)
        controls = s.controls(3)
        np.testing.assert_allclose(controls['uCorners01'], [.2, .8, .8, .8])
        rgb = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
        packet = encode_frame(rgb, controls, 12)
        got, uniforms, frame_id = td.decode_frame(packet)
        np.testing.assert_array_equal(got, rgb)
        self.assertEqual(frame_id, 12)
        self.assertEqual(uniforms, controls)
        with self.assertRaises(ValueError):
            td.decode_frame(packet[:-1])

    def test_loopback_http_transport(self):
        bridge = FrameBridge(port=0)
        try:
            rgb = np.zeros((8, 10, 3), np.uint8)
            bridge.publish(rgb, PortalState().controls(0), 42)
            url = f'http://127.0.0.1:{bridge.server.server_port}/frame'
            with urllib.request.urlopen(url, timeout=2) as response:
                pixels, _, frame_id = td.decode_frame(response.read())
            self.assertEqual(frame_id, 42)
            np.testing.assert_array_equal(pixels, rgb)
        finally:
            bridge.close()


if __name__ == '__main__':
    unittest.main()
