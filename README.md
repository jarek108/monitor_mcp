# monitor_mcp

An MCP (Model Context Protocol) server that allows LLMs to control screen monitoring procedures.

## Features
- **Controlled Observation**: LLM can start/stop monitoring with specific parameters (screen, frequency, max images).
- **History Retrieval**: Query frames from a circular buffer using relative indices and strides.
- **Efficient Capture**: Uses `mss` for high-performance, cross-platform screen grabbing.
- **Memory Management**: Uses a thread-safe circular buffer to limit memory usage.

## Installation

```bash
pip install .
```

## Tools

### `start_monitoring`
Begins the background capture loop.
- `screen` (int): Index of the monitor (default: 0).
- `frequency` (float): Captures per second (default: 2.0).
- `max_images` (int): Capacity of the circular buffer (default: 3600).
- `max_resolution` (list[int]): Optional resize target [width, height].

### `stop_monitoring`
Stops the background capture loop.

### `get_imgs`
Retrieves frames from the buffer.
- `start` (int): Index to start from (-1 for latest).
- `count` (int): Number of images to return.
- `interval` (int): Stride between images (negative for backwards).

### `get_monitoring_status`
Returns information about the current monitoring session.

### `list_monitors`
Lists all available monitors and their dimensions.

## Development

Run tests:
```bash
PYTHONPATH=src pytest
```
