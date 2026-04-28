import threading
import time
import base64
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple
from mcp.server.fastmcp import FastMCP
from .engine import ScreenEngine
from .buffer import MonitorBuffer
from .types import MonitorConfig, Frame, MonitoringStatus

from .logging_setup import logger

class ObservationManager:
    def __init__(self):
        self.engine = ScreenEngine()
        self.buffer: Optional[MonitorBuffer] = None
        self.config: Optional[MonitorConfig] = None
        
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.default_config = self._load_default_config()
        self._fps_frames = [] # timestamps for FPS calculation
        self._current_fps = 0.0

    def _load_default_config(self) -> MonitorConfig:
        config_path = Path("config.json")
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                    return MonitorConfig(**data)
            except Exception as e:
                logger.error(f"Failed to load config.json: {e}")
        return MonitorConfig()

    def start(self, config: MonitorConfig):
        with self._lock:
            logger.info(f"Starting monitoring with config: {config}")
            if self._thread and self._thread.is_alive():
                logger.info("Stopping existing thread...")
                self.stop()
            
            self.config = config
            
            # Generate Session ID and Subfolder
            session_id = datetime.now().strftime("%y%m%d_%H%M%S")
            session_path = Path(config.storage_path) / session_id
            session_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Session directory created: {session_path}")

            # Save run_config.json
            config_file = session_path / "run_config.json"
            with open(config_file, "w") as f:
                f.write(config.model_dump_json(indent=4))

            # Reset buffer only if requested or if size changed
            # Note: We now pass the SESSION path to the buffer, not the root path
            if config.reset_cache or self.buffer is None or self.buffer.max_size != config.max_images:
                logger.info("Initializing new buffer (reset_cache=True or size changed)")
                self.buffer = MonitorBuffer(
                    max_size=config.max_images,
                    storage_path=str(session_path),
                    save_to_disk=config.save_to_disk
                )
            else:
                logger.info("Reusing existing buffer (reset_cache=False)")
                # Update settings for current session
                self.buffer.storage_path = session_path
                self.buffer.save_to_disk = config.save_to_disk

            self._stop_event.clear()
            self._fps_frames = []
            self._current_fps = 0.0
            
            self._thread = threading.Thread(
                target=self._run_loop,
                daemon=True,
                name="ObservationLoop"
            )
            self._thread.start()

    def stop(self):
        with self._lock:
            logger.info("Stopping monitoring...")
            self._stop_event.set()
            if self._thread:
                self._thread.join(timeout=2.0)
                self._thread = None
            self._current_fps = 0.0

    def _run_loop(self):
        logger.info("Observation loop started.")
        if not self.config or not self.buffer:
            logger.error("Missing config or buffer, exiting loop.")
            return

        interval = 1.0 / self.config.frequency
        resize_tuple = tuple(self.config.max_resolution) if self.config.max_resolution else None
        
        while not self._stop_event.is_set():
            loop_start = time.time()
            
            try:
                img = self.engine.capture(
                    screen_index=self.config.screen,
                    resize=resize_tuple,
                    draw_mouse=self.config.draw_mouse
                )
                
                # Encode once to get actual compressed size for reporting
                img_bytes = self.engine.encode_image(img)
                actual_size = len(img_bytes)

                self.buffer.add_frame(
                    frame_data=img,
                    timestamp=loop_start,
                    width=img.width,
                    height=img.height,
                    size_bytes=actual_size
                )
                
                # Update FPS
                now = time.time()
                self._fps_frames.append(now)
                # Keep only last 10 frames or frames from last 2 seconds
                self._fps_frames = [t for t in self._fps_frames if now - t < 2.0]
                if len(self._fps_frames) > 1:
                    self._current_fps = len(self._fps_frames) / (self._fps_frames[-1] - self._fps_frames[0] + 0.0001)
                else:
                    self._current_fps = 0.0

            except Exception as e:
                logger.error(f"Capture error: {e}")
                import traceback
                logger.debug(traceback.format_exc())
            
            # Precise sleep to maintain frequency
            elapsed = time.time() - loop_start
            sleep_time = max(0, interval - elapsed)
            time.sleep(sleep_time)
        logger.info("Observation loop stopped.")

    def get_status(self) -> MonitoringStatus:
        is_active = self._thread is not None and self._thread.is_alive()
        
        last_frame_size_kb = 0.0
        total_buffer_size_mb = 0.0
        
        if self.buffer and self.buffer.current_size > 0:
            with self.buffer._lock:
                last_frame = self.buffer._buffer[-1]
                last_frame_size_kb = last_frame.get("size_bytes", 0) / 1024.0
                
                total_bytes = sum(f.get("size_bytes", 0) for f in self.buffer._buffer)
                total_buffer_size_mb = total_bytes / (1024.0 * 1024.0)

        return MonitoringStatus(
            is_active=is_active,
            config=self.config,
            buffer_size=self.buffer.current_size if self.buffer else 0,
            frames_captured=self.buffer.total_captured if self.buffer else 0,
            current_fps=round(self._current_fps, 1),
            last_frame_size_kb=round(last_frame_size_kb, 1),
            total_buffer_size_mb=round(total_buffer_size_mb, 1)
        )

from .simulator import FolderFeeder
from .analyzer import AIAnalyzer

