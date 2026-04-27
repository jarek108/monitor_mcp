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
    
    # Storage Path Row (Accepted/Leave it as requested)
    def storage_row():
        st.sidebar.markdown("**Storage Path**")
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            st.session_state.storage_path = st.text_input("Path", value=st.session_state.storage_path, label_visibility="collapsed", key="path_input")
        with col2:
            if st.button("📁", use_container_width=True, key="path_btn"):
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
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Buffer Count", f"{status.buffer_size} / {max_images}")
    m2.metric("Total Captured", status.frames_captured)
    
    uptime = 0
    if status.is_active and manager.buffer and manager.buffer.current_size > 0:
        uptime = int(time.time() - manager.buffer._buffer[0]['timestamp'])
    m3.metric("Uptime", f"{uptime}s")
    
    m4.metric("Real FPS", f"{status.current_fps}")
    m5.metric("Last Frame", f"{status.last_frame_size_kb} KB")
    m6.metric("Total Size", f"{status.total_buffer_size_mb} MB")

    # Add a global auto-refresh for metrics/status/live-view
    # If monitoring is active, we refresh once per second
    if status.is_active:
        time.sleep(1.0)
        st.rerun()

    st.markdown("---")

    # Live View & History
    if status.is_active or status.buffer_size > 0:
        tab1, tab2 = st.tabs(["📺 Live View", "🕒 History & Query"])
        
        with tab1:
            # We'll show the last captured image
            if manager.buffer and manager.buffer.current_size > 0:
                frames = manager.buffer.get_frames(start=-1, count=1)
                if frames:
                    st.image(frames[0]["data"], caption=f"Latest Frame (Index: {frames[0]['index']})", width="stretch")
        
        with tab2:
            st.subheader("Query History")
            q_col1, q_col2, q_col3 = st.columns(3)
            q_start = q_col1.number_input("Start Index (-1 for latest)", value=-1)
            q_count = q_col2.number_input("Count", min_value=1, value=12)
            q_interval = q_col3.number_input("Interval (Stride)", value=-1)
            
            if manager.buffer and manager.buffer.current_size > 0:
                # Use the same logic as the tool
                history_frames = manager.buffer.get_frames(start=q_start, count=q_count, interval=q_interval)
                
                if history_frames:
                    st.write(f"Retrieved {len(history_frames)} frames")
                    cols = st.columns(4)
                    for i, frame in enumerate(history_frames):
                        cols[i % 4].image(
                            frame["data"], 
                            caption=f"Idx: {frame['index']} ({frame.get('size_bytes', 0)//1024}KB)", 
                            width="stretch"
                        )
                else:
                    st.warning("No frames found for the given criteria.")


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
