#! /usr/bin/env python -t
"""
Core BoxMaker functionality - refactored for testability
"""

import math
import os
import sys
from copy import deepcopy
from typing import List, Tuple, Optional, Dict, Any

from boxmaker_constants import (
    BoxType, TabType, LayoutStyle, KeyDividerType,
    DEFAULT_LENGTH, DEFAULT_WIDTH, DEFAULT_HEIGHT, DEFAULT_TAB_WIDTH,
    DEFAULT_THICKNESS, DEFAULT_KERF, DEFAULT_SPACING,
    MIN_DIMENSION, MIN_THICKNESS, MIN_TAB_WIDTH,
    MIN_TAB_TO_THICKNESS_RATIO, RECOMMENDED_MIN_TAB_TO_THICKNESS_RATIO,
    MAX_TAB_TO_THICKNESS_RATIO, RECOMMENDED_MAX_TAB_TO_THICKNESS_RATIO,
    MAX_DIMENSION, MAX_THICKNESS,
    INCHES_TO_MM, HAIRLINE_THICKNESS_INCHES,
    HoleType, HoleSide
)
from boxmaker_exceptions import DimensionError, TabError, MaterialError


class BoxMakerCore:
    """Core logic for generating tabbed box SVG files"""
    
    def __init__(self):
        # Default values using constants
        self.unit = 'mm'
        self.inside = False
        self.length = DEFAULT_LENGTH
        self.width = DEFAULT_WIDTH
        self.height = DEFAULT_HEIGHT
        self.tab = DEFAULT_TAB_WIDTH
        self.equal = 0
        self.tabsymmetry = 0
        self.tabtype = TabType.LASER
        self.dimpleheight = 0.0
        self.dimplelength = 0.0
        self.hairline = 0
        self.thickness = DEFAULT_THICKNESS
        self.kerf = DEFAULT_KERF
        self.style = LayoutStyle.SEPARATED
        self.spacing = DEFAULT_SPACING
        self.boxtype = BoxType.FULL_BOX
        self.div_l = 0
        self.div_w = 0
        self.keydiv = KeyDividerType.NONE
        self.optimize = True
        # Entrance hole (e.g. for a bird nest box). Disabled unless hole_type is set.
        self.hole_type = HoleType.NONE   # 'none' | 'round' | 'rect'
        self.hole_side = HoleSide.BIG    # 'big' | 'small' wall pair
        self.hole_diameter = 32.0        # round hole
        self.hole_width = 65.0           # rect hole, horizontal
        self.hole_height = 28.0          # rect hole, vertical
        self.hole_radius = 0.0           # rect hole corner radius
        self.hole_x = None               # centre, from left edge of plate (None = centred)
        self.hole_y = None               # centre, from bottom edge of plate (None = centred)
        # Pilot holes for screws through the joint tabs (only for thick material)
        self.screw_holes = False
        self.screw_diameter = 2.5             # pilot hole diameter (mm)
        self.screw_min_thickness = 9.0        # no screw holes for material this thin or thinner
        self.screw_middle_min_length = 200.0  # edges longer than this also get a middle screw
        self.messages = []                    # notes for the user (e.g. why holes were skipped)
        # Internal state
        self.linethickness = 1
        self.paths: List[str] = []
        self.circles: List[Tuple[float, Tuple[float, float]]] = []
        
    def set_parameters(self, **kwargs) -> None:
        """Set box parameters from keyword arguments
        
        Args:
            **kwargs: Parameter name-value pairs to set
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def _validate_dimensions(self) -> None:
        """Validate box dimensions are within acceptable ranges"""
        dimensions = [
            ('length', self.length),
            ('width', self.width), 
            ('height', self.height)
        ]
        
        for name, value in dimensions:
            if value < MIN_DIMENSION:
                raise DimensionError(name, value, min_val=MIN_DIMENSION)
            if value > MAX_DIMENSION:
                raise DimensionError(name, value, max_val=MAX_DIMENSION)
        
        # Material thickness validation
        if self.thickness < MIN_THICKNESS:
            raise MaterialError(f"Material thickness ({self.thickness}) must be at least {MIN_THICKNESS}mm")
        if self.thickness > MAX_THICKNESS:
            raise MaterialError(f"Material thickness ({self.thickness}) must be no more than {MAX_THICKNESS}mm")        # Tab width validation
        if self.tab < MIN_TAB_WIDTH:
            raise TabError(f"Tab width ({self.tab}) must be at least {MIN_TAB_WIDTH}mm")
          # Tab to thickness ratio validation (tabs can be thinner but become weak)
        min_tab_for_thickness = self.thickness * MIN_TAB_TO_THICKNESS_RATIO
        recommended_min_tab = self.thickness * RECOMMENDED_MIN_TAB_TO_THICKNESS_RATIO
        recommended_max_tab = self.thickness * RECOMMENDED_MAX_TAB_TO_THICKNESS_RATIO
        absolute_max_tab = self.thickness * MAX_TAB_TO_THICKNESS_RATIO
        
        if self.tab < min_tab_for_thickness:
            raise TabError(f"Tab width ({self.tab}mm) is too small - minimum is {min_tab_for_thickness}mm "
                          f"(thickness {self.thickness}mm × {MIN_TAB_TO_THICKNESS_RATIO}). "
                          f"Tabs thinner than this become very weak.")
        
        # Issue warning for weak tabs (but don't fail)
        if self.tab < recommended_min_tab:
            self.log(f"Warning: Tab width ({self.tab}mm) is less than recommended minimum "
                    f"({recommended_min_tab}mm). Tabs may be weak.")
        
        # Physical constraint: tabs can't be larger than smallest dimension / 3
        min_dimension = min(self.length, self.width, self.height)
        max_physical_tab = min_dimension / 3
        
        if self.tab > max_physical_tab:
            raise TabError(f"Tab width ({self.tab}mm) is too large for smallest dimension ({min_dimension}mm). "
                          f"Maximum tab width is {max_physical_tab:.1f}mm (dimension/3).")
        
        # Issue warning for unusually large tabs (but allow them for big boxes)
        if self.tab > recommended_max_tab and self.tab <= absolute_max_tab:
            self.log(f"Info: Large tab width ({self.tab}mm) is {self.tab/self.thickness:.1f}x material thickness. "
                    f"This is fine for large boxes but may be excessive for smaller ones.")
        
        # Only fail for extremely large tabs that exceed physical limits
        if self.tab > absolute_max_tab and self.tab <= max_physical_tab:
            raise TabError(f"Tab width ({self.tab}mm) is excessively large "
                          f"({self.tab/self.thickness:.1f}x thickness). "
                          f"Consider using smaller tabs for better joint geometry.")
          # Check if material is too thick for dimensions
        min_dimension = min(self.length, self.width, self.height)
        if self.thickness >= min_dimension / 2:
            raise MaterialError(f"Material thickness ({self.thickness}) is too large for smallest dimension ({min_dimension})")
        
        # Check if thickness makes valid tabs impossible
        max_tab_size = min_dimension / 3
        if self.thickness > max_tab_size:
            raise MaterialError(f"Material thickness ({self.thickness}) is too large to create valid tabs. "
                               f"For {min_dimension}mm dimension, max thickness is {max_tab_size:.1f}mm")
    
    def log(self, text: str) -> None:
        """Log text to file if SCHROFF_LOG environment variable is set"""
        if 'SCHROFF_LOG' in os.environ:
            with open(os.environ.get('SCHROFF_LOG'), 'a') as f:
                f.write(text + "\n")

    def get_line_path(self, XYstring):
        """Return path data for a line"""
        return {
            'type': 'path',
            'data': XYstring,
            'style': {
                'stroke': '#000000',
                'stroke-width': str(self.linethickness),
                'fill': 'none'
            }
        }

    def get_circle_path(self, r, c):
        """Return path data for a circle"""
        (cx, cy) = c
        self.log("putting circle at (%d,%d)" % (cx, cy))
        return {
            'type': 'circle',
            'cx': cx,
            'cy': cy,
            'r': r,
            'style': {
                'stroke': '#000000',
                'stroke-width': str(self.linethickness),
                'fill': 'none'
            }
        }

    # ------------------------------------------------------------------
    # Entrance hole support
    # ------------------------------------------------------------------
    @staticmethod
    def _fmt(v: float) -> str:
        return ('%.4f' % v).rstrip('0').rstrip('.')

    def round_hole_path(self, cx: float, cy: float, r: float) -> str:
        """Closed SVG path for a circle (two half-arcs)."""
        f = self._fmt
        return (f"M {f(cx - r)},{f(cy)} "
                f"A {f(r)},{f(r)} 0 1 1 {f(cx + r)},{f(cy)} "
                f"A {f(r)},{f(r)} 0 1 1 {f(cx - r)},{f(cy)} Z")

    def rounded_rect_path(self, cx: float, cy: float, w: float, h: float, r: float = 0.0) -> str:
        """Closed SVG path for a w x h rectangle centred on (cx, cy) with corner radius r.

        r is clamped to min(w, h) / 2; with r == h/2 the result is a stadium/oval slot.
        Absolute coordinates are used throughout (no relative h/v/a commands), so the
        path is robust when re-processed by Inkscape or other tools.
        """
        f = self._fmt
        r = max(0.0, min(r, w / 2.0, h / 2.0))
        l, rt, t, b = cx - w / 2.0, cx + w / 2.0, cy - h / 2.0, cy + h / 2.0
        if r <= 1e-9:
            return (f"M {f(l)},{f(t)} L {f(rt)},{f(t)} L {f(rt)},{f(b)} "
                    f"L {f(l)},{f(b)} Z")
        eps = 1e-9
        d = [f"M {f(l + r)},{f(t)}"]
        if w - 2 * r > eps:
            d.append(f"L {f(rt - r)},{f(t)}")
        d.append(f"A {f(r)},{f(r)} 0 0 1 {f(rt)},{f(t + r)}")
        if h - 2 * r > eps:
            d.append(f"L {f(rt)},{f(b - r)}")
        d.append(f"A {f(r)},{f(r)} 0 0 1 {f(rt - r)},{f(b)}")
        if w - 2 * r > eps:
            d.append(f"L {f(l + r)},{f(b)}")
        d.append(f"A {f(r)},{f(r)} 0 0 1 {f(l)},{f(b - r)}")
        if h - 2 * r > eps:
            d.append(f"L {f(l)},{f(t + r)}")
        d.append(f"A {f(r)},{f(r)} 0 0 1 {f(l + r)},{f(t)} Z")
        return ' '.join(d)

    def _hole_target_names(self, X: float, Y: float) -> List[str]:
        """Piece names that may carry the hole, in order of preference.

        Vertical walls come in two pairs: front/back (X wide) and left/right (Y wide);
        both are the same height, so the pair with the larger of X, Y is the 'big' one.
        Ties go to front/back.
        """
        frontback, leftright = ['bk', 'ft'], ['lt', 'rt']
        big, small = (frontback, leftright) if X >= Y else (leftright, frontback)
        return big if self.hole_side == HoleSide.BIG else small

    def _validate_hole(self) -> None:
        if self.hole_type not in HoleType.ALL:
            raise ValueError(f"Hole type must be one of {HoleType.ALL}, got {self.hole_type!r}")
        if self.hole_type == HoleType.NONE:
            return
        if self.hole_side not in HoleSide.ALL:
            raise ValueError(f"Hole side must be one of {HoleSide.ALL}, got {self.hole_side!r}")
        if self.hole_type == HoleType.ROUND:
            if self.hole_diameter <= self.kerf:
                raise ValueError("Hole diameter must be larger than the kerf")
        else:
            if min(self.hole_width, self.hole_height) <= self.kerf:
                raise ValueError("Hole width/height must be larger than the kerf")
            if self.hole_radius < 0:
                raise ValueError("Hole corner radius cannot be negative")

    def add_hole(self, name: str, body: Tuple[float, float, float, float]) -> None:
        """Add the entrance hole to the plate 'name'.

        body = (left, top, right, bottom): the flat plate itself, tabs excluded, in SVG
        coordinates. hole_x is measured from the left edge and hole_y from the bottom edge
        (i.e. the edge that is lower in the SVG, which sits on the floor when assembled).
        Kerf is compensated: the hole is drawn smaller by one kerf so that the cut hole
        ends up at its nominal size.
        """
        left, top, right, bottom = body
        pw, ph = right - left, bottom - top
        if self.hole_type == HoleType.ROUND:
            w = h = self.hole_diameter
        else:
            w, h = self.hole_width, self.hole_height
        # clearance from plate edge: at least one material thickness (joint notches live there)
        margin = self.thickness
        cx_rel = pw / 2.0 if self.hole_x is None else float(self.hole_x)
        cy_rel = ph / 2.0 if self.hole_y is None else float(self.hole_y)
        if (cx_rel - w / 2.0 < margin or cx_rel + w / 2.0 > pw - margin or
                cy_rel - h / 2.0 < margin or cy_rel + h / 2.0 > ph - margin):
            raise ValueError(
                f"Hole ({w:g} x {h:g} mm, centre {cx_rel:g},{cy_rel:g} from left/bottom) does not fit "
                f"in the '{name}' wall plate ({pw:g} x {ph:g} mm) with {margin:g} mm clearance to the "
                f"edges. Adjust --hole-x/--hole-y or the hole size.")
        cx = left + cx_rel
        cy = bottom - cy_rel
        k = self.kerf
        if self.hole_type == HoleType.ROUND:
            d = self.round_hole_path(cx, cy, (w - k) / 2.0)
        else:
            d = self.rounded_rect_path(cx, cy, w - k, h - k, max(0.0, self.hole_radius - k / 2.0))
        self.paths.append(self.get_line_path(d))

    # ------------------------------------------------------------------
    # Screw pilot holes
    # ------------------------------------------------------------------
    def _validate_screws(self) -> None:
        if not self.screw_holes or self.thickness <= self.screw_min_thickness:
            return      # nothing to draw (generate_box adds a note for thin material)
        if self.screw_diameter <= self.kerf:
            raise ValueError("Screw hole diameter must be larger than the kerf")
        if self.screw_diameter > self.thickness / 2.0:
            raise ValueError(f"Screw hole diameter ({self.screw_diameter:g}) must not exceed half the "
                             f"material thickness ({self.thickness / 2.0:g})")

    def _tab_centres(self, length: float) -> List[float]:
        """Centres of the tabs along a tabbed edge, measured from the edge start.

        Mirrors the layout computed in side() (gap first and last, kerf-corrected)."""
        divisions = int(length / self.nomTab)
        if not divisions % 2:
            divisions -= 1
        tabs = (divisions - 1) // 2
        if tabs < 1:
            return []
        if self.equalTabs:
            gap = tab = length / divisions
        else:
            tab = self.nomTab
            gap = (length - tabs * self.nomTab) / (divisions - tabs)
        gap -= self.kerf
        tab += self.kerf
        return [k * gap + (k - 1) * tab + tab / 2.0 for k in range(1, tabs + 1)]

    def add_screw_holes(self, x, y, dx, dy, bits, tabbed) -> None:
        """Pilot holes in the middle of selected tabs of one piece.

        Per tabbed edge: the tab nearest each corner, plus the tab nearest the middle when the
        edge is longer than screw_middle_min_length. A hole sits half a thickness in from the
        tab tip, so the screw runs through the tab's thickness into the edge of the mating
        panel, in the middle of that panel's thickness.
        """
        t = self.thickness
        r = (self.screw_diameter - self.kerf) / 2.0
        a, b, c, d = bits
        atabs, btabs, ctabs, dtabs = tabbed
        # (active, length, position of a point at distance 'along' from the edge start)
        edges = [
            (a and atabs, dx, lambda s: (x + s, y + t / 2.0)),
            (b and btabs, dy, lambda s: (x + dx - t / 2.0, y + s)),
            (c and ctabs, dx, lambda s: (x + dx - s, y + dy - t / 2.0)),
            (d and dtabs, dy, lambda s: (x + t / 2.0, y + dy - s)),
        ]
        for active, length, point in edges:
            if not active:
                continue
            centres = self._tab_centres(length)
            if not centres:
                continue
            chosen = {0, len(centres) - 1}
            if length > self.screw_middle_min_length:
                chosen.add((len(centres) - 1) // 2)
            for i in sorted(chosen):
                cx, cy = point(centres[i])
                self.paths.append(self.get_line_path(self.round_hole_path(cx, cy, r)))

    def dimple_str(self, tabVector, vectorX, vectorY, dirX, dirY, dirxN, diryN, ddir, isTab):
        ds = ''
        if not isTab:
            ddir = -ddir
        if self.dimpleHeight > 0 and tabVector != 0:
            if tabVector > 0:
                dimpleStart = (tabVector - self.dimpleLength) / 2 - self.dimpleHeight
                tabSgn = 1
            else:
                dimpleStart = (tabVector + self.dimpleLength) / 2 + self.dimpleHeight
                tabSgn = -1
            Vxd = vectorX + dirxN * dimpleStart
            Vyd = vectorY + diryN * dimpleStart
            ds += 'L ' + str(Vxd) + ',' + str(Vyd) + ' '
            Vxd = Vxd + (tabSgn * dirxN - ddir * dirX) * self.dimpleHeight
            Vyd = Vyd + (tabSgn * diryN - ddir * dirY) * self.dimpleHeight
            ds += 'L ' + str(Vxd) + ',' + str(Vyd) + ' '
            Vxd = Vxd + tabSgn * dirxN * self.dimpleLength
            Vyd = Vyd + tabSgn * diryN * self.dimpleLength
            ds += 'L ' + str(Vxd) + ',' + str(Vyd) + ' '
            Vxd = Vxd + (tabSgn * dirxN + ddir * dirX) * self.dimpleHeight
            Vyd = Vyd + (tabSgn * diryN + ddir * dirY) * self.dimpleHeight
            ds += 'L ' + str(Vxd) + ',' + str(Vyd) + ' '
        return ds

    def side(self, group_id, root, startOffset, endOffset, tabVec, prevTab, length, direction, isTab, isDivider, numDividers, dividerSpacing):
        rootX, rootY = root
        startOffsetX, startOffsetY = startOffset
        endOffsetX, endOffsetY = endOffset
        dirX, dirY = direction
        notTab = 0 if isTab else 1

        if self.tabSymmetry == 1:        # waffle-block style rotationally symmetric tabs
            divisions = int((length - 2 * self.thickness) / self.nomTab)
            if divisions % 2:
                divisions += 1      # make divs even
            divisions = float(divisions)
            tabs = divisions / 2                  # tabs for side
        else:
            divisions = int(length / self.nomTab)
            if not divisions % 2:
                divisions -= 1  # make divs odd
            divisions = float(divisions)
            tabs = (divisions - 1) / 2              # tabs for side

        if self.tabSymmetry == 1:        # waffle-block style rotationally symmetric tabs
            gapWidth = tabWidth = (length - 2 * self.thickness) / divisions
        elif self.equalTabs:
            gapWidth = tabWidth = length / divisions
        else:
            tabWidth = self.nomTab
            gapWidth = (length - tabs * self.nomTab) / (divisions - tabs)

        if isTab:                 # kerf correction
            gapWidth -= self.kerf
            tabWidth += self.kerf
            first = self.halfkerf
        else:
            gapWidth += self.kerf
            tabWidth -= self.kerf
            first = -self.halfkerf

        firstholelenX = 0
        firstholelenY = 0
        s = []
        h = []
        firstVec = 0
        secondVec = tabVec
        dividerEdgeOffsetX = dividerEdgeOffsetY = self.thickness
        notDirX = 0 if dirX else 1 # used to select operation on x or y
        notDirY = 0 if dirY else 1

        if self.tabSymmetry == 1:
            dividerEdgeOffsetX = dirX * self.thickness
            vectorX = rootX + (0 if dirX and prevTab else startOffsetX * self.thickness)
            vectorY = rootY + (0 if dirY and prevTab else startOffsetY * self.thickness)
            s = 'M ' + str(vectorX) + ',' + str(vectorY) + ' '
            vectorX = rootX + (startOffsetX if startOffsetX else dirX) * self.thickness
            vectorY = rootY + (startOffsetY if startOffsetY else dirY) * self.thickness
            if notDirX and tabVec:
                endOffsetX = 0
            if notDirY and tabVec:
                endOffsetY = 0
        else:
            (vectorX, vectorY) = (rootX + startOffsetX * self.thickness, rootY + startOffsetY * self.thickness)
            dividerEdgeOffsetX = dirY * self.thickness
            dividerEdgeOffsetY = dirX * self.thickness
            s = 'M ' + str(vectorX) + ',' + str(vectorY) + ' '
            if notDirX:
                vectorY = rootY # set correct line start for tab generation
            if notDirY:
                vectorX = rootX

        # generate line as tab or hole using various parameters
        for tabDivision in range(1, int(divisions)):
            if ((tabDivision % 2) ^ (not isTab)) and numDividers > 0 and not isDivider: # draw holes for divider tabs to key into side walls
                w = gapWidth if isTab else tabWidth
                if tabDivision == 1 and self.tabSymmetry == 0:
                    w -= startOffsetX * self.thickness
                holeLenX = dirX * w + notDirX * firstVec + first * dirX
                holeLenY = dirY * w + notDirY * firstVec + first * dirY
                if first:
                    firstholelenX = holeLenX
                    firstholelenY = holeLenY
                for dividerNumber in range(1, int(numDividers) + 1):
                    Dx = vectorX + -dirY * dividerSpacing * dividerNumber + notDirX * self.halfkerf + dirX * self.dogbone * self.halfkerf - self.dogbone * first * dirX
                    Dy = vectorY + dirX * dividerSpacing * dividerNumber - notDirY * self.halfkerf + dirY * self.dogbone * self.halfkerf - self.dogbone * first * dirY
                    if tabDivision == 1 and self.tabSymmetry == 0:
                        Dx += startOffsetX * self.thickness
                    h = 'M ' + str(Dx) + ',' + str(Dy) + ' '
                    Dx = Dx + holeLenX
                    Dy = Dy + holeLenY
                    h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                    Dx = Dx + notDirX * (secondVec - self.kerf)
                    Dy = Dy + notDirY * (secondVec + self.kerf)
                    h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                    Dx = Dx - holeLenX
                    Dy = Dy - holeLenY
                    h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                    Dx = Dx - notDirX * (secondVec - self.kerf)
                    Dy = Dy - notDirY * (secondVec + self.kerf)
                    h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                    self.paths.append(self.get_line_path(h))

            if tabDivision % 2:
                if tabDivision == 1 and numDividers > 0 and isDivider: # draw slots for dividers to slot into each other
                    for dividerNumber in range(1, int(numDividers) + 1):
                        Dx = vectorX + -dirY * dividerSpacing * dividerNumber - dividerEdgeOffsetX + notDirX * self.halfkerf
                        Dy = vectorY + dirX * dividerSpacing * dividerNumber - dividerEdgeOffsetY + notDirY * self.halfkerf
                        h = 'M ' + str(Dx) + ',' + str(Dy) + ' '
                        Dx = Dx + dirX * (first + length / 2)
                        Dy = Dy + dirY * (first + length / 2)
                        h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                        Dx = Dx + notDirX * (self.thickness - self.kerf)
                        Dy = Dy + notDirY * (self.thickness - self.kerf)
                        h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                        Dx = Dx - dirX * (first + length / 2)
                        Dy = Dy - dirY * (first + length / 2)
                        h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                        Dx = Dx - notDirX * (self.thickness - self.kerf)
                        Dy = Dy - notDirY * (self.thickness - self.kerf)
                        h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                        self.paths.append(self.get_line_path(h))
                        
                # draw the gap
                vectorX += dirX * (gapWidth + (isTab & self.dogbone & 1 ^ 0x1) * first + self.dogbone * self.kerf * isTab) + notDirX * firstVec
                vectorY += dirY * (gapWidth + (isTab & self.dogbone & 1 ^ 0x1) * first + self.dogbone * self.kerf * isTab) + notDirY * firstVec
                s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
                if self.dogbone and isTab:
                    vectorX -= dirX * self.halfkerf
                    vectorY -= dirY * self.halfkerf
                    s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
                # draw the starting edge of the tab
                s += self.dimple_str(secondVec, vectorX, vectorY, dirX, dirY, notDirX, notDirY, 1, isTab)
                vectorX += notDirX * secondVec
                vectorY += notDirY * secondVec
                s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
                if self.dogbone and notTab:
                    vectorX -= dirX * self.halfkerf
                    vectorY -= dirY * self.halfkerf
                    s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '

            else:
                # draw the tab
                vectorX += dirX * (tabWidth + self.dogbone * self.kerf * notTab) + notDirX * firstVec
                vectorY += dirY * (tabWidth + self.dogbone * self.kerf * notTab) + notDirY * firstVec
                s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
                if self.dogbone and notTab:
                    vectorX -= dirX * self.halfkerf
                    vectorY -= dirY * self.halfkerf
                    s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
                # draw the ending edge of the tab
                s += self.dimple_str(secondVec, vectorX, vectorY, dirX, dirY, notDirX, notDirY, -1, isTab)
                vectorX += notDirX * secondVec
                vectorY += notDirY * secondVec
                s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
                if self.dogbone and isTab:
                    vectorX -= dirX * self.halfkerf
                    vectorY -= dirY * self.halfkerf
                    s += 'L ' + str(vectorX) + ',' + str(vectorY) + ' '
            (secondVec, firstVec) = (-secondVec, -firstVec) # swap tab direction
            first = 0

        # finish the line off
        s += 'L ' + str(rootX + endOffsetX * self.thickness + dirX * length) + ',' + str(rootY + endOffsetY * self.thickness + dirY * length) + ' '

        if isTab and numDividers > 0 and self.tabSymmetry == 0 and not isDivider: # draw last for divider joints in side walls
            for dividerNumber in range(1, int(numDividers) + 1):
                Dx = vectorX + -dirY * dividerSpacing * dividerNumber + notDirX * self.halfkerf + dirX * self.dogbone * self.halfkerf - self.dogbone * first * dirX
                Dy = vectorY + dirX * dividerSpacing * dividerNumber - dividerEdgeOffsetY + notDirY * self.halfkerf
                h = 'M ' + str(Dx) + ',' + str(Dy) + ' '
                Dx = Dx + firstholelenX
                Dy = Dy + firstholelenY
                h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                Dx = Dx + notDirX * (self.thickness - self.kerf)
                Dy = Dy + notDirY * (self.thickness - self.kerf)
                h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                Dx = Dx - firstholelenX
                Dy = Dy - firstholelenY
                h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                Dx = Dx - notDirX * (self.thickness - self.kerf)
                Dy = Dy - notDirY * (self.thickness - self.kerf)
                h += 'L ' + str(Dx) + ',' + str(Dy) + ' '
                self.paths.append(self.get_line_path(h))

        self.paths.append(self.get_line_path(s))
        return s
        
    def generate_box(self) -> None:
        """Main function to generate the box geometry
        
        Raises:
            DimensionError: If box dimensions are invalid
            MaterialError: If material thickness is invalid
            TabError: If tab configuration is invalid
        """
        # Validate input parameters first
        self._validate_dimensions()
        self._validate_hole()
        self._validate_screws()
        
        # Clear previous paths
        self.paths = []
        self.messages = []
        self.circles = []
        
        # Setup global variables (converted from original)
        self.nomTab = self.tab
        self.equalTabs = self.equal
        self.tabSymmetry = self.tabsymmetry
        self.dimpleHeight = self.dimpleheight
        self.dimpleLength = self.dimplelength
        self.halfkerf = self.kerf / 2
        self.dogbone = 1 if self.tabtype == TabType.CNC else 0
        self.divx = self.div_l
        self.divy = self.div_w
        self.keydivwalls = 0 if self.keydiv == 3 or self.keydiv == 1 else 1
        self.keydivfloor = 0 if self.keydiv == 3 or self.keydiv == 2 else 1

        # Set line thickness
        if self.hairline:
            self.linethickness = 0.002 * 25.4  # Convert from inches to mm
        else:
            self.linethickness = 1

        # Get dimensions (assuming mm units for simplicity)
        X = self.length + self.kerf
        Y = self.width + self.kerf
        Z = self.height + self.kerf

        if self.inside:  # if inside dimension selected correct values to outside dimension
            X += self.thickness * 2
            Y += self.thickness * 2
            Z += self.thickness * 2        # Note: Validation is now handled by _validate_dimensions()
        if self.kerf > min(X, Y, Z) / 3:
            raise ValueError('Error: Kerf too large')
        if self.spacing < self.kerf:
            raise ValueError('Error: Spacing too small')

        # Determine which faces the box has based on the box type
        hasTp = hasBm = hasFt = hasBk = hasLt = hasRt = True
        if self.boxtype == 2:
            hasTp = False
        elif self.boxtype == 3:
            hasTp = hasFt = False
        elif self.boxtype == 4:
            hasTp = hasFt = hasRt = False
        elif self.boxtype == 5:
            hasTp = hasBm = False
        elif self.boxtype == 6:
            hasTp = hasFt = hasBk = hasRt = False

        # Determine where the tabs go based on the tab style
        if self.tabSymmetry == 2:     # Antisymmetric (deprecated)
            tpTabInfo = 0b0110
            bmTabInfo = 0b1100
            ltTabInfo = 0b1100
            rtTabInfo = 0b0110
            ftTabInfo = 0b1100
            bkTabInfo = 0b1001
        elif self.tabSymmetry == 1:   # Rotationally symmetric (Waffle-blocks)
            tpTabInfo = 0b1111
            bmTabInfo = 0b1111
            ltTabInfo = 0b1111
            rtTabInfo = 0b1111
            ftTabInfo = 0b1111
            bkTabInfo = 0b1111
        else:               # XY symmetric
            tpTabInfo = 0b0000
            bmTabInfo = 0b0000
            ltTabInfo = 0b1111
            rtTabInfo = 0b1111
            ftTabInfo = 0b1010
            bkTabInfo = 0b1010

        def fixTabBits(tabbed, tabInfo, bit):
            newTabbed = tabbed & ~bit
            if self.inside:
                newTabInfo = tabInfo | bit      # set bit to 1 to use tab base line
            else:
                newTabInfo = tabInfo & ~bit     # set bit to 0 to use tab tip line
            return newTabbed, newTabInfo

        # Update the tab bits based on which sides of the box don't exist
        tpTabbed = bmTabbed = ltTabbed = rtTabbed = ftTabbed = bkTabbed = 0b1111
        if not hasTp:
            bkTabbed, bkTabInfo = fixTabBits(bkTabbed, bkTabInfo, 0b0010)
            ftTabbed, ftTabInfo = fixTabBits(ftTabbed, ftTabInfo, 0b1000)
            ltTabbed, ltTabInfo = fixTabBits(ltTabbed, ltTabInfo, 0b0001)
            rtTabbed, rtTabInfo = fixTabBits(rtTabbed, rtTabInfo, 0b0100)
            tpTabbed = 0
        if not hasBm:
            bkTabbed, bkTabInfo = fixTabBits(bkTabbed, bkTabInfo, 0b1000)
            ftTabbed, ftTabInfo = fixTabBits(ftTabbed, ftTabInfo, 0b0010)
            ltTabbed, ltTabInfo = fixTabBits(ltTabbed, ltTabInfo, 0b0100)
            rtTabbed, rtTabInfo = fixTabBits(rtTabbed, rtTabInfo, 0b0001)
            bmTabbed = 0
        if not hasFt:
            tpTabbed, tpTabInfo = fixTabBits(tpTabbed, tpTabInfo, 0b1000)
            bmTabbed, bmTabInfo = fixTabBits(bmTabbed, bmTabInfo, 0b1000)
            ltTabbed, ltTabInfo = fixTabBits(ltTabbed, ltTabInfo, 0b1000)
            rtTabbed, rtTabInfo = fixTabBits(rtTabbed, rtTabInfo, 0b1000)
            ftTabbed = 0
        if not hasBk:
            tpTabbed, tpTabInfo = fixTabBits(tpTabbed, tpTabInfo, 0b0010)
            bmTabbed, bmTabInfo = fixTabBits(bmTabbed, bmTabInfo, 0b0010)
            ltTabbed, ltTabInfo = fixTabBits(ltTabbed, ltTabInfo, 0b0010)
            rtTabbed, rtTabInfo = fixTabBits(rtTabbed, rtTabInfo, 0b0010)
            bkTabbed = 0
        if not hasLt:
            tpTabbed, tpTabInfo = fixTabBits(tpTabbed, tpTabInfo, 0b0100)
            bmTabbed, bmTabInfo = fixTabBits(bmTabbed, bmTabInfo, 0b0001)
            bkTabbed, bkTabInfo = fixTabBits(bkTabbed, bkTabInfo, 0b0001)
            ftTabbed, ftTabInfo = fixTabBits(ftTabbed, ftTabInfo, 0b0001)
            ltTabbed = 0
        if not hasRt:
            tpTabbed, tpTabInfo = fixTabBits(tpTabbed, tpTabInfo, 0b0001)
            bmTabbed, bmTabInfo = fixTabBits(bmTabbed, bmTabInfo, 0b0100)
            bkTabbed, bkTabInfo = fixTabBits(bkTabbed, bkTabInfo, 0b0100)
            ftTabbed, ftTabInfo = fixTabBits(ftTabbed, ftTabInfo, 0b0100)
            rtTabbed = 0

        # Layout positions
        row0 = (1, 0, 0, 0)      # top row
        row1y = (2, 0, 1, 0)     # second row, offset by Y
        row1z = (2, 0, 0, 1)     # second row, offset by Z
        row2 = (3, 0, 1, 1)      # third row, always offset by Y+Z

        col0 = (1, 0, 0, 0)      # left column
        col1x = (2, 1, 0, 0)     # second column, offset by X
        col1z = (2, 0, 0, 1)     # second column, offset by Z
        col2xx = (3, 2, 0, 0)    # third column, offset by 2*X
        col2xz = (3, 1, 0, 1)    # third column, offset by X+Z
        col3xzz = (4, 1, 0, 2)   # fourth column, offset by X+2*Z
        col3xxz = (4, 2, 0, 1)   # fourth column, offset by 2*X+Z
        col4 = (5, 2, 0, 2)      # fifth column, always offset by 2*X+2*Z
        col5 = (6, 3, 0, 2)      # sixth column, always offset by 3*X+2*Z

        # Face types
        tpFace = 1
        bmFace = 1
        ftFace = 2
        bkFace = 2
        ltFace = 3
        rtFace = 3

        def reduceOffsets(aa, start, dx, dy, dz):
            for ix in range(start + 1, len(aa)):
                (s, x, y, z) = aa[ix]
                aa[ix] = (s - 1, x - dx, y - dy, z - dz)

        # Layout pieces based on style
        pieces = []
        if self.style == 1:  # Diagramatic Layout
            rr = deepcopy([row0, row1z, row2])
            cc = deepcopy([col0, col1z, col2xz, col3xzz])
            if not hasFt:
                reduceOffsets(rr, 0, 0, 0, 1)     # remove row0, shift others up by Z
            if not hasLt:
                reduceOffsets(cc, 0, 0, 0, 1)
            if not hasRt:
                reduceOffsets(cc, 2, 0, 0, 1)
            if hasBk:
                pieces.append([cc[1], rr[2], X, Z, bkTabInfo, bkTabbed, bkFace, 'bk'])
            if hasLt:
                pieces.append([cc[0], rr[1], Z, Y, ltTabInfo, ltTabbed, ltFace, 'lt'])
            if hasBm:
                pieces.append([cc[1], rr[1], X, Y, bmTabInfo, bmTabbed, bmFace, 'bm'])
            if hasRt:
                pieces.append([cc[2], rr[1], Z, Y, rtTabInfo, rtTabbed, rtFace, 'rt'])
            if hasTp:
                pieces.append([cc[3], rr[1], X, Y, tpTabInfo, tpTabbed, tpFace, 'tp'])
            if hasFt:
                pieces.append([cc[1], rr[0], X, Z, ftTabInfo, ftTabbed, ftFace, 'ft'])
        elif self.style == 2:  # 3 Piece Layout
            rr = deepcopy([row0, row1y])
            cc = deepcopy([col0, col1z])
            if hasBk:
                pieces.append([cc[1], rr[1], X, Z, bkTabInfo, bkTabbed, bkFace, 'bk'])
            if hasLt:
                pieces.append([cc[0], rr[0], Z, Y, ltTabInfo, ltTabbed, ltFace, 'lt'])
            if hasBm:
                pieces.append([cc[1], rr[0], X, Y, bmTabInfo, bmTabbed, bmFace, 'bm'])
        elif self.style == 3:  # Inline(compact) Layout
            rr = deepcopy([row0])
            cc = deepcopy([col0, col1x, col2xx, col3xxz, col4, col5])
            if not hasTp:
                reduceOffsets(cc, 0, 1, 0, 0)     # remove col0, shift others left by X
            if not hasBm:
                reduceOffsets(cc, 1, 1, 0, 0)
            if not hasLt:
                reduceOffsets(cc, 2, 0, 0, 1)
            if not hasRt:
                reduceOffsets(cc, 3, 0, 0, 1)
            if not hasBk:
                reduceOffsets(cc, 4, 1, 0, 0)
            if hasBk:
                pieces.append([cc[4], rr[0], X, Z, bkTabInfo, bkTabbed, bkFace, 'bk'])
            if hasLt:
                pieces.append([cc[2], rr[0], Z, Y, ltTabInfo, ltTabbed, ltFace, 'lt'])
            if hasTp:
                pieces.append([cc[0], rr[0], X, Y, tpTabInfo, tpTabbed, tpFace, 'tp'])
            if hasBm:
                pieces.append([cc[1], rr[0], X, Y, bmTabInfo, bmTabbed, bmFace, 'bm'])
            if hasRt:
                pieces.append([cc[3], rr[0], Z, Y, rtTabInfo, rtTabbed, rtFace, 'rt'])
            if hasFt:
                pieces.append([cc[5], rr[0], X, Z, ftTabInfo, ftTabbed, ftFace, 'ft'])

        # Generate each piece
        initOffsetX = 0
        initOffsetY = 0
        hole_target = None
        screws_ok = self.screw_holes
        if self.screw_holes and self.thickness <= self.screw_min_thickness:
            screws_ok = False
            self.messages.append(f"Screw holes skipped: material thickness {self.thickness:g} mm is not "
                                 f"more than {self.screw_min_thickness:g} mm.")
        elif self.screw_holes and self.tabSymmetry == 1:
            screws_ok = False
            self.messages.append("Screw holes skipped: not supported with rotationally symmetric tabs.")

        for idx, piece in enumerate(pieces):
            (xs, xx, xy, xz) = piece[0]
            (ys, yx, yy, yz) = piece[1]
            x = xs * self.spacing + xx * X + xy * Y + xz * Z + initOffsetX  # root x co-ord for piece
            y = ys * self.spacing + yx * X + yy * Y + yz * Z + initOffsetY  # root y co-ord for piece
            dx = piece[2]
            dy = piece[3]
            tabs = piece[4]
            a = tabs >> 3 & 1
            b = tabs >> 2 & 1
            c = tabs >> 1 & 1
            d = tabs & 1
            tabbed = piece[5]
            atabs = tabbed >> 3 & 1
            btabs = tabbed >> 2 & 1
            ctabs = tabbed >> 1 & 1
            dtabs = tabbed & 1
            xspacing = (X - self.thickness) / (self.divy + 1)
            yspacing = (Y - self.thickness) / (self.divx + 1)
            xholes = 1 if piece[6] < 3 else 0
            yholes = 1 if piece[6] != 2 else 0
            wall = 1 if piece[6] > 1 else 0
            floor = 1 if piece[6] == 1 else 0

            group_id = f"panel_{idx}"

            # Generate and draw the sides of each piece
            self.side(group_id, (x, y), (d, a), (-b, a), atabs * (-self.thickness if a else self.thickness), dtabs, dx, (1, 0), a, 0, (self.keydivfloor | wall) * (self.keydivwalls | floor) * self.divx * yholes * atabs, yspacing)
            self.side(group_id, (x + dx, y), (-b, a), (-b, -c), btabs * (self.thickness if b else -self.thickness), atabs, dy, (0, 1), b, 0, (self.keydivfloor | wall) * (self.keydivwalls | floor) * self.divy * xholes * btabs, xspacing)
            if atabs:
                self.side(group_id, (x + dx, y + dy), (-b, -c), (d, -c), ctabs * (self.thickness if c else -self.thickness), btabs, dx, (-1, 0), c, 0, 0, 0)
            else:
                self.side(group_id, (x + dx, y + dy), (-b, -c), (d, -c), ctabs * (self.thickness if c else -self.thickness), btabs, dx, (-1, 0), c, 0, (self.keydivfloor | wall) * (self.keydivwalls | floor) * self.divx * yholes * ctabs, yspacing)
            if btabs:
                self.side(group_id, (x, y + dy), (d, -c), (d, a), dtabs * (-self.thickness if d else self.thickness), ctabs, dy, (0, -1), d, 0, 0, 0)
            else:
                self.side(group_id, (x, y + dy), (d, -c), (d, a), dtabs * (-self.thickness if d else self.thickness), ctabs, dy, (0, -1), d, 0, (self.keydivfloor | wall) * (self.keydivwalls | floor) * self.divy * xholes * dtabs, xspacing)

            # Entrance hole (nest box): pick the wall plate that receives it
            if self.hole_type != HoleType.NONE:
                if hole_target is None:
                    present = [p[7] for p in pieces]
                    hole_target = next((n for n in self._hole_target_names(X, Y) if n in present), None)
                    if hole_target is None:
                        raise ValueError(
                            f"No '{self.hole_side}' wall exists for this box type/layout, "
                            f"so the hole cannot be placed. Try --hole-side "
                            f"{'small' if self.hole_side == HoleSide.BIG else 'big'} or another box type.")
                if piece[7] == hole_target:
                    t = self.thickness
                    self.add_hole(hole_target, (x + d * t, y + a * t, x + dx - b * t, y + dy - c * t))

            # Screw pilot holes in the tabs
            if self.screw_holes and screws_ok:
                self.add_screw_holes(x, y, dx, dy, (a, b, c, d), (atabs, btabs, ctabs, dtabs))

            # Handle dividers if this is the first piece (template)
            if idx == 0:
                # remove tabs from dividers if not required
                if not self.keydivfloor:
                    a = c = 1
                    atabs = ctabs = 0
                if not self.keydivwalls:
                    b = d = 1
                    btabs = dtabs = 0

                y = 4 * self.spacing + 1 * Y + 2 * Z  # root y co-ord for piece
                for n in range(0, self.divx):  # generate X dividers
                    x = n * (self.spacing + X)  # root x co-ord for piece
                    group_id = f"x_divider_{n}"
                    self.side(group_id, (x, y), (d, a), (-b, a), self.keydivfloor * atabs * (-self.thickness if a else self.thickness), dtabs, dx, (1, 0), a, 1, 0, 0)
                    self.side(group_id, (x + dx, y), (-b, a), (-b, -c), self.keydivwalls * btabs * (self.thickness if b else -self.thickness), atabs, dy, (0, 1), b, 1, self.divy * xholes, xspacing)
                    self.side(group_id, (x + dx, y + dy), (-b, -c), (d, -c), self.keydivfloor * ctabs * (self.thickness if c else -self.thickness), btabs, dx, (-1, 0), c, 1, 0, 0)
                    self.side(group_id, (x, y + dy), (d, -c), (d, a), self.keydivwalls * dtabs * (-self.thickness if d else self.thickness), ctabs, dy, (0, -1), d, 1, 0, 0)
            elif idx == 1:
                y = 5 * self.spacing + 1 * Y + 3 * Z  # root y co-ord for piece
                for n in range(0, self.divy):  # generate Y dividers
                    x = n * (self.spacing + Z)  # root x co-ord for piece
                    group_id = f"y_divider_{n}"
                    self.side(group_id, (x, y), (d, a), (-b, a), self.keydivwalls * atabs * (-self.thickness if a else self.thickness), dtabs, dx, (1, 0), a, 1, self.divx * yholes, yspacing)
                    self.side(group_id, (x + dx, y), (-b, a), (-b, -c), self.keydivfloor * btabs * (self.thickness if b else -self.thickness), atabs, dy, (0, 1), b, 1, 0, 0)
                    self.side(group_id, (x + dx, y + dy), (-b, -c), (d, -c), self.keydivwalls * ctabs * (self.thickness if c else -self.thickness), btabs, dx, (-1, 0), c, 1, 0, 0)
                    self.side(group_id, (x, y + dy), (d, -c), (d, a), self.keydivfloor * dtabs * (-self.thickness if d else self.thickness), ctabs, dy, (0, -1), d, 1, 0, 0)

        return {
            'paths': self.paths,
            'circles': self.circles,
            'bounds': self.calculate_bounds()
        }

    def calculate_bounds(self):
        """Calculate the bounding box of all generated paths"""
        if not self.paths:
            return {'min_x': 0, 'min_y': 0, 'max_x': 0, 'max_y': 0}
        
        min_x = min_y = float('inf')
        max_x = max_y = float('-inf')
        
        for path in self.paths:
            coords = self.extract_coords_from_path(path['data'])
            for x, y in coords:
                min_x = min(min_x, x)
                max_x = max(max_x, x)
                min_y = min(min_y, y)
                max_y = max(max_y, y)
        
        return {'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}
    
    def extract_coords_from_path(self, path_data):
        """Extract coordinates from SVG path data"""
        coords = []
        parts = path_data.split()
        i = 0
        while i < len(parts):
            if parts[i] in ['M', 'L']:
                if i + 1 < len(parts):
                    coord_str = parts[i + 1]
                    if ',' in coord_str:
                        x_str, y_str = coord_str.split(',')
                        try:
                            x, y = float(x_str), float(y_str)
                            coords.append((x, y))
                        except ValueError:
                            pass
                i += 2
            else:
                i += 1
        return coords

    def generate_svg(self, width=None, height=None):
        """Generate SVG content"""
        result = self.generate_box()
        bounds = result['bounds']
        
        if width is None:
            width = bounds['max_x'] - bounds['min_x'] + 20
        if height is None:
            height = bounds['max_y'] - bounds['min_y'] + 20
        
        svg_content = f'''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" 
     width="{width}mm" height="{height}mm" 
     viewBox="{bounds['min_x']-10} {bounds['min_y']-10} {width} {height}">
  <g id="box_parts">
'''
        
        for path in result['paths']:
            svg_content += f'''    <path d="{path['data']}" style="stroke:{path['style']['stroke']};stroke-width:{path['style']['stroke-width']};fill:{path['style']['fill']}" />
'''
        
        for circle in result['circles']:
            svg_content += f'''    <circle cx="{circle['cx']}" cy="{circle['cy']}" r="{circle['r']}" style="stroke:{circle['style']['stroke']};stroke-width:{circle['style']['stroke-width']};fill:{circle['style']['fill']}" />
'''
        
        svg_content += '''  </g>
</svg>'''
        
        return svg_content
