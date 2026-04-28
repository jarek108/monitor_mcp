import os
import time
import threading
from pathlib import Path
from datetime import datetime
from PIL import Image
from .buffer import MonitorBuffer

from .logging_setup import logger

class FolderFeeder:
    def __init__(self, folder_path: str, buffer: MonitorBuffer):
        self.folder_path = Path(folder_path)
        self.buffer = buffer
        self._stop_event = threading.Event()
        self._thread = None
        self.is_finished = False

    def start(self):
        self._stop_event.clear()
        self.is_finished = False
        self._thread = threading.Thread(target=self._run, daemon=True, name="FolderFeeder")
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _parse_timestamp(self, filename: str) -> float:
        """Parse frame_yy_mm_dd_HH_MM_SS_mmmm_index.jpg into unix timestamp."""
        try:
            parts = filename.replace(".jpg", "").split("_")
            # parts[1:7] is yy, mm, dd, HH, MM, SS
            # parts[7] is mmmm (fractional seconds)
            dt_str = "_".join(parts[1:7])
            ms_str = parts[7]
            
            dt = datetime.strptime(dt_str, "%y_%m_%d_%H_%M_%S")
            # Add the fractional part (e.g. 3485 -> 0.3485)
            ts = dt.timestamp() + (int(ms_str) / 10000.0)
            return ts
        except Exception as e:
            logger.error(f"Error parsing filename {filename}: {e}")
            return time.time()

    def _run(self):
        logger.info(f"Starting playback from {self.folder_path}...")
        files = sorted([f for f in self.folder_path.glob("frame_*.jpg")])
        if not files:
            logger.warning(f"No frames found in {self.folder_path}")
            self.is_finished = True
            return

        last_ts = None
        
        for f in files:
            if self._stop_event.is_set():
                break

            current_ts = self._parse_timestamp(f.name)
            
            # Pacing
            if last_ts is not None:
                delta = current_ts - last_ts
                if delta > 0:
                    # Limit sleep to something reasonable if there's a huge gap
                    time.sleep(min(delta, 5.0))
            
            try:
                img = Image.open(f)
                img.load() # Load into memory
                self.buffer.add_frame(
                    frame_data=img,
                    timestamp=current_ts,
                    width=img.width,
                    height=img.height,
                    size_bytes=f.stat().st_size
                )
            except Exception as e:
                logger.error(f"Error loading frame {f}: {e}")

            last_ts = current_ts

        logger.info("Playback finished.")
        self.is_finished = True
