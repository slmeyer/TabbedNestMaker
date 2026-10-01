#! /usr/bin/env python -t
'''
Generates Inkscape SVG file containing box components needed to 
CNC (laser/mill) cut a box with tabbed joints taking kerf and clearance into account

Refactored for testability while maintaining Inkscape compatibility

Original Tabbed Box Maker Copyright (C) 2011 elliot white
Refactoring for testability by GitHub Copilot 2025

[Previous changelog preserved...]
'''
__version__ = "1.3" ### please report bugs, suggestions etc at https://github.com/paulh-rnd/TabbedBoxMaker ###

import os
import sys
import argparse
from pathlib import Path

# Try to import Inkscape modules, fallback gracefully for CLI usage
try:
    import inkex
    import simplestyle
    import gettext
    INKSCAPE_AVAILABLE = True
    _ = gettext.gettext
except ImportError:
    INKSCAPE_AVAILABLE = False
    _ = lambda x: x  # Simple fallback for translation

from boxmaker_core import BoxMakerCore
from boxmaker_constants import (BoxType, TabType, LayoutStyle, HoleType, HoleSide,
                                SWIFT_PRESET, GENERIC_PRESET)
from boxmaker_exceptions import BoxMakerError, DimensionError, TabError, MaterialError

linethickness = 1 # default unless overridden by settings

def log(text):
    if 'SCHROFF_LOG' in os.environ:
        f = open(os.environ.get('SCHROFF_LOG'), 'a')
        f.write(text + "\n")

def newGroup(canvas):
    # Create a new group and add element created from line string
    panelId = canvas.svg.get_unique_id('panel')
    group = canvas.svg.get_current_layer().add(inkex.Group(id=panelId))
    return group
  
def getLine(XYstring):
    line = inkex.PathElement()
    line.style = { 'stroke': '#000000', 'stroke-width'  : str(linethickness), 'fill': 'none' }
    line.path = XYstring
    return line

def getCircle(r, c):
    (cx, cy) = c
    log("putting circle at (%d,%d)" % (cx,cy))
    circle = inkex.PathElement.arc((cx, cy), r)
    circle.style = { 'stroke': '#000000', 'stroke-width': str(linethickness), 'fill': 'none' }
    return circle

# CLI support
def _position(value):
    """argparse type for --hole-x / --hole-y: a number in mm or the word 'center'"""
    if value.lower() in ('c', 'centre', 'center'):
        return 'center'
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("expected a number (mm) or 'center'")

