import subprocess
import time
import os
import sys
import requests
import signal
from pathlib import Path

def kill_related_processes():
    print("Cleaning up existing processes...")
    try:
        # Use our cleanup_utils for the port
        subprocess.run([sys.executable, "tests/e2e/cleanup_utils.py", "8501"], stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"Cleanup warning: {e}")

def run_e2e():
    root_dir = Path(__file__).parent.parent.parent
    print(f"Runner Root Dir: {root_dir}")
    timestamp = time.strftime("%Y_%m_%d_%H_%M_%S")
    run_dir = root_dir / "tests" / "e2e" / "runs" / f"run_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    
    server_log = run_dir / "server_output.log"
    server_err = run_dir / "server_output.err"
    
    kill_related_processes()
    
    print(f"Starting Streamlit in {run_dir}...")
    env = os.environ.copy()
    env["STREAMLIT_SERVER_HEADLESS"] = "true"
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    
    if "GEMINI_API_KEY" in env:
        print(f"GEMINI_API_KEY is set (length: {len(env['GEMINI_API_KEY'])})")
    else:
        print("WARNING: GEMINI_API_KEY is NOT set in environment!")
    
    with open(server_log, "w") as out, open(server_err, "w") as err:
        server_proc = subprocess.Popen(
            ["streamlit", "run", "src/monitor_mcp/ui.py"],
            cwd=str(root_dir),
            env=env,
            stdout=out,
            stderr=err
        )
    
    try:
        # Wait for server
        max_retries = 30
        print("Waiting for http://localhost:8501...", flush=True)
        for i in range(max_retries):
            try:
                resp = requests.get("http://localhost:8501", timeout=1)
                if resp.status_code == 200:
                    print("Server is ready!", flush=True)
                    break
            except:
                pass
            time.sleep(1)
        else:
            print("Server failed to start in time.", flush=True)
            return False
            
        print("Executing test script...", flush=True)
        # We always execute the main suite to guarantee the whole contract is verified
        test_proc = subprocess.run(
            [sys.executable, "tests/e2e/suite_main.py", str(run_dir)],
            cwd=str(root_dir)
        )
        
        if test_proc.returncode == 0:
            print("E2E Test PASSED")
            return True
        else:
            print(f"E2E Test FAILED with return code {test_proc.returncode}")
            return False
            
    finally:
        print("Cleaning up...")
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(server_proc.pid)], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        else:
            server_proc.terminate()
        kill_related_processes()

if __name__ == "__main__":
    success = run_e2e()
    sys.exit(0 if success else 1)
