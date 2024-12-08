import os
import subprocess
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def convert_video_to_mp4(input_path: str, output_path: str) -> Optional[str]:
    """Convert any video format to MP4 using FFmpeg"""
    try:
        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # FFmpeg command to convert to MP4 with H.264 codec
        command = [
            "ffmpeg",
            "-i",
            input_path,  # Input file
            "-c:v",
            "libx264",  # Video codec
            "-preset",
            "medium",  # Encoding speed preset
            "-crf",
            "23",  # Quality (23 is default, lower = better quality)
            "-c:a",
            "aac",  # Audio codec
            "-b:a",
            "128k",  # Audio bitrate
            "-movflags",
            "+faststart",  # Enable streaming
            "-y",  # Overwrite output file if it exists
            output_path,
        ]

        # Run FFmpeg
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            return None

        return output_path

    except Exception as e:
        logger.error(f"Video conversion failed: {str(e)}")
        return None
