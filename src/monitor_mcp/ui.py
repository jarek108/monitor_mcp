import streamlit as st
import time
import base64
import io
import os
import json
import tkinter as tk
from tkinter import filedialog
from PIL import Image
from monitor_mcp.server import manager, sim_manager
from monitor_mcp.types import MonitorConfig
from monitor_mcp.logging_setup import logger

@st.cache_resource
def get_manager():
    return manager

@st.cache_resource
def get_sim_manager():
    return sim_manager

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
                    try:
                        entries.append(json.loads(line))
                    except:
                        continue
    except Exception as e:
        logger.error(f"Error reading log: {e}")
    return list(reversed(entries))

def clear_analysis_log():
    log_path = "analysis_log.jsonl"
    if os.path.exists(log_path):
        try:
            os.remove(log_path)
        except Exception as e:
            logger.error(f"Failed to clear log: {e}")

@st.dialog("Query Results")
def show_query_results(mgr, start, count, interval):
    if not mgr.buffer or mgr.buffer.current_size == 0:
        st.warning("Buffer is empty.")
        return

    history_frames = mgr.buffer.get_frames(start=start, count=count, interval=interval)
    
    if history_frames:
        st.write(f"Retrieved {len(history_frames)} frames")
        cols = st.columns(3)
        for i, frame in enumerate(history_frames):
            cols[i % 3].image(
                frame["data"], 
                caption=f"Idx: {frame['index']} ({frame.get('size_bytes', 0)//1024}KB)", 
                use_container_width=True
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

    mgr = get_manager()
    smgr = get_sim_manager()
    defaults = mgr.default_config

    # Initialize session state for storage path
    if "storage_path" not in st.session_state:
        st.session_state.storage_path = defaults.storage_path

    st.title("🖥️ Monitor MCP Dashboard")
    st.markdown("---")

    # --- SIDEBAR CONFIGURATION ---
    st.sidebar.header("Dashboard Controls")

    # 1. MONITORING CONFIG
    with st.sidebar.expander("📂 Monitoring Config", expanded=True):
        monitors = mgr.engine.list_monitors()
        monitor_options = {f"{m['label']} ({m['width']}x{m['height']})": m['index'] for m in monitors}
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
            if st.button("📁", key="path_btn", use_container_width=True):
                picked_path = select_folder()
                if picked_path:
                    st.session_state.storage_path = picked_path
                    st.rerun()

        use_res = st.checkbox("Limit Resolution", value=defaults.max_resolution is not None)
        res_w = st.number_input("Width", min_value=64, value=defaults.max_resolution[0] if defaults.max_resolution else 1280, disabled=not use_res)
        res_h = st.number_input("Height", min_value=64, value=defaults.max_resolution[1] if defaults.max_resolution else 720, disabled=not use_res)
        max_resolution = [res_w, res_h] if use_res else None

        st.markdown("---")
        status = mgr.get_status()
        col_m1, col_m2 = st.columns(2)
        if col_m1.button("🚀 Start Monitoring", disabled=status.is_active, use_container_width=True):
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
            mgr.start(config)
            st.rerun()
        if col_m2.button("🛑 Stop Monitoring", disabled=not status.is_active, use_container_width=True):
            mgr.stop()
            st.rerun()

    # 2. ANALYSIS CONFIG (SANDBOX)
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
        sim_offset = st.number_input("Frame Offset", value=-1)

        st.markdown("---")
        is_simulating = smgr.is_running
        col_s1, col_s2 = st.columns(2)
        
        if col_s1.button("🚀 Start Simulation", disabled=is_simulating, use_container_width=True):
            smgr.start(sim_folder, sim_model, sim_prompt, sim_delay, sim_count, sim_interval, sim_offset)
            st.rerun()
            
        if col_s2.button("🛑 Stop Simulation", disabled=not is_simulating, use_container_width=True):
            smgr.stop()
            st.rerun()

    # 3. MANUAL QUERY
    with st.sidebar.expander("🔍 Manual Query", expanded=False):
        q_start = st.number_input("Query Start Index", value=-1)
        q_count = st.number_input("Query Count", min_value=1, value=12)
        q_interval = st.number_input("Query Interval", value=-1)
        if st.button("🔍 Fetch Frames (Popup)", use_container_width=True, key="manual_query_btn"):
            show_query_results(mgr, q_start, q_count, q_interval)

    # --- MAIN AREA ---
    status = mgr.get_status()
    is_simulating = smgr.is_running

    if status.is_active:
        st.success(f"Monitoring Active (Screen {status.config.screen} @ {status.config.frequency}Hz)")
    elif is_simulating:
        st.warning("Simulation Running (AI Sandbox Active)")
    else:
        st.info("System Idle")

    # Metrics
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("Buffer Count", f"{status.buffer_size} / {max_images}")
    m2.metric("Total Captured", status.frames_captured)
    
    uptime = 0
    if status.is_active and mgr.buffer and mgr.buffer.current_size > 0:
        uptime = int(time.time() - mgr.buffer._buffer[0]['timestamp'])
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
        if status.is_active and mgr.buffer and mgr.buffer.current_size > 0:
            frames = mgr.buffer.get_frames(start=-1, count=1)
            if frames:
                st.image(frames[0]["data"], caption=f"Latest Frame (Index: {frames[0]['index']})", use_container_width=True)
        else:
            st.info("Start monitoring to see live view.")
    
    with tab2:
        if mgr.buffer and mgr.buffer.current_size > 0:
            st.subheader("Recent Captures")
            history_frames = mgr.buffer.get_frames(start=-1, count=12, interval=-1)
            if history_frames:
                cols = st.columns(4)
                for i, frame in enumerate(history_frames):
                    cols[i % 4].image(frame["data"], caption=f"Idx: {frame['index']}", use_container_width=True)
        else:
            st.info("No frames in buffer.")

    with tab3:
        st.header("AI Analysis Sandbox")
        s_col1, s_col2 = st.columns([1, 2])
        
        with s_col1:
            st.subheader("Simulation Status")
            if is_simulating:
                feeder = smgr.feeder
                sb = smgr.buffer
                
                if feeder and feeder.is_finished:
                    st.success("Playback Complete!")
                    # Check if analyzer is still running
                    if smgr.analyzer and not (smgr.analyzer._thread and smgr.analyzer._thread.is_alive()):
                        # Everything finished
                        pass
                
                st.write(f"Frames in Simulation Buffer: **{sb.current_size}**")
                sim_frames = sb.get_frames(start=sim_offset, count=sim_count, interval=sim_interval)
                if sim_frames:
                    st.markdown("**Last sequence sent to AI:**")
                    preview_indices = [0, len(sim_frames)//2, -1]
                    preview_frames = [sim_frames[i] for i in preview_indices if 0 <= i < len(sim_frames) or (i == -1 and len(sim_frames) > 0)]
                    seen = set()
                    final_preview = []
                    for f in preview_frames:
                        if f["index"] not in seen:
                            final_preview.append(f)
                            seen.add(f["index"])
                    cols = st.columns(len(final_preview))
                    for i, f in enumerate(final_preview):
                         cols[i].image(f["data"], caption=f"Idx: {f['index']}", use_container_width=True)
            else:
                st.info("Simulation is not running. Configure and start it from the sidebar.")

        with s_col2:
            h_col1, h_col2 = st.columns([3, 1])
            with h_col1:
                st.subheader("Analysis Log")
            with h_col2:
                if st.button("🗑️ Clear Log", width="stretch"):
                    clear_analysis_log()
                    st.rerun()

            if smgr.current_session_id:
                with st.expander("ℹ️ Current/Last Run Parameters", expanded=False):
                    st.json(smgr.current_config)
                    st.caption(f"Session ID: `{smgr.current_session_id}`")

            st.caption(f"📜 Story Log: `{os.path.abspath('analysis_log.jsonl')}`")
            st.caption(f"🛠️ System Log: `{os.path.abspath('monitor.log')}`")
            
            entries = read_last_log_entries("analysis_log.jsonl", n=15)
            if entries:
                for entry in entries:
                    header = f"🕒 {entry.get('timestamp', 'Unknown')}"
                    if "session_id" in entry:
                        header += f" | 🆔 {entry['session_id']}"
                    
                    with st.expander(header, expanded=(entry.get("session_id") == smgr.current_session_id)):
                        if "error" in entry:
                            st.error(entry["error"])
                        else:
                            st.markdown(entry.get("story", "No story generated."))
                            st.caption(f"Model: {entry.get('model')} | Prompt: {entry.get('prompt')}")
                            st.caption(f"Frames analyzed: {entry.get('frame_indices')}")
            else:
                st.info("No analysis entries yet.")

    # Auto-refresh
    if status.is_active or is_simulating:
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
