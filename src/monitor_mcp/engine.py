import mss
import mss.tools
from PIL import Image, ImageDraw
import io
import sys
import ctypes
import pyautogui
from typing import List, Dict, Any, Optional, Tuple

from .logging_setup import logger

class ScreenEngine:
    def __init__(self):
        self._setup_dpi_awareness()

    def _setup_dpi_awareness(self):
        """Set DPI awareness for accurate capture on Windows."""
        if sys.platform == "win32":
            try:
                # Per-monitor DPI aware
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                logger.debug("DPI Awareness set to Per-monitor.")
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                    logger.debug("DPI Awareness set to standard.")
                except Exception:
                    logger.warning("Failed to set DPI awareness.")

    def list_monitors(self) -> List[Dict[str, Any]]:
        """List all available monitors."""
        with mss.mss() as sct:
            monitors = []
            for i, mon in enumerate(sct.monitors):
                monitors.append({
                    "index": i,
                    "left": mon["left"],
                    "top": mon["top"],
                    "width": mon["width"],
                    "height": mon["height"],
                    "label": "All Monitors" if i == 0 else f"Monitor {i}"
                })
            logger.debug(f"Monitors listed: {len(monitors)} found.")
            return monitors

    def capture(self, screen_index: int = 0, resize: Optional[Tuple[int, int]] = None, draw_mouse: bool = True) -> Image.Image:
        """Capture a specific monitor and optionally resize it."""
        with mss.mss() as sct:
            if screen_index >= len(sct.monitors):
                screen_index = 0
            
            monitor = sct.monitors[screen_index]
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            if draw_mouse:
                try:
                    # Get absolute mouse position
                    mouse_x, mouse_y = pyautogui.position()
                    
                    # Calculate relative to monitor
                    rel_x = mouse_x - monitor["left"]
                    rel_y = mouse_y - monitor["top"]
                    
                    # Only draw if cursor is within the captured monitor
                    if 0 <= rel_x < monitor["width"] and 0 <= rel_y < monitor["height"]:
                        draw = ImageDraw.Draw(img)
                        # Simple cursor: a white triangle with black outline
                        cursor_size = 15
                        coords = [
                            (rel_x, rel_y),
                            (rel_x, rel_y + cursor_size),
                            (rel_x + cursor_size // 1.5, rel_y + cursor_size // 1.5)
                        ]
                        draw.polygon(coords, fill="white", outline="black")
                except Exception as e:
                    logger.error(f"Error drawing mouse: {e}")
            
            if resize:
                img.thumbnail(resize, Image.Resampling.LANCZOS)
                
            return img

    def encode_image(self, img: Image.Image, format: str = "jpeg", quality: int = 85) -> bytes:
        """Encode PIL Image to bytes."""
        buf = io.BytesIO()
        if format.lower() in ["jpg", "jpeg"]:
            # Ensure RGB for JPEG
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(buf, format="JPEG", quality=quality)
        else:
            img.save(buf, format=format.upper())
        return buf.getvalue()

    def __del__(self):
        pass
