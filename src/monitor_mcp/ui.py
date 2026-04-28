import streamlit as st
import time
import base64
import io
import os
import json
from pathlib import Path
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

def read_last_log_entries(log_dir: str, n: int = 15):
    """Read all JSONL logs in a directory and merge them sorted by timestamp."""
    dir_path = Path(log_dir)
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    
    all_entries = []
    # Find all analysis_*.jsonl files (new format) or analysis_log.jsonl (old format)
    log_files = list(dir_path.glob("analysis_*.jsonl"))
    if (dir_path / "analysis_log.jsonl").exists():
        log_files.append(dir_path / "analysis_log.jsonl")

    for log_file in log_files:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            all_entries.append(json.loads(line))
                        except:
                            continue
        except Exception as e:
            logger.error(f"Error reading log {log_file}: {e}")
    
    # Sort by timestamp (assuming ISO format strings sort correctly)
    all_entries.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return all_entries[:n]

def clear_session_logs(log_dir: str):
    dir_path = Path(log_dir)
    if dir_path.exists() and dir_path.is_dir():
        for log_file in dir_path.glob("analysis_*.jsonl"):
            try:
                os.remove(log_file)
            except:
                pass

@st.dialog("Query Results")
def show_query_results(mgr, start, count, interval):
    if not mgr or not mgr.buffer or mgr.buffer.current_size == 0:
        st.warning("Buffer is empty.")
        return
    history_frames = mgr.buffer.get_frames(start=start, count=count, interval=interval)
    if history_frames:
        st.write(f"Retrieved {len(history_frames)} frames")
        cols = st.columns(3)
        for i, frame in enumerate(history_frames):
            cols[i % 3].image(frame["data"], caption=f"Idx: {frame['index']}", use_container_width=True)
    else:
        st.warning("No frames found for the given criteria.")

