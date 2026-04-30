import pytest
from unittest.mock import MagicMock, patch
from monitor_mcp.server import ObservationManager
from monitor_mcp.types import MonitorConfig
import time

@pytest.fixture
def mock_engine():
    with patch('monitor_mcp.server.ScreenEngine.capture') as mock_capture:
        from PIL import Image
        mock_img = Image.new('RGB', (1920, 1080), color='black')
        mock_capture.return_value = mock_img
        
        with patch('monitor_mcp.server.ScreenEngine.encode_image') as mock_encode:
            mock_encode.return_value = b'fake_image_data'
            yield mock_capture

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
    frames = manager.buffer.get_frames(start_frame_index=-1, frame_count=1)
    assert len(frames) == 1
    assert frames[0]["index"] == status.frames_captured - 1
