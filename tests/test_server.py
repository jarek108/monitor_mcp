import pytest
from unittest.mock import MagicMock, patch
from monitor_mcp.server import ObservationManager
from monitor_mcp.types import MonitorConfig
import time

@pytest.fixture
def mock_engine():
    with patch('monitor_mcp.engine.mss.mss') as mock_mss:
        # Mock monitor info
        mock_mss.return_value.monitors = [
            {"left": 0, "top": 0, "width": 1920, "height": 1080},
            {"left": 0, "top": 0, "width": 1920, "height": 1080}
        ]
        # Mock grab return
        mock_shot = MagicMock()
        mock_shot.size = (1920, 1080)
        mock_shot.bgra = b'\x00' * (1920 * 1080 * 4)
        mock_mss.return_value.grab.return_value = mock_shot
        yield mock_mss

def test_manager_lifecycle(mock_engine):
    manager = ObservationManager()
    config = MonitorConfig(frequency=10.0, max_images=10)
    
    manager.start(config)
    assert manager.get_status().is_active == True
    
    # Wait a bit for frames
    time.sleep(0.5)
    status = manager.get_status()
    assert status.frames_captured > 0
    
    manager.stop()
    assert manager.get_status().is_active == False

def test_get_imgs_logic(mock_engine):
    manager = ObservationManager()
    config = MonitorConfig(frequency=100.0, max_images=10) # Fast for testing
    manager.start(config)
    
    # Wait for buffer to fill
    time.sleep(0.2)
    manager.stop()
    
    status = manager.get_status()
    assert status.buffer_size > 0
    
    # Test tool-like retrieval (though calling manager directly here)
    frames = manager.buffer.get_frames(start=-1, count=1)
    assert len(frames) == 1
    assert frames[0]["index"] == status.frames_captured - 1