def show_ui():

    st.set_page_config(page_title="Monitor MCP", layout="wide")
    mgr = get_manager()
    smgr = get_sim_manager()
    defaults = mgr.default_config
    status = mgr.get_status()
    is_simulating = bool(smgr.is_running)

    st.title("🖥️ Monitor MCP Dashboard")

    # Sidebar
    st.sidebar.header("Controls")
    
    with st.sidebar.expander("📂 Monitoring", expanded=not is_simulating):
        monitors = mgr.engine.list_monitors()
        monitor_options = {f"{m['label']} ({m['width']}x{m['height']})": m['index'] for m in monitors}
        opt_list = list(monitor_options.keys())
        sel_mon = st.selectbox("Screen", options=opt_list, index=0)
        screen_idx = monitor_options[sel_mon]
        freq = st.slider("Hz", 0.1, 30.0, float(defaults.frequency))
        m_imgs = st.number_input("Max Imgs", 1, 10000, int(defaults.max_images))
        s_disk = st.checkbox("Save Disk", value=defaults.save_to_disk)
        r_cache = st.checkbox("Reset Cache", value=defaults.reset_cache)
        d_mouse = st.checkbox("Draw Mouse", value=defaults.draw_mouse)
        path = st.text_input("Path", value=defaults.storage_path)
        
        c1, c2 = st.columns(2)
        if c1.button("Start", disabled=(status.is_active or is_simulating), use_container_width=True):
            cfg = MonitorConfig(screen=screen_idx, frequency=freq, max_images=m_imgs, storage_path=path, save_to_disk=s_disk, reset_cache=r_cache, draw_mouse=d_mouse)
            mgr.start(cfg)
            st.rerun()
        if c2.button("Stop", disabled=not status.is_active, use_container_width=True):
            mgr.stop()
            st.rerun()

    with st.sidebar.expander("🤖 AI Sandbox", expanded=is_simulating):
        sim_folder = st.text_input("Folder", value="E:\\test_recording")
        sim_model = st.selectbox("Model", ["gemini-3.1-flash-lite-preview", "gemini-2.0-flash-lite-preview-02-05"])
        sim_prompt = st.text_area("Prompt", value="Describe the screen.")
        sim_delay = st.number_input("Delay", 5, 3600, 15)
        sim_cnt = st.number_input("Count", 1, 20, 9)
        sim_int = st.number_input("Interval", -100, 100, -10)
        sim_off = st.number_input("Offset", -10000, 10000, -1)
        
        sc1, sc2 = st.columns(2)
        if sc1.button("Start Sim", disabled=(is_simulating or status.is_active), use_container_width=True):
            smgr.start(sim_folder, sim_model, sim_prompt, sim_delay, sim_cnt, sim_int, sim_off)
            st.rerun()
        if sc2.button("Stop Sim", disabled=not is_simulating, use_container_width=True):
            smgr.stop()
            st.rerun()

    with st.sidebar.expander("🔍 Manual Query", expanded=False):
        q_start = st.number_input("Start", value=-1)
        q_count = st.number_input("Count", 1, 100, 12)
        q_interval = st.number_input("Interval", -100, 100, -1)
        if st.button("Fetch Frames", use_container_width=True):
            show_query_results(mgr, q_start, q_count, q_interval)

    # Main Area Metrics
    col_m = st.columns(6)
    col_m[0].metric("Buffer", f"{status.buffer_size}")
    col_m[1].metric("Captured", status.frames_captured)
    
    uptime = 0
    if status.is_active and mgr.buffer and mgr.buffer.current_size > 0:
        uptime = int(time.time() - mgr.buffer._buffer[0]['timestamp'])
    col_m[2].metric("Uptime", f"{uptime}s")
    col_m[3].metric("FPS", status.current_fps)
    col_m[4].metric("Size", f"{status.last_frame_size_kb}KB")
    col_m[5].metric("Total", f"{status.total_buffer_size_mb}MB")

    t1, t2, t3 = st.tabs(["Live", "History", "Logs"])
    
    with t1:
        buf = smgr.buffer if is_simulating else mgr.buffer
        if buf and buf.current_size > 0:
            f = buf.get_frames(-1, 1)
            if f: st.image(f[0]["data"], use_container_width=True)
    
    with t2:
        buf = smgr.buffer if is_simulating else mgr.buffer
        if buf and buf.current_size > 0:
            fs = buf.get_frames(-1, 12, -1)
            cols = st.columns(4)
            for i, f in enumerate(fs):
                cols[i%4].image(f["data"], caption=f"Idx {f['index']}", use_container_width=True)

    with t3:
        # Get all session folders in storage path
        storage_root = Path(defaults.storage_path)
        if not storage_root.exists():
            storage_root.mkdir(parents=True, exist_ok=True)
        
        # List subdirectories (sessions), sorted by name descending (most recent first)
        sessions = sorted([d for d in storage_root.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
        
        if not sessions:
            st.info(f"No sessions found in `{storage_root}`")
        else:
            # Session Selector
            session_names = [s.name for s in sessions]
            # Use index 0 (most recent) as default, but keep track in session state to avoid jumps
            if "selected_session_idx" not in st.session_state:
                st.session_state.selected_session_idx = 0
            
            selected_session_name = st.selectbox("Select Session Folder", options=session_names, index=st.session_state.selected_session_idx)
            st.session_state.selected_session_idx = session_names.index(selected_session_name)
            
            selected_path = storage_root / selected_session_name
            
            # Sub-header with Clear button
            h_col1, h_col2 = st.columns([3, 1])
            with h_col1:
                st.subheader(f"Results for `{selected_session_name}`")
            with h_col2:
                if st.button("🗑️ Clear Logs", use_container_width=True, help="Clear analysis logs in this session folder"): 
                    clear_session_logs(str(selected_path))
                    st.rerun()
            
            # Show Config for this session
            config_file = selected_path / "run_config.json"
            if config_file.exists():
                with st.expander("⚙️ View Session Config", expanded=False):
                    try:
                        with open(config_file, "r") as f:
                            st.json(json.load(f))
                    except:
                        st.error("Failed to load session config.")

            # Show Analysis Runs in this session
            entries = read_last_log_entries(str(selected_path), n=20)
            if not entries:
                st.write("No analysis entries found in this session.")
            else:
                for e in entries:
                    # Determine expansion state: if it's the current active simulation session, expand it
                    is_current = (e.get('session_id') == smgr.current_session_id)
                    with st.expander(f"🕒 {e.get('timestamp')} | Model: {e.get('model')}", expanded=is_current):
                        if "error" in e:
                            st.error(e["error"])
                        else:
                            st.markdown(e.get("story"))
                            st.caption(f"Prompt: {e.get('prompt')}")
                            st.caption(f"Frames: {e.get('frame_indices')}")

    if status.is_active or is_simulating:
        time.sleep(1)
        st.rerun()

def main():
    import sys
    from streamlit.web import cli as stcli
    import os
    file_path = os.path.abspath(__file__)
    sys.argv = ["streamlit", "run", file_path, "--browser.gatherUsageStats", "False", "--server.headless", "True", "--server.port", "8501"]
    stcli.main()

if __name__ == "__main__":
    show_ui()
