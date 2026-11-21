# 🎬 AutoClip AI: Autonomous AI Video Clipping Pipeline

> **Production-Grade Autonomous Short-Form Video Studio (9:16) for YouTube Shorts, Instagram Reels, and TikTok.**

AutoClip AI accepts virtually any long-form video source (YouTube URLs, direct live streams, local MP4/MOV/MKV/WebM files, gaming footage, podcasts, and interviews), intelligently detects high-retention viral moments, reframes landscape footage into 1080×1920 vertical format, burns in animated captions with dynamic word-level highlights, masters audio loudness, embeds customizable creator watermarks (`@BallQ_FC`), generates high-CTR thumbnails, crafts social media metadata, and verifies quality automatically.

---

## ⚡ Features & Capabilities

- **Universal Media Ingestion**: Direct ingestion from local video files or web URLs using `yt-dlp` and `FFmpeg`.
- **Autonomous Livestream Monitoring**: Continuously monitors active YouTube livestreams, captures rolling buffers, detects peak surprise & action spikes, and renders shorts in real-time.
- **Speech Recognition & Alignment**: Dual-engine Whisper with millisecond-accurate word timestamps and automatic language identification.
- **Hinglish Transliteration Engine**: Pure-Python rule-based and colloquial dictionary engine that seamlessly converts Devanagari/Hindi speech to Romanized Hinglish for high-engagement viral captions.
- **Aesthetic Viral Title Presets**:
  - **TikTok / Instagram Sticker Pill**: White rounded card with dark text and optional emoji (`border-radius: 24px`).
  - **Heavy White Stroke**: Bold white lettering with a 6px solid black outline for maximum readability over fast gameplay.
  - **Condensed POV**: Compact white condensed font with a clean black stroke.
  - **Minimalist Modern White**: Sleek white typography with subtle drop-shadow.
- **Creator Watermark Engine**: Automatically applies creator branding (default: `@BallQ_FC`) across all exported clips via synchronized ASS subtitle events and transparent PNG overlays.
- **Intelligent 9:16 Video Reframing**:
  - **Blurred-Background Layout**: Aesthetic full-bleed blurred backdrop with centered 16:9 foreground for presentations, gaming, and screen recordings.
  - **Smart Face Crop**: Subject detection and camera motion smoothing (Exponential Moving Average) to follow active speakers.
  - **Split-Screen Layout**: Multi-speaker / podcast format.
- **Animated Captions & Styling**: Word-by-word synchronized karaoke captions with active yellow highlights (`&H0000FFFF&`).
- **Broadcast Audio Mastering**: EBU R128 loudness normalization (`-14 LUFS`), peak limiting, and noise cleanup.
- **Automated Quality Control (QC)**: Verifies 1080×1920 geometry, 9:16 aspect ratio, duration constraints, audio sync, and black/corrupted frames.
- **Dual Interface**:
  - **CLI**: Direct terminal automation for batch jobs and headless servers.
  - **Web Dashboard Studio**: Real-time dark-themed web dashboard with live SSE progress, video player, and one-click ZIP packaging.

---

## 🖥 System Architecture & Workspace Layout

```text
video clipper/
│
├── bin/                          # Locally bundled FFmpeg 9.1 & FFprobe binaries
│   ├── ffmpeg.exe
│   └── ffprobe.exe
│
├── config/                       # Pipeline configuration & presets
│   ├── settings.yaml             # Core resolution, hardware, branding, and audio settings
│   └── presets.yaml              # Subtitle typography & color styling presets
│
├── models/                       # Local AI model weights
│   ├── ggml-tiny.bin             # Fast local Whisper speech model
│   └── ggml-base.bin             # Balanced Whisper model
│
├── src/                          # Modular autonomous pipeline components
│   ├── __init__.py
│   ├── media_inspector.py        # FFprobe metadata extraction
│   ├── ingestion.py              # yt-dlp & audio normalizer
│   ├── transcription.py          # Native GPU Whisper.cpp engine
│   ├── transliteration.py        # Devanagari to Hinglish transliterator
│   ├── watermark.py              # Creator watermark & branding manager
│   ├── semantic_analyzer.py      # Linguistic & context scoring
│   ├── hook_detector.py          # 3-5s opening hook evaluator
│   ├── retention_scorer.py       # Multi-signal 0-100 score engine
│   ├── clip_selector.py          # Moment selector & boundary alignment
│   ├── face_tracker.py           # Subject tracker & EMA motion smoother
│   ├── smart_crop.py             # 9:16 vertical reframing filters
│   ├── caption_generator.py      # ASS animated subtitle engine
│   ├── audio_processor.py        # EBU R128 loudness mastering
│   ├── video_editor.py           # FFmpeg compositing & NVENC encoder
│   ├── live_stream_monitor.py    # Autonomous rolling live stream clipper
│   ├── thumbnail_generator.py    # 1080x1920 thumbnail designer
│   ├── metadata_generator.py     # Social media copywriter
│   ├── quality_control.py        # Automated export QC checks
│   ├── pipeline.py               # Master autonomous orchestrator
│   └── server.py                 # REST & SSE Studio Web Server
│
├── dashboard/
│   └── index.html                # Dark-themed responsive UI
│
├── input/                        # Input video files
├── output/                       # Output artifacts
│   ├── clips/                    # Exported 1080x1920 MP4s
│   ├── thumbnails/               # Exported 1080x1920 JPGs
│   ├── captions/                 # Synchronized .ass files
│   └── metadata/                 # Platform JSON metadata
│
├── final_clips/                  # Autonomous live stream deliverables
├── tests/
│   ├── test_pipeline.py          # Automated synthetic test suite
│   └── test_watermark.py         # Watermark engine unit tests
│
├── main.py                       # Application entry point & CLI
├── requirements.txt              # Dependency specifications
└── README.md
```

---

## 🚀 Quickstart Guide

### 1. Requirements
- **OS**: Windows 10/11, macOS, or Linux
- **Python**: 3.10+
- **Hardware Acceleration**: NVIDIA GPU with CUDA/NVENC support (automatically used when detected; seamless CPU fallback if unavailable).

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Harshvardhan005/video-cliper.git
cd video-cliper

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate       # On Windows
# source venv/bin/activate  # On macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### 3. Running the CLI Pipeline

Process any video file or URL into 3 viral vertical clips:

```bash
python main.py process "https://www.youtube.com/watch?v=VIDEO_ID" --clips 3 --layout smart_auto --burn-captions
```

Process a local file:

```bash
python main.py process input/podcast_interview.mp4 --clips 3 --burn-captions
```

### 4. Running the Autonomous Livestream Clipper

To autonomously monitor a live stream, detect action/surprise peaks, and render vertical shorts continuously:

```bash
python src/live_stream_monitor.py
```

### 5. Launching the Web Studio Dashboard

```bash
python main.py serve --port 8000
```
Then open `http://localhost:8000` in your web browser.

---

## 🏷️ Creator Watermark Configuration

Configure creator branding inside `config/settings.yaml`:

```yaml
branding:
  watermark: "@BallQ_FC"
  enabled: true
  opacity: 0.85
  font_size: 34
  position: "center_below_video"  # Options: center_below_video, center_above_video, top_right, bottom_right
```

---

## 🧪 Testing

Run the automated test suites:

```bash
# Watermark unit tests
python tests/test_watermark.py

# End-to-end pipeline integration tests
python tests/test_pipeline.py
```

---

## 📜 License

MIT License. Built for autonomous video production and short-form content engineering.
