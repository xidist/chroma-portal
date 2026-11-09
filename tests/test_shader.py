"""Actual offscreen GLSL compilation/rendering; TD host is stubbed explicitly."""
from pathlib import Path
import unittest
import numpy as np
from chroma_portal.core import PortalState


class ShaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import moderngl
            cls.ctx = moderngl.create_standalone_context(backend='egl')
        except Exception as exc:
            raise unittest.SkipTest(f'Optional EGL shader check unavailable: {exc}')

    @classmethod
    def tearDownClass(cls):
        cls.ctx.release()

    def test_shader_preserves_outside_and_hides_invalid_shapes(self):
        ctx = self.ctx
        source = (Path(__file__).resolve().parents[1] / 'touchdesigner/chroma_portal.frag').read_text()
        vertex = '''#version 330
        in vec2 pos; out vec3 vUV;
        void main() { vUV=vec3(pos*.5+.5,0); gl_Position=vec4(pos,0,1); }
        '''
        fragment = '''#version 330
        uniform sampler2D sTD2DInputs[1]; in vec3 vUV;
        vec4 TDOutputSwizzle(vec4 c) { return c; }
        ''' + source
        program = ctx.program(vertex_shader=vertex, fragment_shader=fragment)
        buffer = ctx.buffer(np.array([-1,-1, 1,-1, -1,1, 1,1], np.float32).tobytes())
        vao = ctx.simple_vertex_array(program, buffer, 'pos')
        rgb = np.full((64, 96, 3), [120, 80, 60], np.uint8)
        texture = ctx.texture((96, 64), 3, rgb.tobytes())
        texture.use(0)
        program['sTD2DInputs'].value = 0
        output = ctx.simple_framebuffer((96, 64), components=3)
        output.use()
        controls = PortalState(opacity=1).controls(2.5)
        for name, values in controls.items():
            program[name].value = tuple(values)

        def render():
            vao.render(mode=5)
            return np.frombuffer(output.read(components=3, alignment=1), np.uint8).reshape(64, 96, 3)

        active = render()
        np.testing.assert_array_equal(active[0], rgb[0])
        self.assertFalse(np.array_equal(active[32, 48], rgb[32, 48]))
        program['uControl'].value = (0, 3, 1, 1.5)
        np.testing.assert_array_equal(render(), rgb)
        program['uControl'].value = (1, 3, 1, 1.5)
        program['uCorners01'].value = (.25, .7, .75, .3)
        program['uCorners23'].value = (.75, .7, .25, .3)
        np.testing.assert_array_equal(render(), rgb)
        for resource in (vao, buffer, program, texture, output):
            resource.release()
