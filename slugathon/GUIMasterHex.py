__copyright__ = "Copyright (c) 2003-2008 David Ripton"
__license__ = "GNU GPL v2"


import os
import math

import gtk

import guiutils
import colors

SQRT3 = math.sqrt(3.0)
RAD_TO_DEG = 180. / math.pi

# Where to place the label, by hexside.  Derived experimentally.
x_font_position = [0.5, 0.75, 0.75, 0.5, 0.25, 0.25]
y_font_position = [0.1, 0.125, 0.875, 0.95, 0.875, 0.125]

rp = guiutils.roundpoint

class GUIMasterHex(object):
    def __init__(self, masterhex, guiboard):
        self.masterhex = masterhex
        self.guiboard = guiboard
        scale = self.guiboard.scale
        self.cx = masterhex.x * 4 * scale
        self.cy = masterhex.y * 4 * SQRT3 * scale
        if not masterhex.inverted:
            self.cy += SQRT3 * scale
        self.fillcolor = guiutils.rgb_to_gtk(colors.rgb_colors[
                colors.terrain_colors[self.masterhex.terrain]])
        self.center = (self.cx + 3 * scale, self.cy + 1.5 * SQRT3 * scale)
        self.selected = False

        self.init_vertexes()
        self.init_gates()
        iv = guiutils.scale_polygon(self.vertexes, 0.7)
        self.inner_vertexes = []
        for point in iv:
            self.inner_vertexes.append(rp(point))
        self.init_overlay()


    def init_vertexes(self):
        """Setup the hex vertexes.

        Each vertex is the midpoint between the vertexes of the two
        bordering hexes.
        """
        self.vertexes = []
        for unused in xrange(6):
            self.vertexes.append(None)
        cx = self.cx
        cy = self.cy
        scale = self.guiboard.scale
        if self.masterhex.inverted:
            self.vertexes[0] = (cx + scale, cy)
            self.vertexes[1] = (cx + 5 * scale, cy)
            self.vertexes[2] = rp((cx + 6 * scale, cy + SQRT3 * scale))
            self.vertexes[3] = rp((cx + 4 * scale, cy + 3 * SQRT3 * scale))
            self.vertexes[4] = rp((cx + 2 * scale, cy + 3 * SQRT3 * scale))
            self.vertexes[5] = rp((cx, cy + SQRT3 * scale))
        else:
            self.vertexes[0] = (cx + 2 * scale, cy)
            self.vertexes[1] = (cx + 4 * scale, cy)
            self.vertexes[2] = rp((cx + 6 * scale, cy + 2 * SQRT3 * scale))
            self.vertexes[3] = rp((cx + 5 * scale, cy + 3 * SQRT3 * scale))
            self.vertexes[4] = rp((cx + scale, cy + 3 * SQRT3 * scale))
            self.vertexes[5] = rp((cx, cy + 2 * SQRT3 * scale))


    def draw_hexagon(self, gc):
        """Create the polygon, filled with the terrain color."""

        # TODO Fix random black/white edge color on border between selected
        # and unselected hexes.

        colormap = self.guiboard.area.get_colormap()

        if self.selected:
            # outer portion
            fg = colormap.alloc_color("white")
            gc.foreground = fg
            self.guiboard.area.window.draw_polygon(gc, True, self.points)

            # inner hex
            fg = colormap.alloc_color(*self.fillcolor)
            gc.foreground = fg
            self.guiboard.area.window.draw_polygon(gc, True,
                self.inner_vertexes)

            # outline
            fg = colormap.alloc_color("black")
            gc.foreground = fg
            self.guiboard.area.window.draw_polygon(gc, False, self.points)

        else:
            # hex
            fg = colormap.alloc_color(*self.fillcolor)
            gc.foreground = fg
            self.guiboard.area.window.draw_polygon(gc, True, self.points)

            # outline
            fg = colormap.alloc_color("white")
            gc.foreground = fg
            self.guiboard.area.window.draw_polygon(gc, False, self.points)


    def init_gates(self):
        """Setup the entrance and exit gates.

        There are up to 3 gates to draw on a hexside.  Each is 1/6
        of a hexside square.  The first is positioned from 1/6 to 1/3
        of the way along the hexside, the second from 5/12 to 7/12, and
        the third from 2/3 to 5/6.  The inner edge of each is on the
        hexside, and the outer edge is 1/12 of a hexside outside.

        Since exits extend into adjacent hexes, they can be overdrawn,
        so we need to draw both exits and entrances for both hexes.
        """
        hex1 = self.masterhex
        vertexes = self.vertexes
        ap = []
        for i in xrange(6):
            gp = [vertexes[i]]
            n = (i + 1) % 6
            if hex1.exits[i] != None:
                li = self.init_gate(vertexes[i][0], vertexes[i][1],
                          vertexes[n][0], vertexes[n][1], hex1.exits[i])
                gp.extend(li)
            if hex1.entrances[i] != None:
                li = self.init_gate(vertexes[n][0], vertexes[n][1],
                          vertexes[i][0], vertexes[i][1], hex1.entrances[i])
                li.reverse()
                gp.extend(li)
            ap.extend(gp)
        self.points = [rp(point) for point in ap]

    def init_gate(self, vx1, vy1, vx2, vy2, gate_type):
        """Setup gate on one entrance / exit hexside."""
        x0 = vx1 + (vx2 - vx1) / 6.
        y0 = vy1 + (vy2 - vy1) / 6.
        x1 = vx1 + (vx2 - vx1) / 3.
        y1 = vy1 + (vy2 - vy1) / 3.
        theta = math.atan2(vy2 - vy1, vx2 - vx1)
        unit = self.guiboard.scale / 1.75

        if gate_type == "BLOCK":
            return _init_block(x0, y0, x1, y1, theta, unit)
        elif gate_type == "ARCH":
            return _init_arch(x0, y0, x1, y1, theta, unit)
        elif gate_type == "ARROW":
            return _init_arrow(x0, y0, x1, y1, theta, unit)
        elif gate_type == "ARROWS":
            return _init_arrows(vx1, vy1, vx2, vy2, theta, unit)
        return None


    def init_overlay(self):
        """Setup the overlay with terrain name and image."""
        scale = self.guiboard.scale
        self.bboxsize = (6 * scale, int(3 * SQRT3 * scale))

        myboxsize = [0.85 * mag for mag in self.bboxsize]
        self.dest_x = int(round(self.center[0] - myboxsize[0] / 2.))
        self.dest_y = int(round(self.center[1] - myboxsize[1] / 2.))

        image_filename = os.path.join("../images/masterhex",
          self.masterhex.overlay_filename)
        pixbuf = gtk.gdk.pixbuf_new_from_file(image_filename)
        self.pixbuf = pixbuf.scale_simple(int(round(myboxsize[0])),
            int(round(myboxsize[1])), gtk.gdk.INTERP_BILINEAR)


    def draw_overlay(self, gc):
        drawable = self.guiboard.area.window
        drawable.draw_pixbuf(gc, self.pixbuf, 0, 0, self.dest_x, self.dest_y,
          -1, -1, gtk.gdk.RGB_DITHER_NORMAL, 0, 0)


    def draw_label(self, gc):
        """Display the hex label."""
        label = str(self.masterhex.label)
        layout = self.guiboard.area.create_pango_layout(label)
        text_width, text_height = layout.get_pixel_size()
        half_text_width = 0.5 * text_width
        half_text_height = 0.5 * text_height
        side = self.masterhex.label_side

        x = int(round((self.cx + self.bboxsize[0] * x_font_position[side] -
                half_text_width)))
        y = int(round((self.cy + self.bboxsize[1] * y_font_position[side] -
                half_text_height)))

        colormap = self.guiboard.area.get_colormap()
        fg = colormap.alloc_color("black")
        gc.foreground = fg

        self.guiboard.area.window.draw_layout(gc, x, y, layout)


    def update_gui(self, gc):
        self.draw_hexagon(gc)
        self.draw_overlay(gc)
        self.draw_label(gc)

    def toggle_selection(self):
        self.selected = not self.selected


