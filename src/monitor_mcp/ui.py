import streamlit as st
import time
import base64
import io
import os
import json
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

def read_last_log_entries(log_path: str, n: int = 15):
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
        st.warning("No frames found.")

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
        if c1.button("Start", disabled=status.is_active, use_container_width=True):
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
        if sc1.button("Start Sim", disabled=is_simulating, use_container_width=True):
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
        h_col1, h_col2 = st.columns([3, 1])
        with h_col1:
            st.subheader("Analysis Results")
        with h_col2:
            if st.button("🗑️ Clear", use_container_width=True): 
                clear_analysis_log()
                st.rerun()
        
        st.info(f"Storage: `{os.path.abspath('analysis_log.jsonl')}`")
        
        if smgr.current_session_id:
            with st.expander("ℹ️ Current Session Config", expanded=False):
                st.json(smgr.current_config)
                st.caption(f"Session ID: `{smgr.current_session_id}`")

        entries = read_last_log_entries("analysis_log.jsonl", n=20)
        if not entries:
            st.write("No entries found.")
        else:
            for e in entries:
                with st.expander(f"🕒 {e.get('timestamp')} | Session: {e.get('session_id')}", expanded=(e.get('session_id') == smgr.current_session_id)):
                    if "error" in e:
                        st.error(e["error"])
                    else:
                        st.markdown(e.get("story"))
                        st.caption(f"Model: {e.get('model')} | Frames: {e.get('frame_indices')}")

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
