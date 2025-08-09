import streamlit as st
import yt_dlp
import os
import time
import threading
import mimetypes
import tempfile

st.set_page_config(page_title="YouTube Downloader", page_icon="🎥", layout="centered")

st.title("YouTube Video Downloader (yt-dlp)")

# Helpers for human-readable stats
def _format_bytes(n):
    if not n and n != 0:
        return "?"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(n)
    for u in units:
        if size < 1024 or u == units[-1]:
            return f"{size:.2f} {u}"
        size /= 1024

def _format_time(seconds):
    if seconds is None:
        return "?"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h:d}h {m:02d}m {s:02d}s"
    return f"{m:d}m {s:02d}s"

def _infer_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    return mime or 'application/octet-stream'

def _collect_output_files(info: dict) -> list:
    paths = []
    if not info:
        return paths
    rds = info.get('requested_downloads') or []
    for rd in rds:
        p = rd.get('filepath') or rd.get('filename') or rd.get('_filename')
        if p and p not in paths:
            paths.append(p)
    # Fallbacks
    top_path = info.get('filepath') or info.get('_filename') or info.get('filename')
    if top_path and top_path not in paths:
        paths.append(top_path)
    return paths

# Background fetch task for video info
def _extract_info_task_fn(video_url: str, info_ref: dict, error_ref: dict):
    try:
        with yt_dlp.YoutubeDL({'noplaylist': True}) as ydl_info:
            info = ydl_info.extract_info(video_url, download=False)
        info_ref['info'] = info
    except yt_dlp.utils.DownloadError as e:
        error_ref['error'] = e

# Input for YouTube URL
url = st.text_input("Enter the YouTube video URL:")

if url:
    # Get video info (with progress)
    fetch_status = st.empty()
    fetch_progress = st.progress(0)

    info_holder = {}
    error_holder = {}

    t = threading.Thread(target=_extract_info_task_fn, args=(url, info_holder, error_holder), daemon=True)
    t.start()
    i = 0
    while t.is_alive():
        i = (i + 5) % 105
        fetch_progress.progress(min(i, 100))
        fetch_status.markdown("Fetching video info…")
        time.sleep(0.1)
    t.join()
    fetch_progress.progress(100)

    if 'error' in error_holder:
        st.error(f"Error fetching video info: {error_holder['error']}")
        st.stop()

    info_dict = info_holder.get('info', {})
    video_title = info_dict.get('title', 'video')
    video_author = info_dict.get('uploader', 'unknown')
    video_length = info_dict.get('duration', 0)
    video_views = info_dict.get('view_count', 0)

    st.subheader("📄 Video Information")
    st.write(f"**Title:** {video_title}")
    st.write(f"**Author:** {video_author}")
    st.write(f"**Length:** {video_length // 60} minutes {video_length % 60} seconds")
    st.write(f"**Views:** {video_views:,}")

    # Download option selection
    choice = st.radio(
        "Choose download option:",
        ["Video and Audio (Highest Quality)", "Audio only (Highest Quality)", "Custom format choice"]
    )

    # Download path
    download_path = st.text_input("Enter download folder path (leave blank for current folder):", value=os.getcwd())

    # Advanced options to help with HTTP 403 and restrictions
    cookies_temp_path = None
    with st.expander("Advanced (optional)"):
        cookies_upload = st.file_uploader("Upload cookies.txt (for age/region/member-only videos)", type=["txt"], accept_multiple_files=False)
        force_ipv4 = st.checkbox("Force IPv4 (recommended)", value=True)
        if cookies_upload is not None:
            # Persist uploaded cookies to a temp file path for yt-dlp
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
            tmp.write(cookies_upload.read())
            tmp.flush()
            tmp.close()
            cookies_temp_path = tmp.name

    # Custom format code if selected
    format_code = None
    if choice == "Custom format choice":
        with st.spinner("Fetching format list…"):
            with yt_dlp.YoutubeDL({'listformats': True}) as ydl_formats:
                st.info("Listing available formats in the terminal log...")
                ydl_formats.extract_info(url, download=False)
        format_code = st.text_input("Enter the format code(s) for download (e.g., '137+140'):")

    # Download button
    if st.button("Download"):
        # UI placeholders
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Progress hook
        def _progress_hook(d):
            status = d.get('status')
            if status == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate')
                downloaded = d.get('downloaded_bytes', 0) or 0
                percent = int(downloaded * 100 / total) if total else 0
                speed = d.get('speed')
                eta = d.get('eta')
                progress_bar.progress(min(max(percent, 0), 100))
                status_text.markdown(
                    f"Downloading: {_format_bytes(downloaded)} of {_format_bytes(total)} "
                    f"at {_format_bytes(speed)}/s • ETA: {_format_time(eta)}"
                )
            elif status == 'finished':
                progress_bar.progress(100)
                status_text.markdown("Download complete. Processing (merging/post-processing)…")

        # Ensure output directory exists
        try:
            os.makedirs(download_path, exist_ok=True)
        except OSError as e:
            st.error(f"Cannot create output directory: {e}")
            st.stop()

        ydl_opts = {
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'postprocessors': [],
            'progress_hooks': [_progress_hook],
            'quiet': True,
            # Improve reliability/mitigate 403s
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
                'Referer': url,
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'retries': 10,
            'fragment_retries': 10,
            'sleep_interval_requests': 0.5,
            'max_sleep_interval_requests': 1.5,
            'concurrent_fragment_downloads': 1,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android']
                }
            },
        }

        if cookies_temp_path:
            ydl_opts['cookiefile'] = cookies_temp_path
        if 'force_ipv4' in locals() and force_ipv4:
            # Equivalent to --force-ipv4
            ydl_opts['source_address'] = '0.0.0.0'

        if choice == "Video and Audio (Highest Quality)":
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
        elif choice == "Audio only (Highest Quality)":
            ydl_opts['format'] = 'bestaudio'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        elif choice == "Custom format choice" and format_code:
            ydl_opts['format'] = format_code

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                info_result = ydl_download.extract_info(url, download=True)
            downloaded_files = _collect_output_files(info_result)
            if downloaded_files:
                st.success("✅ Download completed successfully! Use the buttons below to save to your device.")
                for idx, fpath in enumerate(downloaded_files):
                    try:
                        with open(fpath, 'rb') as fh:
                            st.download_button(
                                label=f"Download {os.path.basename(fpath)}",
                                data=fh.read(),
                                file_name=os.path.basename(fpath),
                                mime=_infer_mime(fpath),
                                key=f"dlbtn-{idx}-{os.path.basename(fpath)}"
                            )
                    except OSError as read_err:
                        st.warning(f"Downloaded file is not accessible: {read_err}")
            else:
                st.success("✅ Download completed successfully!")
        except yt_dlp.utils.DownloadError as e:
            st.error(f"Error downloading video: {e}")
        finally:
            # Cleanup temp cookies file if used
            try:
                if cookies_temp_path and os.path.exists(cookies_temp_path):
                    os.remove(cookies_temp_path)
            except OSError:
                pass
