# Monitor MCP Feature Specification Contract

This document serves as the absolute source of truth for the behavior of the `monitor_mcp` application. It acts as a binding contract between Implementing Agents (developers) and Testing Agents (QA).

*   **Implementing Agents:** Must ensure the code strictly adheres to these rules. Any intentional deviations must be documented here first.
*   **Testing Agents:** Must assert against these exact rules. Any undocumented behavior or deviation from this spec is an automatic test failure.

---

## 1. Feature: Live Monitoring Lifecycle & UX

### 1.1 Functional Requirements
*   The system shall capture screen frames at a specified frequency.
*   The system shall maintain a circular buffer of the most recent `N` frames.
*   The system shall respect a Time-To-Live (TTL) parameter, automatically shutting down the observation loop if `ttl_minutes > 0` and the time is exceeded.

### 1.2 UI / UX State Contract
*   **Initial State:** 'Start' button is Enabled. 'Stop' button is Disabled.
*   **Action:** Click 'Start'.
    *   **Expected State:** 'Start' button becomes Disabled.
    *   **Expected State:** 'Stop' button becomes Enabled.
    *   **Metrics:** 'Buffer', 'Captured', 'Uptime', 'FPS', 'Size', and 'Total' metrics begin updating.
*   **Action:** Click 'Stop' (or TTL expires).
    *   **Expected State:** 'Start' button becomes Enabled.
    *   **Expected State:** 'Stop' button becomes Disabled.
    *   **Metrics:** 'FPS' returns to 0.0. Other metrics freeze at their last known values.

---

## 2. Feature: AI Sandbox Simulation Lifecycle & UX

### 2.1 Functional Requirements
*   The system shall parse an existing directory of JPEG frames simulating a live screen capture session (`FolderFeeder`).
*   The system shall sequentially send buffered frames to a configured AI model for analysis at a specified interval (`AIAnalyzer`).
*   Both feeder and analyzer loops must respect a TTL parameter.

### 2.2 UI / UX State Contract
*   **Initial State:** 'Start Sim' button is Enabled. 'Stop Sim' button is Disabled.
*   **Action:** Click 'Start Sim'.
    *   **Expected State:** 'Start Sim' button becomes Disabled immediately (Streamlit `st.rerun()` must execute).
    *   **Expected State:** 'Stop Sim' button becomes Enabled immediately.
*   **Action:** Click 'Stop Sim' (Manual Termination).
    *   **Expected State:** 'Start Sim' button becomes Enabled.
    *   **Expected State:** 'Stop Sim' button becomes Disabled.
*   **Action:** Simulation completes naturally (FolderFeeder runs out of frames).
    *   **Expected State:** The UI must automatically reset to the stopped state ('Start Sim' Enabled, 'Stop Sim' Disabled) without requiring manual interaction.

### 2.3 Background Lifecycle Contract (Critical)
*   **Initialization:** `FolderFeeder` and `AIAnalyzer` threads must start synchronously.
*   **Termination (Manual):** Clicking 'Stop Sim' must immediately send a stop event to both threads, joining them cleanly without deadlocks.
*   **Termination (Autonomous Sync):** 
    *   When `FolderFeeder` exhausts the source directory, it sets `is_finished = True`.
    *   **Rule:** The `AIAnalyzer` loop MUST monitor the `FolderFeeder` state. When the feeder is finished, the analyzer must gracefully break its loop and terminate. It must NEVER loop indefinitely on a frozen buffer.

---

## 3. Feature: Output Artifacts & Logging Standard

### 3.1 Artifact Contract
*   **Session Directory:** Every time Live Monitoring or Simulation is started, a new unique directory must be created.
    *   Live format: `screenshots/YYMMDD_HHMMSS/`
    *   Sim format: `screenshots/sim_YYMMDD_HHMMSS/`
*   **Configuration:** A `run_config.json` file must be deposited in the session directory detailing the parameters used for that specific run.
*   **AI Logs:** The `AIAnalyzer` must generate an `analysis_YYMMDD_HHMMSS.jsonl` file in the session directory.
    *   **Structure:** Each line must be a valid JSON object containing: `session_id`, `timestamp`, `model`, `prompt`, `story` (the raw LLM response), `frame_indices`, and `config`.

### 3.2 Terminal Logging Contract (Noise & Formatting)
*   **Clean Output:** The application must run cleanly. It shall NOT flood the terminal (`stderr` or `stdout`) with framework warnings (e.g., Streamlit deprecation warnings like `use_container_width`). All UI elements must use up-to-date framework parameters.
*   **Encoding Safety:** Terminal logging routines (specifically when printing AI generated text) MUST be safe against UnicodeEncodeErrors on restricted environments (like Windows CMD). Emojis and specialized characters must either be gracefully degraded for terminal output or completely supported by a custom logger handler, ensuring the application never crashes due to a print statement.
*   **Isolated Logging Directory:** The application MUST output application logs (e.g., `monitor.log`) to a dedicated `logs/` subdirectory at the project root. The project root directory itself MUST remain free of runtime log artifacts.

---

## 4. Feature: Unified Dashboard Layout

### 4.1 Main View Layout (Context-Aware)
*   The application shall use a single, unified main view area rather than separated "Live", "History", and "Logs" tabs.
*   **Top Section (Live Stream):** The most recent frame from the active buffer (either Monitoring or Simulation) MUST always be displayed at the top of the main view to provide a continuous video-like feed. The refresh rate of this feed is tied to the UI fragment update interval.
*   **Bottom Section (Dynamic Context):**
    *   **During Simulation (`is_simulating == True`):** The space beneath the Live Stream MUST display the AI Analysis Logs (expandable JSONL entries) for the currently selected session. The History grid is hidden.
    *   **During Monitoring/Idle (`is_simulating == False`):** The space beneath the Live Stream MUST display a grid of recent historical frames (e.g., the last 12 frames). AI Analysis Logs are hidden.

### 4.2 Session Navigation & Visibility
*   **Session List:** Past and current sessions MUST be listed in a highly visible, scrollable window/container (e.g., using a radio list) alongside the main stream, replacing hidden dropdowns (`st.selectbox`). 
*   **Auto-Selection:** When a new Monitoring or Simulation session is initiated, the Session List MUST automatically select and focus on the newly created session, immediately rendering its context in the main view.
*   **Retrospective Viewing Contract (Offline State):** Selecting a historical `sim_` session from the navigation list MUST immediately render the AI Analysis Logs for that session in the bottom main view, regardless of whether the engine is currently idle or active. The UI must not revert to "Recent History" simply because the engine is stopped if a simulation session is explicitly selected.

---

## 5. Feature: UI State Persistence

### 5.1 Persistence Contract
*   The application MUST persist all user-configurable UI parameters (e.g., text inputs, numbers, sliders, checkboxes) across browser refreshes and server restarts.
*   **Scope:** This includes, but is not limited to, settings in the "Monitoring", "AI Sandbox", and "Manual Query" expandable sidebars.
*   **Storage Location:** The persistent state MUST be saved in a hidden JSON file located strictly within the isolated logging directory (`logs/.ui_state.json`), maintaining the cleanliness of the project root.
*   **Real-time Synchronization:** The persistent state file MUST be updated dynamically in real-time as the user modifies values on the dashboard, ensuring no manual "Save" action is required to persist settings.
