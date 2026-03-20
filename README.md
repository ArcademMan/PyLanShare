<p align="center">
  <img src="pylanshare/assets/icon.png" alt="PyLanShare" width="128" height="128"/>
</p>

<h1 align="center">PyLanShare</h1>

<p align="center">
  Fast, secure file synchronization over your local network.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.12+-blue?logo=python&logoColor=white" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/Qt-PySide6-41cd52?logo=qt&logoColor=white" alt="PySide6"/>
  <img src="https://img.shields.io/badge/protocol-WebSocket-orange?logo=websocket" alt="WebSocket"/>
  <img src="https://img.shields.io/badge/platform-Windows-0078d4?logo=windows&logoColor=white" alt="Windows"/>
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License"/>
</p>

---

## Overview

PyLanShare is a desktop application that synchronizes folders between computers on the same LAN. It uses WebSocket connections with optional TLS encryption and password authentication to transfer files efficiently, compressing data on-the-fly and only sending what has changed.

Part of the **AmMstools** suite.

## Features

- **Sender / Receiver modes** — one machine serves, the other connects
- **Smart sync** — SHA-256 manifest diffing, only changed files are transferred
- **Chunked & compressed** — 1 MB chunks with zlib compression
- **Real-time watching** — detects file changes via `watchdog` and syncs automatically
- **TLS/SSL encryption** — optional certificate-based secure transfer
- **Password authentication** — optional shared-secret handshake
- **Rate limiting** — presets from 1 MB/s to 50 MB/s or unlimited
- **Ignore patterns** — `fnmatch`-style rules (like `.gitignore`) with sensible defaults
- **System tray** — minimize to tray, color-coded status icon, desktop notifications
- **Auto-reconnect** — exponential backoff (5 s → 60 s cap)
- **Dark theme** — modern UI with Segoe UI, rounded corners, blue accents
- **Internationalization** — English and Italian, with auto-detection

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.12+ |
| PySide6 | latest |
| websockets | 16.0+ |
| watchdog | 6.0+ |

## Installation

```bash
# Clone the repository
git clone https://github.com/your-user/PyLanShare.git
cd PyLanShare

# Create a virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install PySide6 websockets watchdog
```

## Usage

```bash
# Run from source
python run.py

# Or as a module
python -m pylanshare
```

### Quick start

1. On **Machine A** (receiver): select _Receive_ mode, choose a destination folder, click **Start**.
2. On **Machine B** (sender): select _Send_ mode, choose the folder to share, enter Machine A's IP and port, click **Start**.
3. Files are synced immediately. Any subsequent changes are detected and transferred in real-time.

## Configuration

Settings are persisted in `%APPDATA%\AmMstools\pylanshare\settings.json`.

| Option | Default | Description |
|---|---|---|
| Role | Send | `Send` or `Receive` |
| Directory | — | Folder to sync |
| Host | `localhost` | Receiver IP address |
| Port | `8765` | WebSocket port |
| Password | — | Shared authentication token |
| Speed limit | Unlimited | `1 / 5 / 10 / 50 MB/s` or unlimited |
| TLS | Off | Enable with certificate and key `.pem` files |
| Minimize to tray | On | Keep running in system tray on close |

## Ignore Patterns

Edit ignore patterns per-directory via the **Ignore Patterns** button. Patterns use `fnmatch` syntax (`*`, `?`).

Default patterns:

```
__pycache__    *.pyc    .git    .venv
.env           *.tmp    .DS_Store
Thumbs.db      *.pylanshare.tmp
```

## Protocol

PyLanShare uses a custom protocol (v2) over WebSocket:

1. **Handshake** — version check + authentication
2. **Manifest exchange** — sender sends SHA-256 file manifest, receiver computes diff
3. **File transfer** — only changed/new files, in compressed 1 MB chunks with binary framing (`PLSC` magic header)
4. **Deletion** — files removed on sender are removed on receiver
5. **Watch** — real-time monitoring with debounced incremental syncs

## Project Structure

```
PyLanShare/
├── run.py                  # Entry point
├── pylanshare/
│   ├── core/               # Protocol, hashing, compression, ignore engine
│   ├── gui/                # PySide6 window, tray, dialogs, async worker
│   ├── net/                # WebSocket sender (client) & receiver (server)
│   ├── watch/              # File system watcher with debouncing
│   └── assets/             # Application icon
└── shared/                 # AmMstools shared utilities
    ├── theme.py            # Dark theme & base window class
    ├── config.py           # JSON settings manager
    ├── i18n.py             # Internationalization
    ├── validation.py       # Input validation
    └── locale/             # en.json, it.json
```

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

## License

This project is licensed under the [MIT License](LICENSE). See [DISCLAIMER](DISCLAIMER.md) for additional terms.
