# app.py
from flask import Flask, render_template, request, send_file, jsonify, redirect, url_for
import os
import uuid
import requests
from urllib.parse import urlparse
import re
from werkzeug.utils import secure_filename
import logging
from datetime import datetime
import threading
import queue
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max request size
app.config['DOWNLOAD_FOLDER'] = 'downloads'
app.config['ALLOWED_EXTENSIONS'] = {'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v'}
app.config['TEMP_FOLDER'] = 'temp'

# Create necessary directories
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['TEMP_FOLDER'], exist_ok=True)

# Download queue and status tracking
download_queue = queue.Queue()
download_status = {}
download_history = []

class VideoDownloader:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extract_filename_from_url(self, url, content_type=None):
        """Extract filename from URL or headers"""
        parsed = urlparse(url)
        path = parsed.path
        
        # Try to get filename from URL path
        if path and '/' in path:
            filename = path.split('/')[-1]
            if filename and '.' in filename:
                return secure_filename(filename)
        
        # Try to get from content-disposition header
        try:
            response = self.session.head(url, allow_redirects=True, timeout=5)
            if 'content-disposition' in response.headers:
                content_disp = response.headers['content-disposition']
                fnames = re.findall('filename=(.+)', content_disp)
                if fnames:
                    filename = fnames[0].strip('"\'')
                    return secure_filename(filename)
        except:
            pass
        
        # Generate a filename based on content type or domain
        domain = parsed.netloc.replace('www.', '').split('.')[0]
        ext = self.get_extension_from_content_type(content_type) if content_type else 'mp4'
        return f"{domain}_{uuid.uuid4().hex[:8]}.{ext}"
    
    def get_extension_from_content_type(self, content_type):
        """Map content type to file extension"""
        content_type = content_type.lower()
        if 'mp4' in content_type:
            return 'mp4'
        elif 'avi' in content_type:
            return 'avi'
        elif 'mov' in content_type:
            return 'mov'
        elif 'webm' in content_type:
            return 'webm'
        elif 'x-matroska' in content_type or 'mkv' in content_type:
            return 'mkv'
        return 'mp4'
    
    def download_video(self, url, download_id):
        """Download video from URL"""
        try:
            download_status[download_id] = {
                'status': 'starting',
                'progress': 0,
                'filename': '',
                'error': None
            }
            
            # Start streaming download
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            # Get content length for progress tracking
            total_size = int(response.headers.get('content-length', 0))
            content_type = response.headers.get('content-type', '')
            
            # Generate filename
            filename = self.extract_filename_from_url(url, content_type)
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            
            download_status[download_id]['filename'] = filename
            download_status[download_id]['status'] = 'downloading'
            download_status[download_id]['total_size'] = total_size
            download_status[download_id]['downloaded'] = 0
            
            # Download with progress
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        if total_size > 0:
                            download_status[download_id]['downloaded'] += len(chunk)
                            progress = (download_status[download_id]['downloaded'] / total_size) * 100
                            download_status[download_id]['progress'] = round(progress, 2)
            
            download_status[download_id]['status'] = 'completed'
            download_status[download_id]['progress'] = 100
            download_status[download_id]['filepath'] = filepath
            
            # Add to history
            download_history.append({
                'id': download_id,
                'filename': filename,
                'url': url,
                'timestamp': datetime.now().isoformat(),
                'status': 'completed',
                'size': total_size
            })
            
        except Exception as e:
            download_status[download_id]['status'] = 'error'
            download_status[download_id]['error'] = str(e)
            logging.error(f"Download error: {e}")

def download_worker():
    """Background worker for downloading videos"""
    downloader = VideoDownloader()
    while True:
        try:
            task = download_queue.get(timeout=1)
            if task is None:
                break
            url, download_id = task
            downloader.download_video(url, download_id)
        except queue.Empty:
            continue
        except Exception as e:
            logging.error(f"Worker error: {e}")

# Start download worker thread
worker_thread = threading.Thread(target=download_worker, daemon=True)
worker_thread.start()

