from collections import deque
import threading
import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Any
from PIL import Image
from .types import Frame

from .logging_setup import logger

class MonitorBuffer:
    def __init__(self, max_size: int, storage_path: Optional[str] = None, save_to_disk: bool = False):
        self.max_size = max_size
        self.storage_path = Path(storage_path) if storage_path else None
        self.save_to_disk = save_to_disk
        self._buffer = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._total_captured = 0
        
        if self.save_to_disk and self.storage_path:
            logger.info(f"Initializing disk storage at {self.storage_path}")
            self.storage_path.mkdir(parents=True, exist_ok=True)

    def add_frame(self, frame_data: Any, timestamp: float, width: int, height: int, size_bytes: Optional[int] = None):
        """Add a frame to the buffer. frame_data is usually the raw image or PIL object."""
        with self._lock:
            index = self._total_captured
            # Use provided size or fall back to raw estimation
            actual_size = size_bytes if size_bytes is not None else (width * height * 3)
            
            logger.debug(f"Adding frame {index} to buffer ({width}x{height}, ~{actual_size/1024:.1f} KB)")
            
            final_data = frame_data
            data_type = "pil"

            if self.save_to_disk and self.storage_path:
                # Save as JPEG for easy manual viewing
                try:
                    dt = datetime.fromtimestamp(timestamp)
                    # Format: yy_mm_dd_HH_MM_SS_mmmm (4 digits of milliseconds/fractional)
                    dt_str = dt.strftime("%y_%m_%d_%H_%M_%S")
                    ms_str = dt.strftime("%f")[:4]
                    filename = f"frame_{dt_str}_{ms_str}_{index:06d}.jpg"
                    filepath = self.storage_path / filename
                    # frame_data is a PIL image
                    frame_data.save(filepath, "JPEG", quality=85)
                    
                    # OFF-LOAD FROM MEMORY: Store the path instead of PIL image
                    final_data = filepath
                    data_type = "path"
                except Exception as e:
                    logger.error(f"Failed to save frame {index} to disk: {e}")
                    # Fallback to keeping in memory if save fails
                    pass

            self._buffer.append({
                "index": index,
                "timestamp": timestamp,
                "data": final_data,
                "data_type": data_type,
                "width": width,
                "height": height,
                "size_bytes": actual_size
            })
            self._total_captured += 1

    def get_frames(self, start_frame_index: int = -1, frame_count: int = 1, frame_interval: int = 1) -> List[dict]:
        """
        Retrieve frames based on indexing logic.
        start_frame_index: Start index (negative for relative to the end)
        frame_count: Number of frames to retrieve
        frame_interval: Step/Stride (negative to go backwards)
        """
        with self._lock:
            if not self._buffer:
                return []

            available_frame_count = len(self._buffer)
            
            # Resolve start index
            if start_frame_index < 0:
                resolved_start_idx = available_frame_count + start_frame_index
            else:
                # Absolute index search - find the frame with the requested index
                first_index = self._buffer[0]["index"]
                resolved_start_idx = start_frame_index - first_index
            
            # Clamp resolved_start_idx
            if resolved_start_idx < 0:
                resolved_start_idx = 0
            if resolved_start_idx >= available_frame_count:
                resolved_start_idx = available_frame_count - 1

            result = []
            current_idx = resolved_start_idx
            
            for _ in range(frame_count):
                if 0 <= current_idx < available_frame_count:
                    frame = self._buffer[current_idx].copy()
                    
                    # ON-DEMAND LOADING: If data is a path, load it now
                    if frame.get("data_type") == "path":
                        try:
                            frame["data"] = Image.open(frame["data"])
                            # We don't change data_type in the copy, just the data itself
                        except Exception as e:
                            logger.error(f"Failed to load frame from disk: {e}")
                            # Skip this frame if it can't be loaded
                            current_idx += frame_interval
                            continue

                    result.append(frame)
                    current_idx += frame_interval
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
