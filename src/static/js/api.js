/**
 * API Module
 * Centralized API calls for the detection dashboard
 */

class DetectionAPI {
    constructor() {
        this.baseUrl = '';
    }
    
    // Fetch detections with pagination and filtering
    async fetchDetections(options = {}) {
        const params = new URLSearchParams();
        
        if (options.page) params.append('page', options.page);
        if (options.per_page) params.append('per_page', options.per_page);
        if (options.start_date) params.append('start_date', options.start_date);
        if (options.end_date) params.append('end_date', options.end_date);
        if (options.camera_ids && options.camera_ids.length > 0) {
            params.append('camera_ids', options.camera_ids.join(','));
        }
        
        const url = `/api/detections?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // Fetch cameras list
    async fetchCameras() {
        const response = await fetch('/api/cameras');
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // Fetch daily heatmap data
    async fetchDailyHeatmap(options = {}) {
        const params = new URLSearchParams();
        
        params.append('days', options.days || '30');
        params.append('resolution', 'day');
        params.append('per_camera', options.per_camera || 'false');
        
        if (options.camera_ids && options.camera_ids.length > 0) {
            params.append('camera_ids', options.camera_ids.join(','));
        }
        
        const url = `/api/detections/heatmap?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // Fetch hourly heatmap data
    async fetchHourlyHeatmap(options = {}) {
        const params = new URLSearchParams();
        
        params.append('per_camera', options.per_camera || 'false');
        
        if (options.camera_ids && options.camera_ids.length > 0) {
            params.append('camera_ids', options.camera_ids.join(','));
        }
        
        const url = `/api/detections/heatmap-hourly?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // Fetch detection statistics
    async fetchStats(options = {}) {
        const params = new URLSearchParams();
        
        if (options.camera_ids && options.camera_ids.length > 0) {
            params.append('camera_ids', options.camera_ids.join(','));
        }
        
        const url = `/api/detections/stats?${params.toString()}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // Update detection (for any edit operations)
    async updateDetection(id, data) {
        const response = await fetch(`/api/detections/${id}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.json();
    }
    
    // Delete detection
    async deleteDetection(id) {
        const response = await fetch(`/api/detections/${id}`, {
            method: 'DELETE',
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        return response.ok;
    }
    
    // Helper method to build query parameters
    buildQueryParams(params) {
        return Object.entries(params)
            .filter(([_, value]) => value !== undefined && value !== null && value !== '')
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
            .join('&');
    }
    
    // Handle API errors consistently
    handleError(error) {
        console.error('API Error:', error);
        
        if (error.response) {
            // Server responded with error status
            return {
                success: false,
                message: `Server error: ${error.response.status}`,
                data: null
            };
        } else if (error.request) {
            // Request was made but no response received
            return {
                success: false,
                message: 'Network error: No response from server',
                data: null
            };
        } else {
            // Something else happened
            return {
                success: false,
                message: `Error: ${error.message}`,
                data: null
            };
        }
    }
}

// Export singleton instance
window.detectionAPI = new DetectionAPI(); 