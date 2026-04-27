from collections import deque
import threading
import os
from pathlib import Path
from typing import List, Optional, Any
from .types import Frame

class MonitorBuffer:
    def __init__(self, max_size: int, storage_path: Optional[str] = None, save_to_disk: bool = False):
        self.max_size = max_size
        self.storage_path = Path(storage_path) if storage_path else None
        self.save_to_disk = save_to_disk
        self._buffer = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._total_captured = 0
        
        if self.save_to_disk and self.storage_path:
            self.storage_path.mkdir(parents=True, exist_ok=True)

    def add_frame(self, frame_data: Any, timestamp: float, width: int, height: int):
        """Add a frame to the buffer. frame_data is usually the raw image or PIL object."""
        with self._lock:
            index = self._total_captured
            print(f"Adding frame {index} to buffer")
            self._buffer.append({
                "index": index,
                "timestamp": timestamp,
                "data": frame_data,
                "width": width,
                "height": height
            })
            self._total_captured += 1
            
            if self.save_to_disk and self.storage_path:
                # Save as JPEG for easy manual viewing
                try:
                    filename = f"frame_{index:06d}_{int(timestamp)}.jpg"
                    filepath = self.storage_path / filename
                    # frame_data is a PIL image
                    frame_data.save(filepath, "JPEG", quality=85)
                except Exception:
                    pass

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
