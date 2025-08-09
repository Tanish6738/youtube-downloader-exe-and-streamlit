import yt_dlp
import os

def download_video_yt_dlp():
    url = input("Enter the YouTube video URL: ").strip()
    
    # Define a dictionary of options for yt-dlp
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', # Default: best video and audio merged into MP4
        'outtmpl': '%(title)s.%(ext)s', # Output filename template
        'postprocessors': [],
    }

    try:
        # Get video information first without downloading
        with yt_dlp.YoutubeDL({'noplaylist': True}) as ydl:
            info_dict = ydl.extract_info(url, download=False)
            video_title = info_dict.get('title', 'video')
            video_author = info_dict.get('uploader', 'unknown')
            video_length = info_dict.get('duration', 0)
            video_views = info_dict.get('view_count', 0)
            
            print(f"\nTitle: {video_title}")
            print(f"Author: {video_author}")
            print(f"Length: {video_length // 60} minutes {video_length % 60} seconds")
            print(f"Views: {video_views}")

        print("\nChoose download option:")
        print("1. Video and Audio (Highest Quality)")
        print("2. Audio only (Highest Quality)")
        print("3. Both video and audio (User choice)")

        choice = input("Enter your choice (1/2/3): ").strip()

        download_path = input("Enter download folder path (leave blank for current folder): ").strip()
        if not download_path:
            download_path = os.getcwd()
        
        ydl_opts['outtmpl'] = os.path.join(download_path, '%(title)s.%(ext)s')

        if choice == "1":
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best'
            print("Downloading video and audio...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("Download completed successfully!")

        elif choice == "2":
            ydl_opts['format'] = 'bestaudio'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            print("Downloading audio only...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("Audio downloaded and converted to MP3 successfully!")

        elif choice == "3":
            # List available formats for user to choose
            with yt_dlp.YoutubeDL({'listformats': True}) as ydl:
                ydl.extract_info(url, download=False)

            format_code = input("Enter the format code(s) for download (e.g., '137+140' for video+audio): ").strip()
            ydl_opts['format'] = format_code
            print("Downloading...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            print("Download completed successfully!")

        else:
            print("Invalid choice. Please run the script again.")
            
    except yt_dlp.utils.DownloadError as e:
        print(f"Error downloading video: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    download_video_yt_dlp()