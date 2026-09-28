"""Async media downloader built on yt-dlp and gallery-dl subprocesses."""

import asyncio
import os
import shutil
import signal
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.config.logger import get_logger
from src.config.settings import settings

logger = get_logger()

VIDEO_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".m4v"}

AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".ogg", ".wav"}

IG_AUTH_ERROR_KEYWORDS = ("login", "rate-limit", "rate limit", "429", "403")


@dataclass
class MediaResult:
    """Result of a successful media download."""

    platform: str
    kind: str
    files: List[str]
    total_mb: float
    url: str


class DownloadError(Exception):
    """Raised when media download fails."""


class AuthRequiredError(DownloadError):
    """Raised when platform requires authentication (cookies)."""


class DownloadTimeoutError(DownloadError):
    """Raised when download exceeds timeout."""


def _sanitize_cmd(cmd: List[str]) -> List[str]:
    """Return a copy of cmd with the cookies file path hidden."""
    sanitized: List[str] = []
    hide_next = False
    for arg in cmd:
        if hide_next:
            sanitized.append("[hidden]")
            hide_next = False
        elif arg == "--cookies":
            sanitized.append(arg)
            hide_next = True
        else:
            sanitized.append(arg)
    return sanitized


def _is_ig_auth_error(error: DownloadError, cookies_file: Optional[str]) -> bool:
    """Return True when an Instagram error indicates missing or bad authentication."""
    if cookies_file is None:
        return True
    message = str(error).lower()
    return any(keyword in message for keyword in IG_AUTH_ERROR_KEYWORDS)


def _build_yt_dlp_cmd(url: str, output_dir: str, cookies_file: Optional[str], format_hint: Optional[str] = None) -> List[str]:
    """Build the yt-dlp command line for a URL with an optional quality/format hint."""
    if format_hint == "audio":
        format_args = ["-f", "bestaudio", "-x", "--audio-format", "mp3"]
    elif format_hint:
        format_args = ["-f", format_hint, "--merge-output-format", "mp4"]
    else:
        format_args = ["-f", "best"]
    cmd = [
        sys.executable,
        "-m",
        "yt_dlp",
        url,
        "--no-playlist",
        "--no-part",
        "--newline",
        "--socket-timeout",
        "30",
        "--concurrent-fragments",
        str(settings.MEDIA_YT_CONCURRENT_FRAGMENTS),
        *format_args,
        "-o",
        os.path.join(output_dir, "%(id)s.%(ext)s"),
    ]
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    extractor_args = []
    if settings.MEDIA_YT_POT_BASEURL:
        extractor_args.append(f"getpot_bgutil_baseurl={settings.MEDIA_YT_POT_BASEURL}")
    if settings.MEDIA_YT_PLAYER_CLIENT:
        extractor_args.append(f"player_client={settings.MEDIA_YT_PLAYER_CLIENT}")
    if extractor_args:
        cmd.extend(["--extractor-args", "youtube:" + ";".join(extractor_args)])
    return cmd


def _build_gallery_dl_cmd(url: str, output_dir: str, cookies_file: Optional[str]) -> List[str]:
    """Build the gallery-dl command line for a URL."""
    cmd = [sys.executable, "-m", "gallery_dl", "-D", output_dir, url]
    if cookies_file:
        cmd.extend(["--cookies", cookies_file])
    return cmd


def _detect_kind(files: List[str]) -> str:
    """Return 'video', 'audio' or 'photo' from the first recognised file extension."""
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext in VIDEO_EXTENSIONS:
            return "video"
    for path in files:
        ext = os.path.splitext(path)[1].lower()
        if ext in AUDIO_EXTENSIONS:
            return "audio"
    return "photo"


def _collect_files(output_dir: str) -> List[str]:
    """Collect sorted paths of non-empty files under output_dir."""
    files: List[str] = []
    for root, _dirs, names in os.walk(output_dir):
        for name in names:
            path = os.path.join(root, name)
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                files.append(path)
    logger.debug(f"Collected {len(files)} file(s) from {output_dir}")
    return sorted(files)


