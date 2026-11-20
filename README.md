# 🎬 AutoClip AI: Autonomous AI Video Clipping Pipeline

> **Production-Grade Autonomous Short-Form Video Studio (9:16) for YouTube Shorts, Instagram Reels, and TikTok.**

AutoClip AI accepts virtually any long-form video source (YouTube URLs, direct streaming links, local MP4/MOV/MKV/WebM files, gaming footage, podcasts, and interviews), intelligently detects high-retention viral moments, reframes landscape footage into 1080×1920 vertical format, burns in animated captions with dynamic word-level highlights, masters audio loudness, generates high-CTR thumbnails, crafts social media metadata, and verifies quality automatically.

---

## ⚡ Features & Capabilities

- **Universal Media Ingestion**: Automatic ingestion from local files or web URLs using `yt-dlp` and `FFmpeg`.
- **Speech Recognition & Alignment**: Dual-engine Whisper (`whisper.cpp` native C++ GPU/CPU engine with fast CTranslate2/faster-whisper support) providing millisecond-accurate word timestamps.
- **Autonomous Viral Moment Detection**:
  - **Hook Detector**: Identifies question hooks, truth revelations, pattern interrupts, and curiosity dialogue in the first 3–5 seconds.
  - **Semantic Understanding**: NLP density analysis detecting emotional peaks, actionable insights, controversies, and Q&A pairs.
  - **Multi-Signal Retention Scoring**: 0–100 weighted score combining Hook Strength (25%), Emotional Engagement (20%), Information Value (20%), Narrative Completeness (15%), Visual Activity (10%), and Audio Quality (10%).
- **Intelligent 9:16 Video Reframing**:
  - **Smart Face Crop**: Subject detection and camera motion smoothing (Exponential Moving Average) to follow active speakers.
  - **Blurred-Background Layout**: Aesthetic full-bleed blurred backdrop with centered 16:9 foreground for presentations, gaming, and screen recordings.
  - **Split-Screen Layout**: Multi-speaker / podcast format.
- **Animated Captions & Styling Presets**:
  - **Alex Hormozi Style**: High-energy uppercase bold captions with dynamic yellow/gold active word highlights.
  - **Clean Minimalist**: Modern sans-serif with subtle contrast.
  - **Podcast / Interview**: Balanced dialogue subtitle placement.
  - **Gaming Neon**: High-octane magenta/cyan styling.
  - **Cinematic**: Elegant serif subtitle pacing.
- **Audio Mastering**: Broadcast-standard EBU R128 loudness normalization (`-14 LUFS`), peak limiting, and noise cleanup.
- **High-CTR Thumbnail Generation**: Automatic keyframe selection based on sharpness/contrast with bold headline typography and viral badges.
- **Platform-Specific Metadata**: Titles, summaries, keyword tags, and optimized hashtag bundles tailored for YouTube Shorts, Instagram Reels, and TikTok.
- **Automated Quality Control (QC)**: Automated verification of duration, 1080×1920 resolution, 9:16 aspect ratio, audio presence, and dark/black frame detection.
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
│   ├── settings.yaml             # Core resolution, hardware, and audio settings
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
│   ├── semantic_analyzer.py      # Linguistic & context scoring
│   ├── hook_detector.py          # 3-5s opening hook evaluator
│   ├── retention_scorer.py       # Multi-signal 0-100 score engine
│   ├── clip_selector.py          # Moment selector & boundary alignment
│   ├── face_tracker.py           # Subject tracker & EMA motion smoother
│   ├── smart_crop.py             # 9:16 vertical reframing filters
│   ├── caption_generator.py      # ASS animated subtitle engine
│   ├── audio_processor.py        # EBU R128 loudness mastering
│   ├── video_editor.py           # FFmpeg compositing & NVENC encoder
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
├── temp/                         # Temporary audio/video buffers
├── logs/                         # Execution logs
├── tests/
│   └── test_pipeline.py          # Automated synthetic test suite
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

### 2. Launch the Web Studio Dashboard

To launch the local web interface:

```powershell
.\venv\python.exe main.py server --host 127.0.0.1 --port 8000
```

Open your browser to:
👉 **`http://127.0.0.1:8000`**

From the dashboard:
1. Paste a video URL (e.g. YouTube) or select a local video file (`.mp4`, `.mov`, `.mkv`).
2. Choose your preferred **Caption Style** (`Alex Hormozi`, `Clean Minimalist`, `Podcast`, `Gaming Neon`, `Cinematic`).
3. Select your target **Clip Duration** (`short: 15-30s`, `medium: 30-45s`, `long: 45-60s`).
4. Select **Layout Mode** (`Smart Face Crop`, `Blurred Letterbox`, `Split Screen`).
5. Click **Run Autonomous Pipeline** and watch real-time processing and preview/download generated clips.

---

### 3. CLI Command-Line Usage

Process any video directly from the terminal:

```powershell
# Process a local video
.\venv\python.exe main.py process -i "path/to/video.mp4" -d medium -n 5 -p hormozi

# Process a YouTube video directly
.\venv\python.exe main.py process -i "https://www.youtube.com/watch?v=..." -d short -n 3 -p minimal

# Display environment & hardware diagnostics
.\venv\python.exe main.py info
```

#### CLI Options:
| Flag | Description | Default |
|---|---|---|
| `--input`, `-i` | Video file path or URL | *Required* |
| `--duration`, `-d` | Target clip duration (`short`, `medium`, `long`, `extended`) | `medium` |
| `--preset`, `-p` | Caption style preset (`hormozi`, `minimal`, `podcast`, `gaming`, `cinematic`) | `hormozi` |
| `--max-clips`, `-n` | Maximum number of clips to produce | `5` |
| `--layout`, `-l` | Layout mode (`smart_auto`, `face_crop`, `blurred_bg`, `split_screen`) | `smart_auto` |
| `--model-size` | Whisper model (`tiny`, `base`, `small`, `medium`) | `tiny` |
| `--device` | Execution device (`auto`, `cuda`, `cpu`) | `auto` |

---

## 🧪 Automated Testing

Run the automated test suite verifying media ingestion, FFmpeg encoding, hook detection, caption synchronization, vertical reframing, and quality verification:

```powershell
.\venv\python.exe tests\test_pipeline.py
```

---

## 🛡 Quality Control & Verification

Every generated clip passes an automated multi-point inspection before delivery:
- **File Integrity**: Verifies non-empty file write.
- **Resolution**: Strict verification of `1080 × 1920` vertical canvas.
- **Aspect Ratio**: Mathematical validation of `9:16` geometry.
- **Audio Integrity**: Confirms valid audio stream, loudness compliance, and synchronization.
- **Black Frame Check**: Samples frames across the video to detect accidental black/corrupted sequences.

