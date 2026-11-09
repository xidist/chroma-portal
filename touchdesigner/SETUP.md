# TouchDesigner setup

This is a source-level starter, not a tested `.tox` yet. Use a current TouchDesigner build that supports GLSL TOP and Script TOP. Python/MediaPipe runs in the separate environment from the README; you do **not** need to install MediaPipe inside TouchDesigner.

## 1. Start the camera bridge

From the repository root, with the environment active:

```sh
chroma-portal --bridge --no-preview
```

This owns the webcam and serves matching RGB frames and tracking uniforms at `http://127.0.0.1:8765/frame`. It is a small binary protocol, **not an MJPEG stream**. Use the supplied receiver rather than Movie File In or Video Stream In. Keep the default 640 × 480 for initial testing.

## 2. Receive the camera in a Script TOP

1. Create a Script TOP named **`portal_frame`** in `/project1`.
2. Open its callbacks DAT; name that DAT **`portal_bridge_callbacks`**. Replace its text with `bridge_callbacks.py` from this directory.
3. Ensure the Script TOP's **Callbacks DAT** points to that DAT. View the Script TOP and keep the timeline playing. It starts a background receiver when cooked. Its callback uses only Python stdlib plus the NumPy supplied with TouchDesigner.
4. The raw camera should appear. Hand detection runs in the separate Python process. A black image means no bridge frame has arrived yet.

The background thread does HTTP and decoding only. All TouchDesigner API calls happen in `onCook` on TD's main thread. The receiver flips the image vertically for TD; the Python controls already use bottom-left UV coordinates. Do not add another flip or mirror downstream.

## 3. Add the shader

1. Create a Text DAT named `portal_pixel` and paste `chroma_portal.frag` into it.
2. Create a GLSL TOP named `portal_shader`. Connect `portal_frame` as **input 0**.
3. Set its **Pixel Shader** DAT to `portal_pixel`. Leave the default vertex shader. Match the input resolution and use the GLSL version supported by your TD build; do not prepend `#version` to the supplied DAT text.
4. On the GLSL TOP's **Vectors** page, add four named vec4 uniforms as below. For each row, set x/y/z/w to Python expressions using indices **0/1/2/3** respectively.

| Uniform | Expression pattern for x/y/z/w | Contents |
| --- | --- | --- |
| `uCorners01` | `op('portal_bridge_callbacks').module.uniform('uCorners01', i)` | First two anchors: x0, y0, x1, y1 |
| `uCorners23` | `op('portal_bridge_callbacks').module.uniform('uCorners23', i)` | Last two anchors: x2, y2, x3, y3 |
| `uLook` | `op('portal_bridge_callbacks').module.uniform('uLook', i)` | Time, tilt/palette shift, bands, edge gain |
| `uControl` | `op('portal_bridge_callbacks').module.uniform('uControl', i)` | Tracking opacity, feather pixels, mix, outline pixels |

`i` is explanatory: replace it with `0`, `1`, `2`, or `3`. For example, the x expression of `uControl` is:

```python
op('portal_bridge_callbacks').module.uniform('uControl', 0)
```

These paths assume the TOPs and DATs are siblings. Adjust the helper's `op('portal_frame')` lookup and parameter paths if you move them into different components. Enable parameter **Expression** mode rather than pasting expressions as constant strings.

5. View `portal_shader`. Hold both hands in view with thumb/index tips separated. The raw camera remains outside the polygon. To record later, connect a Movie File Out TOP and choose recording settings deliberately.

## Stop and reconnect

- Stop the external process with Ctrl+C. The last raw image remains; the effect fades after stale frames. This is not a live camera once the sender stops.
- Before editing/reloading the callbacks DAT or deleting the component, stop its worker from the Textport:

```python
op('/project1/portal_bridge_callbacks').module.stop()
```

- The next cook starts it again. To stop it permanently, disable cooking or remove the component after calling `stop()`.
- If you change `--bridge-port`, change the `URL` constant in the callbacks DAT to match, after stopping the worker.
- The bridge sends uncompressed RGB for simple, dependency-free receiving. It is a prototype transport with CPU copies; high-resolution performance is unmeasured.

## Optional OSC output

Use `--osc` to send control vec4s in one OSC bundle to localhost UDP 8000. The addresses are `/portal/uCorners01`, `/portal/uCorners23`, `/portal/uLook`, and `/portal/uControl`. An OSC In CHOP can receive these for other parameter mappings. OSC sends **controls only**, not video. Use the frame bridge for the documented shader setup.

If you wire OSC directly, add a freshness timeout based on the changing time value; an abrupt process kill cannot send a final zero-opacity packet. The frame receiver already includes a timeout.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Camera cannot open | Close other apps using the physical webcam; try `--camera 1`. |
| Black Script TOP | Start the external process, match the bridge port, and ensure the TOP is cooking. |
| Raw image but no effect | Ensure both hands are detected and four uniform rows are configured in expression mode. |
| Corners don't line up | Remove downstream crop/mirror transforms; the bridge image and controls are already matched. |
| Polygon vanishes when twisting | V1 deliberately fades non-convex/crossed/too-small shapes. Separate the tips and hands again. |
| Shader fails compilation | Inspect the GLSL TOP info, use the current TD GLSL mode and default vertex shader, and confirm input 0 is connected. |
| Receiver thread remains after edits | Call the callbacks module's `stop()` before replacing its code. |
