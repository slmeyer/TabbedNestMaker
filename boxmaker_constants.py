"""
Constants and enums for BoxMaker
"""
from enum import IntEnum


class BoxType(IntEnum):
    """Box types available"""
    FULL_BOX = 1
    NO_TOP = 2
    NO_BOTTOM = 3
    NO_SIDES = 4
    NO_FRONT_BACK = 5
    NO_LEFT_RIGHT = 6


class TabType(IntEnum):
    """Tab cutting types"""
    LASER = 0  # Standard tabs for laser cutting
    CNC = 1    # Dogbone tabs for CNC milling


class LayoutStyle(IntEnum):
    """Layout styles for arranging box pieces"""
    SEPARATED = 1
    NESTED = 2
    COMPACT = 3


class KeyDividerType(IntEnum):
    """Key divider types"""
    WALLS_AND_FLOOR = 0
    WALLS_ONLY = 1
    FLOOR_ONLY = 2
    NONE = 3


class HoleType:
    """Entrance-hole shapes (plain strings so they map directly to CLI/Inkscape options)"""
    NONE = 'none'
    ROUND = 'round'
    RECT = 'rect'      # rectangle with (optionally) rounded corners
    ALL = (NONE, ROUND, RECT)


class HoleSide:
    """Which wall receives the entrance hole"""
    BIG = 'big'        # the pair of vertical walls with the larger area
    SMALL = 'small'    # the pair of vertical walls with the smaller area
    ALL = (BIG, SMALL)


# Default values
DEFAULT_LENGTH = 100.0
DEFAULT_WIDTH = 100.0
DEFAULT_HEIGHT = 100.0
DEFAULT_TAB_WIDTH = 25.0
DEFAULT_THICKNESS = 3.0
DEFAULT_KERF = 0.5
DEFAULT_SPACING = 25.0

# Minimum values for validation (realistic for woodworking)
MIN_DIMENSION = 40.0  # 4cm minimum for practical boxes
MIN_THICKNESS = 0.1
MIN_TAB_WIDTH = 2.0   # Minimum practical tab width (2mm is reasonable for thin materials)

# Tab sizing guidelines (based on material thickness)
MIN_TAB_TO_THICKNESS_RATIO = 0.5  # Tabs can be thinner but become weak
RECOMMENDED_MIN_TAB_TO_THICKNESS_RATIO = 1.0  # Recommended minimum for strength
MAX_TAB_TO_THICKNESS_RATIO = 20.0  # Very large tabs for big boxes (was 8.0)
RECOMMENDED_MAX_TAB_TO_THICKNESS_RATIO = 8.0  # Typical maximum for most boxes
RECOMMENDED_TAB_TO_THICKNESS_RATIO = 3.0  # 3x thickness is typical

# Maximum reasonable values
MAX_DIMENSION = 10000.0
MAX_THICKNESS = 100.0

# Conversion factors
INCHES_TO_MM = 25.4
HAIRLINE_THICKNESS_INCHES = 0.002


# Common swift (Apus apus) nest box preset, used as the CLI default.
# Sources: mursejlerne.dk / DOF recommendations (inside 34.5 x 17.5 x 17.5 cm,
# entrance 28 x 65 mm) and Swift Conservation / Action for Swifts / RSPB (UK),
# which recommend the same 65 x 28 mm entrance and 12-15 mm weatherproof ply.
# All values are INSIDE dimensions in mm.
SWIFT_PRESET = {
    'length': 345.0,        # inside width of the box (long wall)
    'width': 175.0,         # inside depth
    'height': 175.0,        # inside height
    'thickness': 12.0,      # 12-15 mm exterior/marine ply is recommended
    'kerf': 0.1,
    'tab': 30.0,            # gives 5 tabs on the long edges, so there is a true centre tab
    'inside': True,
    'hole_type': 'rect',
    'hole_side': 'big',     # entrance in a long wall
    'hole_width': 65.0,     # long dimension of the entrance
    'hole_height': 28.0,    # short dimension of the entrance
    'hole_radius': 14.0,    # = height / 2 -> the oval/stadium slot used on swift boxes
    'hole_x': 60.0,         # entrance near one end, nest cup goes at the far end
    'hole_y': 55.0,         # centre 55 mm above inside floor (lower edge 41 mm; max 50 mm advised)
    'screw_holes': True,    # pilot holes for stainless screws (only if thickness > 9 mm)
}

# Previous generic defaults (--preset generic)
GENERIC_PRESET = {
    'length': DEFAULT_LENGTH,
    'width': DEFAULT_WIDTH,
    'height': DEFAULT_HEIGHT,
    'thickness': DEFAULT_THICKNESS,
    'kerf': DEFAULT_KERF,
    'tab': DEFAULT_TAB_WIDTH,
    'inside': False,
    'hole_type': 'none',
    'hole_side': 'big',
    'hole_width': 65.0,
    'hole_height': 28.0,
    'hole_radius': 0.0,
    'hole_x': None,         # None = centred
    'hole_y': None,
    'screw_holes': False,
}
