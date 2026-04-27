import pytest
from monitor_mcp.buffer import MonitorBuffer

def test_buffer_basic_add():
    buf = MonitorBuffer(max_size=10)
    buf.add_frame("data1", 100.0, 100, 100, size_bytes=1024)
    assert buf.current_size == 1
    assert buf.total_captured == 1
    
    frames = buf.get_frames(start=-1, count=1)
    assert len(frames) == 1
    assert frames[0]["data"] == "data1"
    assert frames[0]["size_bytes"] == 1024

def test_buffer_circular_wrap():
    buf = MonitorBuffer(max_size=3)
    buf.add_frame("1", 1.0, 10, 10, size_bytes=100)
    buf.add_frame("2", 2.0, 10, 10, size_bytes=100)
    buf.add_frame("3", 3.0, 10, 10, size_bytes=100)
    buf.add_frame("4", 4.0, 10, 10, size_bytes=100) # 1 should be gone
    
    assert buf.current_size == 3
    assert buf.total_captured == 4
    
    frames = buf.get_frames(start=0, count=3)
    assert frames[0]["data"] == "2"
    assert frames[1]["data"] == "3"
    assert frames[2]["data"] == "4"

def test_buffer_complex_indexing():
    buf = MonitorBuffer(max_size=100)
    for i in range(20):
        buf.add_frame(str(i), float(i), 10, 10, size_bytes=10)
    
    # LLM case: get 10 images, from the last one (-1), jumping backwards every 4 images
    # get_imgs(start = -1, count = 10, interval = -4)
    frames = buf.get_frames(start=-1, count=5, interval=-4)
    # Expected indices in buffer: 19, 15, 11, 7, 3
    assert len(frames) == 5
    assert frames[0]["data"] == "19"
    assert frames[1]["data"] == "15"
    assert frames[2]["data"] == "11"
    assert frames[3]["data"] == "7"
    assert frames[4]["data"] == "3"

def test_buffer_absolute_indexing():
    buf = MonitorBuffer(max_size=5)
    for i in range(10):
        buf.add_frame(str(i), float(i), 10, 10)
    
    # Total captured 10, max size 5. Indices in buffer: [5, 6, 7, 8, 9]
    # start = 7 (absolute)
    frames = buf.get_frames(start=7, count=2, interval=1)
    assert len(frames) == 2
    assert frames[0]["data"] == "7"
    assert frames[1]["data"] == "8"
    
    # start = 4 (gone) -> should clamp to start of buffer (idx 5)
    frames = buf.get_frames(start=4, count=1)
    assert frames[0]["data"] == "5"
