# monitor_mcp 🖥️

`monitor_mcp` is a Model Context Protocol (MCP) server that empowers LLMs to observe and monitor screen contents in real-time, and simulate visual environments via an AI Sandbox. It provides a controlled observation loop with a thread-safe circular buffer, allowing for highly efficient frame capture and retrieval without exhausting system memory.

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

### 2. The Unified Dashboard
After installation, launch the built-in Streamlit dashboard for manual control and visualization. This eliminates the need for the generic MCP inspector:

```bash
# Option A: Using the built-in CLI command
monitor-mcp-ui

# Option B: Running via python
python -m monitor_mcp.ui
```

The dashboard features a **Context-Aware Layout**:
- **Live Stream**: Always visible at the top, showing a live video-like feed of your active monitoring or simulation session.
- **Dynamic Context Area**:
  - *During Monitoring/Idle*: Displays a history grid of recent frames.
  - *During Simulation*: Displays real-time AI Analysis Logs (JSONL) underneath the stream.
- **Session Navigation**: A highly visible, scrollable list of all past and current runs, allowing you to instantly revisit configurations, clear logs, or view historical AI analysis.

### 3. 🤖 AI Sandbox & Simulation
Test AI vision prompts without running an active screen capture! The AI Sandbox allows you to simulate a live environment and evaluate LLM responses:
1. Provide a folder of pre-recorded `.jpg` frames.
2. Configure your model (e.g., `gemini-2.0-flash-lite-preview-02-05`), prompt, delay, and frame offsets.
3. Click **Start Sim**. The `FolderFeeder` will stream the images into the buffer, while the `AIAnalyzer` background thread autonomously evaluates the frames.
4. Results are saved cleanly into isolated session directories as **JSONL** logs (`analysis_*.jsonl`) and are viewable directly in the dashboard.

---

## 🔌 LLM Integration

### Global Integration (OpenCode)
To make these tools available globally to your OpenCode agent, add the following to your `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "monitor-mcp": {
      "type": "local",
      "command": [
        "python",
        "-m",
        "monitor_mcp.server"
      ],
      "environment": {
        "PYTHONPATH": "E:/projects_large/monitor_mcp/src"
      }
    }
  }
}
```

### Manual Project Config
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

## 🛠️ Tool Reference

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `start_monitoring` | `screen`, `frequency`, `max_images`, `max_res`, `save_to_disk`, `reset_cache`, `draw_mouse`, `ttl_minutes` | Begins background observation. Overrides `config.json` defaults for the current session. |
| `stop_monitoring` | *None* | Stops the capture thread and gracefully terminates the session. |
| `get_imgs` | `start_frame_index`, `frame_count`, `frame_interval` | Returns a list of Base64 encoded frames from the active buffer. |
| `get_monitoring_status` | *None* | Returns active state, buffer size, and total frames captured. |
| `list_monitors` | *None* | Lists available screens and their dimensions. |

### Retrieval Logic Examples (`get_imgs`)
- **Latest Frame**: `start_frame_index: -1, frame_count: 1`
- **Last 5 Seconds (at 2fps)**: `start_frame_index: -1, frame_count: 10, frame_interval: -1`
- **Time-lapse (10 frames, 5 seconds apart)**: `start_frame_index: -1, frame_count: 10, frame_interval: -10`

---

## ⚙️ Configuration & Logging

### Defaults (`config.json`)
A `config.json` file in the root directory manages global defaults for the application:

```json
{
    "screen": 0,             // 0 = All monitors, 1+ = specific monitor
    "frequency": 2.0,        // Captures per second
    "max_images": 3600,      // Buffer capacity
    "max_resolution": null,  // [width, height] or null
    "storage_path": "screenshots",
    "save_to_disk": false,   // Set to true to log every frame to disk
    "reset_cache": true,
    "draw_mouse": true,
    "ttl_minutes": 0         // Auto-stop after X minutes. 0 = no limit.
}
```

### Application Logs
The application outputs runtime execution logs (e.g., thread state, warnings, errors) to an isolated `logs/monitor.log` file, ensuring the project root remains free of execution artifacts. Framework warnings are heavily filtered to keep the terminal output clean.

---

## 🏛️ Architecture: Surface vs. Backend

`monitor_mcp` is designed with a dual-layer approach:

1.  **The Backend (MCP Server)**: A headless Python process that talks to LLMs. It handles the high-speed capture via `mss`, circular buffering, and the background synchronization of `ObservationManager`, `SimulationManager`, `FolderFeeder`, and `AIAnalyzer` threads.
2.  **The Surface (Streamlit Dashboard)**: A visual interface for humans. It securely connects to the same memory space as the backend, allowing you to monitor the active monitoring process, view simulation outcomes, and manually adjust settings with real-time UI state synchronization.

---

## 📜 Scenarios & API Design
For a detailed breakdown of real-world use cases, planned scenarios, and the design philosophy of the retrieval API, see the [Scenarios & API Design Page](SCENARIOS.md).

---

## 🧪 Development & Testing

Run unit and integration tests:
```bash
pytest tests/
```

The test suite includes:
- **`test_buffer.py`**: Validates the complex indexing and circular wrapping logic.
- **`test_engine.py`**: Verifies screen discovery and capture capabilities.
- **`test_server.py`**: Tests the MCP tool orchestration, threading, and TTL boundaries.

---

## 🛡️ Quality Assurance & Contracts

This project employs a strict, contract-driven Quality Assurance (QA) methodology designed to be audited by AI agents.

### 1. The Contract (`docs/feature_spec.md`)
This document is the absolute source of truth for the application's expected behavior. It strictly defines UI states, background thread synchronization, artifact generation, and logging constraints. **Any intentional deviation from this behavior must be documented here first.**

### 2. The Enforcer (`tests/e2e/README_AGENT.md`)
We utilize an AI-driven QA process. The instructions in `README_AGENT.md` guide an AI agent to act as an auditor. The agent does not simply click buttons; it writes Playwright scripts to explicitly `assert` that the application's runtime behavior exactly matches the `feature_spec.md` contract.

### 3. The Autonomous E2E Suite
To execute the comprehensive Playwright E2E suite locally:
```bash
python tests/e2e/runner.py
```
This suite autonomously verifies:
- **Layout Integrity:** Dynamic swapping of the Context-Aware layout.
- **Lifecycle Sync:** Background threads (`FolderFeeder` & `AIAnalyzer`) auto-terminating and successfully triggering Streamlit UI resets.
- **Log Cleanliness:** Zero framework deprecation warnings in the terminal output.
- **Project Cleanliness:** Zero runtime artifacts leaked into the project root directory.

---

## 📜 License
MIT
