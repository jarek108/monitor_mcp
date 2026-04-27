# monitor_mcp

An MCP (Model Context Protocol) server that allows LLMs to control screen monitoring procedures.

## Features
- **Controlled Observation**: LLM can start/stop monitoring with specific parameters (screen, frequency, max images).
- **History Retrieval**: Query frames from a circular buffer using relative indices and strides.
- **Cross-Platform**: Works on Windows, macOS, and Linux using `mss`.

## Tools
- `start_monitoring`: Begin capturing screen frames.
- `stop_monitoring`: Stop the observation loop.
- `get_imgs`: Retrieve specific frames from the buffer.
