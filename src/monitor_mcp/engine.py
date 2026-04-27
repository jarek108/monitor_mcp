import mss
import mss.tools
from PIL import Image
import io
import sys
import ctypes
from typing import List, Dict, Any, Optional, Tuple

class ScreenEngine:
    def __init__(self):
        self._sct = mss.mss()
        self._setup_dpi_awareness()

    def _setup_dpi_awareness(self):
        """Set DPI awareness for accurate capture on Windows."""
        if sys.platform == "win32":
            try:
                # Per-monitor DPI aware
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

    def list_monitors(self) -> List[Dict[str, Any]]:
        """List all available monitors."""
        monitors = []
        for i, mon in enumerate(self._sct.monitors):
            monitors.append({
                "index": i,
                "left": mon["left"],
                "top": mon["top"],
                "width": mon["width"],
                "height": mon["height"],
                "label": "All Monitors" if i == 0 else f"Monitor {i}"
            })
        return monitors

    def capture(self, screen_index: int = 0, resize: Optional[Tuple[int, int]] = None) -> Image.Image:
        """Capture a specific monitor and optionally resize it."""
        if screen_index >= len(self._sct.monitors):
            screen_index = 0
            
        sct_img = self._sct.grab(self._sct.monitors[screen_index])
        img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
        
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
        if hasattr(self, "_sct"):
            self._sct.close()
