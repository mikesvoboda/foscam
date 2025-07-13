/**
 * Camera Filter Module
 * Handles camera selection, filtering, and time navigation
 */

class CameraFilter {
    constructor() {
        this.cameras = [];
        this.selectedCameraIds = [];
        this.currentPage = 1;
        this.currentFilters = {
            start_date: null,
            end_date: null,
            camera_ids: []
        };
        
        this.bindEvents();
    }
    
    bindEvents() {
        // Make functions available globally
        window.applyFilters = () => this.applyFilters();
        window.clearFilters = () => this.clearFilters();
        window.selectAllCameras = () => this.selectAllCameras();
        window.deselectAllCameras = () => this.deselectAllCameras();
        window.searchByDate = () => this.searchByDate();
        window.jumpToDay = (date) => this.jumpToDay(date);
        window.jumpToHour = (hour) => this.jumpToHour(hour);
        window.setQuickFilter = (timeframe) => this.setQuickFilter(timeframe);
        window.previousPage = () => this.previousPage();
        window.nextPage = () => this.nextPage();
    }
    
    // Initialize with cameras data
    async initialize() {
        try {
            const data = await window.detectionAPI.fetchCameras();
            this.cameras = data.cameras || [];
            this.populateCameraSelect();
        } catch (error) {
            console.error('Error loading cameras:', error);
        }
    }
    
    // Populate camera select dropdown
    populateCameraSelect() {
        const select = document.getElementById('cameraSelect');
        if (!select) return;
        
        // Clear existing options
        select.innerHTML = '';
        
        // Add cameras as options
        this.cameras.forEach(camera => {
            const option = document.createElement('option');
            option.value = camera.id;
            option.textContent = camera.location;
            select.appendChild(option);
        });
        
        // Make it multiple select
        select.multiple = true;
        select.size = Math.min(this.cameras.length, 6);
    }
    
    // Apply current filters
    async applyFilters() {
        const select = document.getElementById('cameraSelect');
        const startDate = document.getElementById('startDate');
        const endDate = document.getElementById('endDate');
        
        // Get selected cameras
        if (select) {
            this.selectedCameraIds = Array.from(select.selectedOptions)
                .map(option => parseInt(option.value));
        }
        
        // Get date range
        this.currentFilters = {
            start_date: startDate ? startDate.value : null,
            end_date: endDate ? endDate.value : null,
            camera_ids: this.selectedCameraIds
        };
        
        // Reset to first page
        this.currentPage = 1;
        
        // Update displays
        this.updateSelectedCamerasDisplay();
        
        // Trigger data refresh
        if (window.mainApp) {
            await window.mainApp.refreshData();
        }
    }
    
    // Clear all filters
    async clearFilters() {
        const select = document.getElementById('cameraSelect');
        const startDate = document.getElementById('startDate');
        const endDate = document.getElementById('endDate');
        
        // Clear selections
        if (select) {
            select.selectedIndex = -1;
        }
        if (startDate) startDate.value = '';
        if (endDate) endDate.value = '';
        
        // Reset state
        this.selectedCameraIds = [];
        this.currentFilters = {
            start_date: null,
            end_date: null,
            camera_ids: []
        };
        this.currentPage = 1;
        
        // Update displays
        this.updateSelectedCamerasDisplay();
        this.clearActiveQuickFilters();
        
        // Trigger data refresh
        if (window.mainApp) {
            await window.mainApp.refreshData();
        }
    }
    
    // Select all cameras
    selectAllCameras() {
        const select = document.getElementById('cameraSelect');
        if (!select) return;
        
        for (let i = 0; i < select.options.length; i++) {
            select.options[i].selected = true;
        }
        
        this.applyFilters();
    }
    
    // Deselect all cameras
    deselectAllCameras() {
        const select = document.getElementById('cameraSelect');
        if (!select) return;
        
        select.selectedIndex = -1;
        this.applyFilters();
    }
    