async def _split_video(path: str, output_dir: str, part_mb: int) -> List[str]:
    """Split a video into capped-size parts using ffmpeg stream copy."""
    logger.info(f"Splitting video into {part_mb} MB parts: {path}")
    part_template = os.path.join(output_dir, "part_%04d.mp4")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        path,
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_size",
        f"{part_mb - 1}M",
        "-reset_timestamps",
        "1",
        part_template,
    ]
    await _run_tool(cmd, 900)
    parts: List[str] = []
    for name in os.listdir(output_dir):
        if name.startswith("part_") and name.endswith(".mp4"):
            part_path = os.path.join(output_dir, name)
            if os.path.isfile(part_path) and os.path.getsize(part_path) > 0:
                parts.append(part_path)
    parts = sorted(parts)
    for part in parts:
        part_size_mb = os.path.getsize(part) / (1024 * 1024)
        if part_size_mb > part_mb:
            logger.warning(f"Split part exceeds the {part_mb} MB target: {part} ({part_size_mb:.2f} MB)")
    total_mb = sum(os.path.getsize(part) for part in parts) / (1024 * 1024)
    logger.info(f"Video split complete: {len(parts)} part(s), total {total_mb:.2f} MB")
    return parts


async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """Kill the subprocess and its whole process group, then reap it."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        logger.info(f"Killed process group for pid={proc.pid}")
    except ProcessLookupError:
        logger.warning(f"Process group for pid={proc.pid} already gone")
    try:
        proc.kill()
    except ProcessLookupError:
        logger.debug(f"Process pid={proc.pid} already gone")
    try:
        await proc.wait()
        logger.info(f"Process pid={proc.pid} reaped")
    except Exception as e:
        logger.warning(f"Failed to reap process pid={proc.pid}: {e}")


async def _run_tool(cmd: List[str], timeout: int) -> Tuple[str, str]:
    """Run a download tool subprocess and return (stdout, stderr) text."""
    logger.info(f"Running download tool: {_sanitize_cmd(cmd)}")
    started = time.time()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    logger.debug(f"Download tool started, pid={proc.pid}")
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.error(f"Download tool timed out after {timeout}s, killing process group pid={proc.pid}")
        await _kill_process_group(proc)
        raise DownloadTimeoutError(f"Download tool timed out after {timeout} seconds") from None
    except asyncio.CancelledError:
        logger.error(f"Download tool task cancelled, killing process group pid={proc.pid}")
        await _kill_process_group(proc)
        raise
    elapsed = time.time() - started
    stdout_text = stdout.decode("utf-8", errors="replace")
    stderr_text = stderr.decode("utf-8", errors="replace")
    logger.info(f"Download tool finished: elapsed={elapsed:.2f}s, returncode={proc.returncode}")
    if proc.returncode != 0:
        logger.error(
            f"Download tool failed with returncode={proc.returncode}, stderr tail: {stderr_text[-500:]}"
        )
        raise DownloadError(f"Download tool exited with code {proc.returncode}: {stderr_text[-500:]}")
    return stdout_text, stderr_text


def _stage_ig_cookies() -> Optional[str]:
    """Copy Instagram cookies into a private temp file for read-only tools."""
    src = settings.MEDIA_IG_COOKIES_FILE
    if not os.path.exists(src):
        logger.warning(f"Instagram cookies file not found: {src}")
        return None
    fd, path = tempfile.mkstemp(prefix="ig_cookies_", suffix=".txt")
    os.close(fd)
    try:
        shutil.copyfile(src, path)
        os.chmod(path, 0o600)
    except Exception:
        os.unlink(path)
        raise
    logger.info("Instagram cookies staged to a private temp file")
    return path


async def download_media(
    url: str, platform: str, output_dir: str, format_hint: Optional[str] = None
) -> MediaResult:
    """Download media from a whitelisted URL into output_dir, optionally in a requested quality."""
    logger.info(f"Starting media download: platform={platform}, url={url}, output_dir={output_dir}")
    os.makedirs(output_dir, exist_ok=True)
    logger.debug(f"Media output directory ready: {output_dir}")

    cookies_file = _stage_ig_cookies() if platform == "instagram" else None
    try:
        return await _download_and_collect(url, platform, output_dir, cookies_file, format_hint)
    finally:
        if cookies_file:
            try:
                os.unlink(cookies_file)
                logger.debug("Temporary Instagram cookies file removed")
            except OSError as e:
                logger.warning(f"Failed to remove temporary cookies file: {e}")


async def _download_and_collect(
    url: str, platform: str, output_dir: str, cookies_file: Optional[str], format_hint: Optional[str] = None
) -> MediaResult:
    """Run download tools and post-process files into a MediaResult."""
    started = time.time()
    timeout = settings.MEDIA_DOWNLOAD_TIMEOUT_SEC

    if platform == "instagram":
        gallery_cmd = _build_gallery_dl_cmd(url, output_dir, cookies_file)
        logger.info("Instagram: attempting download via gallery-dl")
        gallery_succeeded = False
        try:
            await _run_tool(gallery_cmd, timeout)
            logger.info("Instagram: gallery-dl finished without errors")
            gallery_succeeded = True
        except DownloadTimeoutError:
            raise
        except DownloadError as e:
            logger.warning(f"Instagram: gallery-dl failed: {e}")
            if _is_ig_auth_error(e, cookies_file):
                logger.warning("Instagram: gallery-dl failure looks like an authentication issue")
                raise AuthRequiredError(str(e)) from e
            logger.warning("Instagram: gallery-dl failed with a non-auth error, falling back to yt-dlp")

        files = _collect_files(output_dir) if gallery_succeeded else []
        if not files:
            logger.warning("Instagram: falling back to yt-dlp")
            yt_cmd = _build_yt_dlp_cmd(url, output_dir, cookies_file)
            try:
                await _run_tool(yt_cmd, timeout)
                logger.info("Instagram: yt-dlp fallback finished without errors")
            except DownloadTimeoutError:
                raise
            except DownloadError as e:
                logger.warning(f"Instagram: yt-dlp fallback failed: {e}")
                if _is_ig_auth_error(e, cookies_file):
                    logger.warning("Instagram: yt-dlp failure looks like an authentication issue")
                    raise AuthRequiredError(str(e)) from e
                raise
    else:
        logger.info(f"Platform {platform}: running yt-dlp")
        yt_cmd = _build_yt_dlp_cmd(url, output_dir, cookies_file, format_hint)
        await _run_tool(yt_cmd, timeout)

    files = _collect_files(output_dir)
    if not files:
        logger.error(f"Download finished but no files found in {output_dir}")
        raise DownloadError("no files downloaded")

    kind = _detect_kind(files)

    if kind == "video":
        largest = max(files, key=os.path.getsize)
        largest_mb = os.path.getsize(largest) / (1024 * 1024)
        if largest_mb > settings.MEDIA_MAX_FILE_MB:
            logger.info(
                f"Largest video is {largest_mb:.2f} MB, exceeds the {settings.MEDIA_MAX_FILE_MB} MB part cap, splitting into parts"
            )
            files = await _split_video(largest, output_dir, settings.MEDIA_MAX_FILE_MB)
            if not files:
                logger.error("Video split finished but no parts were produced")
                raise DownloadError("video split produced no parts")
            try:
                os.remove(largest)
                logger.info(f"Removed original video after split: {largest}")
            except Exception as e:
                logger.warning(f"Failed to remove original video after split: {largest}: {e}")

    total_mb = sum(os.path.getsize(path) for path in files) / (1024 * 1024)
    elapsed = time.time() - started
    logger.info(
        f"Media download complete: platform={platform}, kind={kind}, "
        f"files={len(files)}, total_mb={total_mb:.2f}, elapsed={elapsed:.2f}s"
    )
    return MediaResult(platform=platform, kind=kind, files=files, total_mb=total_mb, url=url)
