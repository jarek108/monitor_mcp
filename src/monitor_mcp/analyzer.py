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
    def __init__(self, buffer: MonitorBuffer, log_path: str = "analysis_log.jsonl"):
        self.buffer = buffer
        self.log_path = Path(log_path)
        self._stop_event = threading.Event()
        self._thread = None
        self._client = None
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key and genai:
            self._client = genai.Client(api_key=api_key)
        else:
            logger.error("AIAnalyzer: GEMINI_API_KEY not set or google-genai not installed.")

    def start(self, model: str, prompt: str, delay: int, count: int, interval: int, offset: int = -1):
        if not self._client:
            logger.error("AIAnalyzer: Cannot start, client not initialized.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(model, prompt, delay, count, interval, offset),
            daemon=True,
            name="AIAnalyzer"
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _log_result(self, data: dict):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def _run(self, model: str, prompt: str, delay: int, count: int, interval: int, offset: int):
        logger.info(f"AIAnalyzer: Starting analysis loop with model {model} (offset={offset})...")
        
        while not self._stop_event.is_set():
            time.sleep(delay)
            
            if self._stop_event.is_set():
                break

            frames = self.buffer.get_frames(start=offset, count=count, interval=interval)
            if not frames:
                logger.debug("AIAnalyzer: No frames in buffer, skipping cycle.")
                continue

            # Strategy 1: Sequential + Timestamps
            chronological_frames = list(reversed(frames))
            actual_count = len(chronological_frames)
            
            if actual_count > 1:
                # Calculate real-world time covered by these frames
                time_span_seconds = chronological_frames[-1]["timestamp"] - chronological_frames[0]["timestamp"]
                avg_gap = time_span_seconds / (actual_count - 1)
                
                dynamic_context = (
                    f"[SYSTEM CONTEXT: You are receiving {actual_count} frames in chronological order. "
                    f"These frames cover a time span of {time_span_seconds:.1f} seconds, "
                    f"with an average gap of {avg_gap:.1f} seconds between each frame. "
                    f"The final frame represents the 'most recent' situation requested (offset={offset}).]\n\n"
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
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🤖 AI Analysis ({model}):\n{response.text}\n" + "-"*50)
                
                result = {
                    "timestamp": datetime.now().isoformat(),
                    "model": model,
                    "prompt": prompt,
                    "story": response.text,
                    "frame_indices": [f["index"] for f in chronological_frames]
                }
                self._log_result(result)
                logger.info("AIAnalyzer: Story logged to JSONL.")
                
            except Exception as e:
                logger.error(f"AIAnalyzer Error: {e}")
                self._log_result({
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                })

        logger.info("AIAnalyzer loop stopped.")
