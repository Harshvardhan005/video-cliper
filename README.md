🎬 AI Universal Video Clipper

Turn Long Videos into Viral Shorts Automatically!

An AI-powered video clipping pipeline that transforms long-form content into engaging **9:16 vertical videos** ready for YouTube Shorts, Instagram Reels, and TikTok.

Upload a video or paste a supported video URL. The system analyzes the content, identifies the most engaging moments, automatically edits them, and generates professional short-form videos with synchronized karaoke captions.

---

✨ Features

- 🤖 AI-Powered Clip Detection – Automatically identifies interesting, funny, emotional, and engaging moments.
- 🎯 Smart Moment Selection – Finds high-retention moments using transcription, semantic analysis, and audio/visual signals.
- 🎮 Gaming Video Support – Intelligent gameplay framing and optional facecam layouts.
- 🎙️ **Podcast & Interview Support** – Speaker-focused cropping and stacked layouts.
- 📱 **Automatic 9:16 Conversion** – Converts landscape videos into vertical Shorts and Reels.
- 🗣️ **Karaoke Captions** – Word-by-word animated captions with automatic language detection.
- 👁️ **Face Tracking** – Keeps speakers and important subjects visible.
- 🎨 **Smart Video Editing** – Dynamic zooms, jump cuts, transitions, and audio enhancement.
- 🖼️ **Thumbnail Generation** – Automatically extracts engaging frames for thumbnails.
- 📝 **AI Metadata Generation** – Generates titles, descriptions, and niche-specific hashtags.
- ⚡ **GPU Acceleration** – Uses supported hardware acceleration with CPU fallback.
- 📦 **Batch Processing** – Generate multiple clips from a single long-form video.

---

## 🔄 How It Works

```text
      LONG-FORM VIDEO
             │
             ▼
      VIDEO INGESTION
             │
             ▼
      AUDIO EXTRACTION
             │
             ▼
       AI TRANSCRIPTION
             │
             ▼
     SEMANTIC ANALYSIS
             │
             ▼
      VIRAL MOMENT
        DETECTION
             │
             ▼
      CLIP SELECTION
             │
             ▼
     SMART 9:16 CROPPING
             │
             ▼
      KARAOKE CAPTIONS
             │
             ▼
      VIDEO ENHANCEMENT
             │
             ▼
    THUMBNAILS & METADATA
             │
             ▼
       QUALITY CONTROL
             │
             ▼
       FINAL SHORTS
```

---

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core automation and processing |
| FFmpeg | Video editing, encoding, and rendering |
| Faster-Whisper | AI speech recognition |
| OpenCV | Face detection and tracking |
| yt-dlp | Video downloading |
| PySceneDetect | Scene detection |
| FastAPI | Backend API |
| HTML, CSS, JavaScript | Dashboard interface |
| PyTorch | AI model execution |

---

## 📂 Project Structure

```text
AI-Universal-Video-Clipper/
│
├── config/
│   ├── settings.yaml
│   └── presets.yaml
│
├── models/
│
├── src/
│   ├── ingestion.py
│   ├── transcription.py
│   ├── semantic_analyzer.py
│   ├── hook_detector.py
│   ├── retention_scorer.py
│   ├── clip_selector.py
│   ├── face_tracker.py
│   ├── smart_crop.py
│   ├── caption_generator.py
│   ├── video_editor.py
│   ├── thumbnail_generator.py
│   ├── metadata_generator.py
│   ├── quality_control.py
│   └── pipeline.py
│
├── dashboard/
├── input/
├── output/
│   ├── clips/
│   ├── thumbnails/
│   ├── captions/
│   └── metadata/
│
├── temp_work/
├── logs/
├── tests/
│
├── main.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/AI-Universal-Video-Clipper.git

cd AI-Universal-Video-Clipper
```

### 2. Create a Virtual Environment

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

**Linux / macOS:**

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
python -m pip install --upgrade pip

pip install -r requirements.txt
```

### 4. Install FFmpeg

Make sure FFmpeg and FFprobe are installed and available in your system PATH.

Verify:

```bash
ffmpeg -version
ffprobe -version
```

### 5. Run the Application

```bash
python main.py
```

Follow the startup instructions displayed by the application.

---

## 🎥 Usage

1. Open the local dashboard.
2. Upload a video or paste a supported video URL.
3. Select the number of clips.
4. Choose your preferred caption style.
5. Let the AI analyze the video.
6. Review the selected moments.
7. Generate and export your vertical videos.

### Default Processing Configuration

| Setting | Value |
|---|---|
| Number of clips | 3 |
| Clip duration | 25–55 seconds |
| Aspect ratio | 9:16 |
| Resolution | 1080 × 1920 |
| Frame rate | 60 FPS |
| Video format | MP4 |
| Video codec | H.264 |
| Audio codec | AAC |
| Caption style | Word-by-word karaoke |

---

## 📁 Output

Generated clips are stored inside:

```text
final_clips/
│
├── clip_1.mp4
├── clip_2.mp4
└── clip_3.mp4
```

Each clip can include:

- Original video timestamps.
- Automatically generated captions.
- Suggested viral title.
- Relevant hashtags.
- Thumbnail.
- Clip summary.

---

## 🚀 Supported Content Types

| Content | Framing Mode |
|---|---|
| Gaming Streams | Gameplay + Facecam |
| Podcasts | Speaker-Focused |
| Interviews | Split / Stacked |
| Challenges | Full-Screen Crop |
| Vlogs | Dynamic Tracking |
| Tech Videos | Full-Screen / Smart Crop |
| Educational Videos | Speaker-Focused |

---

## 💻 Hardware Requirements

**Minimum:**
- Python 3.10+
- 8 GB RAM
- Modern multi-core CPU
- FFmpeg
- Sufficient storage for temporary video processing

**Recommended:**
- 16 GB+ RAM
- NVIDIA GPU with compatible CUDA support
- SSD storage
- Modern multi-core processor

CPU processing is supported when GPU acceleration is unavailable.

---

## 🔮 Future Improvements

- [ ] Fully autonomous web dashboard.
- [ ] Advanced AI viral moment detection.
- [ ] Improved speaker diarization.
- [ ] Multi-speaker face tracking.
- [ ] Custom caption templates.
- [ ] Automatic thumbnail variations.
- [ ] Batch URL processing.
- [ ] Multiple social media export presets.
- [ ] Cloud processing support.
- [ ] AI-powered clip performance prediction.

---

⚠️ Disclaimer

This project is intended for legitimate video editing and content creation.

Users are responsible for ensuring they have the necessary rights and permissions to download, process, and publish video content. Respect copyright laws and platform terms of service.

AI-generated clip selections and retention scores are predictions, not guarantees of viral performance.

---

🤝 Contributing

Contributions, bug reports, feature requests, and improvements are welcome!

1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Open a Pull Request.

---

📜 License

Choose an appropriate open-source license before distributing this project. See the `LICENSE` file for details.

---

**Built with ❤️ using Python, AI, and FFmpeg.**

*Long videos in. Engaging shorts out.*