class SimulationManager:
    def __init__(self):
        from .buffer import MonitorBuffer
        self.buffer = MonitorBuffer(max_size=3600)
        self.feeder = None
        self.analyzer = None
        self._lock = threading.Lock()
        self.current_session_id = None
        self.current_config = None

    @property
    def is_running(self):
        running_feeder = bool(self.feeder and not self.feeder.is_finished)
        running_analyzer = bool(self.analyzer and self.analyzer._thread and self.analyzer._thread.is_alive())
        return running_feeder or running_analyzer

    def start(self, folder_path, model, prompt, delay, count, interval, offset):
        with self._lock:
            self.stop()
            self.buffer.clear()
            self.current_session_id = datetime.now().strftime("%y%m%d_%H%M%S")
            self.current_config = {
                "folder": folder_path,
                "model": model,
                "prompt": prompt,
                "delay": delay,
                "count": count,
                "interval": interval,
                "offset": offset
            }
            
            # Simulation results go into a subfolder of the test folder (or a fixed path)
            # Let's use the monitoring storage path if available, or just the project root
            storage_root = Path(manager.default_config.storage_path)
            session_path = storage_root / f"sim_{self.current_session_id}"
            session_path.mkdir(parents=True, exist_ok=True)

            # Save run_config.json for simulation
            config_file = session_path / "run_config.json"
            with open(config_file, "w") as f:
                f.write(json.dumps(self.current_config, indent=4))

            self.feeder = FolderFeeder(folder_path, self.buffer)
            self.analyzer = AIAnalyzer(self.buffer, log_dir=str(session_path))
            
            self.feeder.start()
            self.analyzer.start(model, prompt, delay, count, interval, offset, session_id=self.current_session_id)
            logger.info(f"Simulation started (Session: {self.current_session_id}, Dir: {session_path}).")

    def stop(self):
        with self._lock:
            if self.feeder:
                self.feeder.stop()
                self.feeder = None
            if self.analyzer:
                self.analyzer.stop()
                self.analyzer = None
            logger.info("Simulation stopped.")

# Initialize MCP Server
mcp = FastMCP("monitor_mcp")
manager = ObservationManager()
sim_manager = SimulationManager()

@mcp.tool()
def start_monitoring(
    screen: Optional[int] = None,
    frequency: Optional[float] = None,
    max_images: Optional[int] = None,
    max_resolution: Optional[List[int]] = None,
    storage_path: Optional[str] = None,
    save_to_disk: Optional[bool] = None,
    reset_cache: Optional[bool] = None,
    draw_mouse: Optional[bool] = None
) -> str:
    """
    Start monitoring the screen.
    :param screen: Index of the monitor (0 for all, 1 for primary)
    :param frequency: Captures per second
    :param max_images: Max images in circular buffer
    :param max_resolution: Optional [width, height] constraint
    :param storage_path: Folder to save images to
    :param save_to_disk: Whether to save every frame to disk
    :param reset_cache: Whether to clear the buffer on start
    :param draw_mouse: Whether to draw the mouse cursor on frames
    """
    # Use defaults from config.json if not provided
    defaults = manager.default_config
    
    config = MonitorConfig(
        screen=screen if screen is not None else defaults.screen,
        frequency=frequency if frequency is not None else defaults.frequency,
        max_images=max_images if max_images is not None else defaults.max_images,
        max_resolution=max_resolution if max_resolution is not None else defaults.max_resolution,
        storage_path=storage_path if storage_path is not None else defaults.storage_path,
        save_to_disk=save_to_disk if save_to_disk is not None else defaults.save_to_disk,
        reset_cache=reset_cache if reset_cache is not None else defaults.reset_cache,
        draw_mouse=draw_mouse if draw_mouse is not None else defaults.draw_mouse
    )
    manager.start(config)
    return f"Monitoring started: {config}"

@mcp.tool()
def stop_monitoring() -> str:
    """Stop the current monitoring procedure."""
    manager.stop()
    return "Monitoring stopped."

@mcp.tool()
def get_imgs(
    start: int = -1,
    count: int = 1,
    interval: int = 1
) -> List[Frame]:
    """
    Retrieve images from the buffer.
    :param start: Start index (negative for relative to end)
    :param count: How many images to get
    :param interval: Step between images (negative to go backwards)
    """
    if not manager.buffer:
        return []
        
    raw_frames = manager.buffer.get_frames(start=start, count=count, interval=interval)
    processed_frames = []
    
    for f in raw_frames:
        # Encode PIL image to Base64
        img_bytes = manager.engine.encode_image(f["data"])
        b64_data = base64.b64encode(img_bytes).decode("utf-8")
        
        processed_frames.append(Frame(
            index=f["index"],
            timestamp=f["timestamp"],
            data=b64_data,
            width=f["width"],
            height=f["height"]
        ))
        
    return processed_frames

@mcp.tool()
def get_monitoring_status() -> MonitoringStatus:
    """Get the current status of the monitoring server."""
    return manager.get_status()

@mcp.tool()
def list_monitors() -> List[dict]:
    """List all available monitors and their dimensions."""
    return manager.engine.list_monitors()

def main():
    mcp.run()

if __name__ == "__main__":
    main()
