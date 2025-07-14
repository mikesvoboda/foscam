/**
 * Main Application Module
 * Coordinates all other modules and handles app initialization
 */

class MainApp {
    constructor() {
        this.enhancedHeatmap = null;
        this.isInitialized = false;
        this.currentPage = 1;
        this.perPage = 50;
    }
    
    // Initialize the entire application
    async initialize() {
        try {
            console.log('Initializing Foscam Detection Dashboard...');
            
            // Initialize GPU metrics
            try {
                if (window.gpuMetrics) {
                    await window.gpuMetrics.initialize();
                    console.log('GPU metrics initialized successfully');
                }
            } catch (error) {
                console.warn('GPU metrics initialization failed:', error);
            }
            
            // Initialize camera filter
            try {
                await window.cameraFilter.initialize();
                console.log('Camera filter initialized successfully');
            } catch (error) {
                console.warn('Camera filter initialization failed:', error);
            }
            
            // Initialize enhanced heatmap
            try {
                this.enhancedHeatmap = new EnhancedHeatmap();
                const cameras = window.cameraFilter ? window.cameraFilter.getAllCameras() : [];
                this.enhancedHeatmap.initializeWithCameras(cameras);
                console.log('Enhanced heatmap initialized successfully');
            } catch (error) {
                console.warn('Enhanced heatmap initialization failed:', error);
            }
            
            // Load initial data (with individual error handling)
            await this.loadInitialData();
            
            // Set up periodic refresh
            this.setupPeriodicRefresh();
            
            this.isInitialized = true;
            console.log('Dashboard initialized successfully');
            
        } catch (error) {
            console.error('Critical error during dashboard initialization:', error);
            this.showError('Some dashboard features may not work properly. Functionality will continue loading in the background.');
        }
    }
    
    // Load initial data
    async loadInitialData() {
        await Promise.all([
            this.loadDetections(),
            this.updateHeatmap(),
            this.loadStats()
        ]);
    }
    
    // Load detections
    async loadDetections() {
        try {
            console.log('loadDetections called - fetching page', this.currentPage, 'with', this.perPage, 'per page');
            const response = await fetch(`/api/detections?page=${this.currentPage}&per_page=${this.perPage}`);
            const data = await response.json();
            
            console.log('API response received:', data);
            console.log('Detections array:', data.detections);
            console.log('Pagination info:', data.pagination);
            
            this.displayDetections(data.detections);
            this.updatePagination(data.pagination);
            
        } catch (error) {
            console.error('Error loading detections:', error);
            this.showError('Failed to load detections');
        }
    }
    
    // Update heatmap
    async updateHeatmap() {
        if (this.enhancedHeatmap) {
            await this.enhancedHeatmap.updateHeatmap();
        }
    }
    
