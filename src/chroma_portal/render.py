"""CPU reference effect. The GLSL version uses the same palette idea."""
import cv2
import numpy as np
from .core import valid_quad


def portal_mask(shape, points, feather_px=3.0):
    height, width = shape[:2]
    mask = np.zeros((height, width), np.uint8)
    if not valid_quad(points):
        return mask.astype(np.float32)
    xy = np.rint(np.asarray(points) * [width - 1, height - 1]).astype(np.int32)
    cv2.fillPoly(mask, [xy], 255)
    if feather_px <= 0:
        return mask.astype(np.float32) / 255
    # Feather inward only: pixels outside the polygon stay untouched.
    distance = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
    t = np.clip(distance / feather_px, 0, 1)
    return t * t * (3 - 2 * t)


def psychedelic_rgb(rgb, seconds=0, shift=0, bands=8, edge_gain=1.3):
    rgbf = rgb.astype(np.float32) / 255
    luma = rgbf @ np.array([.2126, .7152, .0722], np.float32)
    bands = max(2, int(bands))
    level = np.minimum(np.floor(luma * bands), bands - 1) / (bands - 1)
    phase = level * 1.6 + seconds * .08 + shift
    color = .5 + .5 * np.cos(2 * np.pi * (phase[..., None] + np.array([0, .33, .67])))
    gx = cv2.Sobel(luma, cv2.CV_32F, 1, 0, ksize=3) / 8
    gy = cv2.Sobel(luma, cv2.CV_32F, 0, 1, ksize=3) / 8
    edge = np.clip(np.hypot(gx, gy) * edge_gain * 4, 0, 1)
    color = color * (1 - .6 * edge[..., None]) + edge[..., None] * np.array([.1, .3, .2])
    return np.clip(color, 0, 1).astype(np.float32)


def composite(rgb, state, seconds):
    controls = state.controls(seconds)
    mask = portal_mask(rgb.shape, state.points) * state.opacity
    fx = psychedelic_rgb(rgb, seconds, controls['uLook'][1])
    out = rgb.astype(np.float32) * (1 - mask[..., None]) + fx * 255 * mask[..., None]
    return np.clip(np.rint(out), 0, 255).astype(np.uint8)
