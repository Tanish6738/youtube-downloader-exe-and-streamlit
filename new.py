import streamlit as st
import yt_dlp
import os
import time
import threading

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

        ydl_opts = {
            'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'),
            'postprocessors': [],
            'progress_hooks': [_progress_hook],
            'quiet': True,
        }

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
                ydl_download.download([url])
            st.success("✅ Download completed successfully!")
        except yt_dlp.utils.DownloadError as e:
            st.error(f"Error downloading video: {e}")
