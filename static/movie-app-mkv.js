// Enhanced Let's Watch app with advanced MKV support
document.addEventListener('DOMContentLoaded', function() {
    // DOM elements
    const uploadForm = document.getElementById('upload-form');
    const movieFile = document.getElementById('movie-file');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadProgress = document.getElementById('upload-progress');
    const progress = document.querySelector('.progress');
    const uploadMessage = document.getElementById('upload-message');
    const moviesContainer = document.getElementById('movies-container');
    
    // Track VideoJS players to dispose them properly
    const videoPlayers = {};
    
    // Load movies on page load
    loadMovies();
    
    // Handle movie upload
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (!movieFile.files[0]) {
            showMessage('Please select a file to upload.', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('movie', movieFile.files[0]);
        
        // Disable upload button and show progress
        uploadBtn.disabled = true;
        uploadProgress.classList.remove('hidden');
        progress.style.width = '0%';
        progress.textContent = '0%';
        
        // Create XHR request
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                progress.style.width = percentComplete + '%';
                progress.textContent = Math.round(percentComplete) + '%';
            }
        });
        
        // Handle upload complete
        xhr.addEventListener('load', function() {
            if (xhr.status === 200) {
                const response = JSON.parse(xhr.responseText);
                showMessage(`Successfully uploaded: ${response.title}`, 'success');
                loadMovies(); // Refresh the movie list
                uploadForm.reset();
            } else {
                try {
                    const error = JSON.parse(xhr.responseText);
                    showMessage(`Upload failed: ${error.error}`, 'error');
                } catch (e) {
                    showMessage('Upload failed: Server error', 'error');
                }
            }
            uploadBtn.disabled = false;
            uploadProgress.classList.add('hidden');
        });
        
        // Handle upload error
        xhr.addEventListener('error', function() {
            showMessage('Upload failed: Network error', 'error');
            uploadBtn.disabled = false;
            uploadProgress.classList.add('hidden');
        });
        
        // Open and send the request
        xhr.open('POST', '/api/upload', true);
        xhr.send(formData);
    });
    
    // Function to load movies from the server
    function loadMovies() {
        fetch('/api/movies')
            .then(response => response.json())
            .then(movies => {
                displayMovies(movies);
            })
            .catch(error => {
                console.error('Error loading movies:', error);
                moviesContainer.innerHTML = '<p class="error">Error loading movies. Please refresh the page.</p>';
            });
    }
    
    // Function to display movies
    function displayMovies(movies) {
        // Dispose all existing VideoJS players
        disposeAllPlayers();
        
        if (!movies || movies.length === 0) {
            moviesContainer.innerHTML = '<p>No videos found. Upload your first video above!</p>';
            return;
        }
        
        // Sort movies by upload date (newest first)
        movies.sort((a, b) => new Date(b.upload_date) - new Date(a.upload_date));
        
        // Clear container
        moviesContainer.innerHTML = '';
        
        // Add each movie
        movies.forEach(movie => {
            const movieCard = document.createElement('div');
            movieCard.className = 'movie-card';
            movieCard.dataset.id = movie.id;
            
            // Format file size
            const fileSize = formatFileSize(movie.size);
            
            // Format date
            const uploadDate = new Date(movie.upload_date).toLocaleDateString();
            
            // Determine file type and support level
            const fileExt = movie.original_filename.split('.').pop().toLowerCase();
            const uniqueId = `video-${movie.id}`;
            
            // Create appropriate video container
            let videoContainerHTML;
            
            if (fileExt === 'mkv') {
                videoContainerHTML = `
                    <div class="video-container">
                        <div id="${uniqueId}-wrapper" class="video-wrapper">
                            <video id="${uniqueId}" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="metadata">
                                <source src="${movie.url}" type="video/x-matroska">
                                <p class="vjs-no-js">
                                    This browser may not fully support MKV playback.
                                </p>
                            </video>
                        </div>
                        <div id="${uniqueId}-fallback" class="mkv-fallback hidden">
                            <div class="file-icon">MKV</div>
                            <p>Alternative MKV playback options:</p>
                            <div class="player-options">
                                <button class="try-videojs-player-btn">Try VideoJS Player</button>
                                <button class="try-mse-player-btn">Try MSE Playback</button>
                                <button class="try-webcodecs-player-btn">Try WebCodecs</button>
                                <a href="${movie.url}" download="${movie.original_filename}" class="download-link">
                                    Download to watch offline
                                </a>
                            </div>
                        </div>
                    </div>
                `;
            } else if (movie.streamable) {
                // Standard VideoJS for MP4, WebM, etc.
                videoContainerHTML = `
                    <div class="video-container">
                        <video id="${uniqueId}" class="video-js vjs-default-skin vjs-big-play-centered" controls preload="metadata">
                            <source src="${movie.url}" type="${movie.mime_type}">
                            Your browser does not support the video tag.
                        </video>
                    </div>
                `;
            } else {
                // For any other non-streamable formats
                const fileExtension = fileExt.toUpperCase();
                videoContainerHTML = `
                    <div class="video-container non-streamable">
                        <div class="placeholder">
                            <div class="file-icon">${fileExtension}</div>
                            <p>This ${fileExtension} file cannot be played directly in the browser</p>
                            <a href="${movie.url}" download="${movie.original_filename}" class="download-link">
                                Download to watch offline
                            </a>
                        </div>
                    </div>
                `;
            }
            
            movieCard.innerHTML = `
                ${videoContainerHTML}
                <div class="movie-info">
                    <h3 class="movie-title">${movie.title}</h3>
                    <div class="movie-details">
                        <div>Size: ${fileSize}</div>
                        <div>Uploaded: ${uploadDate}</div>
                        <div>Format: ${fileExt.toUpperCase()}</div>
                    </div>
                    <div class="movie-actions">
                        <button class="delete-btn" data-id="${movie.id}">Delete</button>
                        <a href="${movie.url}" class="download-btn" download="${movie.original_filename}">Download</a>
                    </div>
                </div>
            `;
            
            moviesContainer.appendChild(movieCard);
            
            // Initialize VideoJS for playable videos
            // Initialize VideoJS for playable videos
if (fileExt === 'mkv' || movie.streamable) {
    try {
        const player = videojs(uniqueId, {
            fluid: true,
            responsive: true,
            preload: 'auto', // Changed from 'metadata' to 'auto'
            controls: true,
            autoplay: false,
            playsinline: true, // Important for mobile
            controlBar: {
                playToggle: true,
                volumePanel: true,
                currentTimeDisplay: true,
                timeDivider: true,
                durationDisplay: true,
                progressControl: {
                    seekBar: true
                },
                fullscreenToggle: true
            },
            html5: {
                vhs: { // Support for HLS if available
                    overrideNative: true
                },
                nativeAudioTracks: false,
                nativeVideoTracks: false,
                nativeTextTracks: false
            }
        });
        
        // Fix for direct play triggering
        player.ready(function() {
            // Store player reference for later disposal
            videoPlayers[uniqueId] = player;
            
            // Make sure play/pause works through the API
            const playerContainer = document.querySelector(`#${uniqueId}-wrapper`);
            if (playerContainer) {
                playerContainer.addEventListener('click', function(e) {
                    // Don't trigger when clicking controls
                    if (e.target.closest('.vjs-control-bar') || e.target.closest('.vjs-big-play-button')) return;
                    
                    console.log('Click detected, attempting playback control');
                    if (player.paused()) {
                        console.log('Attempting to play');
                        // Use promise to handle autoplay restrictions
                        player.play().then(() => {
                            console.log('Playback started successfully');
                        }).catch(error => {
                            console.error('Playback failed:', error);
                            // Try again with user interaction flag
                            player.muted(true); // Mute as fallback for autoplay policy
                            player.play().catch(e => console.error('Second attempt failed:', e));
                        });
                    } else {
                        console.log('Attempting to pause');
                        player.pause();
                    }
                });
            }
            
            // Fix for big play button
            const bigPlayButton = playerContainer?.querySelector('.vjs-big-play-button');
            if (bigPlayButton) {
                bigPlayButton.addEventListener('click', function(e) {
                    e.stopPropagation(); // Prevent double handling
                    console.log('Big play button clicked');
                    player.play().catch(error => {
                        console.error('Play from button failed:', error);
                        // Try muted as fallback for autoplay policy
                        player.muted(true);
                        player.play().catch(e => console.error('Second play attempt failed:', e));
                    });
                });
            }
        });
        
        // For MKV files, add error handler to show fallback
        if (fileExt === 'mkv') {
            player.on('error', function() {
                console.log('VideoJS player error detected for MKV file');
                // Show fallback for MKV when VideoJS fails
                const fallbackElement = document.getElementById(`${uniqueId}-fallback`);
                if (fallbackElement) {
                    fallbackElement.classList.remove('hidden');
                    // Don't dispose the player yet - we might want to retry with it
                }
            });
            
            // Try to use VideoJS MKV playback first
            player.on('loadedmetadata', function() {
                console.log('VideoJS successfully loaded MKV metadata');
                // Hide the fallback if we successfully loaded metadata
                const fallbackElement = document.getElementById(`${uniqueId}-fallback`);
                if (fallbackElement) {
                    fallbackElement.classList.add('hidden');
                }
            });
            
            // Use the new checkMkvPlaybackStatus function
            checkMkvPlaybackStatus(player, uniqueId);
        }
    } catch (e) {
        console.error(`Error initializing player for ${movie.title}:`, e);
        // Show fallback for initialization errors
        if (fileExt === 'mkv') {
            const fallbackElement = document.getElementById(`${uniqueId}-fallback`);
            if (fallbackElement) {
                fallbackElement.classList.remove('hidden');
            }
        }
    }
}            
            // Add delete event listener
            const deleteBtn = movieCard.querySelector('.delete-btn');
            deleteBtn.addEventListener('click', function() {
                deleteMovie(movie.id, movie.title);
            });

            // Initialize MKV fallback buttons - outside the try-catch so it always runs
            if (fileExt === 'mkv') {
                // Add slight delay to ensure DOM elements are fully created
                setTimeout(() => {
                    initMkvFallbackButtons(movie, uniqueId);
                }, 100);
            }
        });
    }
    
    // Function to check MKV playback status
    function checkMkvPlaybackStatus(player, uniqueId) {
        // Check if MKV playback started successfully
        setTimeout(() => {
            const fallbackElement = document.getElementById(`${uniqueId}-fallback`);
            if (!fallbackElement) return;
            
            if (player && (player.error() || player.readyState() < 1)) {
                console.log('MKV did not load properly after timeout check');
                fallbackElement.classList.remove('hidden');
            } else {
                console.log('MKV playback appears to be working');
            }
        }, 3000);
    }
    
    // Initialize MKV fallback buttons
    function initMkvFallbackButtons(movie, uniqueId) {
        // Find the buttons within the fallback menu
        const fallbackElement = document.getElementById(`${uniqueId}-fallback`);
        if (!fallbackElement) return;
        
        const videoJsBtn = fallbackElement.querySelector('.try-videojs-player-btn');
        const mseBtn = fallbackElement.querySelector('.try-mse-player-btn');
        const webCodecsBtn = fallbackElement.querySelector('.try-webcodecs-player-btn');
        
        // Add click handlers to all buttons
        if (videoJsBtn) {
            videoJsBtn.addEventListener('click', function() {
                console.log('VideoJS button clicked for:', uniqueId);
                retryVideoJsPlayer(movie, uniqueId);
            });
        }
        
        if (mseBtn) {
            mseBtn.addEventListener('click', function() {
                console.log('MSE button clicked for:', uniqueId);
                tryMSEPlayer(movie, uniqueId);
            });
        }
        
        if (webCodecsBtn) {
            webCodecsBtn.addEventListener('click', function() {
                console.log('WebCodecs button clicked for:', uniqueId);
                tryWebCodecsPlayer(movie, uniqueId);
            });
        }
    }
    
    // Retry with VideoJS player using different configuration
    function retryVideoJsPlayer(movie, containerId) {
        const fallbackElement = document.getElementById(`${containerId}-fallback`);
        const videoWrapper = document.getElementById(`${containerId}-wrapper`);
        
        if (!fallbackElement || !videoWrapper) return;
        
        // Hide the fallback UI while we try
        fallbackElement.classList.add('hidden');
        
        // Display loading status
        videoWrapper.innerHTML = '<div class="loading">Retrying with enhanced VideoJS settings...</div>';
        
        // Create a new video element
        const videoElement = document.createElement('video');
        videoElement.id = containerId;
        videoElement.className = 'video-js vjs-default-skin vjs-big-play-centered';
        videoElement.controls = true;
        videoElement.preload = 'auto';
        
        // Add source element
        const sourceElement = document.createElement('source');
        sourceElement.src = movie.url;
        sourceElement.type = 'video/x-matroska';
        videoElement.appendChild(sourceElement);
        
        // Replace the wrapper content with the new video element
        videoWrapper.innerHTML = '';
        videoWrapper.appendChild(videoElement);
        
        try {
            // Dispose of old player if exists
            if (videoPlayers[containerId]) {
                videoPlayers[containerId].dispose();
                delete videoPlayers[containerId];
            }
            
            // Initialize VideoJS with more robust options
            const player = videojs(containerId, {
                fluid: true,
                responsive: true,
                preload: 'auto',
                controls: true,
                controlBar: {
                    playToggle: true,
                    volumePanel: true,
                    currentTimeDisplay: true,
                    timeDivider: true,
                    durationDisplay: true,
                    progressControl: {
                        seekBar: true
                    },
                    fullscreenToggle: true
                },
                html5: {
                    hls: {
                        overrideNative: true
                    },
                    nativeAudioTracks: false,
                    nativeVideoTracks: false,
                    nativeTextTracks: false
                },
                techOrder: ['html5']
            });
            
            // Store player reference
            videoPlayers[containerId] = player;
            
            // Handle errors
            player.on('error', function() {
                console.log('Retry VideoJS player error');
                fallbackElement.classList.remove('hidden');
            });
            
            // Check if video loaded
            player.on('loadedmetadata', function() {
                console.log('Retry VideoJS successfully loaded MKV metadata');
                // Video loaded successfully!
                fallbackElement.classList.add('hidden');
            });
            
            // Use the checkMkvPlaybackStatus function
            checkMkvPlaybackStatus(player, containerId);
            
        } catch (e) {
            console.error('Error retrying VideoJS player:', e);
            fallbackElement.classList.remove('hidden');
        }
    }
    
    // Try MSE (Media Source Extensions) player for MKV
    function tryMSEPlayer(movie, containerId) {
        const fallbackElement = document.getElementById(`${containerId}-fallback`);
        const videoWrapper = document.getElementById(`${containerId}-wrapper`);
        
        if (!fallbackElement || !videoWrapper) return;
        
        // Hide the fallback UI while we try
        fallbackElement.classList.add('hidden');
        
        // Display loading message
        videoWrapper.innerHTML = '<div class="loading">Setting up MSE playback for MKV...</div>';
        
        // Check if the browser supports MSE
        if (!window.MediaSource) {
            videoWrapper.innerHTML = '<div class="error">Your browser does not support Media Source Extensions (MSE)</div>';
            fallbackElement.classList.remove('hidden');
            return;
        }
        
        // Create video element
        const videoElement = document.createElement('video');
        videoElement.id = `mse-${containerId}`;
        videoElement.className = 'mse-video';
        videoElement.controls = true;
        videoElement.style.width = '100%';
        videoElement.style.height = 'auto';
        
        // Add video element to the DOM
        videoWrapper.innerHTML = '';
        videoWrapper.appendChild(videoElement);
        
        // Dispose of old player if exists
        if (videoPlayers[containerId]) {
            videoPlayers[containerId].dispose();
            delete videoPlayers[containerId];
        }
        
        // Create a MediaSource instance
        const mediaSource = new MediaSource();
        videoElement.src = URL.createObjectURL(mediaSource);
        
        mediaSource.addEventListener('sourceopen', async function() {
            try {
                // Fetch the MKV file
                const response = await fetch(movie.url);
                if (!response.ok) {
                    throw new Error('Failed to fetch MKV file');
                }
                
                // Get ArrayBuffer data
                const arrayBuffer = await response.arrayBuffer();
                
                // Try to create a source buffer with common codecs
                let sourceBuffer;
                try {
                    // Try WebM codecs first (might work for some MKV files)
                    sourceBuffer = mediaSource.addSourceBuffer('video/webm; codecs="vp8,vorbis"');
                } catch (e) {
                    try {
                        // Try MP4 codecs as fallback
                        sourceBuffer = mediaSource.addSourceBuffer('video/mp4; codecs="avc1.42E01E,mp4a.40.2"');
                    } catch (e2) {
                        throw new Error('Unsupported codec format in MKV file');
                    }
                }
                
                // Append the data to the source buffer
                sourceBuffer.addEventListener('updateend', function() {
                    if (!sourceBuffer.updating && mediaSource.readyState === 'open') {
                        mediaSource.endOfStream();
                        videoElement.play().catch(e => console.error('Play failed:', e));
                    }
                });
                
                sourceBuffer.addEventListener('error', function(e) {
                    console.error('Source buffer error:', e);
                    fallbackElement.classList.remove('hidden');
                });
                
                // Append the buffer to the source buffer
                sourceBuffer.appendBuffer(arrayBuffer);
                
            } catch (e) {
                console.error('MSE error:', e);
                videoWrapper.innerHTML = `<div class="error">Failed to play MKV file with MSE: ${e.message}</div>`;
                fallbackElement.classList.remove('hidden');
            }
        });
        
        mediaSource.addEventListener('error', function(e) {
            console.error('MediaSource error:', e);
            fallbackElement.classList.remove('hidden');
        });
        
        // Add error event listener to video element
        videoElement.addEventListener('error', function(e) {
            console.error('Video element error:', e);
            fallbackElement.classList.remove('hidden');
        });
    }
    
    // Try WebCodecs player for MKV
    function tryWebCodecsPlayer(movie, containerId) {
        const fallbackElement = document.getElementById(`${containerId}-fallback`);
        const videoWrapper = document.getElementById(`${containerId}-wrapper`);
        
        if (!fallbackElement || !videoWrapper) return;
        
        // Hide the fallback UI while we try
        fallbackElement.classList.add('hidden');
        
        // Check if browser supports WebCodecs
        if (typeof VideoDecoder === 'undefined') {
            videoWrapper.innerHTML = '<div class="error">Your browser does not support WebCodecs API</div>';
            fallbackElement.classList.remove('hidden');
            return;
        }
        
        // Display loading message
        videoWrapper.innerHTML = '<div class="loading">Setting up WebCodecs playback for MKV...</div>';
        
        // Create a canvas for rendering decoded frames
        const canvas = document.createElement('canvas');
        canvas.id = `webcodecs-canvas-${containerId}`;
        canvas.width = 640;
        canvas.height = 360;
        canvas.style.width = '100%';
        canvas.style.height = 'auto';
        
        // Create custom controls
        const controlsDiv = document.createElement('div');
        controlsDiv.className = 'webcodecs-controls';
        controlsDiv.innerHTML = `
            <button id="play-btn-${containerId}" class="play-btn">Play</button>
            <div class="progress-container">
                <div id="progress-bar-${containerId}" class="progress-bar">
                    <div id="progress-${containerId}" class="progress"></div>
                </div>
            </div>
        `;
        
        // Add canvas and controls to wrapper
        videoWrapper.innerHTML = '';
        videoWrapper.appendChild(canvas);
        videoWrapper.appendChild(controlsDiv);
        
        // Dispose of old player if exists
        if (videoPlayers[containerId]) {
            videoPlayers[containerId].dispose();
            delete videoPlayers[containerId];
        }
        
        // Create and initialize the custom WebCodecs player
        initializeWebCodecsPlayer(movie, containerId, canvas).catch(error => {
            console.error('Error initializing WebCodecs player:', error);
            videoWrapper.innerHTML = `<div class="error">Failed to initialize WebCodecs player: ${error.message}</div>`;
            fallbackElement.classList.remove('hidden');
        });
    }
    
    // Initialize WebCodecs player
    async function initializeWebCodecsPlayer(movie, containerId, canvas) {
        try {
            // Fetch the MKV file
            const response = await fetch(movie.url);
            if (!response.ok) {
                throw new Error('Failed to fetch MKV file');
            }
            
            const arrayBuffer = await response.arrayBuffer();
            
            // Just a placeholder - actual WebCodecs implementation would be much more complex
            // and would require MKV demuxer and proper codec handling
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = 'black';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = 'white';
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('WebCodecs API requires custom MKV demuxer', canvas.width / 2, canvas.height / 2 - 20);
            ctx.fillText('which is beyond the scope of this implementation.', canvas.width / 2, canvas.height / 2 + 10);
            ctx.fillText('Try the other playback options instead.', canvas.width / 2, canvas.height / 2 + 40);
            
            // For a complete implementation, you would:
            // 1. Demux the MKV container to extract video and audio tracks
            // 2. Use VideoDecoder and AudioDecoder to decode frames/samples
            // 3. Render video frames to canvas and play audio samples
            
            // Get the play button
            const playBtn = document.getElementById(`play-btn-${containerId}`);
            if (playBtn) {
                playBtn.addEventListener('click', function() {
                    const fallbackElement = document.getElementById(`${containerId}-fallback`);
                    if (fallbackElement) {
                        fallbackElement.classList.remove('hidden');
                    }
                });
            }
            
        } catch (error) {
            throw error;
        }
    }
    
    // Function to dispose all VideoJS players
    function disposeAllPlayers() {
        Object.keys(videoPlayers).forEach(playerId => {
            if (videoPlayers[playerId]) {
                try {
                    videoPlayers[playerId].dispose();
                } catch (e) {
                    console.error(`Error disposing player ${playerId}:`, e);
                }
            }
        });
        
        // Clear the players object
        Object.keys(videoPlayers).forEach(key => delete videoPlayers[key]);
    }
    
    // Function to delete a movie
    function deleteMovie(id, title) {
        if (confirm(`Are you sure you want to delete "${title}"?`)) {
            fetch(`/api/movies/${id}`, {
                method: 'DELETE'
            })
            .then(response => response.json())
            .then(data => {
                if (data.message) {
                    // Dispose VideoJS player if it exists
                    const videoId = `video-${id}`;
                    if (videoPlayers[videoId]) {
                        videoPlayers[videoId].dispose();
                        delete videoPlayers[videoId];
                    }
                    
                    loadMovies(); // Refresh the movie list
                    showMessage(`Successfully deleted: ${title}`, 'success');
                } else {
                    showMessage(`Delete failed: ${data.error}`, 'error');
                }
            })
            .catch(error => {
                console.error('Error deleting movie:', error);
                showMessage('Delete failed: Network error', 'error');
            });
        }
    }
    
    // Helper function to format file size
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Helper function to show messages
    function showMessage(message, type) {
        uploadMessage.textContent = message;
        uploadMessage.className = type;
        
        // Clear message after 8 seconds
        setTimeout(() => {
            uploadMessage.textContent = '';
            uploadMessage.className = '';
        }, 8000);
    }
    
    // Clean up before unloading the page
    window.addEventListener('beforeunload', function() {
        disposeAllPlayers();
    });
});