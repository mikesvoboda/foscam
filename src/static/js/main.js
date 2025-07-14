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
            const fileTimestamp = detection.file_timestamp ? this.formatTimestamp(detection.file_timestamp) : 'N/A';
            const mediaContent = this.formatMediaCell(detection);
            
            // Extract filename from media_filename path
            const filename = detection.media_filename ? 
                detection.media_filename.split('/').pop() : 'No filename';
            
            // Format alert flags
            const alertFlags = this.formatAlertFlags(detection);
            
            // Format media info
            const mediaInfo = this.formatMediaInfo(detection);
            
            // Format processing info
            const processingInfo = this.formatProcessingInfo(detection);
            
            return `
                <div class="detection-card">
                    <div class="detection-header">
                        <div class="detection-timestamp">
                            <strong>Processed:</strong> ${timestamp}
                            <br><strong>File Date:</strong> ${fileTimestamp}
                        </div>
                        <div class="detection-camera">
                            <strong>Camera:</strong> ${detection.camera_location}
                            <br><strong>ID:</strong> ${detection.id}
                        </div>
                    </div>
                    
                    <div class="detection-filename">
                        📄 ${filename}
                        <span style="color: #666; font-size: 0.9rem; margin-left: 10px;">
                            (${detection.media_type.toUpperCase()})
                        </span>
                    </div>
                    
                    <div class="detection-metadata" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 1rem 0; padding: 1rem; background: #f8f9fa; border-radius: 8px;">
                        <div>
                            ${processingInfo}
                        </div>
                        <div>
                            ${mediaInfo}
                        </div>
                    </div>
                    
                    ${alertFlags}
                    
                    <div class="detection-description" style="margin: 1rem 0; padding: 1rem; background: #e8f4f8; border-radius: 8px;">
                        <strong>Description:</strong><br>
                        ${this.formatTimelineAnalysis(detection.description) || 'No description available'}
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

    // Format alert flags
    formatAlertFlags(detection) {
        const alerts = [];
        if (detection.has_person) alerts.push('👤 Person');
        if (detection.has_vehicle) alerts.push('🚗 Vehicle');
        if (detection.has_package) alerts.push('📦 Package');
        if (detection.has_unusual_activity) alerts.push('⚠️ Unusual Activity');
        if (detection.is_night_time) alerts.push('🌙 Night Time');
        
        if (alerts.length === 0 && detection.alert_count > 0) {
            alerts.push(`🔔 ${detection.alert_count} Alert${detection.alert_count !== 1 ? 's' : ''}`);
        }
        
        if (alerts.length === 0) {
            return '<div style="color: #666; font-style: italic; margin: 1rem 0;">No alerts detected</div>';
        }
        
        return `
            <div class="detection-alerts" style="margin: 1rem 0; padding: 1rem; background: #fff3cd; border-radius: 8px;">
                <strong>Alerts (${detection.alert_count || alerts.length}):</strong>
                <div style="display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.5rem;">
                    ${alerts.map(alert => `<span style="background: #ffc107; color: #212529; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.9rem;">${alert}</span>`).join('')}
                </div>
            </div>
        `;
    }
    
    // Format media info
    formatMediaInfo(detection) {
        let info = [];
        
        if (detection.width && detection.height) {
            info.push(`📏 <strong>Dimensions:</strong> ${detection.width}×${detection.height}`);
        }
        
        if (detection.duration) {
            info.push(`⏱️ <strong>Duration:</strong> ${detection.duration.toFixed(1)}s`);
        }
        
        if (detection.frame_count) {
            info.push(`🎞️ <strong>Frames:</strong> ${detection.frame_count}`);
        }
        
        if (detection.motion_detection_type) {
            info.push(`🚀 <strong>Motion Type:</strong> ${detection.motion_detection_type}`);
        }
        
        return info.length > 0 ? info.join('<br>') : '<span style="color: #666; font-style: italic;">No media info</span>';
    }
    
    // Format processing info
    formatProcessingInfo(detection) {
        let info = [];
        
        if (detection.confidence !== null && detection.confidence !== undefined) {
            const confidencePercent = (detection.confidence * 100).toFixed(1);
            const confidenceColor = detection.confidence > 0.8 ? '#28a745' : detection.confidence > 0.6 ? '#ffc107' : '#dc3545';
            info.push(`🎯 <strong>Confidence:</strong> <span style="color: ${confidenceColor}; font-weight: bold;">${confidencePercent}%</span>`);
        }
        
        if (detection.processing_time) {
            info.push(`⚡ <strong>Processing Time:</strong> ${detection.processing_time.toFixed(3)}s`);
        }
        
        const statusColor = detection.processed ? '#28a745' : '#dc3545';
        const statusText = detection.processed ? '✅ Processed' : '❌ Not Processed';
        info.push(`📊 <strong>Status:</strong> <span style="color: ${statusColor}; font-weight: bold;">${statusText}</span>`);
        
        return info.length > 0 ? info.join('<br>') : '<span style="color: #666; font-style: italic;">No processing info</span>';
    }

    // Format timeline analysis for video descriptions
    formatTimelineAnalysis(description) {
        if (!description || typeof description !== 'string') {
            return description;
        }
        
        // Check if this is a timeline-based analysis
        if (description.includes('TIMELINE ANALYSIS') || description.includes('EVENTS:')) {
            return this.formatTimelineDescription(description);
        }
        
        // Check for old format repetitive descriptions
        if (description.includes('VIDEO ANALYSIS') && description.includes('ACTIVITIES:')) {
            return this.formatLegacyVideoDescription(description);
        }
        
        return description;
    }
    
    // Format new timeline-based descriptions
    formatTimelineDescription(description) {
        try {
            const sections = description.split(' | ');
            let formatted = '<div class="timeline-analysis">';
            
            for (let section of sections) {
                if (section.startsWith('TIMELINE ANALYSIS')) {
                    formatted += `<div class="timeline-header"><strong>📅 ${section}</strong></div>`;
                } else if (section.startsWith('EVENTS:')) {
                    const eventsText = section.replace('EVENTS:', '').trim();
                    const events = eventsText.split(' | ');
                    
                    formatted += '<div class="timeline-events"><strong>🎬 Timeline Events:</strong>';
                    formatted += '<div class="timeline-list">';
                    
                    for (let event of events) {
                        if (event.trim()) {
                            // Extract timestamp and description
                            const timestampMatch = event.match(/^(\d{2}:\d{2}):\s*(.+)$/);
                            if (timestampMatch) {
                                const [, timestamp, eventDesc] = timestampMatch;
                                formatted += `<div class="timeline-event">
                                    <span class="timestamp">${timestamp}</span>
                                    <span class="event-desc">${eventDesc}</span>
                                </div>`;
                            } else {
                                formatted += `<div class="timeline-event"><span class="event-desc">${event}</span></div>`;
                            }
                        }
                    }
                    formatted += '</div></div>';
                } else if (section.startsWith('EVENT TYPES:')) {
                    const eventTypes = section.replace('EVENT TYPES:', '').trim();
                    formatted += `<div class="event-types"><strong>📋 Event Types:</strong> ${eventTypes}</div>`;
                } else if (section.startsWith('ALERTS:')) {
                    const alerts = section.replace('ALERTS:', '').trim();
                    formatted += `<div class="timeline-alerts"><strong>🔔 Alerts:</strong> ${alerts}</div>`;
                } else if (section.trim()) {
                    formatted += `<div class="timeline-section">${section}</div>`;
                }
            }
            
            formatted += '</div>';
            
            // Add timeline-specific CSS
            if (!document.getElementById('timeline-css')) {
                const style = document.createElement('style');
                style.id = 'timeline-css';
                style.textContent = `
                    .timeline-analysis {
                        background: #f8f9fa;
                        border-radius: 8px;
                        padding: 1rem;
                        margin: 0.5rem 0;
                    }
                    .timeline-header {
                        color: #495057;
                        margin-bottom: 1rem;
                        font-size: 1.1rem;
                    }
                    .timeline-events {
                        margin: 1rem 0;
                    }
                    .timeline-list {
                        margin-top: 0.5rem;
                        border-left: 3px solid #007bff;
                        padding-left: 1rem;
                    }
                    .timeline-event {
                        display: flex;
                        align-items: flex-start;
                        margin: 0.5rem 0;
                        padding: 0.5rem;
                        background: white;
                        border-radius: 4px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }
                    .timestamp {
                        background: #007bff;
                        color: white;
                        padding: 0.2rem 0.5rem;
                        border-radius: 4px;
                        font-family: monospace;
                        font-weight: bold;
                        margin-right: 0.5rem;
                        min-width: 50px;
                        text-align: center;
                    }
                    .event-desc {
                        flex: 1;
                        color: #495057;
                    }
                    .event-types, .timeline-alerts {
                        margin: 0.5rem 0;
                        padding: 0.5rem;
                        background: #e9ecef;
                        border-radius: 4px;
                    }
                    .timeline-section {
                        margin: 0.5rem 0;
                        color: #6c757d;
                    }
                `;
                document.head.appendChild(style);
            }
            
            return formatted;
        } catch (error) {
            console.error('Error formatting timeline description:', error);
            return description;
        }
    }
    
    // Format legacy video descriptions (for backward compatibility)
    formatLegacyVideoDescription(description) {
        try {
            const sections = description.split(' | ');
            let formatted = '<div class="legacy-video-analysis">';
            
            for (let section of sections) {
                if (section.startsWith('VIDEO ANALYSIS')) {
                    formatted += `<div class="video-header"><strong>📹 ${section}</strong></div>`;
                } else if (section.startsWith('ACTIVITIES:')) {
                    const activities = section.replace('ACTIVITIES:', '').trim();
                    // Clean up repetitive activities but don't limit the count
                    const activityList = activities.split(', ');
                    const uniqueActivities = [...new Set(activityList)];
                    
                    // Group similar activities
                    const cleanedActivities = this.cleanupRepetitiveActivities(uniqueActivities);
                    
                    formatted += `<div class="activities-section">
                        <strong>🎬 Key Activities:</strong><br>
                        <div class="activity-list">
                            ${cleanedActivities.map(activity => `<div class="activity-item">• ${activity}</div>`).join('')}
                        </div>
                    </div>`;
                } else if (section.startsWith('ENVIRONMENT:')) {
                    const environment = section.replace('ENVIRONMENT:', '').trim();
                    const uniqueEnv = [...new Set(environment.split(', '))];
                    const cleanedEnv = uniqueEnv.filter(env => env.length > 3); // Remove very short fragments
                    formatted += `<div class="environment-section">
                        <strong>🌍 Environment:</strong> ${cleanedEnv.join(', ')}
                    </div>`;
                } else if (section.startsWith('MAIN SCENE:')) {
                    const mainScene = section.replace('MAIN SCENE:', '').trim();
                    formatted += `<div class="main-scene-section">
                        <strong>🎯 Main Scene:</strong> ${mainScene}
                    </div>`;
                } else if (section.startsWith('ALERTS:')) {
                    const alerts = section.replace('ALERTS:', '').trim();
                    formatted += `<div class="alerts-section">
                        <strong>🔔 Alerts:</strong> ${alerts}
                    </div>`;
                }
            }
            
            formatted += '</div>';
            
            // Add improved styling for legacy descriptions
            if (!document.getElementById('legacy-analysis-css')) {
                const style = document.createElement('style');
                style.id = 'legacy-analysis-css';
                style.textContent = `
                    .legacy-video-analysis {
                        background: #f8f9fa;
                        border-radius: 8px;
                        padding: 1rem;
                        margin: 0.5rem 0;
                    }
                    .activity-list {
                        max-height: 200px;
                        overflow-y: auto;
                        margin-top: 0.5rem;
                        padding: 0.5rem;
                        background: white;
                        border-radius: 4px;
                        border: 1px solid #dee2e6;
                    }
                    .activity-item {
                        margin: 0.2rem 0;
                        color: #495057;
                        line-height: 1.4;
                    }
                    .video-header {
                        color: #495057;
                        margin-bottom: 1rem;
                        font-size: 1.1rem;
                    }
                    .activities-section, .environment-section, .main-scene-section, .alerts-section {
                        margin: 1rem 0;
                        padding: 0.5rem;
                        background: #e9ecef;
                        border-radius: 4px;
                    }
                `;
                document.head.appendChild(style);
            }
            
            return formatted;
        } catch (error) {
            console.error('Error formatting legacy video description:', error);
            return description;
        }
    }
    
    // Clean up repetitive activities while keeping meaningful content
    cleanupRepetitiveActivities(activities) {
        // Group activities by similar patterns
        const patterns = {
            'camera_views': [],
            'house_views': [],
            'vehicle_activity': [],
            'person_activity': [],
            'general': []
        };
        
        for (let activity of activities) {
            const activityLower = activity.toLowerCase();
            if (activityLower.includes('camera') && (activityLower.includes('view') || activityLower.includes('captures'))) {
                patterns.camera_views.push(activity);
            } else if (activityLower.includes('house') || activityLower.includes('building')) {
                patterns.house_views.push(activity);
            } else if (activityLower.includes('car') || activityLower.includes('vehicle') || activityLower.includes('driving')) {
                patterns.vehicle_activity.push(activity);
            } else if (activityLower.includes('person') || activityLower.includes('man') || activityLower.includes('woman')) {
                patterns.person_activity.push(activity);
            } else {
                patterns.general.push(activity);
            }
        }
        
        let cleanedActivities = [];
        
        // Add summary for camera views if many
        if (patterns.camera_views.length > 0) {
            if (patterns.camera_views.length > 3) {
                cleanedActivities.push(`Camera captures multiple views of the scene (${patterns.camera_views.length} different angles)`);
            } else {
                cleanedActivities.push(...patterns.camera_views.slice(0, 2));
            }
        }
        
        // Add house/building views
        if (patterns.house_views.length > 0) {
            cleanedActivities.push(...patterns.house_views.slice(0, 2));
        }
        
        // Add vehicle activities
        if (patterns.vehicle_activity.length > 0) {
            cleanedActivities.push(...patterns.vehicle_activity);
        }
        
        // Add person activities
        if (patterns.person_activity.length > 0) {
            cleanedActivities.push(...patterns.person_activity);
        }
        
        // Add general activities
        if (patterns.general.length > 0) {
            cleanedActivities.push(...patterns.general);
        }
        
        return cleanedActivities.length > 0 ? cleanedActivities : activities;
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