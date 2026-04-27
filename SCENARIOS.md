# Scenarios & API Design

This document outlines the core use cases and technical logic behind the `monitor_mcp` API.

## 🎯 Core Scenarios

`monitor_mcp` is designed for scenarios where an LLM needs to observe a computer screen over time to perform visual reasoning, debugging, or monitoring tasks.

### 1. The "Continuous Observer"
**Scenario**: An AI agent is helping a user debug a flaky UI test.
- **LLM Call**: `start_monitoring(screen=1, freq=1.0, max_images=600)`
- **Behavior**: The server captures the primary screen once per second, keeping a 10-minute rolling window (600 frames) in memory.

### 2. The "Retrospective Debugger"
**Scenario**: Something just went wrong on the screen (e.g., an error message appeared). The AI wants to see what happened leading up to that moment.
- **LLM Call**: `get_imgs(start=-1, count=10, interval=-10)`
- **Logic**: 
    - `start=-1`: Start at the most recent frame.
    - `count=10`: Get 10 frames total.
    - `interval=-10`: Jump backwards by 10 frames (if freq=2fps, this retrieves a frame every 5 seconds).
- **Result**: The AI gets a time-lapse of the last 50 seconds.

### 3. The "State Change Validator"
**Scenario**: The AI performed an action (like a click) and wants to see the immediate result.
- **LLM Call**: `get_imgs(start=-5, count=5, interval=1)`
- **Result**: Retrieves the last 5 frames in chronological order to observe the UI transition.

---

## 🛠️ API Specification

### `start_monitoring`
Initializes a background observation thread. 
- **Frequency**: Controlled via `frequency` (Hz). High frequency allows for smooth animation capture; low frequency saves memory and processing power.
- **Buffer Management**: `max_images` defines the capacity of the `collections.deque` circular buffer. Once reached, the oldest frames are automatically dropped.

### `get_imgs`
The primary retrieval tool. It uses a flexible indexing system inspired by Python's slicing:
- **Relative Indexing**: `start` values < 0 are relative to the end of the buffer. `-1` is always the "latest" frame.
- **Strided Retrieval**: `interval` (or "step") allows the LLM to "skip" frames to look further back in time without fetching every single image.
- **On-Demand Encoding**: To save RAM, images are stored in memory as PIL objects. They are converted to JPEG/Base64 only at the moment of the tool call.

### `stop_monitoring`
Safely terminates the capture thread. This is crucial for resource management when the LLM's task is complete.

---

## 🏗️ Technical Implementation
- **Capture**: Uses the `mss` library, which bypasses many of the performance bottlenecks found in standard Python imaging libraries.
- **Threading**: Uses a `threading.Thread` with a `threading.Event` kill-switch to ensure the capture loop doesn't hang the main MCP server.
- **Thread-Safety**: A `threading.Lock` protects the circular buffer during simultaneous write (capture loop) and read (LLM query) operations.

---

## 🔍 Relation to Existing Projects

During the planning of `monitor_mcp`, several prominent projects were analyzed:

1. **`Z-ComputerUse-MCP-Server`**: A robust server for full computer control (mouse/keyboard). While high-performance, it is designed for *action*. Using it would have required stripping out 80% of the code to create a dedicated observer.
2. **`gemma-screen-observer`**: Focused on vision-based game testing. It performs analysis *inside* the capture loop. `monitor_mcp` differs by acting as a "dumb buffer" that allows the LLM to decide when and what to analyze retrospectively.
3. **`Anthropic Computer Use Demo`**: The industry reference for visual agents, but primarily optimized for Linux/Docker/X11 environments.
4. **`Screenpipe`**: Excellent for 24/7 recording and retrospective search, but less suited for fine-grained, tool-triggered observation sessions with specific frequency/resolution constraints.

## ⚖️ Justification for Our Path

We chose to build `monitor_mcp` from scratch to achieve three main goals:

- **Lightweight Precision**: By building from scratch, we implemented the exact `get_imgs(start, count, interval)` logic requested without the overhead of existing automation frameworks.
- **Cross-Platform Reliability**: We "stole" the best engine choice (`mss`) from top projects to ensure high-speed capture on Windows, Mac, and Linux, while keeping the implementation minimal and readable.
- **Modern MCP Native**: Using `FastMCP` (Python) allowed us to create a server that is easy to extend, debug, and integrate into modern LLM workflows without legacy baggage.
