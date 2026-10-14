# File Downloader

A **Flask web app for downloading videos and files** from URLs. Paste a link and
it queues the download, tracks progress/status, and lets you grab the finished
file from the browser. Supports common video formats and uses `yt-dlp` for
site-aware downloads (including Mail.ru via `mailru.py`).

## Features
- Browser UI (Flask + templates) — no desktop app needed
- Queued downloads with live status + history
- `yt-dlp`-powered extraction across many sites
- Handles mp4/mkv/webm/mov/avi and more; 16 MB request cap for direct uploads

## Stack
Python · Flask · yt-dlp · requests

## Getting started
```bash
pip install -r requirements.txt
python filedownloader.py          # serves the web UI
```

## Notes
- Downloads land in `downloads/`; temporary files in `temp/`.
- Only download content you have the right to download.
