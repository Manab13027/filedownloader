# batch_downloader.py
import yt_dlp
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

class BatchVideoDownloader:
    def __init__(self, output_dir="./downloads", max_workers=3):
        self.output_dir = output_dir
        self.max_workers = max_workers
        os.makedirs(output_dir, exist_ok=True)
    
    def download_single(self, url, quality='best'):
        """Download a single video"""
        ydl_opts = {
            'outtmpl': os.path.join(self.output_dir, '%(title)s.%(ext)s'),
            'quiet': False,
        }
        
        if quality == 'audio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        else:
            ydl_opts['format'] = quality
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return {
                    'url': url,
                    'title': info.get('title'),
                    'success': True,
                    'filename': info.get('_filename')
                }
        except Exception as e:
            return {
                'url': url,
                'success': False,
                'error': str(e)
            }
    
    def download_batch(self, urls, quality='best'):
        """Download multiple videos concurrently"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all download tasks
            future_to_url = {
                executor.submit(self.download_single, url, quality): url 
                for url in urls
            }
            
            # Process completed downloads
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results.append(result)
                    if result['success']:
                        print(f"✓ Downloaded: {result['title']}")
                    else:
                        print(f"✗ Failed: {url} - {result['error']}")
                except Exception as e:
                    print(f"✗ Error: {url} - {e}")
        
        return results
    
    def save_results(self, results, filename="download_results.json"):
        """Save download results to JSON file"""
        with open(os.path.join(self.output_dir, filename), 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {filename}")

# Example usage
if __name__ == "__main__":
    # List of URLs to download
    urls = [
        "https://www.youtube.com/watch?v=EXAMPLE1",
        "https://www.youtube.com/watch?v=EXAMPLE2",
        # Add more URLs here
    ]
    
    downloader = BatchVideoDownloader(output_dir="./my_videos", max_workers=2)
    results = downloader.download_batch(urls, quality='720p')
    
    # Print summary
    successful = sum(1 for r in results if r['success'])
    print(f"\nSummary: {successful}/{len(urls)} downloads successful")
    
    # Save results
    downloader.save_results(results)