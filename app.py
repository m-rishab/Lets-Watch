from flask import Flask, render_template, send_from_directory, Response, abort, request
import os
import logging
import subprocess
import shutil
import time
import re
import sys
import traceback
import threading
import psutil  # You might need to install this: pip install psutil

app = Flask(__name__)
VIDEO_FOLDER = 'videos'
CONVERTED_FOLDER = 'converted_videos'
# Store active streaming processes to manage them properly
ACTIVE_STREAMS = {}

# Enhanced logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('video_server.log')
    ]
)
logger = logging.getLogger(__name__)

def check_ffmpeg():
    """Check if FFmpeg is installed on the system and return version info"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        logger.info(f"FFmpeg found: {result.stdout.splitlines()[0]}")
        return True
    except FileNotFoundError:
        logger.warning("FFmpeg not found. Video conversion and streaming will not be available.")
        return False

def create_directories():
    """Create necessary directories"""
    for directory in [VIDEO_FOLDER, CONVERTED_FOLDER, 'static', 'temp']:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logger.info(f"Created directory: {directory}")

def convert_video(input_file, output_file):
    """Convert video to MP4 format using FFmpeg"""
    try:
        # Use FFmpeg to convert the video to MP4 format
        cmd = [
            'ffmpeg', '-i', input_file, 
            '-c:v', 'libx264', '-c:a', 'aac', 
            '-strict', 'experimental', 
            '-b:a', '192k', '-f', 'mp4',
            '-y',  # Overwrite output files without asking
            output_file
        ]
        logger.info(f"Running conversion command: {' '.join(cmd)}")
        
        process = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            check=True
        )
        
        logger.info(f"Successfully converted {input_file} to {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error converting video: {e}")
        logger.error(f"FFmpeg stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error in convert_video: {e}")
        logger.error(traceback.format_exc())
        return False

def get_video_duration(filename):
    """Get the duration of a video file using FFmpeg"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            filename
        ], capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        logger.warning(f"Couldn't determine duration for {filename}: {e}")
        return 0
    except Exception as e:
        logger.warning(f"Error getting video duration: {e}")
        return 0