def _init_block(x0, y0, x1, y1, theta, unit):
    """Return a list of points to make a block."""
    xy = []
    xy.append((x0, y0))
    xy.append((x0 + unit * math.sin(theta), (y0 - unit * math.cos(theta))))
    xy.append((x1 + unit * math.sin(theta), (y1 - unit * math.cos(theta))))
    xy.append((x1, y1))
    return xy


def _init_arch(x0, y0, x1, y1, theta, unit):
    """Return a list of points to make an approximate arch."""
    xy = []
    half = unit / 2.0
    p0 = ((x0 + half * math.sin(theta), y0 - half * math.cos(theta)))
    p1 = ((x1 + half * math.sin(theta), y1 - half * math.cos(theta)))

    xy = []

    xy.append((x0, y0))
    xy.append(p0)

    arcpoints = guiutils.get_semicircle_points(p0[0], p0[1], p1[0], p1[1], 10)
    xy.extend(arcpoints)

    xy.append(p1)
    xy.append((x1, y1))

    return xy

def _init_arrow(x0, y0, x1, y1, theta, unit):
    """Return a list of points to make a single arrow."""
    xy = []
    xy.append((x0, y0))
    xy.append(((x0 + x1) / 2. + unit * math.sin(theta),
               (y0 + y1) / 2. - unit * math.cos(theta)))
    xy.append((x1, y1))
    return xy


def _init_arrows(vx1, vy1, vx2, vy2, theta, unit):
    """Return a list of points to make three arrows."""
    xy = []
    for i in range(3):
        x0 = vx1 + (vx2 - vx1) * (2 + 3 * i) / 12.
        y0 = vy1 + (vy2 - vy1) * (2 + 3 * i) / 12.
        x1 = vx1 + (vx2 - vx1) * (4 + 3 * i) / 12.
        y1 = vy1 + (vy2 - vy1) * (4 + 3 * i) / 12.
        xy.extend(_init_arrow(x0, y0, x1, y1, theta, unit))
    return xy
