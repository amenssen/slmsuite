import pyglet
import pyglet.gl as gl
import os
import ctypes
import numpy as np
import threading


class Window:
    def __init___():
        self.shape = None

    def _create_window(self, screen=None):
        # Setup the window. If failure, closes elegantly upon except().
        try:
            # Make the window and do basic setup.
            if screen is None:  # Not fullscreen
                display = pyglet.canvas.get_display()

                self.window = pyglet.window.Window(
                    screen=display.get_default_screen(),
                    width=self.shape[1],
                    height=self.shape[0],
                    resizable=True,
                    fullscreen=False,
                    vsync=True
                )
            else:               # Fullscreen
                self.window = pyglet.window.Window(
                    screen=screen,
                    fullscreen=True,
                    vsync=True
                )
                self.window.set_mouse_visible(False)

            # Window dressing
            self.window.set_caption(self.name)

            try:
                # Icons. Currently hardcoded. Feel free to implement custom icons.
                path, _ = os.path.split(os.path.realpath(__file__))
                path = os.path.join(path, '..', '..',
                                    'docs', 'source', 'static', 'qp-slm-notext-')
                img16x16 = pyglet.image.load(path + '16x16.png')
                img32x32 = pyglet.image.load(path + '32x32.png')
                img32x32 = pyglet.image.load(path + '128x128.png')
                self.window.set_icon(img16x16, img32x32)
            except Exception as e:
                print(e)

            # Set the viewpoint.
            proj = pyglet.window.Projection2D()
            proj.set(self.shape[1], self.shape[0], self.shape[1], self.shape[0])

            # Setup shapes
            texture_shape = tuple(np.power(2, np.ceil(np.log2(self.shape)))
                                .astype(np.int64))
            self.tex_shape_ratio = (float(self.shape[0])/float(texture_shape[0]),
                                    float(self.shape[1])/float(texture_shape[1]))
            B = 4

            # Setup buffers (texbuffer is power of 2 padded to init the memory in OpenGL)
            self.buffer = np.zeros(self.shape + (B,), dtype=np.uint8)
            N = int(self.shape[0] * self.shape[1] * B)
            self.cbuffer = (gl.GLubyte * N).from_buffer(self.buffer)

            texbuffer = np.zeros(texture_shape + (B,), dtype=np.uint8)
            Nt = int(texture_shape[0] * texture_shape[1] * B)
            texcbuffer = (gl.GLubyte * Nt).from_buffer(texbuffer)

            # Setup the texture
            gl.glEnable(gl.GL_TEXTURE_2D)
            self.texture = gl.GLuint()
            gl.glGenTextures(1, ctypes.byref(self.texture))
            gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.value)

            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_GENERATE_MIPMAP, gl.GL_FALSE)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_NEAREST)

            # Malloc the OpenGL memory
            gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8,
                            texture_shape[1], texture_shape[0],
                            0, gl.GL_BGRA, gl.GL_UNSIGNED_BYTE,
                            texcbuffer)

            # Make sure we can write to a subset of the memory (as we will do in the future)
            gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0,
                            self.shape[1], self.shape[0],
                            gl.GL_BGRA, gl.GL_UNSIGNED_BYTE,
                            self.cbuffer)

            # Cleanup
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
            gl.glFlush()
        except:
            try:
                self.window.close()
            except:
                pass
            raise

    def _flip(self):
        # Setup texture variables.
        x1 = 0
        y1 = 0
        x2 = self.shape[1]
        y2 = self.shape[0]

        xa = 0
        ya = 0
        xb = self.tex_shape_ratio[1]
        yb = self.tex_shape_ratio[0]

        array = (gl.GLfloat * 32)(
            xa, ya, 0., 1.,         # tex coord,
            x1, y1, 0., 1.,         # real coord, ...
            xb, ya, 0., 1.,
            x2, y1, 0., 1.,
            xb, yb, 0., 1.,
            x2, y2, 0., 1.,
            xa, yb, 0., 1.,
            x1, y2, 0., 1.)

        # Update the texture.
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.texture.value)
        gl.glTexSubImage2D(gl.GL_TEXTURE_2D, 0, 0, 0,
                        self.shape[1], self.shape[0],
                        gl.GL_RGBA, gl.GL_UNSIGNED_BYTE,
                        self.cbuffer)

        # Blit the texture.
        gl.glPushClientAttrib(gl.GL_CLIENT_VERTEX_ARRAY_BIT)
        gl.glInterleavedArrays(gl.GL_T4F_V4F, 0, array)
        gl.glDrawArrays(gl.GL_QUADS, 0, 4)
        gl.glPopClientAttrib()

        # Display the other side of the double buffer.
        # (with vsync enabled, this will block until the next frame is ready to display).
        self.window.flip()

    def close(self):
        """Closes frame. See :class:`.SLM`."""
        self.window.close()

    @staticmethod
    def info(verbose=True):
        """
        Get information about the available displays, their indexes, and their sizes.

        Parameters
        ----------
        verbose : bool
            Whether or not to print display information.

        Returns
        -------
        list of (int, (int, int, int, int)) tuples
            The number and geometry of each display.
        """
        # Note: in pyglet, the display is the full arrangement of screens,
        # unlike the terminology in other SLM subclasses
        display = pyglet.canvas.get_display()

        screens = display.get_screens()
        default = display.get_default_screen()
        windows = display.get_windows()

        def parse_screen(screen):
            return ("x={}, y={}, width={}, height={}"
                .format(screen.x, screen.y, screen.width, screen.height))
        def parse_screen_int(screen):
            return (screen.x, screen.y, screen.width, screen.height)
        def parse_window(window):
            x, y = window.get_location()
            return ("x={}, y={}, width={}, height={}"
                .format(x, y, window.width, window.height))

        default_str = parse_screen(default)

        window_strs = []
        for window in windows:
            window_strs.append(parse_window(window))

        if verbose:
            print('Display Positions:')
            print('#,  Position')

        screen_list = []

        for x, screen in enumerate(screens):
            screen_str = parse_screen(screen)

            main_bool = False
            window_bool = False

            if screen_str == default_str:
                main_bool = True
                screen_str += ' (main)'
            if screen_str in window_strs:
                window_bool = True
                screen_str += ' (has ScreenMirrored)'

            if verbose:
                print('{},  {}'.format(x, screen_str))

            screen_list.append((x, parse_screen_int(screen),
                                main_bool, window_bool))

        return screen_list
