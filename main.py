"""
Autonomous AI Video Clipper Pipeline - Entry Point & CLI
Provides full command-line orchestration and web dashboard management.
"""

import argparse
import json
import logging
import os
import sys

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.media_inspector import MediaInspector
from src.pipeline import VideoClipperPipeline
from src.server import run_server

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join("logs", "clipper.log"), encoding="utf-8")
    ]
)
logger = logging.getLogger("AutoClipAI")


def cmd_server(args):
    """Launches the modern web dashboard studio."""
    logger.info(f"Starting AutoClip AI Studio on http://{args.host}:{args.port}")
    run_server(host=args.host, port=args.port)


def cmd_process(args):
    """Executes end-to-end pipeline on input video."""
    logger.info(f"Initiating autonomous processing on: {args.input}")
    pipeline = VideoClipperPipeline(
        model_size=args.model_size,
        device=args.device
    )

    def progress_printer(msg: str, pct: float):
        print(f"[{int(pct * 100):3d}%] {msg}")

    result = pipeline.process(
        input_source=args.input,
        duration_preset=args.duration,
        max_clips=args.max_clips,
        caption_preset=args.preset,
        layout_mode=args.layout,
        progress_callback=progress_printer
    )

    print("\n" + "=" * 60)
    print(f"✨ PIPELINE COMPLETE in {result.total_processing_time}s")
    print(f"Total Viral Clips Generated: {len(result.clips)}")
    print("=" * 60)

    for clip in result.clips:
        print(f"\n[Clip #{clip.clip_id}] {clip.title}")
        print(f"  Duration: {clip.duration}s ({clip.start_time}s -> {clip.end_time}s)")
        print(f"  Retention Score: {clip.retention_score}%")
        print(f"  Video: {clip.clip_video_path}")
        print(f"  Thumbnail: {clip.thumbnail_path}")
        print(f"  Metadata: {clip.metadata_json_path}")
        print(f"  Quality Valid: {clip.quality.is_valid} ({', '.join(clip.quality.errors) if clip.quality.errors else 'PASSED'})")


def cmd_info(args):
    """Prints environment and hardware diagnostic report."""
    inspector = MediaInspector()
    print("=" * 60)
    print("AUTOCLIP AI - ENVIRONMENT DIAGNOSTICS")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Workspace: {os.path.abspath('.')}")
    print(f"FFmpeg Binary: {os.path.abspath('bin/ffmpeg.exe') if os.path.exists('bin/ffmpeg.exe') else 'System PATH'}")
    print(f"FFprobe Binary: {inspector.ffprobe_path}")
    print(f"Models Directory: {os.path.abspath('models')}")
    models = os.listdir("models") if os.path.exists("models") else []
    print(f"Available Whisper Models: {', '.join(models) if models else 'None'}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="AutoClip AI: Autonomous 9:16 Short-Form Video Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Server command
    server_parser = subparsers.add_parser("server", help="Launch web dashboard studio")
    server_parser.add_argument("--host", default="127.0.0.1", help="Host address")
    server_parser.add_argument("--port", type=int, default=8000, help="Port number")

    # Process command
    proc_parser = subparsers.add_parser("process", help="Process video to vertical clips")
    proc_parser.add_argument("--input", "-i", required=True, help="Video file path or YouTube URL")
    proc_parser.add_argument("--duration", "-d", choices=["short", "medium", "long", "extended"], default="medium")
    proc_parser.add_argument("--preset", "-p", choices=["hormozi", "minimal", "podcast", "gaming", "cinematic"], default="hormozi")
    proc_parser.add_argument("--max-clips", "-n", type=int, default=5, help="Maximum number of clips")
    proc_parser.add_argument("--layout", "-l", choices=["smart_auto", "face_crop", "blurred_bg", "split_screen"], default="smart_auto")
    proc_parser.add_argument("--model-size", choices=["tiny", "base", "small", "medium", "large-v3"], default="tiny")
    proc_parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")

    # Info command
    subparsers.add_parser("info", help="Display environment diagnostics")

    args = parser.parse_args()

    if args.command == "server":
        cmd_server(args)
    elif args.command == "process":
        cmd_process(args)
    elif args.command == "info":
        cmd_info(args)
    else:
        # Default action: launch server
        cmd_server(argparse.Namespace(host="127.0.0.1", port=8000))


if __name__ == "__main__":
    main()
