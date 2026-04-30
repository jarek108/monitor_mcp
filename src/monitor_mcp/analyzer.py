import time
import threading
import base64
import io
import json
import os
from datetime import datetime
from pathlib import Path
from PIL import Image
from .buffer import MonitorBuffer

try:
    from google import genai
except ImportError:
    genai = None

from .logging_setup import logger

class AIAnalyzer:
    def __init__(self, buffer: MonitorBuffer, log_dir: str = "."):
        self.buffer = buffer
        self.log_dir = Path(log_dir)
        self.log_path = None # Will be set in start()
        self._stop_event = threading.Event()
        self._thread = None
        self._client = None
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and genai:
            self._client = genai.Client(api_key=api_key)
        else:
            logger.error("AIAnalyzer: GEMINI_API_KEY not set or google-genai not installed.")

    def start(self, model: str, prompt: str, delay_in_seconds: int, frame_count: int, frame_interval: int, frame_offset: int = -1, session_id: str = "default", ttl_minutes: int = 0, feeder=None):
        """
        Start the background AI analysis loop.
        
        :param model: The AI model ID to use for analysis (e.g., 'gemini-2.0-flash').
        :param prompt: The instructions to send to the model.
        :param delay_in_seconds: Time in seconds between analysis requests.
        :param frame_count: Number of frames to retrieve from the buffer for analysis.
        :param frame_interval: Step size between frames (negative to move backwards in time).
        :param frame_offset: Starting frame index (negative for relative to the end of the buffer).
        :param session_id: Identifier for the current session, used in logs and UI tracking.
        :param ttl_minutes: Auto-stop after X minutes. 0 means no limit.
        :param feeder: Optional FolderFeeder instance to monitor for completion.
        """
        if not self._client:
            raise ValueError("AIAnalyzer: Cannot start, GEMINI_API_KEY not set or google-genai not installed.")

        # Create a specific log file for this analysis run inside the log_dir
        run_ts = datetime.now().strftime("%y%m%d_%H%M%S")
        self.log_path = self.log_dir / f"analysis_{run_ts}.jsonl"
        logger.info(f"AIAnalyzer: Logging to {self.log_path}")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(model, prompt, delay_in_seconds, frame_count, frame_interval, frame_offset, session_id, ttl_minutes, feeder),
            daemon=True,
            name="AIAnalyzer"
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _log_result(self, data: dict):
        if not self.log_path:
            return
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _run(self, model: str, prompt: str, delay_in_seconds: int, frame_count: int, frame_interval: int, frame_offset: int, session_id: str, ttl_minutes: int, feeder=None):
        logger.info(f"AIAnalyzer: Starting analysis loop with model {model} (offset={frame_offset}, session={session_id}, ttl={ttl_minutes})...")
        start_time = time.time()
        ttl_seconds = ttl_minutes * 60 if ttl_minutes > 0 else None
        
        while not self._stop_event.is_set():
            # Check Feeder completion BEFORE sleeping to catch finished state immediately
            if feeder and feeder.is_finished:
                logger.info("AIAnalyzer: Feeder finished. Terminating analysis loop autonomously.")
                break

            time.sleep(delay_in_seconds)
            
            if self._stop_event.is_set():
                break

            # Re-check Feeder after sleep
            if feeder and feeder.is_finished:
                logger.info("AIAnalyzer: Feeder finished after sleep. Terminating analysis loop autonomously.")
                break

            # Check TTL
            if ttl_seconds and (time.time() - start_time) > ttl_seconds:
                logger.info(f"AIAnalyzer: TTL limit reached ({ttl_minutes} min). Stopping analysis loop.")
                break

            frames = self.buffer.get_frames(start_frame_index=frame_offset, frame_count=frame_count, frame_interval=frame_interval)
            if not frames:
                logger.debug("AIAnalyzer: No frames in buffer, skipping cycle.")
                continue

            # Strategy 1: Sequential + Timestamps
            chronological_frames = list(reversed(frames))
            actual_frame_count = len(chronological_frames)
            
            if actual_frame_count > 1:
                # Calculate real-world time covered by these frames
                time_span_seconds = chronological_frames[-1]["timestamp"] - chronological_frames[0]["timestamp"]
                avg_gap_seconds = time_span_seconds / (actual_frame_count - 1)
                
                dynamic_context = (
                    f"[SYSTEM CONTEXT: You are receiving {actual_frame_count} frames in chronological order. "
                    f"These frames cover a time span of {time_span_seconds:.1f} seconds, "
                    f"with an average gap of {avg_gap_seconds:.1f} seconds between each frame. "
                    f"The final frame represents the 'most recent' situation requested (offset={frame_offset}).]\n\n"
                )
            else:
                dynamic_context = "[SYSTEM CONTEXT: You are receiving a single frame representing the situation at the requested offset.]\n\n"

            base_time = chronological_frames[0]["timestamp"]
            
            contents = [
                "You are an AI screen monitor. Below are sequential frames captured from the screen.",
                f"{dynamic_context}User Prompt: {prompt}\n\nTimeline of Frames:"
            ]
            
            for i, f in enumerate(chronological_frames):
                rel_time = f["timestamp"] - base_time
                ts_str = datetime.fromtimestamp(f["timestamp"]).strftime("%H:%M:%S.%f")[:-2]
                contents.append(f"--- Frame {i+1} at {ts_str} (T+{rel_time:.2f}s) ---")
                contents.append(f["data"])

            try:
                logger.info(f"AIAnalyzer: Requesting analysis from {model}...")
                response = self._client.models.generate_content(
                    model=model,
                    contents=contents
                )
                
                # RESTORE CLEAR TERMINAL PRINT
                try:
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] AI Analysis ({model}):\n{response.text}\n" + "-"*50)
                except UnicodeEncodeError:
                    # Fallback for terminals with limited encoding support (e.g. Windows CMD)
                    clean_text = response.text.encode('ascii', 'replace').decode('ascii')
                    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] AI Analysis ({model}) [Encoding limited]:\n{clean_text}\n" + "-"*50)
                
                result = {
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "model": model,
                    "prompt": prompt,
                    "story": response.text,
                    "frame_indices": [f["index"] for f in chronological_frames],
                    "config": {
                        "delay_in_seconds": delay_in_seconds,
                        "frame_count": frame_count,
                        "frame_interval": frame_interval,
                        "frame_offset": frame_offset
                    }
                }
                self._log_result(result)
                logger.info("AIAnalyzer: Story logged to JSONL.")
                
            except Exception as e:
                logger.error(f"AIAnalyzer Error: {e}")
                self._log_result({
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                })

        logger.info("AIAnalyzer loop stopped.")
