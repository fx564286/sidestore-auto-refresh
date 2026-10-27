from pathlib import Path

def test_patch_has_expected_markers():
    s = Path('scripts/patch_v137_rotation_glass_owner.py').read_text()
    assert 'SCARLET_V137_TOUCH_SETTLE' in s
    assert 'SCARLET_V137_SCENE_OWNER' in s
    assert 'SCARLET_V137_REGULAR_GLASS' in s
