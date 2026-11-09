// TouchDesigner GLSL TOP pixel shader. Camera / bridge RGB TOP is input 0.
// TD injects its sampler declarations, vUV and TDOutputSwizzle; omit #version.
uniform vec4 uCorners01;
uniform vec4 uCorners23;
uniform vec4 uLook;     // seconds, palette shift, bands, edge gain
uniform vec4 uControl;  // tracking opacity, feather px, effect mix, outline px
layout(location = 0) out vec4 fragColor;

float cross2(vec2 a, vec2 b) { return a.x * b.y - a.y * b.x; }
float luma(vec3 rgb) { return dot(rgb, vec3(.2126, .7152, .0722)); }
float sampleLuma(vec2 uv) { return luma(texture(sTD2DInputs[0], clamp(uv, 0.0, 1.0)).rgb); }

void main() {
    vec2 uv = vUV.st;
    vec4 camera = texture(sTD2DInputs[0], uv);
    vec2 size = vec2(textureSize(sTD2DInputs[0], 0));
    vec2 px = 1.0 / size;
    vec2 p[4] = vec2[4](uCorners01.xy, uCorners01.zw, uCorners23.xy, uCorners23.zw);
    float orientation = sign(cross2(p[1] - p[0], p[2] - p[1]));
    float distanceInside = 1e6;
    bool valid = orientation != 0.0;
    float twiceArea = 0.0;
    for (int i = 0; i < 4; ++i) {
        vec2 a = p[i] * size;
        vec2 b = p[(i + 1) % 4] * size;
        vec2 edge = b - a;
        float turn = cross2(p[(i + 1) % 4] - p[i], p[(i + 2) % 4] - p[(i + 1) % 4]);
        valid = valid && orientation * turn > 1e-6 && all(greaterThanEqual(p[i], vec2(0))) && all(lessThanEqual(p[i], vec2(1)));
        twiceArea += cross2(p[i], p[(i + 1) % 4]);
        distanceInside = min(distanceInside, orientation * cross2(edge, uv * size - a) / max(length(edge), .001));
    }
    valid = valid && abs(twiceArea) >= .004;
    float mask = valid ? smoothstep(0.0, max(uControl.y, .001), distanceInside) : 0.0;
    float amount = mask * clamp(uControl.x, 0.0, 1.0) * clamp(uControl.z, 0.0, 1.0);
    float bands = max(2.0, floor(uLook.z));
    float value = min(floor(luma(camera.rgb) * bands), bands - 1.0) / (bands - 1.0);
    float phase = value * 1.6 + uLook.x * .08 + uLook.y;
    vec3 color = .5 + .5 * cos(6.2831853 * (phase + vec3(0, .33, .67)));
    float gx = sampleLuma(uv + vec2(px.x, 0)) - sampleLuma(uv - vec2(px.x, 0));
    float gy = sampleLuma(uv + vec2(0, px.y)) - sampleLuma(uv - vec2(0, px.y));
    float edge = clamp(length(vec2(gx, gy)) * uLook.w * 2.0, 0.0, 1.0);
    color = clamp(color * (1.0 - .6 * edge) + edge * vec3(.1, .3, .2), 0.0, 1.0);
    float outline = uControl.w > 0.0 ? 1.0 - smoothstep(uControl.w, uControl.w + 1.0, distanceInside) : 0.0;
    color = mix(color, vec3(.4, 1.0, .65), outline * .6);
    fragColor = TDOutputSwizzle(vec4(mix(camera.rgb, color, amount), camera.a));
}
