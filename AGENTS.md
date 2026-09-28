# Repo working notes

## Media downloader (src/media/)

- Extractors rot when platforms change: bump `yt-dlp[default]` and `gallery-dl` pins in requirements.txt, rebuild image (`docker compose build --no-cache`).
- YouTube needs `MEDIA_YT_PLAYER_CLIENT=android` default; web clients hit SABR errors (yt-dlp issue #12482).
- Instagram requires cookies (`MEDIA_IG_COOKIES_FILE`); without them bot returns auth error by design.
- VK extractor must be smoke-tested inside the production container; local macOS LibreSSL gives false TLS failures.
- All user-facing strings live in src/config/strings.py; media settings in src/config/settings.py via env.
- Large videos (any size, up to 10h) are split into parts <= MEDIA_MAX_FILE_MB via ffmpeg `-c copy` (no re-encode) and sent as documents; part cap: MEDIA_MAX_PARTS.
- Local Bot API mode via TELEGRAM_API_ID/TELEGRAM_API_HASH (base http://telegram-bot-api:8081/bot) enables 2GB sends (videos up to ~3h go whole); in standard mode MEDIA_MAX_FILE_MB is clamped to 48MB at startup.
- Keep `context` and `caption_entities` explicit through every media-delivery helper; an out-of-scope value aborts delivery after a successful download. A single video should use `reply_video`; `reply_document` is only its Telegram-error fallback.
- Local Bot API can accept a valid MP4 without deriving its card metadata. Before `reply_video`, probe it with ffprobe and supply duration/width/height plus an ffmpeg JPEG thumbnail, otherwise Telegram displays a blank `00:00` card.
- Never offer fixed YouTube heights blindly: query yt-dlp format metadata first and show only the heights present in that source, since the fallback selector otherwise makes several quality buttons download the same stream.

## Deployment

- Until the owner requests CI/CD, deploy directly through `ssh worksquad`: archive the tested commit into a new release directory, reuse the persistent `.env`, cookies, and Bot API data, build there, then recreate the existing Compose project. Use Docker cache for normal code changes; reserve `--no-cache` for base-image or downloader-dependency updates.
