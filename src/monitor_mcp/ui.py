import streamlit as st
import time
import base64
import io
from PIL import Image
from monitor_mcp.server import ObservationManager
from monitor_mcp.types import MonitorConfig

@st.cache_resource
def get_manager():
    return ObservationManager()

def show_ui():
    # Page config
    st.set_page_config(
        page_title="Monitor MCP Dashboard",
        page_icon="🖥️",
        layout="wide"
    )

    manager = get_manager()

    st.title("🖥️ Monitor MCP Dashboard")
    st.markdown("---")

    # Sidebar for Configuration
    st.sidebar.header("Configuration")
    defaults = manager.default_config

    screen = st.sidebar.number_input("Screen Index", min_value=0, value=defaults.screen, help="0 for all, 1 for primary")
    frequency = st.sidebar.slider("Capture Frequency (Hz)", min_value=0.1, max_value=30.0, value=defaults.frequency)
    max_images = st.sidebar.number_input("Buffer Size (images)", min_value=1, value=defaults.max_images)
    save_to_disk = st.sidebar.checkbox("Save to Disk", value=defaults.save_to_disk)
    storage_path = st.sidebar.text_input("Storage Path", value=defaults.storage_path)

    # Manual Resolution
    use_res = st.sidebar.checkbox("Limit Resolution", value=defaults.max_resolution is not None)
    res_w = st.sidebar.number_input("Width", min_value=64, value=defaults.max_resolution[0] if defaults.max_resolution else 1280)
    res_h = st.sidebar.number_input("Height", min_value=64, value=defaults.max_resolution[1] if defaults.max_resolution else 720)

    max_resolution = [res_w, res_h] if use_res else None

    st.sidebar.markdown("---")

    # Control Buttons
    col1, col2 = st.sidebar.columns(2)
    status = manager.get_status()

    if col1.button("🚀 Start", disabled=status.is_active, width="stretch"):
        config = MonitorConfig(
            screen=screen,
            frequency=frequency,
            max_images=max_images,
            max_resolution=max_resolution,
            storage_path=storage_path,
            save_to_disk=save_to_disk
        )
        manager.start(config)
        st.rerun()

    if col2.button("🛑 Stop", disabled=not status.is_active, width="stretch"):
        manager.stop()
        st.rerun()

    # Main Area
    status = manager.get_status()

    # Status Banner
    if status.is_active:
        st.success(f"Monitoring Active (Screen {status.config.screen} @ {status.config.frequency}Hz)")
    else:
        st.info("Monitoring Idle")

    # Metrics
    m1, m2, m3 = st.columns(3)
    m1.metric("Buffer Size", f"{status.buffer_size} / {max_images}")
    m2.metric("Total Captured", status.frames_captured)
    
    uptime = 0
    if status.is_active and manager.buffer and manager.buffer.current_size > 0:
        uptime = int(time.time() - manager.buffer._buffer[0]['timestamp'])
    m3.metric("Uptime", f"{uptime}s")

    st.markdown("---")

    # Live View & History
    if status.is_active or status.buffer_size > 0:
        tab1, tab2 = st.tabs(["📺 Live View", "🕒 History Gallery"])
        
        with tab1:
            # We'll show the last captured image
            if manager.buffer and manager.buffer.current_size > 0:
                frames = manager.buffer.get_frames(start=-1, count=1)
                if frames:
                    st.image(frames[0]["data"], caption=f"Latest Frame (Index: {frames[0]['index']})", width="stretch")
                    # Auto-refresh logic for Streamlit
                    if status.is_active:
                        time.sleep(1.0 / frequency)
                        st.rerun()
        
        with tab2:
            if manager.buffer and manager.buffer.current_size > 0:
                st.subheader("Recent Frames")
                # Get last 12 frames
                history_frames = manager.buffer.get_frames(start=-1, count=12, interval=-1)
                if history_frames:
                    cols = st.columns(4)
                    for i, frame in enumerate(history_frames):
                        cols[i % 4].image(frame["data"], caption=f"Index: {frame['index']}", width="stretch")


def main():
    import sys
    from streamlit.web import cli as stcli
    import os
    
    file_path = os.path.abspath(__file__)
    sys.argv = [
        "streamlit", 
        "run", 
        file_path, 
        "--browser.gatherUsageStats", "False",
        "--server.headless", "True"
    ]
    sys.exit(stcli.main())

if __name__ == "__main__":
    show_ui()
