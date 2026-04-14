import requests
import re
import sys

def download_mailru_video(video_url, output_filename=None):
    """
    Downloads a video from a my.mail.ru/video/embed/ URL.
    
    Args:
        video_url (str): The full URL to the video embed page (e.g., https://my.mail.ru/video/embed/9209825065758097925).
        output_filename (str, optional): The desired name for the saved file (e.g., 'my_video.mp4'). If not provided, it will be generated.
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # Step 1: Fetch the embed page HTML
        print(f"Fetching page: {video_url}")
        response = requests.get(video_url, headers=headers, timeout=10)
        response.raise_for_status()  # Raise an error for bad status codes

        html_content = response.text

        # Step 2: Look for the video source URL in the page
        # Common patterns for Mail.ru video sources (mp4 files)
        video_patterns = [
            r'"url"\s*:\s*"([^"]+\.mp4[^"]*)"',  # JSON-style url
            r'data-url="([^"]+\.mp4[^"]*)"',      # data-url attribute
            r'src\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',  # src: '...'
            r'file["\']?\s*:\s*["\']([^"\']+\.mp4[^"\']*)["\']',  # file: '...'
        ]
        
        video_src = None
        for pattern in video_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                video_src = match.group(1)
                # Sometimes the URL might be escaped or relative
                if video_src.startswith('//'):
                    video_src = 'https:' + video_src
                elif video_src.startswith('/'):
                    # Construct full URL if it's a relative path
                    from urllib.parse import urlparse
                    parsed_url = urlparse(video_url)
                    video_src = f"{parsed_url.scheme}://{parsed_url.netloc}{video_src}"
                print(f"Found video source using pattern: {video_src[:80]}...")
                break

        if not video_src:
            # Alternative method: Look for meta tags with video info
            print("Trying alternative method: checking meta tags...")
            meta_pattern = r'<meta property="og:video:url" content="([^"]+)"'
            match = re.search(meta_pattern, html_content)
            if match:
                video_src = match.group(1)
                print(f"Found video source via og:video: {video_src[:80]}...")
            else:
                raise Exception("Could not find video source URL in the page.")

        # Step 3: Download the video file
        if not output_filename:
            # Try to extract a sensible filename
            title_match = re.search(r'<title>([^<]+)</title>', html_content)
            if title_match:
                title = title_match.group(1).split('::')[0].strip()
                safe_title = re.sub(r'[^\w\s-]', '', title).strip()
                safe_title = re.sub(r'[-\s]+', '_', safe_title)
                output_filename = f"{safe_title}.mp4"
            else:
                # Fallback to video ID
                video_id = video_url.split('/')[-1]
                output_filename = f"mailru_video_{video_id}.mp4"

        print(f"Downloading video to: {output_filename}")
        
        # Stream the download to handle large files
        video_response = requests.get(video_src, headers=headers, stream=True, timeout=30)
        video_response.raise_for_status()
        
        total_size = int(video_response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_filename, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Show progress if we know total size
                    if total_size > 0:
                        percent = (downloaded / total_size) * 100
                        print(f"\rProgress: {downloaded}/{total_size} bytes ({percent:.1f}%)", end='', flush=True)
                    else:
                        print(f"\rDownloaded: {downloaded} bytes", end='', flush=True)
        
        print(f"\n✅ Download complete: {output_filename}")
        return output_filename

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None


def main():
    """Example usage of the download function."""
    # Get video URL from command line or use a default
    if len(sys.argv) > 1:
        video_url = sys.argv[1]
    else:
        # Use the URL from your query
        video_url = "https://my.mail.ru/video/embed/9209825065758097925"
    
    # Optionally specify an output filename
    output_file = None  # Let the function generate a filename
    
    # Download the video
    result = download_mailru_video(video_url, output_file)
    
    if result:
        print(f"\n🎉 Successfully downloaded: {result}")
    else:
        print("\nFailed to download the video.")

if __name__ == "__main__":
    main()