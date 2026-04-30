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

PERSIST_FILE = Path("logs/.ui_state.json")
PERSISTENT_KEYS = [
    "sel_mon", "freq", "m_imgs", "s_disk", "r_cache", "d_mouse", "path", "ttl",
    "sim_folder", "sim_model", "sim_prompt", "sim_delay", "sim_cnt", "sim_int", "sim_off", "sim_ttl",
    "q_start", "q_count", "q_interval", "selected_session_name"
]

def load_ui_state():
    """Load UI state from local JSON file into st.session_state."""
    if PERSIST_FILE.exists():
        try:
            with open(PERSIST_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                for k, v in state.items():
                    if k in PERSISTENT_KEYS:
                        st.session_state[k] = v
        except Exception as e:
            logger.error(f"Failed to load UI state: {e}")

def save_ui_state():
    """Save current UI state from st.session_state to local JSON file."""
    state = {k: st.session_state[k] for k in PERSISTENT_KEYS if k in st.session_state}
    try:
        PERSIST_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(PERSIST_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save UI state: {e}")

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
def show_query_results(mgr, start_frame_index, frame_count, frame_interval):
    if not mgr or not mgr.buffer or mgr.buffer.current_size == 0:
        st.warning("Buffer is empty.")
        return
    history_frames = mgr.buffer.get_frames(start_frame_index=start_frame_index, frame_count=frame_count, frame_interval=frame_interval)
    if history_frames:
        st.write(f"Retrieved {len(history_frames)} frames")
        cols = st.columns(3)
        for i, frame in enumerate(history_frames):
            cols[i % 3].image(frame["data"], caption=f"Idx: {frame['index']}", width='stretch')
    else:
        st.warning("No frames found for the given criteria.")

def show_ui():
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    
    if "state_loaded" not in st.session_state:
        load_ui_state()
        st.session_state.state_loaded = True

    st.set_page_config(page_title="Monitor MCP", layout="wide")
    mgr = get_manager()
    smgr = get_sim_manager()
    defaults = mgr.default_config
    status = mgr.get_status()
    is_simulating = bool(smgr.is_running)

    st.title("Monitor MCP Dashboard")

    # Sidebar
    st.sidebar.header("Controls")
    
    with st.sidebar.expander("Monitoring", expanded=not is_simulating):
        monitors = mgr.engine.list_monitors()
        monitor_options = {f"{m['label']} ({m['width']}x{m['height']})": m['index'] for m in monitors}
        opt_list = list(monitor_options.keys())
        
        # Check if saved monitor still exists
        saved_mon = st.session_state.get("sel_mon")
        mon_idx = 0
        if saved_mon in opt_list:
            mon_idx = opt_list.index(saved_mon)

        sel_mon = st.selectbox("Screen", options=opt_list, index=mon_idx, key="sel_mon", on_change=save_ui_state)
        screen_idx = monitor_options[sel_mon]
        freq = st.slider("Hz", 0.1, 30.0, float(defaults.frequency), key="freq", on_change=save_ui_state)
        m_imgs = st.number_input("Max Imgs", 1, 10000, int(defaults.max_images), key="m_imgs", on_change=save_ui_state)
        s_disk = st.checkbox("Save Disk", value=defaults.save_to_disk, key="s_disk", on_change=save_ui_state)
        r_cache = st.checkbox("Reset Cache", value=defaults.reset_cache, key="r_cache", on_change=save_ui_state)
        d_mouse = st.checkbox("Draw Mouse", value=defaults.draw_mouse, key="d_mouse", on_change=save_ui_state)
        path = st.text_input("Path", value=defaults.storage_path, key="path", on_change=save_ui_state)
        ttl = st.number_input("TTL (min)", 0, 1440, int(defaults.ttl_minutes), help="Auto-stop after X minutes. 0 for no limit.", key="ttl", on_change=save_ui_state)
        
        c1, c2 = st.columns(2)
        if c1.button("Start", disabled=(status.is_active or is_simulating), width='stretch', key="btn_start_live"):
            cfg = MonitorConfig(screen=screen_idx, frequency=freq, max_images=m_imgs, storage_path=path, save_to_disk=s_disk, reset_cache=r_cache, draw_mouse=d_mouse, ttl_minutes=ttl)
            mgr.start(cfg)
            st.rerun()
        if c2.button("Stop", disabled=not status.is_active, width='stretch', key="btn_stop_live"):
            mgr.stop()
            st.rerun()

    with st.sidebar.expander("AI Sandbox", expanded=is_simulating):
        sim_folder = st.text_input("Folder", value="E:\\test_recording", key="sim_folder", on_change=save_ui_state)
        
        # Model selection
        model_options = ["gemini-3.1-flash-lite-preview", "gemini-2.0-flash-lite-preview-02-05"]
        saved_model = st.session_state.get("sim_model")
        model_idx = 0
        if saved_model in model_options:
            model_idx = model_options.index(saved_model)

        sim_model = st.selectbox("Model", model_options, index=model_idx, key="sim_model", on_change=save_ui_state)
        sim_prompt = st.text_area("Prompt", value="Describe the screen.", key="sim_prompt", on_change=save_ui_state)
        sim_delay_in_seconds = st.number_input("Delay (s)", 5, 3600, 15, key="sim_delay", on_change=save_ui_state)
        sim_frame_count = st.number_input("Count (frames)", 1, 20, 9, key="sim_cnt", on_change=save_ui_state)
        sim_frame_interval = st.number_input("Interval (step)", -100, 100, -10, key="sim_int", on_change=save_ui_state)
        sim_frame_offset = st.number_input("Offset (frame index)", -10000, 10000, -1, key="sim_off", on_change=save_ui_state)
        sim_ttl = st.number_input("TTL (min)", 0, 1440, 0, help="Auto-stop after X minutes. 0 for no limit.", key="sim_ttl", on_change=save_ui_state)
        
        sc1, sc2 = st.columns(2)
        if sc1.button("Start Sim", disabled=(is_simulating or status.is_active), width='stretch', key="btn_start_sim"):
            try:
                smgr.start(sim_folder, sim_model, sim_prompt, sim_delay_in_seconds, sim_frame_count, sim_frame_interval, sim_frame_offset, ttl_minutes=sim_ttl)
                st.rerun()
            except Exception as e:
                st.error(f"Failed to start simulation: {e}")
                logger.error(f"Simulation Start Error: {e}")
        if sc2.button("Stop Sim", disabled=not is_simulating, width='stretch', key="btn_stop_sim"):
            smgr.stop()
            st.rerun()

    with st.sidebar.expander("Manual Query", expanded=False):
        q_start_frame_index = st.number_input("Start Frame Index", value=-1, key="q_start", on_change=save_ui_state)
        q_frame_count = st.number_input("Frame Count", 1, 100, 12, key="q_count", on_change=save_ui_state)
        q_frame_interval = st.number_input("Frame Interval", -100, 100, -1, key="q_interval", on_change=save_ui_state)
        if st.button("Fetch Frames", width='stretch', key="btn_fetch"):
            show_query_results(mgr, q_start_frame_index, q_frame_count, q_frame_interval)

    # Main Area
    show_main_area(mgr, smgr, defaults)

@st.fragment(run_every=1)
def show_main_area(mgr, smgr, defaults):
    status = mgr.get_status()
    is_simulating = bool(smgr.is_running)

    # Autonomous UI Reset Detection
    if "last_active_state" not in st.session_state:
        st.session_state.last_active_state = status.is_active
    if "last_sim_state" not in st.session_state:
        st.session_state.last_sim_state = is_simulating

    if (st.session_state.last_active_state and not status.is_active) or \
       (st.session_state.last_sim_state and not is_simulating):
        st.session_state.last_active_state = status.is_active
        st.session_state.last_sim_state = is_simulating
        logger.info("UI: Autonomous backend stop detected. Triggering full UI reset.")
        st.rerun()

    st.session_state.last_active_state = status.is_active
    st.session_state.last_sim_state = is_simulating

    # Metrics
    col_metrics = st.columns(6)
    
    # Use simulation buffer if active
    buf = smgr.buffer if is_simulating else mgr.buffer
    
    if is_simulating:
        buffer_size = buf.current_size
        frames_captured = buf.total_captured
        fps = 0.0
        last_frame_size_kb = 0.0
        total_buffer_size_mb = 0.0
        if buf.current_size > 0:
            with buf._lock:
                last_frame = buf._buffer[-1]
                last_frame_size_kb = last_frame.get("size_bytes", 0) / 1024.0
                total_bytes = sum(f.get("size_bytes", 0) for f in buf._buffer)
                total_buffer_size_mb = total_bytes / (1024.0 * 1024.0)
    else:
        buffer_size = status.buffer_size
        frames_captured = status.frames_captured
        fps = status.current_fps
        last_frame_size_kb = status.last_frame_size_kb
        total_buffer_size_mb = status.total_buffer_size_mb

    col_metrics[0].metric("Buffer", f"{buffer_size}")
    col_metrics[1].metric("Captured", frames_captured)
    
    uptime = 0
    if (status.is_active or is_simulating) and buf and buf.current_size > 0:
        uptime = int(time.time() - buf._buffer[0]['timestamp'])
    col_metrics[2].metric("Uptime", f"{uptime}s")
    col_metrics[3].metric("FPS", fps)
    col_metrics[4].metric("Size", f"{round(last_frame_size_kb, 1)}KB")
    col_metrics[5].metric("Total", f"{round(total_buffer_size_mb, 1)}MB")

    # Layout: Main View (Left) and Session List (Right)
    main_col, side_col = st.columns([4, 1])

    with side_col:
        st.subheader("Sessions")
        storage_root = Path(defaults.storage_path)
        if not storage_root.exists():
            storage_root.mkdir(parents=True, exist_ok=True)
        
        sessions = sorted([d for d in storage_root.iterdir() if d.is_dir()], key=lambda x: x.name, reverse=True)
        session_names = [s.name for s in sessions]

        if not session_names:
            st.info("No sessions found.")
            selected_session_name = None
        else:
            # Auto-select newest session if monitoring or simulating just started
            if is_simulating or status.is_active:
                st.session_state.selected_session_name = session_names[0]
            
            if "selected_session_name" not in st.session_state or st.session_state.selected_session_name not in session_names:
                st.session_state.selected_session_name = session_names[0]

            # Calculate index safely
            try:
                radio_idx = session_names.index(st.session_state.selected_session_name)
            except:
                radio_idx = 0

            with st.container(height=600, border=True):
                selected_session_name = st.radio(
                    "Select Session",
                    options=session_names,
                    index=radio_idx,
                    label_visibility="collapsed",
                    key="session_radio",
                    on_change=save_ui_state
                )
                if st.session_state.selected_session_name != selected_session_name:
                    st.session_state.selected_session_name = selected_session_name
                    save_ui_state()

            if selected_session_name:
                selected_path = storage_root / selected_session_name
                if st.button("Clear Logs", width="stretch", key="btn_clear_logs"): 
                    clear_session_logs(str(selected_path))
                    st.rerun()
                
                config_file = selected_path / "run_config.json"
                if config_file.exists():
                    with st.expander("View Config", expanded=False):
                        try:
                            with open(config_file, "r") as f:
                                st.json(json.load(f))
                        except:
                            st.error("Failed to load config.")

    with main_col:
        # Live Stream Section
        st.subheader("Live Stream")
        if buf and buf.current_size > 0:
            f = buf.get_frames(start_frame_index=-1, frame_count=1)
            if f: st.image(f[0]["data"], width="stretch")
        else:
            st.info("Stream inactive. Start monitoring or simulation to see frames.")

        # Bottom Section: Context-Aware
        # Show logs if actively simulating OR if looking at a past simulation session
        show_logs = is_simulating or (selected_session_name and selected_session_name.startswith("sim_"))
        
        if show_logs:
            st.subheader("AI Analysis Logs")
            if selected_session_name:
                entries = read_last_log_entries(str(storage_root / selected_session_name), n=20)
                if not entries:
                    st.write("No analysis entries found.")
                else:
                    for idx, e in enumerate(entries):
                        is_current = (e.get('session_id') == smgr.current_session_id)
                        with st.expander(f"{e.get('timestamp')} | Model: {e.get('model')}", expanded=is_current):
                            if "error" in e:
                                st.error(e["error"])
                            else:
                                st.markdown(e.get("story"))
                                st.caption(f"Prompt: {e.get('prompt')}")
                                st.caption(f"Frames: {e.get('frame_indices')}")
        else:
            st.subheader("Recent History")
            if buf and buf.current_size > 0:
                fs = buf.get_frames(start_frame_index=-1, frame_count=12, frame_interval=-1)
                cols = st.columns(4)
                for i, f in enumerate(fs):
                    cols[i%4].image(f["data"], caption=f"Idx {f['index']}", width="stretch")
            else:
                st.write("No historical frames available.")

def main():
    import sys
    from streamlit.web import cli as stcli
    import os
    file_path = os.path.abspath(__file__)
    sys.argv = ["streamlit", "run", file_path, "--browser.gatherUsageStats", "False", "--server.headless", "True", "--server.port", "8501"]
    stcli.main()

if __name__ == "__main__":
    show_ui()
