import pytest
from monitor_mcp.engine import ScreenEngine
from PIL import Image

def test_engine_list_monitors():
    engine = ScreenEngine()
    monitors = engine.list_monitors()
    assert len(monitors) > 0
    assert monitors[0]["index"] == 0
    assert "width" in monitors[0]

def test_engine_capture():
    engine = ScreenEngine()
    img = engine.capture(screen_index=0)
    assert isinstance(img, Image.Image)
    assert img.width > 0
    assert img.height > 0

def test_engine_capture_resize():
    engine = ScreenEngine()
    img = engine.capture(screen_index=0, resize=(100, 100))
    # img.thumbnail preserves aspect ratio, so it might not be exactly 100x100
    assert img.width <= 100
    assert img.height <= 100
