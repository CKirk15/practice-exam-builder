# Practice Exam Builder

Turns a YouTube playlist of narrated practice questions into a single offline study app.
Iteration 1 targets the DVA-C02 (AWS Certified Developer – Associate) "500 Real Exam
Questions" playlist.

This repository contains the tool only. Ingested transcripts (`sources/`) and the
extracted question bank (`bank/`) are third-party content and are git-ignored. Run the
pipeline below to produce them locally.

## Setup

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Node 22+ must be on PATH. yt-dlp uses it as its YouTube JS runtime, and it runs the JS tests.

## Pipeline

```bash
# 1. Ingest captions + chapters into sources/ (re-runnable; skips finished videos)
.venv/Scripts/python -m peb ingest "https://www.youtube.com/playlist?list=PLB574eEmT4ofjfiABMEx5c19Q_lCbaADV"

# 2. Extract questions into bank/: done by Claude Code following docs/extraction.md

# 3. Validate and build
.venv/Scripts/python -m peb validate
.venv/Scripts/python -m peb build        # -> dist/dva-c02-practice.html
```

If YouTube rate-limits caption downloads (HTTP 429), wait and re-run ingest,
optionally with `--delay 15` or `--cookies-from-browser chrome`.

## Using the app

Open `dist/dva-c02-practice.html` in a browser. There are three areas:

- **Practice** (untimed): works through all questions in random order without repeats. You can filter to never-answered or previously missed questions and pick a session size.
- **Timed exam**: 65 questions in 130 minutes, weighted 21/17/15/12 by DVA-C02 domain.
- **Statistics**: accuracy by domain and by video, your weakest questions, and exam history.

Progress lives in browser storage, so keep the file at a fixed path and use
**Export progress** as a backup.

## Tests

```bash
.venv/Scripts/python -m pytest -q
node --test tests-js/*.test.js
```
