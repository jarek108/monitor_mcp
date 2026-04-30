import os
import signal
import subprocess
import sys

def kill_process_on_port(port):
    """Finds and kills the process running on the specified port."""
    print(f"Checking for processes on port {port}...")
    
    if sys.platform.startswith('win'):
        # Windows implementation
        try:
            # Get the PID of the process using the port
            cmd = f'netstat -ano | findstr LISTENING | findstr :{port}'
            output = subprocess.check_output(cmd, shell=True).decode()
            for line in output.strip().split('\n'):
                if f':{port}' in line:
                    pid = line.strip().split()[-1]
                    print(f"Found process {pid} on port {port}. Terminating...")
                    subprocess.run(['taskkill', '/F', '/PID', pid], check=True)
                    print(f"Successfully killed process {pid}.")
        except subprocess.CalledProcessError:
            print(f"No active process found on port {port}.")
    else:
        # Unix/Linux/macOS implementation
        try:
            cmd = f'lsof -t -i:{port}'
            pid = subprocess.check_output(cmd, shell=True).decode().strip()
            if pid:
                print(f"Found process {pid} on port {port}. Terminating...")
                os.kill(int(pid), signal.SIGKILL)
                print(f"Successfully killed process {pid}.")
        except subprocess.CalledProcessError:
            print(f"No active process found on port {port}.")

def kill_all_related_processes():
    """Kills all python processes that are running streamlit or monitor_mcp."""
    print("Cleaning up all related python processes...")
    if sys.platform.startswith('win'):
        # On Windows, we can use wmic or tasklist, but Get-Process is better in PS
        # Here we use taskkill for simplicity in a python script
        try:
            # This is broad but effective for a test environment
            cmd = 'taskkill /F /IM python.exe /T'
            # We want to be careful not to kill our own parent if possible, 
            # but usually, the agent runs in a way that this is fine.
            # Actually, let's try to be more specific if possible.
            subprocess.run(['taskkill', '/F', '/IM', 'streamlit.exe'], stderr=subprocess.DEVNULL)
            # Find python processes with 'ui.py' or 'monitor_mcp' in command line is harder with taskkill
        except:
            pass
    else:
        subprocess.run(['pkill', '-f', 'streamlit'], stderr=subprocess.DEVNULL)
        subprocess.run(['pkill', '-f', 'monitor_mcp'], stderr=subprocess.DEVNULL)

if __name__ == "__main__":
    target_port = 8501
    if len(sys.argv) > 1:
        try:
            target_port = int(sys.argv[1])
            kill_process_on_port(target_port)
        except ValueError:
            pass # Not a port
    
    kill_all_related_processes()
