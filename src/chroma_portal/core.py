"""Geometry and temporal state, independent of camera / inference / TouchDesigner."""
from dataclasses import dataclass, field
import math
import numpy as np


def valid_quad(points, min_area=0.002):
    """Reject crossed, concave, collapsed, nonfinite, or off-image quadrilaterals."""
    p = np.asarray(points, dtype=float)
    if p.shape != (4, 2) or not np.isfinite(p).all():
        return False
    if np.any(p < 0) or np.any(p > 1):
        return False
    edges = np.roll(p, -1, axis=0) - p
    after = np.roll(edges, -1, axis=0)
    crosses = edges[:, 0] * after[:, 1] - edges[:, 1] * after[:, 0]
    if not (np.all(crosses > 1e-6) or np.all(crosses < -1e-6)):
        return False
    area = 0.5 * abs(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - p[:, 1] * np.roll(p[:, 0], -1)))
    return bool(area >= min_area)


def anchors_from_hands(hands):
    """Screen-left index, screen-right index, right thumb, left thumb.

    Screen position avoids reliance on detector list order / handedness labels.
    This v1 deliberately hides shapes when the hands overlap or corners cross.
    Coordinates are normalized with origin at the TOP LEFT of the mirrored frame.
    """
    if len(hands) != 2:
        return None
    pair = [np.asarray(h, dtype=float) for h in hands]
    if any(h.shape != (21, 2) or not np.isfinite(h).all() for h in pair):
        return None
    pair.sort(key=lambda h: float(h[[0, 5, 9, 13, 17], 0].mean()))
    left, right = pair
    if abs(left[[0, 5, 9, 13, 17], 0].mean() - right[[0, 5, 9, 13, 17], 0].mean()) < 0.06:
        return None
    corners = np.array([left[8], right[8], right[4], left[4]])
    return corners if valid_quad(corners) else None


@dataclass
class PortalState:
    points: np.ndarray = field(default_factory=lambda: np.array([[.25, .3], [.75, .3], [.75, .7], [.25, .7]]))
    opacity: float = 0.0
    last_time: float | None = None
    last_seen: float | None = None

    def update(self, target, now):
        if not math.isfinite(now):
            raise ValueError("Time must be finite")
        dt = 1 / 30 if self.last_time is None else max(0.0, now - self.last_time)
        self.last_time = now
        visible = target is not None and valid_quad(target)
        if visible:
            target = np.asarray(target, dtype=float)
            if self.last_seen is None or now - self.last_seen > .5:
                self.points = target.copy()
            else:
                smoothed = self.points + (target - self.points) * (-math.expm1(-dt / .07))
                self.points = smoothed if valid_quad(smoothed) else target.copy()
            self.last_seen = now
        tau = .10 if visible else .18
        self.opacity += (float(visible) - self.opacity) * (-math.expm1(-dt / tau))
        if self.opacity < .002:
            self.opacity = 0.0
        return self

    def controls(self, seconds):
        """Four vec4 uniforms; y is converted exactly once into bottom-up UVs."""
        p = self.points.copy()
        p[:, 1] = 1 - p[:, 1]
        delta = self.points[1] - self.points[0]
        tilt = math.atan2(float(delta[1]), float(delta[0])) / (2 * math.pi)
        return {
            "uCorners01": p[:2].reshape(-1).tolist(),
            "uCorners23": p[2:].reshape(-1).tolist(),
            "uLook": [float(seconds), tilt, 8.0, 1.3],
            "uControl": [float(self.opacity), 3.0, 1.0, 1.5],
        }
