# monitor_mcp 🖥️

`monitor_mcp` is a Model Context Protocol (MCP) server that empowers LLMs to observe and monitor screen contents in real-time. It provides a controlled observation loop with a thread-safe circular buffer, allowing for efficient frame capture and retrieval.

---

## 🚀 Quickstart

### 1. Installation
Clone the repository and install the package in editable mode:
```bash
git clone https://github.com/jarek108/monitor_mcp.git
cd monitor_mcp
pip install -e .
```

### 2. Manual Testing (MCP Inspector)
The easiest way to test the server manually is using the MCP Inspector:
```bash
npx -y @modelcontextprotocol/inspector python -m monitor_mcp.server
```
1. Open the provided URL in your browser.
2. Use **`start_monitoring`** to begin capturing.
3. Use **`get_imgs`** with `start: -1` to see the latest frame.
4. Use **`stop_monitoring`** when finished.

### 📜 Scenarios & API Design
For a detailed breakdown of use cases, planned scenarios, and the design philosophy of the retrieval API, see the [Scenarios & API Design Page](SCENARIOS.md).

### 3. LLM Integration
Add the server to your MCP client configuration (e.g., Claude Desktop or Windsurf):
```json
{
  "mcpServers": {
    "monitor": {
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

## ✨ Features
- **High-Performance Capture**: Uses `mss` for low-latency screen grabbing on Windows, macOS, and Linux.
- **DPI Aware**: Handles high-resolution displays correctly on Windows.
- **Circular Buffer**: Stores a rolling history of frames in memory without exhausting RAM.
- **Advanced Retrieval**: Retrieve frames using relative indices (`-1` for latest) and custom strides (e.g., every 5th frame).
- **Optional Disk Logging**: Save frames to a directory for manual inspection.
- **Configurable Defaults**: Manage settings via a central `config.json`.

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
| `start_monitoring` | `screen`, `frequency`, `max_images`, `max_res`, `save_to_disk` | Begins background observation. Overrides `config.json`. |
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
