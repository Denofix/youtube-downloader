# Legacy desktop source

The original main.py, icons, screenshots, MIT license and history are retained. requirements-original.txt preserves the original UTF-16 freeze for audit. The separate runtime/build lists are for isolated historical experiments, not the web service.

The GUI remains legacy: its Windows FFmpeg/folder handling, static formats and exception callbacks are described in the audit. These files do not claim that the old executable has been repaired. Current development uses the web-service runtime in pyproject.toml/uv.lock; the root requirements.txt is its UTF-8 frozen export.