    // Load stats
    async loadStats() {
        try {
            const response = await fetch('/api/detections/stats');
            const data = await response.json();
            
            this.updateStats(data.stats);
            
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }
    
    // Display detections in the table
    displayDetections(detections) {
        console.log('displayDetections called with:', detections.length, 'detections');
        const container = document.getElementById('detectionsContainer');
        
        if (!container) {
            console.error('Detections container not found - DOM element detectionsContainer missing');
            return;
        }
        
        console.log('Container found:', container);
        
        if (detections.length === 0) {
            console.log('No detections to display');
            container.innerHTML = `
                <div style="text-align: center; padding: 3rem; color: #666; font-size: 1.2rem;">
                    <p>📭 No detections found</p>
                    <small>Try adjusting your filters or check back later</small>
                </div>
            `;
            return;
        }

        console.log('Creating cards for', detections.length, 'detections');
        
        // Create card-based layout
        container.innerHTML = detections.map(detection => {
            const timestamp = this.formatTimestamp(detection.timestamp);
            const mediaContent = this.formatMediaCell(detection);
            
            // Extract filename from media_filename path
            const filename = detection.media_filename ? 
                detection.media_filename.split('/').pop() : 'No filename';
            
            return `
                <div class="detection-card">
                    <div class="detection-header">
                        <div class="detection-timestamp">${timestamp}</div>
                        <div class="detection-camera">${detection.camera_location}</div>
                    </div>
                    
                    <div class="detection-filename">
                        📄 ${filename}
                    </div>
                    
                    <div class="detection-description">
                        ${detection.description || 'No description available'}
                    </div>
                    
                    <div class="detection-media">
                        ${mediaContent}
                    </div>
                </div>
            `;
        }).join('');
        
        console.log('Cards rendered, container innerHTML length:', container.innerHTML.length);
    }
    
    // Format media cell
    formatMediaCell(detection) {
        if (detection.media_filename) {
            if (detection.media_type === 'image') {
                return `<div class="media-container">
                    <img src="/media/${detection.media_filename}" 
                         alt="Detection" 
                         style="max-width: 1250px; max-height: 1000px; cursor: pointer; border-radius: 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.2);"
                         onclick="window.open('/media/${detection.media_filename}', '_blank')"
                         onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"
                         onload="console.log('Thumbnail loaded: ${detection.media_filename}')">
                    <div style="display: none; padding: 2rem; background: #f8f9fa; border-radius: 12px; font-size: 1.2rem; color: #6c757d; width: 1250px; height: 1000px; display: flex; align-items: center; justify-content: center;">
                        📷 Image unavailable
                    </div>
                </div>`;
            } else if (detection.media_type === 'video') {
                const videoId = `video_${detection.id}`;
                return `
                <div class="video-container" style="display: flex; flex-direction: column; align-items: center; gap: 1.5rem;">
                    <div class="video-thumbnail" style="position: relative;">
                        <img src="/api/video/thumbnail/${detection.id}" 
                             alt="Video thumbnail" 
                             style="width: 1400px; height: 1050px; border-radius: 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.2); object-fit: cover; cursor: pointer;"
                             onclick="convertAndPlay(${detection.id}, '${videoId}')"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"
                             title="Click to play video">
                        <div style="display: none; width: 1400px; height: 1050px; background: #f8f9fa; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; color: #6c757d;">
                            🎬 Video
                        </div>
                        <div style="position: absolute; bottom: 20px; right: 20px; background: rgba(0,0,0,0.8); color: white; padding: 12px 20px; border-radius: 8px; font-size: 1.2rem; font-weight: bold; backdrop-filter: blur(4px);">
                            ▶️ Click to Play
                        </div>
                    </div>
                    <div class="video-controls" style="display: flex; flex-direction: column; align-items: center; gap: 1rem; max-width: 800px;">
                        <video id="${videoId}" width="800" height="600" controls style="display: none; border-radius: 12px; box-shadow: 0 6px 16px rgba(0,0,0,0.2);">
                            <source src="/media/${detection.media_filename}" type="video/mp4">
                            Your browser does not support the video tag.
                        </video>
                        <button onclick="convertAndPlay(${detection.id}, '${videoId}')" 
                                class="convert-btn" 
                                style="padding: 1rem 2rem; background: #007bff; color: white; border: none; border-radius: 8px; cursor: pointer; font-size: 1.2rem; font-weight: 600; box-shadow: 0 4px 8px rgba(0,123,255,0.3); transition: all 0.2s ease;">
                            🎬 Convert & Play Video
                        </button>
                        <div class="video-message" style="background-color: #e7f3ff; padding: 1rem; border-radius: 8px; font-size: 1rem; text-align: center; max-width: 600px;">
                            <p id="msg_${videoId}">
                                <strong>🎬 Smart Video Player</strong><br>
                                <small>Click thumbnail or button to create a browser-friendly version optimized for web playback.</small>
                            </p>
                        </div>
                    </div>
                </div>
            `;
            }
        }
        
        return '<span style="color: #6c757d; font-style: italic; font-size: 1.1rem;">No media</span>';
    }
    
    // Format timestamp
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString();
    }
    
