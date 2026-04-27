import streamlit as st
import time
import base64
import io
import os
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from monitor_mcp.server import ObservationManager
from monitor_mcp.types import MonitorConfig

@st.cache_resource
def get_manager():
    return ObservationManager()

@st.dialog("Query Results")
def show_query_results(manager, start, count, interval):
    if not manager.buffer or manager.buffer.current_size == 0:
        st.warning("Buffer is empty.")
        return

    history_frames = manager.buffer.get_frames(start=start, count=count, interval=interval)
    
    if history_frames:
        st.write(f"Retrieved {len(history_frames)} frames")
        # Grid layout for popup
        cols = st.columns(3)
        for i, frame in enumerate(history_frames):
            cols[i % 3].image(
                frame["data"], 
                caption=f"Idx: {frame['index']} ({frame.get('size_bytes', 0)//1024}KB)", 
                width="stretch"
            )
    else:
        st.warning("No frames found for the given criteria.")

def select_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    folder_path = filedialog.askdirectory(master=root)
    root.destroy()
    return folder_path

def show_ui():
    # Page config
    st.set_page_config(
        page_title="Monitor MCP Dashboard",
        page_icon="🖥️",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    manager = get_manager()
    defaults = manager.default_config

    # Initialize session state for folder path
    if "storage_path" not in st.session_state:
        st.session_state.storage_path = defaults.storage_path

    st.title("🖥️ Monitor MCP Dashboard")
    st.markdown("---")

    # Sidebar for Configuration
    st.sidebar.header("Configuration")

    # Fetch monitors
    monitors = manager.engine.list_monitors()
    monitor_options = {
        f"{m['label']} ({m['width']}x{m['height']})": m['index'] 
        for m in monitors
    }
    
    # Try to find the default monitor in the list
    default_label = next((l for l, i in monitor_options.items() if i == defaults.screen), list(monitor_options.keys())[0])
    
    selected_monitor_label = st.sidebar.selectbox("Select Screen", options=list(monitor_options.keys()), index=list(monitor_options.keys()).index(default_label))
    screen = monitor_options[selected_monitor_label]

    frequency = st.sidebar.slider("Frequency (Hz)", min_value=0.1, max_value=30.0, value=defaults.frequency)
    max_images = st.sidebar.number_input("Buffer Size", min_value=1, value=defaults.max_images)
    save_to_disk = st.sidebar.checkbox("Save to Disk", value=defaults.save_to_disk)
    reset_cache = st.sidebar.checkbox("Reset Cache on Start", value=defaults.reset_cache)
    draw_mouse = st.sidebar.checkbox("Draw Mouse Cursor", value=defaults.draw_mouse)
    
    # Storage Path Row (Accepted/Leave it as requested)
    def storage_row():
        st.sidebar.markdown("**Storage Path**")
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            st.session_state.storage_path = st.text_input("Path", value=st.session_state.storage_path, label_visibility="collapsed", key="path_input")
        with col2:
            if st.button("📁", width="stretch", key="path_btn"):
                picked_path = select_folder()
                if picked_path:
                    st.session_state.storage_path = picked_path
                    st.rerun()
        return st.session_state.storage_path

    storage_path = storage_row()

    # Manual Resolution
    use_res = st.sidebar.checkbox("Limit Resolution", value=defaults.max_resolution is not None)
    res_w = st.sidebar.number_input("Width", min_value=64, value=defaults.max_resolution[0] if defaults.max_resolution else 1280, disabled=not use_res)
    res_h = st.sidebar.number_input("Height", min_value=64, value=defaults.max_resolution[1] if defaults.max_resolution else 720, disabled=not use_res)

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
            storage_path=st.session_state.storage_path,
            save_to_disk=save_to_disk,
            reset_cache=reset_cache
        )
        manager.start(config)
        st.rerun()

    if col2.button("🛑 Stop", disabled=not status.is_active, width="stretch"):
        manager.stop()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("Manual Query")
    q_start = st.sidebar.number_input("Start Index (-1 for latest)", value=-1)
    q_count = st.sidebar.number_input("Count", min_value=1, value=12)
    q_interval = st.sidebar.number_input("Interval (Stride)", value=-1)
    
    if st.sidebar.button("🔍 Fetch Frames", width="stretch"):
        show_query_results(manager, q_start, q_count, q_interval)

    # Main Area
    status = manager.get_status()

    # Status Banner
    if status.is_active:
        st.success(f"Monitoring Active (Screen {status.config.screen} @ {status.config.frequency}Hz)")
    else:
        st.info("Monitoring Idle")

    # Metrics
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Buffer Count", f"{status.buffer_size} / {max_images}")
    m2.metric("Total Captured", status.frames_captured)
    
    uptime = 0
    if status.is_active and manager.buffer and manager.buffer.current_size > 0:
        uptime = int(time.time() - manager.buffer._buffer[0]['timestamp'])
    m3.metric("Uptime", f"{uptime}s")
    
    # FPS Metric with conditional color
    target_freq = status.config.frequency if status.config else frequency
    fps_color = "red" if status.is_active and status.current_fps < (target_freq * 0.8) else "inherit"
    
    with m4:
        st.markdown(f"**Real FPS**")
        st.markdown(f"<p style='color:{fps_color}; font-size:24px; margin:0;'>{status.current_fps}</p>", unsafe_allow_html=True)
        
    m5.metric("Last Frame", f"{status.last_frame_size_kb} KB")
    m6.metric("Total Size", f"{status.total_buffer_size_mb} MB")

    st.markdown("---")

    # Live View & History
    if status.is_active or status.buffer_size > 0:
        tab1, tab2 = st.tabs(["📺 Live View", "🕒 Recent History"])
        
        with tab1:
            # We'll show the last captured image
            if manager.buffer and manager.buffer.current_size > 0:
                frames = manager.buffer.get_frames(start=-1, count=1)
                if frames:
                    st.image(frames[0]["data"], caption=f"Latest Frame (Index: {frames[0]['index']})", width="stretch")
        
        with tab2:
            if manager.buffer and manager.buffer.current_size > 0:
                st.subheader("Recent Captures")
                # Fixed view of last 12 frames for convenience
                history_frames = manager.buffer.get_frames(start=-1, count=12, interval=-1)
                if history_frames:
                    cols = st.columns(4)
                    for i, frame in enumerate(history_frames):
                        cols[i % 4].image(
                            frame["data"], 
                            caption=f"Idx: {frame['index']}", 
                            width="stretch"
                        )

    # Move auto-refresh to the VERY END so components actually render
    if status.is_active:
        time.sleep(1.0)
        st.rerun()


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
