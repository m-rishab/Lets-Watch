from flask import Flask, request, jsonify, send_from_directory, abort, render_template
import os
import uuid
import json
from werkzeug.utils import secure_filename
import time
from datetime import datetime

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'webm'}
STREAMABLE_EXTENSIONS = {'mp4', 'webm'}  # Formats that can be streamed in most browsers
DATABASE_FILE = 'movies_db.json'

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 4 * 1024 * 1024 * 1024  # 4GB max upload size

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize database if it doesn't exist
if not os.path.exists(DATABASE_FILE):
    with open(DATABASE_FILE, 'w') as f:
        json.dump([], f)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_streamable(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in STREAMABLE_EXTENSIONS

def get_movies_db():
    with open(DATABASE_FILE, 'r') as f:
        return json.load(f)

def save_movies_db(movies):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(movies, f, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/movies', methods=['GET'])
def get_movies():
    movies = get_movies_db()
    # Add full URL and streamable flag to each movie
    for movie in movies:
        movie['url'] = f"/uploads/{movie['filename']}"
        movie['streamable'] = is_streamable(movie['filename'])
    return jsonify(movies)

@app.route('/api/movies/<movie_id>', methods=['GET'])
def get_movie(movie_id):
    movies = get_movies_db()
    for movie in movies:
        if movie['id'] == movie_id:
            movie['url'] = f"/uploads/{movie['filename']}"
            movie['streamable'] = is_streamable(movie['filename'])
            return jsonify(movie)
    return jsonify({"error": "Movie not found"}), 404

@app.route('/api/movies/<movie_id>', methods=['DELETE'])
def delete_movie(movie_id):
    movies = get_movies_db()
    movie_to_delete = None
    
    # Find the movie to delete
    for movie in movies:
        if movie['id'] == movie_id:
            movie_to_delete = movie
            break
    
    if not movie_to_delete:
        return jsonify({"error": "Movie not found"}), 404
    
    # Delete the file
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], movie_to_delete['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        return jsonify({"error": f"Failed to delete file: {str(e)}"}), 500
    
    # Remove from database
    movies = [movie for movie in movies if movie['id'] != movie_id]
    save_movies_db(movies)
    
    return jsonify({"message": "Movie deleted successfully"})

@app.route('/api/upload', methods=['POST'])
def upload_movie():
    # Check if the post request has the file part
    if 'movie' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['movie']
    
    # If user does not select file, browser may
    # submit an empty file without a filename
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        # Generate a unique filename to prevent overwriting
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"
        
        # Save the file
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Check if file is streamable in browsers
        streamable = is_streamable(file.filename)
        
        # Add to database
        movie_id = str(uuid.uuid4())
        movie_data = {
            "id": movie_id,
            "title": original_filename,
            "filename": unique_filename,
            "original_filename": original_filename,
            "size": file_size,
            "upload_date": datetime.now().isoformat(),
            "mime_type": file.mimetype,
            "streamable": streamable
        }
        
        movies = get_movies_db()
        movies.append(movie_data)
        save_movies_db(movies)
        
        # Return success response
        movie_data['url'] = f"/uploads/{unique_filename}"
        return jsonify(movie_data)
    
    return jsonify({"error": "File type not allowed"}), 400

@app.route('/uploads/<filename>')
def serve_movie(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except:
        abort(404)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not found"}), 404

@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "File too large"}), 413

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    # Ensure the static and templates directories exist
    if not os.path.exists('static'):
        os.makedirs('static')
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    app.run(debug=True, host='0.0.0.0', port=8080)