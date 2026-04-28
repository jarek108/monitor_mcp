import streamlit as st
import time
import base64
import io
import os
import json
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from monitor_mcp.server import ObservationManager
from monitor_mcp.types import MonitorConfig
from monitor_mcp.simulator import FolderFeeder
from monitor_mcp.analyzer import AIAnalyzer

@st.cache_resource
def get_manager():
    return ObservationManager()

def read_last_log_entries(log_path: str, n: int = 5):
    path = os.path.abspath(log_path)
    if not os.path.exists(path):
        return []
    
    entries = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[-n:]:
                if line.strip():
                    entries.append(json.loads(line))
    except Exception as e:
        print(f"Error reading log: {e}")
    return list(reversed(entries))

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

    # Simulation State
    if "sim_manager" not in st.session_state:
        # Isolated buffer for simulation
        from monitor_mcp.buffer import MonitorBuffer
        st.session_state.sim_buffer = MonitorBuffer(max_size=3600)
        st.session_state.feeder = None
        st.session_state.analyzer = None
        st.session_state.is_simulating = False
        st.session_state.storage_path = defaults.storage_path

    st.title("🖥️ Monitor MCP Dashboard")
    st.markdown("---")

    # --- SIDEBAR CONFIGURATION ---
    st.sidebar.header("Dashboard Controls")

    # 1. MONITORING CONFIG EXPANDER
    with st.sidebar.expander("📂 Monitoring Config", expanded=True):
        # Fetch monitors
        monitors = manager.engine.list_monitors()
        monitor_options = {
            f"{m['label']} ({m['width']}x{m['height']})": m['index'] 
            for m in monitors
        }
        default_label = next((l for l, i in monitor_options.items() if i == defaults.screen), list(monitor_options.keys())[0])
        
        selected_monitor_label = st.selectbox("Select Screen", options=list(monitor_options.keys()), index=list(monitor_options.keys()).index(default_label))
        screen = monitor_options[selected_monitor_label]

        frequency = st.slider("Frequency (Hz)", min_value=0.1, max_value=30.0, value=defaults.frequency)
        max_images = st.number_input("Buffer Size", min_value=1, value=defaults.max_images)
        save_to_disk = st.checkbox("Save to Disk", value=defaults.save_to_disk)
        reset_cache = st.checkbox("Reset Cache on Start", value=defaults.reset_cache)
        draw_mouse = st.checkbox("Draw Mouse Cursor", value=defaults.draw_mouse)
        
        st.markdown("**Storage Path**")
        col_p1, col_p2 = st.columns([3, 1])
        with col_p1:
            st.session_state.storage_path = st.text_input("Path", value=st.session_state.storage_path, label_visibility="collapsed", key="path_input")
        with col_p2:
            if st.button("📁", width="stretch", key="path_btn"):
                picked_path = select_folder()
                if picked_path:
                    st.session_state.storage_path = picked_path
                    st.rerun()

        use_res = st.checkbox("Limit Resolution", value=defaults.max_resolution is not None)
        res_w = st.number_input("Width", min_value=64, value=defaults.max_resolution[0] if defaults.max_resolution else 1280, disabled=not use_res)
        res_h = st.number_input("Height", min_value=64, value=defaults.max_resolution[1] if defaults.max_resolution else 720, disabled=not use_res)
        max_resolution = [res_w, res_h] if use_res else None

        st.markdown("---")
        status = manager.get_status()
        col_m1, col_m2 = st.columns(2)
        if col_m1.button("🚀 Start Monitoring", disabled=status.is_active, width="stretch"):
            config = MonitorConfig(
                screen=screen,
                frequency=frequency,
                max_images=max_images,
                max_resolution=max_resolution,
                storage_path=st.session_state.storage_path,
                save_to_disk=save_to_disk,
                reset_cache=reset_cache,
                draw_mouse=draw_mouse
            )
            manager.start(config)
            st.rerun()
        if col_m2.button("🛑 Stop Monitoring", disabled=not status.is_active, width="stretch"):
            manager.stop()
            st.rerun()

    # 2. ANALYSIS CONFIG EXPANDER
    with st.sidebar.expander("🧠 Analysis Config (Sandbox)", expanded=True):
        sim_folder = st.text_input("Test Folder Path", value="E:\\test_recording")
        sim_model = st.selectbox("AI Model", options=[
            "gemini-3.1-flash-lite-preview",
            "gemini-2.0-flash-lite-preview-02-05",
            "gemini-2.0-pro-exp-02-05"
        ], index=0)
        sim_prompt = st.text_area("Analysis Prompt", value="Describe what is happening on the screen. Focus on any changes between the frames.")
        sim_delay = st.number_input("Analysis Delay (s)", min_value=5, value=15)
        sim_count = st.number_input("Frame Count", min_value=1, max_value=20, value=9)
        sim_interval = st.number_input("Frame Interval (Stride)", value=-10)
        sim_offset = st.number_input("Frame Offset", value=-1, help="-1 for latest available")

        st.markdown("---")
        if not st.session_state.is_simulating:
            if st.button("🚀 Start Simulation", use_container_width=True):
                st.session_state.sim_buffer.clear()
                st.session_state.feeder = FolderFeeder(sim_folder, st.session_state.sim_buffer)
                st.session_state.feeder.start()
                st.session_state.analyzer = AIAnalyzer(st.session_state.sim_buffer)
                st.session_state.analyzer.start(
                    model=sim_model,
                    prompt=sim_prompt,
                    delay=sim_delay,
                    count=sim_count,
                    interval=sim_interval,
                    offset=sim_offset
                )
                st.session_state.is_simulating = True
                st.rerun()
        else:
            if st.button("🛑 Stop Simulation", use_container_width=True):
                if st.session_state.feeder: st.session_state.feeder.stop()
                if st.session_state.analyzer: st.session_state.analyzer.stop()
                st.session_state.is_simulating = False
                st.rerun()

    # 3. MANUAL QUERY EXPANDER
    with st.sidebar.expander("🔍 Manual Query", expanded=False):
        q_start = st.number_input("Query Start Index", value=-1)
        q_count = st.number_input("Query Count", min_value=1, value=12)
        q_interval = st.number_input("Query Interval", value=-1)
        if st.button("🔍 Fetch Frames (Popup)", width="stretch"):
            # Check which buffer to use. For simplicity, we use the main manager's buffer here.
            show_query_results(manager, q_start, q_count, q_interval)

    # --- MAIN AREA ---
    status = manager.get_status()

    # Status Banner
    if status.is_active:
        st.success(f"Monitoring Active (Screen {status.config.screen} @ {status.config.frequency}Hz)")
    elif st.session_state.is_simulating:
        st.warning("Simulation Running (AI Sandbox Active)")
    else:
        st.info("System Idle")

    # Metrics Row
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Buffer Count", f"{status.buffer_size} / {max_images}")
    m2.metric("Total Captured", status.frames_captured)
    
    uptime = 0
    if status.is_active and manager.buffer and manager.buffer.current_size > 0:
        uptime = int(time.time() - manager.buffer._buffer[0]['timestamp'])
    m3.metric("Uptime", f"{uptime}s")
    
    target_freq = status.config.frequency if status.config else frequency
    fps_color = "red" if status.is_active and status.current_fps < (target_freq * 0.8) else "inherit"
    with m4:
        st.markdown(f"**Real FPS**")
        st.markdown(f"<p style='color:{fps_color}; font-size:24px; margin:0;'>{status.current_fps}</p>", unsafe_allow_html=True)
        
    m5.metric("Last Frame", f"{status.last_frame_size_kb} KB")
    m6.metric("Total Size", f"{status.total_buffer_size_mb} MB")

    st.markdown("---")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📺 Live View", "🕒 Recent History", "🤖 AI Sandbox"])
    
    with tab1:
        if status.is_active and manager.buffer and manager.buffer.current_size > 0:
            frames = manager.buffer.get_frames(start=-1, count=1)
            if frames:
                st.image(frames[0]["data"], caption=f"Latest Frame (Index: {frames[0]['index']})", width="stretch")
        else:
            st.info("Start monitoring to see live view.")
    
    with tab2:
        if manager.buffer and manager.buffer.current_size > 0:
            st.subheader("Recent Captures")
            history_frames = manager.buffer.get_frames(start=-1, count=12, interval=-1)
            if history_frames:
                cols = st.columns(4)
                for i, frame in enumerate(history_frames):
                    cols[i % 4].image(frame["data"], caption=f"Idx: {frame['index']}", width="stretch")
        else:
            st.info("No frames in buffer.")

    with tab3:
        st.header("AI Analysis Sandbox")
        s_col1, s_col2 = st.columns([1, 2])
        
        with s_col1:
            st.subheader("Simulation Status")
            if st.session_state.is_simulating:
                sb = st.session_state.sim_buffer
                st.write(f"Frames in Simulation Buffer: **{sb.current_size}**")
                
                # Show what AI is seeing (last sequence)
                # Use params from session state/input
                sim_frames = sb.get_frames(start=sim_offset, count=sim_count, interval=sim_interval)
                if sim_frames:
                    st.markdown("**Last sequence sent to AI:**")
                    cols = st.columns(min(len(sim_frames), 3))
                    # Show oldest and newest of the sequence for context
                    for i, f in enumerate([sim_frames[0], sim_frames[len(sim_frames)//2], sim_frames[-1]]):
                         cols[i % 3].image(f["data"], caption=f"Idx: {f['index']}", width="stretch")
            else:
                st.info("Simulation is not running. Configure and start it from the sidebar.")

        with s_col2:
            st.subheader("Analysis Log")
            entries = read_last_log_entries("analysis_log.jsonl", n=5)
            if entries:
                for entry in entries:
                    with st.expander(f"🕒 {entry.get('timestamp', 'Unknown')} - {entry.get('model', 'Unknown')}", expanded=True):
                        if "error" in entry:
                            st.error(entry["error"])
                        else:
                            st.markdown(entry.get("story", "No story generated."))
                            st.caption(f"Prompt: {entry.get('prompt')}")
                            st.caption(f"Frames analyzed: {entry.get('frame_indices')}")
            else:
                st.info("No analysis entries yet.")

    # Auto-refresh at the very end
    if status.is_active or st.session_state.is_simulating:
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