def create_cli_parser():
    """Create command line argument parser

    Every option that the presets know about defaults to None; the effective value is
    then taken from the selected preset (see resolve_cli_options). By default the
    'swift' preset is used, which describes a common swift (Apus apus) nest box.
    """
    parser = argparse.ArgumentParser(
        description='Generate tabbed box SVG files. By default a nest box for the common swift '
                    '(inside 345 x 175 x 175 mm, 12 mm ply, 65 x 28 mm oval entrance) is produced; '
                    'use --preset generic for a plain box, or override any value.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--preset', choices=['swift', 'generic'], default='swift',
                        help="Source of default values: 'swift' = common swift nest box, "
                             "'generic' = plain 100x100x100 mm box without hole")

    box = parser.add_argument_group('box')
    box.add_argument('--length', type=float, default=None, help='Length of box (mm) [swift: 345]')
    box.add_argument('--width', type=float, default=None, help='Width of box (mm) [swift: 175]')
    box.add_argument('--height', type=float, default=None, help='Height of box (mm) [swift: 175]')
    box.add_argument('--thickness', type=float, default=None, help='Material thickness (mm) [swift: 12]')
    box.add_argument('--kerf', type=float, default=None, help='Kerf width (mm) [swift: 0.1, generic: 0.5]')
    box.add_argument('--tab', type=float, default=None, help='Tab width (mm) [25]')
    box.add_argument('--style', type=int, choices=[1, 2, 3], default=LayoutStyle.SEPARATED, help='Layout style')
    box.add_argument('--boxtype', type=int, choices=range(1, 7), default=BoxType.FULL_BOX, help='Box type')
    box.add_argument('--tabtype', type=int, choices=[0, 1], default=TabType.LASER, help='Tab type (0=laser, 1=mill)')
    box.add_argument('--div-l', type=int, default=0, help='Dividers along length')
    box.add_argument('--div-w', type=int, default=0, help='Dividers along width')
    box.add_argument('--output', '-o', type=str, default='box.svg', help='Output SVG file')
    dims = box.add_mutually_exclusive_group()
    dims.add_argument('--inside', dest='inside', action='store_true', default=None,
                      help='Dimensions are inside measurements [swift default]')
    dims.add_argument('--outside', dest='inside', action='store_false',
                      help='Dimensions are outside measurements [generic default]')

    hole = parser.add_argument_group(
        'entrance hole',
        'Cuts an entrance hole into one vertical wall (e.g. to make a bird nest box). '
        'Positions refer to the flat wall plate as drawn in the SVG (joint tabs excluded): '
        '--hole-x from its left edge, --hole-y from its bottom edge (the edge that rests on '
        'the floor panel, so --hole-y is the height above the inside floor). Both give the '
        'hole CENTRE. The hole must keep at least one material thickness from the plate edges.')
    hole.add_argument('--hole', dest='hole_type', choices=list(HoleType.ALL), default=None,
                      help="Hole type: round, rect (rectangle, optionally with rounded corners) "
                           "or none [swift: rect]")
    hole.add_argument('--no-hole', dest='hole_type', action='store_const', const=HoleType.NONE,
                      help='Shortcut for --hole none')
    hole.add_argument('--hole-side', choices=list(HoleSide.ALL), default=None,
                      help="Wall pair that gets the hole: 'big' = the larger vertical walls, "
                           "'small' = the smaller ones (compared by footprint: max(length, width) "
                           "decides). Only one wall gets a hole. [big]")
    hole.add_argument('--hole-x', type=_position, default=None, metavar='MM|center',
                      help='Horizontal hole centre from left plate edge, or "center" [swift: 60]')
    hole.add_argument('--hole-y', type=_position, default=None, metavar='MM|center',
                      help='Vertical hole centre above bottom plate edge, or "center" [swift: 55]')
    hole.add_argument('--hole-diameter', type=float, default=32.0, help='Diameter of a round hole (mm)')
    hole.add_argument('--hole-width', type=float, default=None,
                      help='Width of a rect hole (mm) [65]')
    hole.add_argument('--hole-height', type=float, default=None,
                      help='Height of a rect hole (mm) [28]')
    hole.add_argument('--hole-radius', type=float, default=None,
                      help='Corner radius of a rect hole (mm); half the smaller side gives a '
                           'fully rounded oval slot [swift: 14, generic: 0]')
    return parser

def resolve_cli_options(args):
    """Fill every option the user did not give from the selected preset. Returns a dict."""
    preset = SWIFT_PRESET if args.preset == 'swift' else GENERIC_PRESET
    opts = {}
    for key, default in preset.items():
        given = getattr(args, key, None)
        opts[key] = default if given is None else given
    for key in ('hole_x', 'hole_y'):
        if opts[key] == 'center':
            opts[key] = None
    # An explicitly requested hole with no explicit position defaults to the plate centre,
    # not to the swift entrance position (which would only make sense for the swift box).
    if args.preset == 'swift' and args.hole_type is not None and args.hole_type != preset['hole_type']:
        for key in ('hole_x', 'hole_y'):
            if getattr(args, key) is None:
                opts[key] = None
    return opts

def main():
    """Main CLI function"""
    # Check if we're being run as CLI (no Inkscape SVG input)
    import sys
    
    # Simple check: if we have CLI-style arguments, run in CLI mode
    cli_args = ['--length', '--width', '--height', '--thickness', '--kerf', '--tab', '--output',
                '--preset', '--hole', '--no-hole', '--outside']
    is_cli = any(arg in sys.argv for arg in cli_args)
    
    if not INKSCAPE_AVAILABLE or is_cli:
        # CLI mode
        parser = create_cli_parser()
        args = parser.parse_args()
        opts = resolve_cli_options(args)
        
        # Create core instance and set parameters
        core = BoxMakerCore()
        core.set_parameters(
            length=opts['length'],
            width=opts['width'],
            height=opts['height'],
            thickness=opts['thickness'],
            kerf=opts['kerf'],
            tab=opts['tab'],
            style=args.style,
            boxtype=args.boxtype,
            tabtype=args.tabtype,
            div_l=args.div_l,
            div_w=args.div_w,
            inside=1 if opts['inside'] else 0,
            hole_type=opts['hole_type'],
            hole_side=opts['hole_side'],
            hole_diameter=args.hole_diameter,
            hole_width=opts['hole_width'],
            hole_height=opts['hole_height'],
            hole_radius=opts['hole_radius'],
            hole_x=opts['hole_x'],
            hole_y=opts['hole_y'],
        )
        
        try:
            # Generate SVG
            svg_content = core.generate_svg()
            
            # Write to file
            with open(args.output, 'w') as f:
                f.write(svg_content)
            
            print(f"Box SVG generated: {args.output}")
            
        except DimensionError as e:
            print(f"❌ Dimension Error: {e}")
            print("💡 Tip: All dimensions should be at least 40mm for practical boxes")
            sys.exit(1)
        except TabError as e:
            print(f"❌ Tab Error: {e}")
            print("💡 Tip: Use tabs between material thickness and dimension/3")
            sys.exit(1)
        except MaterialError as e:
            print(f"❌ Material Error: {e}")
            print("💡 Tip: Material thickness should be much smaller than box dimensions")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error: {e}")
            sys.exit(1)
            
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)
    else:
        # Inkscape extension mode
        effect = BoxMaker()
        effect.run()

