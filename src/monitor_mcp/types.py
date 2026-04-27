from pydantic import BaseModel, Field
from typing import Optional, List
import time

class MonitorConfig(BaseModel):
    screen: int = Field(0, description="Index of the screen to monitor (0 for all, 1 for primary)")
    frequency: float = Field(2.0, description="Number of captures per second")
    max_images: int = Field(3600, description="Maximum number of images to store in the circular buffer")
    max_resolution: Optional[List[int]] = Field(None, description="Max width and height for images (e.g. [1280, 720])")

class Frame(BaseModel):
    index: int
    timestamp: float = Field(default_factory=time.time)
    data: str = Field(..., description="Base64 encoded image data")
    format: str = "jpeg"
    width: int
    height: int

class MonitoringStatus(BaseModel):
    is_active: bool
    config: Optional[MonitorConfig] = None
    buffer_size: int
    frames_captured: int
