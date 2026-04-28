import time
import base64
import io
import os
import sys
from datetime import datetime
from PIL import Image

# Add src to path so we can import monitor_mcp without installation
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from monitor_mcp.server import manager, start_monitoring, get_imgs
from monitor_mcp.types import MonitorConfig

try:
    from google import genai
except ImportError:
    print("Error: 'google-genai' package not found.")
    print("Please run: pip install google-genai")
    sys.exit(1)

def analyze_loop(model: str, prompt: str, delay: int, count: int, interval: int):
    """
    Continuous analysis loop.
    :param model: Gemini model ID (e.g., 'gemini-2.0-flash-lite-preview')
    :param prompt: Instruction for the model
    :param delay: Seconds to wait between analysis cycles
    :param count: Number of frames to send per cycle
    :param interval: Stride between frames (negative for backwards)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        sys.exit(1)

    client = genai.Client(api_key=api_key)
    
    print(f"🚀 Starting analysis loop...")
    print(f"Model: {model}")
    print(f"Prompt: {prompt}")
    print(f"Config: {count} frames every {delay}s (interval={interval})")
    print("-" * 50)

    # 1. Ensure monitoring is running
    status = manager.get_status()
    if not status.is_active:
        print("Starting background capture at 2Hz...")
        # Start with default settings or from config.json
        start_monitoring(frequency=2.0, draw_mouse=True)
        time.sleep(2) # Buffer some frames

    try:
        while True:
            # 2. Retrieve frames using custom logic
            # get_imgs returns List[Frame] (Base64 encoded)
            frames = get_imgs(start=-1, count=count, interval=interval)
            
            if not frames:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Buffer empty, waiting...")
                time.sleep(2)
                continue

            # 3. Construct multimodal prompt (Strategy 1: Sequential + Timestamps)
            # Reverse so frames are in chronological order for the model
            chronological_frames = list(reversed(frames))
            base_time = chronological_frames[0].timestamp
            
            contents = [
                "You are an AI screen monitor. Below are sequential frames captured from the screen.",
                f"User Prompt: {prompt}\n\nTimeline of Frames:"
            ]
            
            for i, f in enumerate(chronological_frames):
                rel_time = f.timestamp - base_time
                timestamp_str = datetime.fromtimestamp(f.timestamp).strftime("%H:%M:%S.%f")[:-2]
                
                # Interleave text description and image
                contents.append(f"--- Frame {i+1} at {timestamp_str} (T+{rel_time:.2f}s) ---")
                
                # Decode Base64 back to PIL for the SDK
                img_bytes = base64.b64decode(f.data)
                img = Image.open(io.BytesIO(img_bytes))
                contents.append(img)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Analyzing {len(frames)} frames...")
            
            # 4. Call Gemini
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents
                )
                print(f"\n🤖 Gemini Analysis:\n{response.text}")
                print("-" * 50)
            except Exception as e:
                print(f"❌ API Error: {e}")

            # 5. Wait for the next cycle
            time.sleep(delay)
            
    except KeyboardInterrupt:
        print("\n👋 Analysis loop stopped by user.")
    finally:
        manager.stop()

if __name__ == "__main__":
    # You can change these defaults or pass them via CLI
    DEFAULT_MODEL = "gemini-2.0-flash-lite-preview-02-05"
    DEFAULT_PROMPT = "Describe what is happening on the screen. Focus on any changes between the frames."
    
    analyze_loop(
        model=DEFAULT_MODEL,
        prompt=DEFAULT_PROMPT,
        delay=10,      # Analyze every 10 seconds
        count=5,       # Take 5 frames
        interval=-4    # Jump back 4 frames (if 2Hz, that's one frame every 2 seconds)
    )