if INKSCAPE_AVAILABLE:
    class BoxMaker(inkex.Effect):
        def __init__(self):
            # Call the base class constructor.
            inkex.Effect.__init__(self)
            # Define options - keeping original interface
            self.arg_parser.add_argument('--schroff',action='store',type=int,
              dest='schroff',default=0,help='Enable Schroff mode')
            self.arg_parser.add_argument('--rail_height',action='store',type=float,
              dest='rail_height',default=10.0,help='Height of rail')
            self.arg_parser.add_argument('--rail_mount_depth',action='store',type=float,
              dest='rail_mount_depth',default=17.4,help='Depth at which to place hole for rail mount bolt')
            self.arg_parser.add_argument('--rail_mount_centre_offset',action='store',type=float,
              dest='rail_mount_centre_offset',default=0.0,help='How far toward row centreline to offset rail mount bolt (from rail centreline)')
            self.arg_parser.add_argument('--rows',action='store',type=int,
              dest='rows',default=0,help='Number of Schroff rows')
            self.arg_parser.add_argument('--hp',action='store',type=int,
              dest='hp',default=0,help='Width (TE/HP units) of Schroff rows')
            self.arg_parser.add_argument('--row_spacing',action='store',type=float,
              dest='row_spacing',default=10.0,help='Height of rail')
            self.arg_parser.add_argument('--unit',action='store',type=str,
              dest='unit',default='mm',help='Measure Units')
            self.arg_parser.add_argument('--inside',action='store',type=int,
              dest='inside',default=0,help='Int/Ext Dimension')
            self.arg_parser.add_argument('--length',action='store',type=float,
              dest='length',default=100,help='Length of Box')
            self.arg_parser.add_argument('--width',action='store',type=float,
              dest='width',default=100,help='Width of Box')
            self.arg_parser.add_argument('--depth',action='store',type=float,
              dest='height',default=100,help='Height of Box')
            self.arg_parser.add_argument('--tab',action='store',type=float,
              dest='tab',default=25,help='Nominal Tab Width')
            self.arg_parser.add_argument('--equal',action='store',type=int,
              dest='equal',default=0,help='Equal/Prop Tabs')
            self.arg_parser.add_argument('--tabsymmetry',action='store',type=int,
              dest='tabsymmetry',default=0,help='Tab style')
            self.arg_parser.add_argument('--tabtype',action='store',type=int,
              dest='tabtype',default=0,help='Tab type: regular or dogbone')
            self.arg_parser.add_argument('--dimpleheight',action='store',type=float,
              dest='dimpleheight',default=0,help='Tab Dimple Height')
            self.arg_parser.add_argument('--dimplelength',action='store',type=float,
              dest='dimplelength',default=0,help='Tab Dimple Tip Length')
            self.arg_parser.add_argument('--hairline',action='store',type=int,
              dest='hairline',default=0,help='Line Thickness')
            self.arg_parser.add_argument('--thickness',action='store',type=float,
              dest='thickness',default=10,help='Thickness of Material')
            self.arg_parser.add_argument('--kerf',action='store',type=float,
              dest='kerf',default=0.5,help='Kerf (width of cut)')
            self.arg_parser.add_argument('--style',action='store',type=int,
              dest='style',default=25,help='Layout/Style')
            self.arg_parser.add_argument('--spacing',action='store',type=float,
              dest='spacing',default=25,help='Part Spacing')
            self.arg_parser.add_argument('--boxtype',action='store',type=int,
              dest='boxtype',default=25,help='Box type')
            self.arg_parser.add_argument('--div_l',action='store',type=int,
              dest='div_l',default=25,help='Dividers (Length axis)')
            self.arg_parser.add_argument('--div_w',action='store',type=int,
              dest='div_w',default=25,help='Dividers (Width axis)')
            self.arg_parser.add_argument('--keydiv',action='store',type=int,
              dest='keydiv',default=3,help='Key dividers into walls/floor')
            self.arg_parser.add_argument('--hole_type',action='store',type=str,
              dest='hole_type',default='none',help='Entrance hole: none, round or rect')
            self.arg_parser.add_argument('--hole_side',action='store',type=str,
              dest='hole_side',default='big',help='Wall pair for the hole: big or small')
            self.arg_parser.add_argument('--hole_diameter',action='store',type=float,
              dest='hole_diameter',default=32.0,help='Round hole diameter')
            self.arg_parser.add_argument('--hole_width',action='store',type=float,
              dest='hole_width',default=65.0,help='Rectangular hole width')
            self.arg_parser.add_argument('--hole_height',action='store',type=float,
              dest='hole_height',default=28.0,help='Rectangular hole height')
            self.arg_parser.add_argument('--hole_radius',action='store',type=float,
              dest='hole_radius',default=0.0,help='Rectangular hole corner radius')
            self.arg_parser.add_argument('--hole_x',action='store',type=float,
              dest='hole_x',default=-1.0,help='Hole centre from left edge (negative = centred)')
            self.arg_parser.add_argument('--hole_y',action='store',type=float,
              dest='hole_y',default=-1.0,help='Hole centre from bottom edge (negative = centred)')
            self.arg_parser.add_argument('--optimize',action='store',type=inkex.utils.Boolean,
              dest='optimize',default=True,help='Optimize paths')

        def effect(self):
            # Create BoxMakerCore instance and configure it
            core = BoxMakerCore()
            
            # Get script's option values and transfer to core
            core.hairline = self.options.hairline
            core.unit = self.options.unit
            core.inside = self.options.inside
            
            # Convert units using Inkscape's unit conversion
            core.kerf = self.svg.unittouu(str(self.options.kerf) + core.unit)
            core.length = self.svg.unittouu(str(self.options.length + self.options.kerf) + core.unit)
            core.width = self.svg.unittouu(str(self.options.width + self.options.kerf) + core.unit)
            core.height = self.svg.unittouu(str(self.options.height + self.options.kerf) + core.unit)
            core.thickness = self.svg.unittouu(str(self.options.thickness) + core.unit)
            core.tab = self.svg.unittouu(str(self.options.tab) + core.unit)
            core.spacing = self.svg.unittouu(str(self.options.spacing) + core.unit)
            core.dimpleheight = self.svg.unittouu(str(self.options.dimpleheight) + core.unit)
            core.dimplelength = self.svg.unittouu(str(self.options.dimplelength) + core.unit)
            
            # Set other options
            core.equal = self.options.equal
            core.tabsymmetry = self.options.tabsymmetry
            core.tabtype = self.options.tabtype
            core.style = self.options.style
            core.boxtype = self.options.boxtype
            core.div_l = self.options.div_l
            core.div_w = self.options.div_w
            core.keydiv = self.options.keydiv
            core.optimize = self.options.optimize

            # Entrance hole (all lengths converted to user units like the other dimensions)
            u = lambda v: self.svg.unittouu(str(v) + core.unit)
            core.hole_type = self.options.hole_type
            core.hole_side = self.options.hole_side
            core.hole_diameter = u(self.options.hole_diameter)
            core.hole_width = u(self.options.hole_width)
            core.hole_height = u(self.options.hole_height)
            core.hole_radius = u(self.options.hole_radius)
            core.hole_x = u(self.options.hole_x) if self.options.hole_x >= 0 else None
            core.hole_y = u(self.options.hole_y) if self.options.hole_y >= 0 else None
            
            # Set line thickness based on hairline option
            global linethickness
            if core.hairline:
                linethickness = self.svg.unittouu('0.002in')
                core.linethickness = linethickness
            else:
                linethickness = 1
                core.linethickness = linethickness
            
            try:
                # Generate the box using core functionality
                result = core.generate_box()
                
                # Convert core output to Inkscape elements
                for path_data in result['paths']:
                    line = getLine(path_data['data'])
                    group = newGroup(self)
                    group.add(line)
                    
                for circle_data in result['circles']:
                    circle = getCircle(circle_data['r'], (circle_data['cx'], circle_data['cy']))
                    group = newGroup(self)
                    group.add(circle)
                    
            except ValueError as e:
                inkex.errormsg(_(str(e)))
                return

if __name__ == '__main__':
    main()