def is_valid_url(url):
    """Validate URL format"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def download_video():
    """API endpoint to start video download"""
    data = request.get_json()
    url = data.get('url')
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not is_valid_url(url):
        return jsonify({'error': 'Invalid URL format'}), 400
    
    # Create download ID
    download_id = str(uuid.uuid4())
    
    # Add to download queue
    download_queue.put((url, download_id))
    
    # Initialize download status
    download_status[download_id] = {
        'status': 'queued',
        'progress': 0,
        'filename': '',
        'error': None
    }
    
    return jsonify({
        'success': True,
        'download_id': download_id,
        'message': 'Download queued successfully'
    })

@app.route('/api/status/<download_id>')
def get_status(download_id):
    """Get download status"""
    if download_id not in download_status:
        return jsonify({'error': 'Download not found'}), 404
    
    status = download_status[download_id].copy()
    return jsonify(status)

@app.route('/api/downloads')
def get_downloads():
    """Get download history"""
    return jsonify(download_history[-20:])  # Return last 20 downloads

@app.route('/download/<download_id>')
def download_file(download_id):
    """Download completed file"""
    if download_id not in download_status:
        return "File not found", 404
    
    status = download_status[download_id]
    if status['status'] != 'completed' or 'filepath' not in status:
        return "File not ready for download", 404
    
    try:
        return send_file(
            status['filepath'],
            as_attachment=True,
            download_name=status['filename']
        )
    except Exception as e:
        return str(e), 500

@app.route('/api/cancel/<download_id>', methods=['POST'])
def cancel_download(download_id):
    """Cancel a download"""
    if download_id in download_status:
        download_status[download_id]['status'] = 'cancelled'
        return jsonify({'success': True})
    return jsonify({'error': 'Download not found'}), 404

@app.route('/cleanup', methods=['POST'])
def cleanup_old_files():
    """Cleanup old downloaded files"""
    try:
        cutoff_time = time.time() - (24 * 3600)  # 24 hours ago
        deleted = 0
        
        for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
                    deleted += 1
        
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create the template file
    with open('templates/index.html', 'w') as f:
        f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Downloader</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .card {
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            border: none;
        }
        .download-item {
            transition: all 0.3s;
            border-left: 4px solid #667eea;
        }
        .download-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .progress {
            height: 10px;
            border-radius: 5px;
        }
        .status-badge {
            font-size: 0.8rem;
            padding: 3px 10px;
            border-radius: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <div class="card p-4 mt-5">
                    <h1 class="text-center mb-4">
                        <i class="fas fa-download me-2"></i>Video Downloader
                    </h1>
                    
                    <div class="mb-4">
                        <div class="input-group">
                            <input type="text" class="form-control form-control-lg" 
                                   id="videoUrl" placeholder="Enter video URL (e.g., https://example.com/video.mp4)">
                            <button class="btn btn-primary btn-lg" id="downloadBtn">
                                <i class="fas fa-download me-2"></i>Download
                            </button>
                        </div>
                        <div class="form-text mt-2">
                            Supported formats: MP4, AVI, MOV, WMV, FLV, MKV, WebM, M4V
                        </div>
                    </div>

                    <div id="statusAlert" class="alert d-none"></div>

                    <div class="mt-4">
                        <h4><i class="fas fa-history me-2"></i>Downloads</h4>
                        <div id="downloadsList" class="mt-3">
                            <!-- Downloads will appear here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let pollInterval;
        
        document.getElementById('downloadBtn').addEventListener('click', startDownload);
        document.getElementById('videoUrl').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') startDownload();
        });
        
        function startDownload() {
            const url = document.getElementById('videoUrl').value.trim();
            if (!url) {
                showAlert('Please enter a valid URL', 'danger');
                return;
            }
            
            const btn = document.getElementById('downloadBtn');
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            
            fetch('/api/download', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({url: url})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showAlert('Download started! Check the downloads list below.', 'success');
                    document.getElementById('videoUrl').value = '';
                    pollDownloadStatus(data.download_id);
                    updateDownloadsList();
                } else {
                    showAlert(data.error || 'Download failed', 'danger');
                }
            })
            .catch(error => {
                showAlert('Network error: ' + error.message, 'danger');
            })
            .finally(() => {
                btn.disabled = false;
                btn.innerHTML = '<i class="fas fa-download me-2"></i>Download';
            });
        }
        
        function pollDownloadStatus(downloadId) {
            if (pollInterval) clearInterval(pollInterval);
            
            pollInterval = setInterval(() => {
                fetch(`/api/status/${downloadId}`)
                    .then(response => response.json())
                    .then(status => {
                        updateDownloadItem(downloadId, status);
                        
                        if (status.status === 'completed' || status.status === 'error' || status.status === 'cancelled') {
                            clearInterval(pollInterval);
                            updateDownloadsList();
                        }
                    });
            }, 1000);
        }
        
        function updateDownloadItem(downloadId, status) {
            let item = document.getElementById(`download-${downloadId}`);
            if (!item) {
                item = createDownloadItem(downloadId, status);
                document.getElementById('downloadsList').prepend(item);
            }
            
            const progressBar = item.querySelector('.progress-bar');
            const statusBadge = item.querySelector('.status-badge');
            const progressText = item.querySelector('.progress-text');
            
            if (progressBar) {
                progressBar.style.width = `${status.progress}%`;
                progressBar.textContent = `${status.progress}%`;
            }
            
            if (statusBadge) {
                statusBadge.className = `status-badge badge bg-${getStatusColor(status.status)}`;
                statusBadge.textContent = status.status.charAt(0).toUpperCase() + status.status.slice(1);
            }
            
            if (progressText && status.filename) {
                progressText.textContent = status.filename;
            }
            
            const downloadBtn = item.querySelector('.download-btn');
            if (downloadBtn) {
                if (status.status === 'completed') {
                    downloadBtn.href = `/download/${downloadId}`;
                    downloadBtn.classList.remove('d-none');
                } else if (status.status === 'error') {
                    downloadBtn.classList.add('d-none');
                }
            }
        }
        
        function createDownloadItem(downloadId, status) {
            const div = document.createElement('div');
            div.id = `download-${downloadId}`;
            div.className = 'download-item card p-3 mb-3';
            
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <strong class="progress-text">${status.filename || 'Preparing...'}</strong>
                        <div class="mt-2">
                            <span class="status-badge badge bg-${getStatusColor(status.status)}">
                                ${status.status.charAt(0).toUpperCase() + status.status.slice(1)}
                            </span>
                        </div>
                    </div>
                    <div class="text-end">
                        <a href="/download/${downloadId}" class="download-btn btn btn-sm btn-success d-none">
                            <i class="fas fa-file-download me-1"></i>Download
                        </a>
                        <button onclick="cancelDownload('${downloadId}')" class="btn btn-sm btn-danger ms-2">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
                <div class="progress mt-2">
                    <div class="progress-bar progress-bar-striped progress-bar-animated" 
                         role="progressbar" style="width: ${status.progress}%">
                        ${status.progress}%
                    </div>
                </div>
                ${status.error ? `<div class="text-danger small mt-2">${status.error}</div>` : ''}
            `;
            
            return div;
        }
        
        function getStatusColor(status) {
            const colors = {
                'queued': 'secondary',
                'downloading': 'info',
                'completed': 'success',
                'error': 'danger',
                'cancelled': 'warning'
            };
            return colors[status] || 'secondary';
        }
        
        function cancelDownload(downloadId) {
            fetch(`/api/cancel/${downloadId}`, {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showAlert('Download cancelled', 'warning');
                    }
                });
        }
        
        function updateDownloadsList() {
            fetch('/api/downloads')
                .then(response => response.json())
                .then(downloads => {
                    const list = document.getElementById('downloadsList');
                    // Keep existing active downloads
                    const existingIds = Array.from(list.children)
                        .map(item => item.id.replace('download-', ''))
                        .filter(id => downloadStatus[id] && downloadStatus[id].status !== 'completed');
                    
                    // Add completed downloads from history
                    downloads.reverse().forEach(download => {
                        if (!existingIds.includes(download.id)) {
                            const item = createDownloadItem(download.id, {
                                filename: download.filename,
                                status: download.status,
                                progress: 100
                            });
                            list.prepend(item);
                        }
                    });
                });
        }
        
        function showAlert(message, type) {
            const alert = document.getElementById('statusAlert');
            alert.className = `alert alert-${type} alert-dismissible fade show`;
            alert.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `;
            alert.classList.remove('d-none');
            
            setTimeout(() => {
                alert.classList.add('d-none');
            }, 5000);
        }
        
        // Initial load
        updateDownloadsList();
    </script>
</body>
</html>''')
    
    print("Starting Video Downloader...")
    print("Open http://localhost:5000 in your browser")
    print("\nNote: This app downloads publicly accessible video files.")
    print("Make sure you have permission to download any content.")
    
    app.run(debug=True, host='0.0.0.0', port=25000)