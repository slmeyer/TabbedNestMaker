#!/usr/bin/env python3
"""
Test script for BoxMaker functionality
Tests various configurations to ensure the refactored code works correctly
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the current directory to the path to import our modules
sys.path.insert(0, str(Path(__file__).parent))

from boxmaker_core import BoxMakerCore
from boxmaker_exceptions import DimensionError, TabError, MaterialError


def test_basic_box():
    """Test basic box generation"""
    print("Testing basic box generation...")
    
    core = BoxMakerCore()
    core.set_parameters(
        length=100.0,
        width=80.0,
        height=50.0,
        thickness=3.0,
        kerf=0.1,
        tab=15.0,
        tabtype=0  # Laser
    )
    
    try:
        result = core.generate_box()
        assert len(result['paths']) > 0, "Should generate some paths"
        print("✓ Basic box test passed")
        return True
    except Exception as e:
        print(f"✗ Basic box test failed: {e}")
        return False


def test_box_with_dividers():
    """Test box with 3 dividers"""
    print("Testing box with 3 dividers...")
    
    core = BoxMakerCore()
    core.set_parameters(
        length=120.0,
        width=100.0,
        height=60.0,
        thickness=3.0,
        kerf=0.1,
        tab=20.0,
        div_l=2,  # 2 dividers along length
        div_w=1,  # 1 divider along width
        tabtype=0  # Laser
    )
    
    try:
        result = core.generate_box()
        assert len(result['paths']) > 0, "Should generate paths for box and dividers"
        print("✓ Box with dividers test passed")
        return True
    except Exception as e:
        print(f"✗ Box with dividers test failed: {e}")
        return False


def test_different_material_thickness():
    """Test with different material thickness (6mm instead of 3mm)"""
    print("Testing with 6mm material thickness...")
    
    core = BoxMakerCore()
    core.set_parameters(
        length=150.0,
        width=100.0,
        height=75.0,
        thickness=6.0,  # Thicker material
        kerf=0.2,       # Larger kerf for thicker material
        tab=25.0,
        tabtype=0  # Laser
    )
    
    try:
        result = core.generate_box()
        assert len(result['paths']) > 0, "Should generate paths with thicker material"
        print("✓ Different material thickness test passed")
        return True
    except Exception as e:
        print(f"✗ Different material thickness test failed: {e}")
        return False


def test_cnc_vs_laser():
    """Test CNC (dogbone) vs Laser cutting"""
    print("Testing CNC vs Laser cutting...")
    
    # Test laser cutting
    core_laser = BoxMakerCore()
    core_laser.set_parameters(
        length=100.0,
        width=80.0,
        height=50.0,
        thickness=3.0,
        kerf=0.1,
        tab=15.0,
        tabtype=0  # Laser
    )
    
    # Test CNC cutting (dogbone)
    core_cnc = BoxMakerCore()
    core_cnc.set_parameters(
        length=100.0,
        width=80.0,
        height=50.0,
        thickness=3.0,
        kerf=0.1,
        tab=15.0,
        tabtype=1  # CNC/Dogbone
    )
    
    try:
        result_laser = core_laser.generate_box()
        result_cnc = core_cnc.generate_box()
        
        assert len(result_laser['paths']) > 0, "Laser should generate paths"
        assert len(result_cnc['paths']) > 0, "CNC should generate paths"
        
        # The paths should be different due to dogbone cuts
        assert result_laser['paths'] != result_cnc['paths'], "Laser and CNC paths should differ"
        
        print("✓ CNC vs Laser test passed")
        return True
    except Exception as e:
        print(f"✗ CNC vs Laser test failed: {e}")
        return False


def test_svg_generation():
    """Test SVG file generation"""
    print("Testing SVG generation...")
    
    core = BoxMakerCore()
    core.set_parameters(
        length=100.0,
        width=80.0,
        height=50.0,
        thickness=3.0,
        kerf=0.1,
        tab=15.0
    )
    
    try:
        svg_content = core.generate_svg()
        
        # Basic SVG validation
        assert svg_content.startswith('<?xml'), "Should start with XML declaration"
        assert '<svg' in svg_content, "Should contain SVG element"
        assert '</svg>' in svg_content, "Should end with SVG closing tag"
        assert 'path' in svg_content, "Should contain path elements"
        
        # Write to temporary file to test file I/O
        with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
            f.write(svg_content)
            temp_path = f.name
        
        # Verify file was written
        assert os.path.exists(temp_path), "SVG file should be created"
        
        # Clean up
        os.unlink(temp_path)
        
        print("✓ SVG generation test passed")
        return True
    except Exception as e:
        print(f"✗ SVG generation test failed: {e}")
        return False


def test_error_conditions():
    """Test error handling"""
    print("Testing error conditions...")
    
    # Test zero dimensions
    core = BoxMakerCore()
    try:
        core.set_parameters(length=0, width=100, height=50)
        core.generate_box()
        print("✗ Should have raised error for zero dimensions")
        return False
    except DimensionError:
        print("✓ Correctly handled zero dimensions")
      # Test tab too large (physical constraint - larger than dimension/3)
    core = BoxMakerCore()
    try:
        # 200x250x100mm box with 80mm tabs (larger than 100mm/3 = 33mm)
        core.set_parameters(length=200, width=250, height=100, tab=80, thickness=3)
        core.generate_box()
        print("✗ Should have raised error for oversized tab")
        return False
    except TabError:
        print("✓ Correctly handled oversized tab")    # Test thickness too large for dimensions
    core = BoxMakerCore()
    try:
        # Small 6x6x6cm box with 3.5cm thickness (more than half)
        core.set_parameters(length=60, width=60, height=60, thickness=35, tab=19)  # 19mm < 20mm (60/3) and > 17.5mm (35*0.5)
        core.generate_box()
        print("✗ Should have raised error for excessive thickness")
        return False
    except MaterialError:
        print("✓ Correctly handled excessive thickness")
    
    return True


def test_box_layouts():
    """Test different box layouts"""
    print("Testing different box layouts...")
    
    layouts = [1, 2, 3]  # Diagramatic, 3-piece, Inline
    
    for layout in layouts:
        core = BoxMakerCore()
        core.set_parameters(
            length=100.0,
            width=80.0,
            height=50.0,
            thickness=3.0,
            kerf=0.1,
            tab=15.0,
            style=layout
        )
        
        try:
            result = core.generate_box()
            assert len(result['paths']) > 0, f"Layout {layout} should generate paths"
        except Exception as e:
            print(f"✗ Layout {layout} test failed: {e}")
            return False
    
    print("✓ All layout tests passed")
    return True


def test_save_test_files():
    """Generate test files for manual inspection"""
    print("Generating test files for manual inspection...")
    
    # Ensure test_results directory exists
    test_results_dir = Path("test_results")
    test_results_dir.mkdir(exist_ok=True)
    
    test_cases = [
        {
            'name': 'basic_box_laser',
            'params': {
                'length': 100.0, 'width': 80.0, 'height': 50.0,
                'thickness': 3.0, 'kerf': 0.1, 'tab': 15.0, 'tabtype': 0
            }
        },
        {
            'name': 'basic_box_cnc',
            'params': {
                'length': 100.0, 'width': 80.0, 'height': 50.0,
                'thickness': 3.0, 'kerf': 0.1, 'tab': 15.0, 'tabtype': 1
            }
        },
        {
            'name': 'box_with_dividers',
            'params': {
                'length': 120.0, 'width': 100.0, 'height': 60.0,
                'thickness': 3.0, 'kerf': 0.1, 'tab': 20.0,
                'div_l': 2, 'div_w': 1, 'tabtype': 0
            }
        },
        {
            'name': 'thick_material_box',
            'params': {
                'length': 150.0, 'width': 100.0, 'height': 75.0,
                'thickness': 6.0, 'kerf': 0.2, 'tab': 25.0, 'tabtype': 0
            }
        }
    ]
    
    try:
        for test_case in test_cases:
            core = BoxMakerCore()
            core.set_parameters(**test_case['params'])
            
            svg_content = core.generate_svg()
            
            output_file = test_results_dir / f"test_{test_case['name']}.svg"
            with open(output_file, 'w') as f:
                f.write(svg_content)
            
            print(f"  Generated: {output_file}")
        
        print("✓ Test files generated successfully")
        return True
    except Exception as e:
        print(f"✗ Test file generation failed: {e}")
        return False


def test_realistic_compartment_box():
    """Test realistic compartment box (20x25x10cm with 3 dividers)"""
    print("Testing realistic compartment box...")
    
    core = BoxMakerCore()
    # Your example: 200x250x100mm box with 3mm material, 12mm tabs, 3 compartments
    core.set_parameters(
        length=200, width=250, height=100,
        thickness=3, kerf=0.1, tab=12,
        div_l=3  # 3 compartments in length direction
    )
    
    try:
        core.generate_box()
        print("✓ Realistic compartment box test passed")
        return True
    except Exception as e:
        print(f"✗ Realistic compartment box test failed: {e}")
        return False


def test_thin_tabs():
    """Test tabs thinner than material thickness (allowed but weak)"""
    print("Testing thin tabs (weaker but allowed)...")
    
    core = BoxMakerCore()
    # 6mm thickness with 4mm tabs (2/3 ratio) - should work but be weak
    core.set_parameters(length=200, width=250, height=100, thickness=6, tab=4, div_l=3)
    
    try:
        core.generate_box()
        svg_content = core.generate_svg()
        
        # Should generate valid SVG
        if '<svg' in svg_content and '</svg>' in svg_content:
            print("✓ Thin tabs test passed (tabs allowed but may be weak)")
            return True
        else:
            print("✗ Failed to generate valid SVG for thin tabs")
            return False
    except Exception as e:
        print(f"✗ Unexpected error with thin tabs: {e}")
        return False


def test_large_box_big_tabs():
    """Test large box with proportionally large tabs"""
    print("Testing large box with big tabs...")
    
    core = BoxMakerCore()
    # Large 60x40x30cm box with 6mm material and 60mm tabs (10x thickness)
    core.set_parameters(
        length=600, width=400, height=300,
        thickness=6, tab=60  # 60mm tabs (10x thickness) - should work for large box
    )
    
    try:
        core.generate_box()
        svg_content = core.generate_svg()
        
        if '<svg' in svg_content and '</svg>' in svg_content:
            print("✓ Large box with big tabs test passed")
            return True
        else:
            print("✗ Failed to generate valid SVG for large box")
            return False
    except Exception as e:
        print(f"✗ Large box test failed: {e}")
        return False


def _swift_core(**over):
    from boxmaker_constants import SWIFT_PRESET
    core = BoxMakerCore()
    params = dict(SWIFT_PRESET)
    params['inside'] = 1
    params.update(over)
    core.set_parameters(**params)
    return core


def _closed_paths(core):
    return [p['data'] for p in core.paths if p['data'].rstrip().endswith('Z')]


def test_swift_preset_hole():
    """Swift preset: exactly one oval 65x28 entrance (kerf compensated)"""
    print("Testing swift preset entrance hole...")
    core = _swift_core()
    core.generate_box()
    holes = _closed_paths(core)
    if len(holes) != 1 or holes[0].count(' A ') != 4:
        print(f"✗ expected one rounded hole, got {holes}")
        return False
    import re
    xs = [float(x) for x in re.findall(r'(?:M|L|[01] [01] [01]) (-?[\d.]+),', holes[0])]
    # arcs end points span the full 65 mm minus one kerf (0.1)
    if abs((max(xs) - min(xs)) - (65 - 0.1)) > 0.01:
        print(f"✗ unexpected hole length {max(xs) - min(xs)}")
        return False
    print("✓ Swift entrance hole test passed")
    return True


def test_hole_variants():
    """Round / rect / rounded rect, sides, and placement errors"""
    print("Testing hole variants...")
    ok = True
    core = BoxMakerCore()
    for r, arcs in ((0, 0), (3, 4), (99, 4)):   # oversize radius is clamped
        if core.rounded_rect_path(0, 0, 20, 10, r).count('A') != arcs:
            print(f"✗ radius {r}: expected {arcs} arcs"); ok = False
    for kw in (dict(hole_type='round', hole_diameter=32, hole_x=None, hole_y=None),
               dict(hole_type='rect', hole_width=50, hole_height=40, hole_radius=0, hole_x=None, hole_y=None),
               dict(hole_side='small', hole_type='round', hole_diameter=40, hole_x=None, hole_y=None)):
        c = _swift_core(**kw)
        c.generate_box()
        if len(_closed_paths(c)) != 1:
            print(f"✗ {kw}: expected one hole"); ok = False
    c = _swift_core(hole_type='none')
    c.generate_box()
    if _closed_paths(c):
        print("✗ hole_type none must not add a hole"); ok = False
    for kw in (dict(hole_y=400), dict(hole_x=2), dict(hole_width=500), dict(boxtype=6), dict(hole_type='star')):
        try:
            _swift_core(**kw).generate_box()
            print(f"✗ {kw}: should have raised ValueError"); ok = False
        except ValueError:
            pass
    print("✓ Hole variants test passed" if ok else "✗ Hole variants test failed")
    return ok


def test_hole_side_selection():
    """'big' picks the larger wall pair, 'small' the other one"""
    print("Testing big/small wall selection...")
    core = BoxMakerCore()
    core.set_parameters(hole_side='big')
    ok = core._hole_target_names(300, 100)[0] in ('bk', 'ft') and core._hole_target_names(100, 300)[0] in ('lt', 'rt')
    core.set_parameters(hole_side='small')
    ok = ok and core._hole_target_names(300, 100)[0] in ('lt', 'rt') and core._hole_target_names(100, 300)[0] in ('bk', 'ft')
    print("✓ Wall selection test passed" if ok else "✗ Wall selection test failed")
    return ok


def test_cli_defaults_are_swift_box():
    """CLI with no options = swift box; --preset generic = old plain box"""
    import subprocess
    print("Testing CLI defaults...")
    here = str(Path(__file__).parent)
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, 'd.svg')
        def run(*a):
            return subprocess.run([sys.executable, 'boxmaker.py', *a, '-o', out], cwd=here,
                                  capture_output=True, text=True)
        r = run()
        if r.returncode != 0 or ' A ' not in open(out).read():
            print("✗ default run should give an entrance hole:", r.stderr); return False
        r = run('--preset', 'generic')
        if r.returncode != 0 or ' A ' in open(out).read():
            print("✗ generic preset should have no hole:", r.stderr); return False
        if run('--hole-y', '999').returncode == 0:
            print("✗ impossible hole position should fail"); return False
    print("✓ CLI defaults test passed")
    return True


def run_all_tests():
    """Run all tests"""
    print("Running BoxMaker tests...\n")
    
    tests = [
        test_basic_box,
        test_box_with_dividers,
        test_different_material_thickness,
        test_cnc_vs_laser,
        test_svg_generation,
        test_error_conditions,
        test_box_layouts,
        test_save_test_files,
        test_realistic_compartment_box,
        test_thin_tabs,
        test_large_box_big_tabs,
        test_swift_preset_hole,
        test_hole_variants,
        test_hole_side_selection,
        test_cli_defaults_are_swift_box
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()  # Empty line between tests
    
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! The refactor was successful.")
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
