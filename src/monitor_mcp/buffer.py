from collections import deque
import threading
from typing import List, Optional, Any
from .types import Frame

class MonitorBuffer:
    def __init__(self, max_size: int):
        self.max_size = max_size
        self._buffer = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._total_captured = 0

    def add_frame(self, frame_data: Any, timestamp: float, width: int, height: int):
        """Add a frame to the buffer. frame_data is usually the raw image or PIL object."""
        with self._lock:
            # We store the raw data/object and metadata. 
            # Encoding happens only when requested by the LLM.
            self._buffer.append({
                "index": self._total_captured,
                "timestamp": timestamp,
                "data": frame_data,
                "width": width,
                "height": height
            })
            self._total_captured += 1

    def get_frames(self, start: int = -1, count: int = 1, interval: int = 1) -> List[dict]:
        """
        Retrieve frames based on indexing logic.
        start: Start index (negative for relative to end)
        count: Number of frames to retrieve
        interval: Step/Stride (negative to go backwards)
        """
        with self._lock:
            if not self._buffer:
                return []

            available_count = len(self._buffer)
            
            # Resolve start index
            if start < 0:
                start_idx = available_count + start
            else:
                # Absolute index search - find the frame with the requested index
                # Since indices are monotonically increasing, we can calculate the offset
                first_index = self._buffer[0]["index"]
                start_idx = start - first_index
            
            # Clamp start_idx
            if start_idx < 0:
                start_idx = 0
            if start_idx >= available_count:
                start_idx = available_count - 1

            result = []
            current_idx = start_idx
            
            for _ in range(count):
                if 0 <= current_idx < available_count:
                    result.append(self._buffer[current_idx])
                    current_idx += interval
                else:
                    break
            
            return result

    @property
    def total_captured(self) -> int:
        return self._total_captured

    @property
    def current_size(self) -> int:
        return len(self._buffer)

    def clear(self):
        with self._lock:
            self._buffer.clear()
            self._total_captured = 0
