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
            
            // Initialize enhanced heatmap
            this.enhancedHeatmap = new EnhancedHeatmap();
            
            // Initialize camera filter
            await window.cameraFilter.initialize();
            
            // Initialize heatmap with cameras
            const cameras = window.cameraFilter.getAllCameras();
            this.enhancedHeatmap.initializeWithCameras(cameras);
            
            // Load initial data
            await this.loadInitialData();
            
            // Set up periodic refresh
            this.setupPeriodicRefresh();
            
            this.isInitialized = true;
            console.log('Dashboard initialized successfully');
            
        } catch (error) {
            console.error('Error initializing dashboard:', error);
            this.showError('Failed to initialize dashboard. Please refresh the page.');
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
    
    // Load detections table
    async loadDetections() {
        try {
            const options = window.cameraFilter.getFilterOptions();
            const data = await window.detectionAPI.fetchDetections(options);
            
            this.renderDetectionsTable(data);
            this.updatePagination(data.pagination);
            
        } catch (error) {
            console.error('Error loading detections:', error);
            this.showError('Failed to load detections.');
        }
    }
    
    // Update heatmap
    async updateHeatmap() {
        try {
            const selectedCameraIds = window.cameraFilter.getSelectedCameraIds();
            await this.enhancedHeatmap.update(selectedCameraIds);
            
        } catch (error) {
            console.error('Error updating heatmap:', error);
        }
    }
    
    // Load statistics
    async loadStats() {
        try {
            const options = {
                camera_ids: window.cameraFilter.getSelectedCameraIds()
            };
            const data = await window.detectionAPI.fetchStats(options);
            
            this.renderStats(data);
            
        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }
    
    // Render detections table
    renderDetectionsTable(data) {
        const tableBody = document.getElementById('detectionsTableBody');
        if (!tableBody) return;
        
        tableBody.innerHTML = '';
        
        if (!data.detections || data.detections.length === 0) {
            tableBody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 2rem;">No detections found</td></tr>';
            return;
        }
        
        data.detections.forEach(detection => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>
                    <div class="timestamp">${this.formatTimestamp(detection.timestamp)}</div>
                </td>
                <td>
                    <span class="camera-name">${detection.camera_location}</span>
                </td>
                <td>
                    <span class="media-type">${detection.media_type}</span>
                </td>
                <td>
                    <div class="description">${detection.description || 'No description'}</div>
                </td>
                <td>
                    <span class="confidence">${detection.confidence}%</span>
                </td>
                <td>
                    ${this.renderMediaPreview(detection)}
                </td>
            `;
            tableBody.appendChild(row);
        });
    }
    
    // Render media preview
    renderMediaPreview(detection) {
        const baseUrl = window.location.origin;
        
        if (detection.media_type === 'image') {
            return `
                <a href="${baseUrl}/media/${detection.media_filename}" target="_blank" class="image-link">
                    <img src="${baseUrl}/media/${detection.media_filename}" 
                         alt="Detection thumbnail" 
                         class="thumbnail-image"
                         onerror="this.style.display='none'">
                </a>
            `;
        } else if (detection.media_type === 'video') {
            return `
                <div class="video-indicator">
                    <a href="${baseUrl}/media/${detection.media_filename}" target="_blank">
                        📹 Video
                    </a>
                </div>
            `;
        }
        
        return '<span>No media</span>';
    }
    
    // Format timestamp
    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    // Render statistics
    renderStats(data) {
        const stats = data.stats || {};
        
        // Update stat cards
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
            const start = ((pagination.page - 1) * pagination.per_page) + 1;
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
    
    // Refresh all data
    async refreshData() {
        if (!this.isInitialized) return;
        
        await Promise.all([
            this.loadDetections(),
            this.updateHeatmap(),
            this.loadStats()
        ]);
    }
    
    // Set up periodic refresh
    setupPeriodicRefresh() {
        // Refresh data every 30 seconds
        setInterval(async () => {
            try {
                await this.refreshData();
            } catch (error) {
                console.error('Error during periodic refresh:', error);
            }
        }, 30000);
    }
    
    // Show error message
    showError(message) {
        // Create a simple error display
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #e74c3c;
            color: white;
            padding: 1rem;
            border-radius: 4px;
            z-index: 1000;
            max-width: 400px;
        `;
        errorDiv.textContent = message;
        
        document.body.appendChild(errorDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 5000);
    }
    
    // Show success message
    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background-color: #27ae60;
            color: white;
            padding: 1rem;
            border-radius: 4px;
            z-index: 1000;
            max-width: 400px;
        `;
        successDiv.textContent = message;
        
        document.body.appendChild(successDiv);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.parentNode.removeChild(successDiv);
            }
        }, 3000);
    }
    
    // Handle window resize
    handleResize() {
        // Refresh heatmap on resize to ensure proper rendering
        if (this.enhancedHeatmap) {
            this.enhancedHeatmap.renderCurrentView();
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', async () => {
    window.mainApp = new MainApp();
    await window.mainApp.initialize();
});

// Handle window resize
window.addEventListener('resize', () => {
    if (window.mainApp) {
        window.mainApp.handleResize();
    }
});

// Export for debugging
window.MainApp = MainApp; 