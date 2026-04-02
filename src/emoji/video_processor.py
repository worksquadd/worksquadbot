"""Video processing and conversion utilities for emoji stickers."""

import os
import subprocess
from typing import List, Tuple

from src.config.logger import get_logger
from src.config import settings

logger = get_logger()


class VideoProcessor:
    """Handles video conversion and emoji preparation for Telegram video stickers."""

    def __init__(self):
        """Initialize video processor."""
        logger.info("VideoProcessor initialized")

    def check_transparency(self, video_path: str) -> bool:
        """
        Check if video has alpha channel.
        Args:
            video_path: Path to video file
        Returns:
            True if video has alpha channel
        """
        ffprobe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=pix_fmt:stream_tags=alpha_mode",
            "-of", "default=noprint_wrappers=1",
            video_path
        ]
        result = subprocess.run(
            ffprobe_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            logger.error(f"ffprobe failed: {result.stderr}")
            return False
        pix_fmt = result.stdout.strip()
        has_alpha = 'yuva' in pix_fmt or 'rgba' in pix_fmt or 'gbra' in pix_fmt
        logger.info(f"Video {video_path} pixel format: {pix_fmt}, has_alpha: {has_alpha}")
        return has_alpha

    def extract_frame_for_debug(self, video_path: str, output_png: str):
        """Extract first frame as PNG to check transparency."""
        ffmpeg_cmd = [
            "ffmpeg",
            "-i", video_path,
            "-vframes", "1",
            "-y",
            output_png
        ]

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        logger.info(f"Frame extraction stderr: {result.stderr}")
        logger.info(f"Saved frame to: {output_png}")

    def convert_to_webm(self, input_path: str, output_path: str, max_duration: float = 3.0) -> str:
        """
        Convert any video format to WebM VP9 format suitable for Telegram.

        Args:
            input_path: Path to input video (mp4, gif, etc)
            output_path: Path for output WebM file
            max_duration: Maximum duration in seconds (default 3.0)

        Returns:
            Path to converted WebM file
        """
        # import shutil   # making this to check where transparcency go away
        # shutil.copy(input_path, "/app/assettts/before_converting.webm")  # making this to check where transparcency go away
        # self.extract_frame_for_debug(input_path, "/app/assettts/input_frame.png")  # making this to check where transparcency go away
        # input_has_alpha = self.check_transparency(input_path)  # making this to check where transparcency go away
        # logger.info(f"Input has alpha: {input_has_alpha}")  # making this to check where transparcency go away

        logger.info(f"Converting video to WebM: {input_path} -> {output_path}")

        ffmpeg_cmd = [
            "ffmpeg",
            "-i", input_path,
            "-vf", "format=yuva420p",  # Force alpha format as filter
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-b:v", "0",
            "-crf", "30",
            "-an",
            "-r", "30",
            "-t", str(max_duration),
            "-auto-alt-ref", "0",
            "-y",
            output_path
        ]

        logger.debug(f"Running ffmpeg: {' '.join(ffmpeg_cmd)}")

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg conversion failed: {result.stderr}")
            raise RuntimeError(f"Video conversion failed: {result.stderr}")

        output_has_alpha = self.check_transparency(output_path)
        logger.info(f"Output has alpha: {output_has_alpha}")

        file_size = os.path.getsize(output_path)
        logger.info(f"Video converted successfully, size: {file_size} bytes")

        # shutil.copy(output_path, "/app/assettts/after_converting.webm")  # making this to check where transparcency go away
        return output_path

    def crop_to_grid(
        self,
        input_path: str,
        output_folder: str,
        grid_size: Tuple[int, int],
        padding: int
    ) -> List[str]:
        """
        Crop video into NxM grid with padding for emoji stickers.

        Args:
            input_path: Path to input WebM video
            output_folder: Folder to save cropped videos
            grid_size: Tuple of (columns, rows)
            padding: Padding value (1-5), each unit adds 3% transparent padding on each side

        Returns:
            List of paths to cropped video files
        """
        logger.info(f"Starting crop_to_grid: input={input_path}, grid_size={grid_size}, padding={padding}")
        import shutil
        shutil.copy(input_path, "/app/assettts/before_cropping.webm")

        os.makedirs(output_folder, exist_ok=True)
        logger.debug(f"Created output folder: {output_folder}")

        cols, rows = grid_size
        total_tiles = cols * rows
        logger.info(f"Cropping video into {total_tiles} tiles ({cols}x{rows})")

        padding_percent = padding * 3
        logger.debug(f"Padding: {padding_percent}%")

        video_files = []

        for row in range(rows):
            for col in range(cols):
                output_filename = f"emoji_{row}_{col}.webm"
                output_path = os.path.join(output_folder, output_filename)

                logger.info(f"Processing tile [{row},{col}]: {output_path}")

                try:
                    self._create_video_tile(
                        input_path,
                        output_path,
                        col,
                        row,
                        cols,
                        rows,
                        padding_percent
                    )
                    video_files.append(output_path)
                    logger.debug(f"Created tile: {output_filename}")

                except Exception as e:
                    logger.error(f"Failed to create tile [{row},{col}]: {e}", exc_info=True)
                    raise

        logger.info(f"Successfully created {len(video_files)} video emoji files")
        return video_files

    def _create_video_tile(
        self,
        input_path: str,
        output_path: str,
        col: int,
        row: int,
        cols: int,
        rows: int,
        padding_percent: int
    ):
        """
        Create single 100x100 video tile with cropping and padding.

        Args:
            input_path: Input video path
            output_path: Output video path
            col: Column index
            row: Row index
            cols: Total columns
            rows: Total rows
            padding_percent: Padding percentage
        """
        tile_width = 100 / cols
        tile_height = 100 / rows

        content_percent = 100 - (2 * padding_percent)
        content_width = tile_width * content_percent / 100
        content_height = tile_height * content_percent / 100

        x_offset = (col * tile_width) + (tile_width - content_width) / 2
        y_offset = (row * tile_height) + (tile_height - content_height) / 2

        crop_filter = f"crop=iw*{content_width/100}:ih*{content_height/100}:iw*{x_offset/100}:ih*{y_offset/100}"
        scale_filter = "scale=100:100:flags=bicubic"
        pad_filter = "pad=100:100:(ow-iw)/2:(oh-ih)/2:color=0x00000000"

        ffmpeg_cmd = [
            "ffmpeg",
            "-vcodec", "libvpx-vp9",  # decode with libvpx to preserve alpha
            "-i", input_path,
            "-vf", f"{crop_filter},{scale_filter},{pad_filter}",
            "-c:v", "libvpx-vp9",
            "-b:v", "0",
            "-crf", "35",
            "-an",
            "-r", "30",
            "-pix_fmt", "yuva420p",
            "-auto-alt-ref", "0",
            "-y",
            output_path
        ]

        logger.debug(f"Running ffmpeg for tile: {' '.join(ffmpeg_cmd)}")

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"FFmpeg tile creation failed: {result.stderr}")
            raise RuntimeError(f"Video tile creation failed: {result.stderr}")

        file_size = os.path.getsize(output_path)
        logger.debug(f"Tile size: {file_size} bytes")

        if file_size > 256 * 1024:
            logger.warning(f"Video tile exceeds 256KB ({file_size} bytes), recompressing")
            self._recompress_video(output_path)

    def _recompress_video(self, video_path: str):
        """
        Recompress video to meet 256KB limit.

        Args:
            video_path: Path to video file
        """
        temp_path = video_path + ".tmp"
        current_size = os.path.getsize(video_path)

        target_bitrate = int((256 * 1024 * 8) / 3 * 0.85)

        ffmpeg_cmd = [
            "ffmpeg",
            "-i", video_path,
            "-c:v", "libvpx-vp9",
            "-b:v", str(target_bitrate),
            "-an",
            "-r", "30",
            "-pix_fmt", "yuva420p",
            "-auto-alt-ref", "0",
            "-y",
            temp_path
        ]

        logger.debug(f"Recompressing with bitrate: {target_bitrate}bps")

        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"Recompression failed: {result.stderr}")
            raise RuntimeError(f"Video recompression failed: {result.stderr}")

        os.replace(temp_path, video_path)
        new_size = os.path.getsize(video_path)
        logger.info(f"Recompressed from {current_size} to {new_size} bytes")

        if new_size > 256 * 1024:
            logger.error(f"Video still exceeds 256KB: {new_size} bytes")
            raise RuntimeError("Unable to compress video below 256KB")

    def get_video_info(self, path: str) -> dict:
        """
        Get video metadata.

        Args:
            path: Path to video file

        Returns:
            Dictionary with width, height, duration, fps
        """
        logger.debug(f"Getting video info: {path}")

        ffprobe_cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height,r_frame_rate,duration",
            "-of", "default=noprint_wrappers=1",
            path
        ]

        result = subprocess.run(
            ffprobe_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"ffprobe failed: {result.stderr}")
            raise RuntimeError(f"Failed to get video info: {result.stderr}")

        info = {}
        for line in result.stdout.strip().split("\n"):
            if "=" in line:
                key, value = line.split("=", 1)
                info[key] = value

        width = int(info.get("width", 0))
        height = int(info.get("height", 0))

        duration_str = info.get("duration", "N/A")
        if duration_str == "N/A" or duration_str == "":
            duration = 3.0
            logger.warning(f"Duration not available, using default: {duration}s")
        else:
            try:
                duration = float(duration_str)
            except ValueError:
                duration = 3.0
                logger.warning(f"Invalid duration value: {duration_str}, using default: {duration}s")

        fps_str = info.get("r_frame_rate", "30/1")
        if "/" in fps_str:
            num, den = map(float, fps_str.split("/"))
            fps = num / den if den != 0 else 30
        else:
            fps = float(fps_str)

        logger.info(f"Video: {width}x{height}, {fps:.2f}fps, {duration:.2f}s")

        return {
            "width": width,
            "height": height,
            "duration": duration,
            "fps": fps
        }

    def suggest_grid_sizes(self, width: int, height: int) -> List[Tuple[int, int]]:
        """
        Suggest grid sizes based on video dimensions.

        Args:
            width: Video width
            height: Video height

        Returns:
            List of suggested grid sizes
        """
        import math

        logger.info(f"Calculating grid suggestions for {width}x{height}")

        max_cols = round(width / 100)
        max_rows = round(height / 100)

        scale = math.sqrt(settings.MAX_CELLS / (max_cols * max_rows))
        max_cols = int(max_cols * scale)
        max_rows = int(max_rows * scale)
        logger.info(f"Scaled to {max_cols}x{max_rows} = {max_cols * max_rows} cells")

        if max_cols > settings.MAX_COLS:
            logger.info(f"max cols {max_cols} > {settings.MAX_COLS}, scaling to {settings.MAX_COLS}")
            scale = settings.MAX_COLS / max_cols
            max_cols = int(max_cols * scale)
            max_rows = int(max_rows * scale)

        if max_cols < 2 or max_rows < 2:
            logger.warning("Video too small for 2x2 grid")
            return []

        base_aspect = max_cols / max_rows
        max_cells = max_cols * max_rows

        grid_sizes = []
        for pct in settings.SELECT_PERCENTAGES:
            target_cells = int(max_cells * pct)

            cols = max(2, int(math.sqrt(target_cells * base_aspect)))
            rows = max(2, int(math.sqrt(target_cells / base_aspect)))

            while cols * rows > target_cells and (cols > 2 or rows > 2):
                if cols >= rows and cols > 2:
                    cols -= 1
                elif rows > 2:
                    rows -= 1
                else:
                    break

            if cols < 2 or rows < 2:
                continue

            current_aspect = cols / rows
            aspect_diff_ratio = abs(current_aspect - base_aspect) / base_aspect

            if aspect_diff_ratio > settings.MIN_ASPECT_RATIO:
                break

            grid_sizes.append((cols, rows))

        seen = set()
        unique_sizes = []
        for size in grid_sizes:
            if size not in seen:
                seen.add(size)
                unique_sizes.append(size)

        logger.info(f"Suggested grid sizes: {unique_sizes}")
        return unique_sizes
