# Validation — starter 0.1.0

Checked on 2026-11-09 in Linux with Python 3.12.14.

| Check | Result |
| --- | --- |
| Package installation and CLI help | Passed |
| Geometry and detector-order cases | Passed |
| Time-based smoothing and loss/reacquisition | Passed |
| CPU mask keeps exterior pixels unchanged | Passed |
| RGB/uniform packet encode/decode and actual localhost HTTP roundtrip | Passed |
| GLSL compilation and rendering with a headless OpenGL 4.5 EGL context | Passed |
| Shader zero-opacity and crossed-polygon cases | Passed |
| Synthetic PNG render | Passed and visually inspected |
| Official model download | Passed; not committed |
| MediaPipe native inference smoke test | Blocked in this Linux runtime: missing `libGLESv2.so.2`; Python API import passed |
| Live hand tracking on webcam | Not tested: no physical camera in this environment |
| Native TouchDesigner network / receiver thread lifecycle | Not tested: TouchDesigner unavailable here |

The unittest command reported **8 passing tests**, with no skipped shader test in this environment. The GLSL test supplies TD-compatible sampler/UV/output stubs in OpenGL; it does not validate TouchDesigner's Vulkan compiler, parameter UI, or native cooking behavior.

The CPU preview and GPU shader share the palette/mask concept but are not pixel-identical: their gradient filters and boundary rendering differ. No FPS, latency, or tracking-accuracy claim is made.

The development runtime could not install the missing native GLES library. On a Linux machine, install the distribution's OpenGL ES runtime before using MediaPipe if this error appears. Windows/macOS use their platform wheels; those platforms have not been tested here.

Installed versions during these checks:

- NumPy 2.5.4
- OpenCV contrib 5.0.0.93 (`cv2` reports 5.0.0)
- MediaPipe 1.2.2
- python-osc 1.10.2
- ModernGL 5.13.0 (optional shader test)

Google Hand Landmarker model (float16, version 1) downloaded SHA-256:

`fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`

## First machine test

1. Run the standalone preview and verify index/thumb tips on both hands.
2. Move only one hand, reverse detector ordering, tilt the window, and briefly remove a hand.
3. Check that the image stays aligned across the polygon boundary.
4. Follow the TouchDesigner setup; confirm all four uniforms update with the same frame.
5. Stop the sender and verify the effect fades. Restart it and check recovery.
6. Call the receiver's `stop()` before editing or deleting its callbacks DAT.
7. Record operating system, Python version, TD build, webcam resolution, and measured timings before a release.