def get_video_codec(filename):
    """Get video codec information using FFprobe"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0', 
            '-show_entries', 'stream=codec_name',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filename
        ], capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Error getting video codec: {e}")
        return "unknown"

def get_video_bitrate(filename):
    """Get video bitrate information using FFprobe"""
    try:
        result = subprocess.run([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            filename
        ], capture_output=True, text=True, check=True)
        bitrate = result.stdout.strip()
        # If bitrate is empty or "N/A", estimate based on file size and duration
        if not bitrate or bitrate == "N/A":
            filesize = os.path.getsize(filename)  # in bytes
            duration = get_video_duration(filename)  # in seconds
            if duration > 0:
                # Estimate bitrate in bits per second
                bitrate = str(int((filesize * 8) / duration))
        return bitrate
    except Exception as e:
        logger.warning(f"Error getting video bitrate: {e}")
        return "0"

def get_video_info(filename):
    """Get detailed information about the video file"""
    file_path = os.path.join(VIDEO_FOLDER, filename)
    if not os.path.exists(file_path):
        return None
    
    duration = get_video_duration(file_path)
    size = os.path.getsize(file_path) / (1024 * 1024)  # Size in MB
    codec = get_video_codec(file_path)
    
    # For large files, calculate a reasonable bitrate for streaming
    bitrate = get_video_bitrate(file_path)
    try:
        bitrate_mbps = int(bitrate) / 1000000  # Convert to Mbps
    except (ValueError, TypeError):
        # If bitrate conversion fails, estimate based on file size
        if size > 0 and duration > 0:
            bitrate_mbps = (size * 8) / duration  # Rough estimate
        else:
            bitrate_mbps = 5  # Default 5 Mbps if we can't calculate
    
    return {
        'duration': duration,
        'size': size,
        'filename': filename,
        'codec': codec,
        'bitrate': bitrate_mbps,
        'is_large': size > 1000  # Consider files > 1GB as large
    }

@app.route('/')
def index():
    # Scan for video files
    all_videos = []
    mkv_files = []
    mp4_files = []
    
    # Check if FFmpeg is available
    has_ffmpeg = check_ffmpeg()
    
    if os.path.exists(VIDEO_FOLDER):
        # First find all MKV and MP4 files
        for file in os.listdir(VIDEO_FOLDER):
            file_path = os.path.join(VIDEO_FOLDER, file)
            if file.lower().endswith('.mkv'):
                info = get_video_info(file)
                if info:
                    if has_ffmpeg:
                        mkv_files.append(info)
                    else:
                        # If FFmpeg is not available, mark MKV files as needing conversion
                        # but we won't be able to convert them
                        all_videos.append({
                            'title': f"{os.path.splitext(file)[0]} (MKV - not supported)",
                            'src': f'/videos/{file}',
                            'type': 'mkv'
                        })
            elif file.lower().endswith('.mp4'):
                mp4_files.append(file)
    
    # Check converted videos
    converted_videos = []
    if os.path.exists(CONVERTED_FOLDER):
        for file in os.listdir(CONVERTED_FOLDER):
            if file.lower().endswith('.mp4'):
                converted_videos.append(file)
    
    # Build the video list with both original MP4s and converted videos
    for file in mp4_files:
        title = os.path.splitext(file)[0]
        all_videos.append({
            'title': title,
            'src': f'/videos/{file}',
            'type': 'mp4'
        })
    
    for file in converted_videos:
        title = os.path.splitext(file)[0]
        # Remove the "_converted" suffix if present
        if title.endswith("_converted"):
            title = title[:-10]
        all_videos.append({
            'title': f"{title}",
            'src': f'/converted/{file}',
            'type': 'mp4'
        })
    
    # Add MKV files that can be streamed
    if has_ffmpeg:
        for info in mkv_files:
            file = info['filename']
            title = os.path.splitext(file)[0]
            duration_str = time.strftime('%H:%M:%S', time.gmtime(info['duration']))
            size_str = f"{info['size']:.1f} MB"
            
            # Add large file indicator if appropriate
            size_indicator = f"{size_str} - LARGE FILE" if info['is_large'] else size_str
            codec_info = f"({info['codec']})" if info['codec'] != "unknown" else ""
            
            all_videos.append({
                'title': f"{title} (MKV - {duration_str}, {size_indicator} {codec_info})",
                'src': f'/stream/{file}{"?optimized=1" if info["is_large"] else ""}',
                'type': 'mkv',
                'streamable': True
            })
    
    # Log found videos
    if not all_videos:
        logger.warning(f"No video files found in {VIDEO_FOLDER}.")
        
    return render_template('index.html', videos=all_videos, has_ffmpeg=has_ffmpeg)

@app.route('/videos/<path:filename>')
def stream_video(filename):
    """Stream original videos"""
    file_path = os.path.join(VIDEO_FOLDER, filename)
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        abort(404)
    return send_from_directory(VIDEO_FOLDER, filename)

@app.route('/converted/<path:filename>')
def stream_converted_video(filename):
    """Stream converted videos"""
    file_path = os.path.join(CONVERTED_FOLDER, filename)
    if not os.path.exists(file_path):
        logger.error(f"Converted file not found: {file_path}")
        abort(404)
    return send_from_directory(CONVERTED_FOLDER, filename)

def get_optimal_streaming_settings(file_path, is_large=False):
    """Calculate optimal streaming settings based on file characteristics"""
    # Get system information
    system_memory = psutil.virtual_memory().total / (1024 * 1024 * 1024)  # in GB
    cpu_count = psutil.cpu_count(logical=False) or 2  # Physical CPU cores, minimum 2
    
    try:
        info = get_video_info(file_path)
        
        # Base quality settings on file size, system memory, and CPU
        if is_large or (info and info.get('is_large', False)):
            # For large files, use reduced quality to ensure smooth streaming
            # Adjust based on available system resources
            
            # Video bitrate calculation
            if system_memory < 4:  # Less than 4GB RAM
                video_bitrate = '1M'  # Low bitrate for constrained systems
                preset = 'ultrafast'
            elif system_memory < 8:  # 4-8GB RAM
                video_bitrate = '2M'  # Medium bitrate
                preset = 'superfast'
            else:  # 8GB+ RAM
                video_bitrate = '3M'  # Higher quality
                preset = 'veryfast'
            
            # Audio bitrate and buffer settings
            audio_bitrate = '96k'
            buf_size = min(8192 * cpu_count, 65536)  # Scale with CPU but cap at 64KB
            
            # Optional scale down for very large files
            scale = None
            if info and info.get('size', 0) > 3000:  # Above 3GB
                scale = '1280:-2'  # Scale to 720p width, keep aspect ratio
            
            return {
                'video_bitrate': video_bitrate,
                'audio_bitrate': audio_bitrate,
                'preset': preset,
                'buf_size': buf_size,
                'scale': scale
            }
        else:
            # For smaller files, use better quality
            return {
                'video_bitrate': '4M',
                'audio_bitrate': '128k',
                'preset': 'veryfast',
                'buf_size': 16384,
                'scale': None
            }
    except Exception as e:
        logger.error(f"Error determining streaming settings: {e}")
        # Default fallback values
        return {
            'video_bitrate': '2M',
            'audio_bitrate': '128k',
            'preset': 'ultrafast',
            'buf_size': 8192,
            'scale': None
        }

def create_stream_session_id():
    """Generate a unique session ID for a stream"""
    import uuid
    return str(uuid.uuid4())

def cleanup_stream(session_id):
    """Clean up resources for a completed stream"""
    if session_id in ACTIVE_STREAMS:
        stream_info = ACTIVE_STREAMS.pop(session_id)
        process = stream_info.get('process')
        
        try:
            if process and process.poll() is None:
                logger.info(f"Cleaning up process for session {session_id[:8]}...")
                process.terminate()
                process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Error during cleanup for session {session_id[:8]}: {e}")

@app.route('/stream/<path:filename>')
def stream_mkv(filename):
    """Stream MKV files with on-the-fly transcoding"""
    input_path = os.path.join(VIDEO_FOLDER, filename)
    
    # Check if file exists
    if not os.path.exists(input_path):
        logger.error(f"File not found: {input_path}")
        abort(404)
    
    # Check if FFmpeg is available
    if not check_ffmpeg():
        logger.error("FFmpeg not available for streaming")
        abort(500)
    
    # Generate a unique session ID for this stream
    session_id = create_stream_session_id()
    
    # Get the start time from query parameters (for seeking)
    start_time = request.args.get('start', '0')
    if not re.match(r'^\d+(\.\d+)?$', start_time):
        start_time = '0'  # Default to 0 if invalid format
    
    # Check if optimized mode is requested (for large files)
    optimized = request.args.get('optimized', '0') == '1'
    
    # Get optimal settings based on file and system
    settings = get_optimal_streaming_settings(filename, optimized)
    
    # Set up FFmpeg command for streaming
    cmd = ['ffmpeg']
    
    # Input options
    cmd.extend([
        '-nostdin',          # Don't expect input from stdin to prevent freezes
        '-ss', start_time,   # Start time for seeking
    ])
    
    # Add input file path
    cmd.extend(['-i', input_path])
    
    # Video options
    cmd.extend([
        '-c:v', 'libx264',        # Video codec
        '-preset', settings['preset'],
        '-tune', 'zerolatency',   # Minimize latency
        '-b:v', settings['video_bitrate'],  # Video bitrate
    ])
    
    # Optionally scale down for large files
    if settings['scale']:
        cmd.extend(['-vf', f'scale={settings["scale"]}'])
    
    # Audio options
    cmd.extend([
        '-c:a', 'aac',            # Audio codec
        '-b:a', settings['audio_bitrate'],  # Audio bitrate
    ])
    
    # Output options
    cmd.extend([
        '-f', 'mp4',              # Output format
        '-movflags', 'frag_keyframe+empty_moov+faststart',  # Optimize for streaming
        '-max_muxing_queue_size', '1024',  # Increase muxing queue for complex files
    ])
    
    # Output to pipe
    cmd.append('-')
    
    logger.info(f"[Session {session_id[:8]}] Starting stream: {' '.join(cmd)}")
    
    # Create a generator function that yields chunks of the transcoded video
    def generate():
        try:
            # Create process to run ffmpeg command
            process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                bufsize=settings['buf_size']  # Use optimized buffer size
            )
            
            # Track this process for management
            ACTIVE_STREAMS[session_id] = {
                'process': process,
                'filename': filename,
                'started_at': time.time()
            }
            
            logger.info(f"[Session {session_id[:8]}] Started FFmpeg process for {filename}")
            
            # Capture stderr in a separate thread for logging
            def log_errors():
                for line in process.stderr:
                    if not line:
                        continue
                    line_str = line.decode('utf-8', errors='replace').strip()
                    # Only log important messages, not progress updates
                    if line_str and not line_str.startswith('frame='):
                        if 'error' in line_str.lower() or 'warning' in line_str.lower():
                            logger.warning(f"[Session {session_id[:8]}] FFmpeg: {line_str}")
                        else:
                            logger.debug(f"[Session {session_id[:8]}] FFmpeg: {line_str}")
            
            error_thread = threading.Thread(target=log_errors)
            error_thread.daemon = True
            error_thread.start()
            
            # Stream the output
            try:
                # Use a larger chunk size for large files
                chunk_size = 64 * 1024 if optimized else 16 * 1024  # 64KB vs 16KB
                
                while True:
                    chunk = process.stdout.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            finally:
                cleanup_stream(session_id)
                logger.info(f"[Session {session_id[:8]}] Finished streaming {filename}")
                
        except Exception as e:
            logger.error(f"[Session {session_id[:8]}] Error during streaming: {e}")
            logger.error(traceback.format_exc())
            cleanup_stream(session_id)
            yield b''  # Send empty response to trigger error handling in browser
    
    # Return a streaming response
    return Response(
        generate(), 
        mimetype='video/mp4',
        headers={
            'Accept-Ranges': 'bytes',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'X-Stream-Session': session_id
        }
    )

@app.route('/stream-stats/<path:session_id>')
def get_stream_stats(session_id):
    """Return status of a specific stream"""
    if session_id in ACTIVE_STREAMS:
        stream_info = ACTIVE_STREAMS[session_id]
        process = stream_info.get('process')
        
        # Check if process is still running
        is_running = process and process.poll() is None
        
        # Get CPU usage of the process
        cpu_percent = 0
        try:
            if is_running:
                process_obj = psutil.Process(process.pid)
                cpu_percent = process_obj.cpu_percent(interval=0.1)
        except:
            cpu_percent = 0
        
        return {
            'running': is_running,
            'filename': stream_info.get('filename', ''),
            'uptime': int(time.time() - stream_info.get('started_at', time.time())),
            'cpu_percent': cpu_percent
        }
    
    return {'running': False, 'error': 'Stream not found'}, 404

@app.route('/convert/<path:filename>')
def convert_video_route(filename):
    """API endpoint to convert a video"""
    input_path = os.path.join(VIDEO_FOLDER, filename)
    
    # Check if input file exists
    if not os.path.exists(input_path):
        logger.error(f"Source file not found for conversion: {input_path}")
        return {'success': False, 'error': 'Source file not found'}, 404
        
    # Create output filename and path
    base_name = os.path.splitext(filename)[0]
    output_filename = f"{base_name}_converted.mp4"
    output_path = os.path.join(CONVERTED_FOLDER, output_filename)
    
    # Check if FFmpeg is available
    if not check_ffmpeg():
        logger.error("FFmpeg not installed, cannot convert video")
        return {'success': False, 'error': 'FFmpeg not installed'}, 500
    
    # Convert the video
    if convert_video(input_path, output_path):
        # Return the URL to the converted video
        logger.info(f"Successfully converted {filename} to {output_filename}")
        return {
            'success': True, 
            'message': 'Video converted successfully', 
            'url': f'/converted/{output_filename}'
        }
    else:
        return {'success': False, 'error': 'Conversion failed'}, 500

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# Clean up old streams periodically
def cleanup_old_streams():
    """Check for and clean up stale stream processes"""
    while True:
        time.sleep(60)  # Check every minute
        try:
            now = time.time()
            sessions_to_remove = []
            
            for session_id, stream_info in ACTIVE_STREAMS.items():
                # Check if stream has been running for over 3 hours (unusual)
                if (now - stream_info.get('started_at', now)) > 3 * 60 * 60:
                    logger.warning(f"Stream {session_id[:8]} has been running for over 3 hours, cleaning up")
                    sessions_to_remove.append(session_id)
                    
                # Check if process is dead but not removed
                process = stream_info.get('process')
                if process and process.poll() is not None:
                    logger.info(f"Stream {session_id[:8]} process has ended, cleaning up")
                    sessions_to_remove.append(session_id)
            
            # Clean up identified sessions
            for session_id in sessions_to_remove:
                cleanup_stream(session_id)
                
        except Exception as e:
            logger.error(f"Error in cleanup thread: {e}")

if __name__ == '__main__':
    create_directories()
    
    # Ensure CSS file exists in static folder
    static_css_path = os.path.join('static', 'styles.css')
    root_css_path = 'styles.css'
    
    if not os.path.exists(static_css_path) and os.path.exists(root_css_path):
        try:
            shutil.copy2(root_css_path, static_css_path)
            logger.info("Copied styles.css to static directory")
        except Exception as e:
            logger.error(f"Error copying CSS file: {e}")
    
    # Start background cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_streams, daemon=True)
    cleanup_thread.start()
    
    # Print instructions for the user
    print("\n" + "="*80)
    print("ENHANCED VIDEO PLAYER WITH LIVE MKV STREAMING")
    print("="*80)
    print("Instructions:")
    print("1. Place your video files in the 'videos' directory")
    print("2. MKV files will be streamed in real-time with on-the-fly transcoding")
    print("3. Large files (>1GB) will automatically use optimized streaming settings")
    print("4. You can still convert videos permanently using the 'Convert' button")
    print("\nFFmpeg Status:")
    ffmpeg_available = check_ffmpeg()
    print(f"FFmpeg installed: {'YES' if ffmpeg_available else 'NO - INSTALL FFMPEG FOR STREAMING'}")
    if not ffmpeg_available:
        print("\nTo install FFmpeg:")
        print("- Ubuntu/Debian: sudo apt install ffmpeg")
        print("- macOS: brew install ffmpeg")
        print("- Windows: Download from https://ffmpeg.org/download.html")
    print("\nAccess the player at http://127.0.0.1:5000")
    print("="*80 + "\n")
    
    # Create a log file handler for debugging
    app.run(debug=True)