    // Update selected cameras display
    updateSelectedCamerasDisplay() {
        const container = document.getElementById('selectedCameras');
        if (!container) return;
        
        if (this.selectedCameraIds.length === 0) {
            container.innerHTML = '<div class="selected-cameras-label">All cameras selected</div>';
            return;
        }
        
        let html = '<div class="selected-cameras-label">Selected cameras:</div>';
        
        this.selectedCameraIds.forEach(cameraId => {
            const camera = this.cameras.find(c => c.id === cameraId);
            if (camera) {
                html += `<span class="camera-tag">
                    ${camera.location}
                    <span class="remove" onclick="window.cameraFilter.removeCameraFilter(${cameraId})">×</span>
                </span>`;
            }
        });
        
        container.innerHTML = html;
    }
    
    // Remove a specific camera from filter
    removeCameraFilter(cameraId) {
        this.selectedCameraIds = this.selectedCameraIds.filter(id => id !== cameraId);
        
        // Update select element
        const select = document.getElementById('cameraSelect');
        if (select) {
            const option = select.querySelector(`option[value="${cameraId}"]`);
            if (option) {
                option.selected = false;
            }
        }
        
        this.applyFilters();
    }
    
    // Search by date range
    searchByDate() {
        this.applyFilters();
    }
    
    // Jump to a specific day
    jumpToDay(date) {
        const startDate = document.getElementById('startDate');
        const endDate = document.getElementById('endDate');
        
        if (startDate && endDate) {
            const dateStr = date.toISOString().split('T')[0];
            startDate.value = dateStr;
            endDate.value = dateStr;
            this.searchByDate();
        }
    }
    
    // Jump to a specific hour (for today)
    jumpToHour(hour) {
        const today = new Date();
        const startDate = document.getElementById('startDate');
        const endDate = document.getElementById('endDate');
        
        if (startDate && endDate) {
            const dateStr = today.toISOString().split('T')[0];
            startDate.value = dateStr;
            endDate.value = dateStr;
            this.searchByDate();
        }
    }
    
    // Set quick filter (last 24h, 7d, 30d, etc.)
    setQuickFilter(timeframe) {
        const now = new Date();
        const startDate = document.getElementById('startDate');
        const endDate = document.getElementById('endDate');
        
        if (!startDate || !endDate) return;
        
        let startTime = new Date(now);
        
        switch (timeframe) {
            case '24h':
                startTime.setHours(now.getHours() - 24);
                break;
            case '7d':
                startTime.setDate(now.getDate() - 7);
                break;
            case '30d':
                startTime.setDate(now.getDate() - 30);
                break;
            case '90d':
                startTime.setDate(now.getDate() - 90);
                break;
            default:
                return;
        }
        
        startDate.value = startTime.toISOString().split('T')[0];
        endDate.value = now.toISOString().split('T')[0];
        
        // Update active button
        this.setActiveQuickFilter(timeframe);
        
        this.searchByDate();
    }
    
    // Set active quick filter button
    setActiveQuickFilter(timeframe) {
        const buttons = document.querySelectorAll('.quick-filter-btn');
        buttons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.dataset.timeframe === timeframe) {
                btn.classList.add('active');
            }
        });
    }
    
    // Clear active quick filter buttons
    clearActiveQuickFilters() {
        const buttons = document.querySelectorAll('.quick-filter-btn');
        buttons.forEach(btn => btn.classList.remove('active'));
    }
    
    // Pagination
    async previousPage() {
        if (this.currentPage > 1) {
            this.currentPage--;
            if (window.mainApp) {
                await window.mainApp.loadDetections();
            }
        }
    }
    
    async nextPage() {
        this.currentPage++;
        if (window.mainApp) {
            await window.mainApp.loadDetections();
        }
    }
    
    // Get current filter options
    getFilterOptions() {
        return {
            page: this.currentPage,
            per_page: 50,
            start_date: this.currentFilters.start_date,
            end_date: this.currentFilters.end_date,
            camera_ids: this.selectedCameraIds
        };
    }
    
    // Get selected cameras for heatmap
    getSelectedCameraIds() {
        return this.selectedCameraIds;
    }
    
    // Get all cameras
    getAllCameras() {
        return this.cameras;
    }
}

// Export singleton instance
window.cameraFilter = new CameraFilter(); 