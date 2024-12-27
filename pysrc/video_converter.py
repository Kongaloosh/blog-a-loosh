from concurrent.futures import ThreadPoolExecutor
import logging
import subprocess
import os
from typing import Optional, Dict
from threading import Lock
import threading

logger = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=1)
conversion_status: Dict[str, str] = {}
status_lock = Lock()


def convert_video_to_mp4(input_path: str, output_path: str) -> Optional[str]:
    """Start video conversion in background and return immediately"""
    video_id = os.path.basename(input_path)

    def convert_in_background():
        try:
            command = [
                "ffmpeg",
                "-i",
                input_path,
                "-c:v",
                "libx264",
                "-crf",
                "18",  # Lower CRF = higher quality (18 is visually lossless)
                "-preset",
                "slow",  # Slower preset = better compression
                "-vf",
                "format=yuv420p",  # Simpler color conversion
                "-c:a",
                "aac",
                "-b:a",
                "192k",  # Higher audio bitrate
                "-movflags",
                "+faststart",
                "-y",
                output_path,
            ]

            logger.info(f"Starting conversion in background: {input_path}")

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=300,
            )

            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"Successfully converted video to: {output_path}")
                with status_lock:
                    conversion_status[video_id] = "completed"
            else:
                logger.error(f"Conversion failed for: {input_path}")
                with status_lock:
                    conversion_status[video_id] = "failed"

        except Exception as e:
            logger.error(f"Error converting video: {str(e)}")
            with status_lock:
                conversion_status[video_id] = "error"

    # Start conversion in background
    with status_lock:
        conversion_status[video_id] = "starting"

    thread = threading.Thread(target=convert_in_background)
    thread.daemon = True
    thread.start()

    # Return immediately with the expected output path
    return output_path
