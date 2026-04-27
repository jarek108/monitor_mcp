# monitor_mcp 🖥️

`monitor_mcp` is a Model Context Protocol (MCP) server that empowers LLMs to observe and monitor screen contents in real-time. It provides a controlled observation loop with a thread-safe circular buffer, allowing for efficient frame capture and retrieval.

---

## 🚀 Quickstart

### 1. Installation
Requires Python **>=3.10**. 

Clone the repository and install the package in editable mode:
```bash
git clone https://github.com/jarek108/monitor_mcp.git
cd monitor_mcp
pip install -e .
```

### 2. Manual Testing (Dashboard)
After installation, the project includes a dedicated visual "Surface" for manual control. This eliminates the need for the generic MCP inspector:

```bash
# Option A: Using the built-in CLI command
monitor-mcp-ui

# Option B: Running via python
python -m monitor_mcp.ui
```

This will open a browser window where you can:
- Configure screen, frequency, and resolution.
- Start/Stop monitoring with one click.
- See a **live preview** of the capture.
- Browse the history gallery of recently captured frames.

### 3. Alternative Testing (MCP Inspector)
If you want to test the raw MCP protocol:
```bash
npx -y @modelcontextprotocol/inspector python -m monitor_mcp.server
```

### 3. LLM Integration
Add the server to your MCP client configuration (e.g., Claude Desktop, Windsurf, or Cursor):
```json
{
  "mcpServers": {
    "monitor-mcp": {
      "command": "python",
      "args": ["-m", "monitor_mcp.server"],
      "env": {
        "PYTHONPATH": "path/to/monitor_mcp/src"
      }
    }
  }
}
```

---

## 📜 Scenarios & API Design
For a detailed breakdown of real-world use cases, planned scenarios, and the design philosophy of the retrieval API, see the [Scenarios & API Design Page](SCENARIOS.md).

---

## ✨ Features
- **High-Performance Capture**: Uses `mss` for low-latency screen grabbing on Windows, macOS, and Linux.
- **DPI Aware**: Handles high-resolution displays correctly on Windows.
- **Circular Buffer**: Stores a rolling history of frames in memory without exhausting RAM.
- **Advanced Retrieval**: Retrieve frames using relative indices (`-1` for latest) and custom strides (e.g., every 5th frame).
- **Optional Disk Logging**: Save frames to a directory for manual inspection.
- **Configurable Defaults**: Manage settings via a central `config.json`.

## 🏛️ Architecture: Surface vs. Backend

`monitor_mcp` is designed with a dual-layer approach:

1.  **The Backend (MCP Server)**: A headless Python process that talks to LLMs. It handles the "dirty work" of high-speed capture, circular buffering, and threading.
2.  **The Surface (Streamlit Dashboard)**: A visual interface for humans. It connects to the same logic as the backend, allowing you to monitor the monitoring process, verify results, and manually adjust settings without JSON editing.

---

## ⚙️ Configuration

A `config.json` file in the root directory manages global defaults:

```json
{
    "screen": 0,           // 0 = All monitors, 1+ = specific monitor
    "frequency": 2.0,      // Captures per second
    "max_images": 3600,    // Buffer capacity
    "max_resolution": null,// [width, height] or null
    "storage_path": "screenshots",
    "save_to_disk": false  // Set to true to log every frame to disk
}
```

---

## 🛠️ Tool Reference

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `start_monitoring` | `screen`, `frequency`, `max_images`, `max_res`, `save_to_disk`, `reset_cache` | Begins background observation. Overrides `config.json`. |
| `stop_monitoring` | *None* | Stops the capture thread and clears the session. |
| `get_imgs` | `start` (idx), `count`, `interval` | Returns a list of Base64 encoded frames. |
| `get_monitoring_status` | *None* | Returns active state, buffer size, and total frames captured. |
| `list_monitors` | *None* | Lists available screens and their resolutions. |

### Retrieval Logic Examples
- **Latest Frame**: `start: -1, count: 1`
- **Last 5 Seconds (at 2fps)**: `start: -1, count: 10, interval: -1`
- **Time-lapse (10 frames, 5 seconds apart)**: `start: -1, count: 10, interval: -10`

---

## 🧪 Development & Testing

Run unit and integration tests:
```bash
PYTHONPATH=src pytest
```

The test suite includes:
- **`test_buffer.py`**: Validates the complex indexing and circular wrapping logic.
- **`test_engine.py`**: Verifies screen discovery and capture capabilities.
- **`test_server.py`**: Tests the MCP tool orchestration and threading.

---

## 📜 License
MIT
