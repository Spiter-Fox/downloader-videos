from flask import Flask, render_template, request, send_file, jsonify
from flask_socketio import SocketIO, emit
import yt_dlp
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.config['DOWNLOAD_FOLDER'] = './downloads'
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

# Lista podržanih domena
ALLOWED_DOMAINS = [
    'youtube.com', 'youtu.be',
    'facebook.com', 'fb.watch',
    'tiktok.com', 'instagram.com',
    'reddit.com', 'twitter.com',
    'x.com'
]

# Provera da li je URL sa podržanog sajta
def is_valid_url(url):
    try:
        result = urlparse(url)
        return any(result.netloc.endswith(domain) for domain in ALLOWED_DOMAINS)
    except:
        return False

# Dobijanje informacija o videu
def get_video_info(url):
    ydl_opts = {'quiet': True}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

# Početna stranica
@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

# Endpoint za preuzimanje
@app.route('/download', methods=['POST'])
def download():
    url = request.form['url']
    download_type = request.form.get('downloadType', 'video')  # video ili audio
    if not is_valid_url(url):
        return jsonify({'error': 'Unsupported site!'}), 400
    
    try:
        video_info = get_video_info(url)
        if not video_info:
            return jsonify({'error': 'Failed to fetch video info. Please check the URL.'}), 400

        title = video_info.get('title', 'video')
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_')).rstrip()

        if download_type == 'audio':
            filename = f"{safe_title}.mp3"  # Osiguravamo .mp3 ekstenziju
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            ydl_opts = {
                'format': 'bestaudio/best',  # Najbolji audio format
                'outtmpl': filepath,         # Izlazni fajl
                'postprocessors': [{         # Konverzija u MP3
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',  # Kvalitet audio zapisa
                }],
                'ffmpeg_location': 'C:\\Users\\Strac\\Desktop\\downloader\\ffmpeg\\bin',  # Tačna putanja do ffmpeg
                'progress_hooks': [lambda d: socketio.emit('progress', {'progress': d['_percent_str']})],  # Praćenje napretka
            }
        else:
            filename = f"{safe_title}.mp4"
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': filepath,
                'merge_output_format': 'mp4',
                'progress_hooks': [lambda d: socketio.emit('progress', {'progress': d['_percent_str']})],  # Praćenje napretka
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Proveri da li fajl postoji
        if not os.path.exists(filepath):
            return jsonify({'error': 'File not found after download.'}), 500

        return jsonify({'filename': filename, 'title': title})

    except yt_dlp.utils.DownloadError as e:
        return jsonify({'error': f"Download failed: {str(e)}"}), 500
    except Exception as e:
        return jsonify({'error': f"An unexpected error occurred: {str(e)}"}), 500

# Endpoint za preuzimanje fajla
@app.route('/downloads/<filename>')
def download_file(filename):
    filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found.'}), 404
    return send_file(filepath, as_attachment=True)

# Pokretanje aplikacije
if __name__ == '__main__':
    if not os.path.exists(app.config['DOWNLOAD_FOLDER']):
        os.makedirs(app.config['DOWNLOAD_FOLDER'])
    socketio.run(app, debug=True)