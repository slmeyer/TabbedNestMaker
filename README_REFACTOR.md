# TabbedBox2 - Refactored for Testability

[![CI - Test and Validate BoxMaker](https://github.com/YOUR_USERNAME/TabbedBox2/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/TabbedBox2/actions/workflows/ci.yml)

This is a refactored version of the TabbedBoxMaker Inkscape extension that maintains full compatibility with Inkscape while adding CLI support and testability.

## What's New

### ✨ New Features
- **CLI Support**: Generate box SVGs from command line without Inkscape
- **Testability**: Core functionality separated for easy testing
- **Same Output**: Identical behavior to original when used in Inkscape
- **Continuous Integration**: Automated testing on every commit and PR

### 🔧 Refactoring Details
- **`boxmaker_core.py`**: Core box generation logic, no Inkscape dependencies
- **`boxmaker.py`**: Inkscape extension wrapper + CLI support
- **`test_boxmaker.py`**: Comprehensive test suite
- **`cli_examples.py`**: Example CLI usage

## Quality Assurance

This project uses GitHub Actions for continuous integration:

- **Automated Testing**: Full test suite runs on Python 3.8-3.12
- **Cross-Platform**: Tested on Ubuntu, Windows, and macOS
- **Performance Testing**: Stress tests with large boxes and complex layouts
- **SVG Validation**: All generated files are validated for correctness
- **Example Generation**: CLI examples run automatically to ensure they work

## Usage

### As Inkscape Extension (Original Usage)
Copy `boxmaker.py`, `boxmaker_core.py`, and `boxmaker.inx` to your Inkscape extensions folder. Use exactly as before - no changes to the interface or behavior.

### As CLI Tool
```bash
# Basic box (100x80x50mm, 3mm material, laser cutting)
python boxmaker.py --preset generic --length 100 --width 80 --height 50 --thickness 3 --kerf 0.1 --output my_box.svg

# CNC milling with dogbone cuts
python boxmaker.py --preset generic --length 100 --width 80 --height 50 --thickness 3 --tabtype 1 --output cnc_box.svg

# Box with dividers
python boxmaker.py --preset generic --length 120 --width 100 --height 60 --div-l 2 --div-w 1 --output box_with_dividers.svg

# Thick material (6mm)
python boxmaker.py --preset generic --length 150 --width 100 --height 75 --thickness 6 --kerf 0.2 --tab 25 --output thick_box.svg
```

### Bird nest boxes: entrance hole and the swift default

Run with **no options** and you get a nest box for the common swift (*Apus apus*):
inside 345 x 175 x 175 mm, 12 mm plywood, and a 65 x 28 mm fully rounded (oval) entrance in a
long wall, near one end, 41 mm above the floor (nest cup goes at the far end). These are the
dimensions recommended by mursejlerne.dk / DOF and, for the 28 x 65 mm entrance, by Swift
Conservation, Action for Swifts and the RSPB.

```bash
python boxmaker.py -o swift_box.svg                       # swift box
python boxmaker.py --preset generic --length 100 ...      # previous plain-box defaults, no hole
python boxmaker.py --no-hole -o swift_box_no_hole.svg     # swift dimensions, no hole

# Round 32 mm entrance (blue tit) high in the big wall, centred horizontally
python boxmaker.py --length 120 --width 120 --height 250 --hole round --hole-diameter 32 \
    --hole-x center --hole-y 170 -o tit_box.svg

# Rectangular entrance with 8 mm rounded corners in the small end wall
python boxmaker.py --hole rect --hole-width 60 --hole-height 40 --hole-radius 8 \
    --hole-side small --hole-x center --hole-y 60 -o box.svg
```

Hole options:
```
--hole {none,round,rect}   Hole type (rect = rectangle with optional rounded corners)
--no-hole                  Same as --hole none
--hole-side {big,small}    big = the larger vertical walls (long walls), small = the other pair
--hole-x MM|center         Hole centre from the LEFT edge of the wall plate
--hole-y MM|center         Hole centre ABOVE the BOTTOM edge of the wall plate
--hole-diameter MM         Round hole diameter
--hole-width/--hole-height MM   Rectangular hole size
--hole-radius MM           Corner radius; half of the smaller side gives an oval slot
--preset {swift,generic}   Where unspecified values come from (default: swift)
--outside                  Dimensions are outside measurements (swift default is --inside)
```

Notes:
- Positions refer to the flat wall plate as drawn (tabs excluded). For the wall plates the bottom
  edge is the one that sits on the floor panel, so `--hole-y` is the height above the inside floor.
  Assemble with the plate oriented as drawn.
- Only one wall gets a hole (the back plate of the chosen pair, or the first available one).
- The hole must stay at least one material thickness away from the plate edges; otherwise the
  command stops with an explanatory error. The hole is kerf-compensated (drawn one kerf smaller).
- The Inkscape dialog has the same options in a new "Entrance hole" section (default: none;
  -1 = centred).

### CLI Options
```
--length FLOAT      Length of box (mm)
--width FLOAT       Width of box (mm) 
--height FLOAT      Height of box (mm)
--thickness FLOAT   Material thickness (mm)
--kerf FLOAT        Kerf width (mm)
--tab FLOAT         Tab width (mm)
--style {1,2,3}     Layout style (1=diagramatic, 2=3-piece, 3=compact)
--boxtype {1-6}     Box type (1=full, 2=no top, etc.)
--tabtype {0,1}     Tab type (0=laser, 1=cnc/dogbone)
--div-l INT         Dividers along length
--div-w INT         Dividers along width
--inside            Dimensions are inside measurements
--output FILE       Output SVG file
```

## Testing

Run the comprehensive test suite:
```bash
python test_boxmaker.py
```

This tests:
- ✅ Basic box generation
- ✅ Boxes with dividers  
- ✅ Different material thicknesses
- ✅ Laser vs CNC cutting modes
- ✅ SVG file generation
- ✅ Error handling
- ✅ Different layouts
- ✅ Sample file generation (outputs to `test_results/`)

## Example Test Cases

The test script generates these example files in `test_results/`:

1. **`test_basic_box_laser.svg`** - Standard laser-cut box
2. **`test_basic_box_cnc.svg`** - Same box with CNC dogbone cuts
3. **`test_box_with_dividers.svg`** - Box with internal dividers
4. **`test_thick_material_box.svg`** - Box for 6mm material

## CLI Examples

Run example CLI commands:
```bash
python cli_examples.py
```

This generates several sample boxes in `test_assets/` demonstrating different CLI usage patterns.

## Directory Structure

```
├── boxmaker.py              # Main file (Inkscape extension + CLI)
├── boxmaker_core.py         # Core box generation logic
├── boxmaker.inx             # Inkscape interface definition
├── test_boxmaker.py         # Test suite
├── cli_examples.py          # CLI usage examples
├── test_assets/             # Reference examples (keep in git)
│   ├── basic_laser_box.svg
│   ├── basic_cnc_box.svg
│   ├── box_with_dividers.svg
│   └── ...
├── test_results/            # Generated during testing (gitignored)
│   ├── test_basic_box_laser.svg
│   └── ...
└── .gitignore              # Excludes test_results/ and __pycache__/
```

## Files

- **`boxmaker.py`** - Main file (Inkscape extension + CLI)
- **`boxmaker_core.py`** - Core box generation logic
- **`boxmaker.inx`** - Inkscape interface definition (unchanged)
- **`test_boxmaker.py`** - Test suite (outputs to `test_results/`)
- **`cli_examples.py`** - CLI usage examples (outputs to `test_assets/`)
- **`test_assets/`** - Reference examples (tracked in git)
- **`test_results/`** - Test outputs (gitignored, regenerated on each test)

## Key Benefits

### For Users
- **Same Inkscape experience** - No changes to existing workflow
- **CLI access** - Generate boxes in scripts, automation, web apps
- **Validation** - Comprehensive testing ensures reliability

### For Developers  
- **Testable** - Core logic separated from UI
- **Modular** - Easy to extend or integrate
- **Maintainable** - Clear separation of concerns

## Compatibility

- ✅ **Inkscape 1.0+** - Full compatibility maintained
- ✅ **Python 3.6+** - Works standalone or in Inkscape
- ✅ **Original interface** - All existing .inx options preserved
- ✅ **Same output** - Identical SVG generation

## Testing Focus Areas

As requested, the tests focus on:

- ✅ **No dividers** vs **3 dividers** - Tests divider generation
- ✅ **3mm vs 6mm material** - Tests different material thicknesses  
- ✅ **Laser vs CNC** - Tests both cutting modes (main focus on laser)

## Error Handling

The refactored code includes proper error handling for:
- Zero or invalid dimensions
- Tab sizes too large for box dimensions
- Material thickness too large
- Invalid kerf values

## Future Enhancements

The modular structure makes it easy to add:
- Web API endpoints
- Batch processing
- Custom material presets
- Advanced optimization algorithms
- Export to other formats

---

*The core functionality remains unchanged - this refactor just makes it more accessible and testable while maintaining 100% Inkscape compatibility.*