    // Update stats
    updateStats(stats) {
        const todayElement = document.getElementById('todayCount');
        const weekElement = document.getElementById('weekCount');
        const monthElement = document.getElementById('monthCount');
        const totalElement = document.getElementById('totalCount');
        
        if (todayElement) todayElement.textContent = (stats.today || 0).toLocaleString();
        if (weekElement) weekElement.textContent = (stats.week || 0).toLocaleString();
        if (monthElement) monthElement.textContent = (stats.month || 0).toLocaleString();
        if (totalElement) totalElement.textContent = (stats.total || 0).toLocaleString();
    }
    
    // Update pagination
    updatePagination(pagination) {
        const paginationInfo = document.getElementById('paginationInfo');
        const prevBtn = document.getElementById('prevPage');
        const nextBtn = document.getElementById('nextPage');
        
        if (paginationInfo) {
            const start = (pagination.page - 1) * pagination.per_page + 1;
            const end = Math.min(pagination.page * pagination.per_page, pagination.total);
            paginationInfo.textContent = `Showing ${start}-${end} of ${pagination.total} detections`;
        }
        
        if (prevBtn) {
            prevBtn.disabled = pagination.page <= 1;
        }
        
        if (nextBtn) {
            nextBtn.disabled = pagination.page >= pagination.total_pages;
        }
    }
    
    // Set up periodic refresh
    setupPeriodicRefresh() {
        setInterval(async () => {
            if (this.isInitialized && !document.hidden) {
                await this.loadStats();
                await this.updateHeatmap();
            }
        }, 30000); // Refresh every 30 seconds
    }
    
    // Show error message
    showError(message) {
        // Create error notification
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-notification';
        errorDiv.textContent = message;
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #dc3545;
            color: white;
            padding: 1rem;
            border-radius: 4px;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
        `;
        
        document.body.appendChild(errorDiv);
        
        // Remove after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

// Pagination functions
function previousPage() {
    if (window.mainApp && window.mainApp.currentPage > 1) {
        window.mainApp.currentPage--;
        window.mainApp.loadDetections();
    }
}

function nextPage() {
    if (window.mainApp) {
        window.mainApp.currentPage++;
        window.mainApp.loadDetections();
    }
}

// Video conversion function
async function convertAndPlay(detectionId, videoId) {
    const button = event.target;
    const messageElement = document.getElementById(`msg_${videoId}`);
    const videoElement = document.getElementById(videoId);
    
    // Show loading state
    button.disabled = true;
    button.innerHTML = '⏳ Converting...';
    messageElement.innerHTML = '<strong>🔄 Converting Video</strong><br><small>Please wait while we convert your video to a browser-friendly format...</small>';
    
    try {
        const response = await fetch(`/api/video/convert/${detectionId}`);
        const result = await response.json();
        
        if (result.success) {
            messageElement.innerHTML = `
                <strong>✅ Conversion Complete!</strong><br>
                <small>Video converted successfully. File size: ${(result.file_size / 1024 / 1024).toFixed(1)}MB</small>
            `;
            
            // Update video source and show player
            videoElement.src = result.converted_url;
            videoElement.style.display = 'block';
            button.style.display = 'none';
            
            // Auto-play the video
            videoElement.play();
            
        } else {
            messageElement.innerHTML = `
                <strong>❌ Conversion Failed</strong><br>
                <small>Error: ${result.error}</small>
            `;
            button.disabled = false;
            button.innerHTML = '🎬 Convert & Play';
        }
        
    } catch (error) {
        console.error('Error converting video:', error);
        messageElement.innerHTML = `
            <strong>❌ Conversion Error</strong><br>
            <small>Failed to convert video. Please try again.</small>
        `;
        button.disabled = false;
        button.innerHTML = '🎬 Convert & Play';
    }
}

// Initialize the main app when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    window.mainApp = new MainApp();
    // App initialization will happen after components are loaded
}); 