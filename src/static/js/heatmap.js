/**
 * Enhanced Heatmap Module
 * Handles dynamic camera colors, dual-view heatmap (30-day & 24-hour), and per-camera breakdown
 */

class EnhancedHeatmap {
    constructor() {
        // Heatmap state
        this.currentView = 'daily'; // 'daily' or 'hourly'
        this.showPerCamera = false;
        this.data = { daily: null, hourly: null };
        this.cameraColorMap = new Map();
        
        // Color palette for dynamic assignment
        this.colorPalette = [
            '#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c',
            '#34495e', '#e67e22', '#95a5a6', '#16a085', '#27ae60', '#2980b9',
            '#8e44ad', '#f1c40f', '#e8c07a', '#d35400', '#c0392b', '#7f8c8d',
            '#2c3e50', '#bdc3c7', '#ecf0f1', '#f7dc6f', '#bb8fce', '#85c1e9',
            '#f8d7da', '#d1ecf1', '#d4edda', '#fff3cd', '#f4cccc', '#cce5ff'
        ];
        
        this.bindEvents();
    }
    
    bindEvents() {
        // Make sure functions are available globally for onclick handlers
        window.switchToDaily = () => this.switchToDaily();
        window.switchToHourly = () => this.switchToHourly();
        window.toggleCameraBreakdown = () => this.toggleCameraBreakdown();
    }
    
    // Generate dynamic colors for cameras
    generateCameraColors(cameras) {
        cameras.forEach((camera, index) => {
            const color = this.colorPalette[index % this.colorPalette.length];
            this.cameraColorMap.set(camera.location, color);
        });
    }
    
    // Apply dynamic colors to heatmap squares
    applyDynamicColors() {
        const style = document.createElement('style');
        style.id = 'dynamic-camera-colors';
        
        // Remove existing dynamic styles
        const existingStyle = document.getElementById('dynamic-camera-colors');
        if (existingStyle) {
            existingStyle.remove();
        }
        
        let cssRules = '';
        
        // Generate CSS for each camera
        for (const [location, color] of this.cameraColorMap) {
            const rgb = this.hexToRgb(color);
            if (rgb) {
                cssRules += `
                    .heatmap-square.camera-${location}.level-1 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.3) !important; }
                    .heatmap-square.camera-${location}.level-2 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.5) !important; }
                    .heatmap-square.camera-${location}.level-3 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.7) !important; }
                    .heatmap-square.camera-${location}.level-4 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.9) !important; }
                    
                    .hourly-square.camera-${location}.level-1 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.3) !important; }
                    .hourly-square.camera-${location}.level-2 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.5) !important; }
                    .hourly-square.camera-${location}.level-3 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.7) !important; }
                    .hourly-square.camera-${location}.level-4 { background-color: rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.9) !important; }
                `;
            }
        }
        
        style.textContent = cssRules;
        document.head.appendChild(style);
    }
    
    // Convert hex to RGB
    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16)
        } : null;
    }
    
    // Create dynamic camera legends
    createCameraLegends() {
        const legendsDiv = document.getElementById('cameraLegends');
        if (!legendsDiv) return;
        
        legendsDiv.innerHTML = '';
        
        for (const [location, color] of this.cameraColorMap) {
            const legendItem = document.createElement('div');
            legendItem.className = 'legend-item';
            
            const colorBox = document.createElement('div');
            colorBox.className = 'legend-color';
            colorBox.style.backgroundColor = color;
            
            const locationName = document.createElement('span');
            locationName.className = 'legend-name';
            locationName.textContent = location.charAt(0).toUpperCase() + location.slice(1);
            
            legendItem.appendChild(colorBox);
            legendItem.appendChild(locationName);
            legendsDiv.appendChild(legendItem);
        }
    }
    
    // Main update function
    async update(selectedCameraIds = []) {
        try {
            // Load both daily and hourly data
            await Promise.all([
                this.loadDailyData(selectedCameraIds),
                this.loadHourlyData(selectedCameraIds)
            ]);
            
            // Render current view
            this.renderCurrentView();
            
        } catch (error) {
            console.error('Error updating heatmap:', error);
        }
    }
    
    // Load daily heatmap data (30 days)
    async loadDailyData(selectedCameraIds = []) {
        let url = `/api/detections/heatmap?days=30&resolution=day&per_camera=${this.showPerCamera}`;
        
        if (selectedCameraIds.length > 0) {
            url += `&camera_ids=${selectedCameraIds.join(',')}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        this.data.daily = data;
    }
    
    // Load hourly heatmap data (24 hours)
    async loadHourlyData(selectedCameraIds = []) {
        let url = `/api/detections/heatmap-hourly?per_camera=${this.showPerCamera}`;
        
        if (selectedCameraIds.length > 0) {
            url += `&camera_ids=${selectedCameraIds.join(',')}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        this.data.hourly = data;
    }
    
    // Render current heatmap view
    renderCurrentView() {
        const dailyElement = document.getElementById('dailyHeatmap');
        const hourlyElement = document.getElementById('hourlyHeatmap');
        
        if (this.currentView === 'daily') {
            if (dailyElement) dailyElement.style.display = 'block';
            if (hourlyElement) hourlyElement.style.display = 'none';
            this.createDailyHeatmap(this.data.daily);
        } else {
            if (dailyElement) dailyElement.style.display = 'none';
            if (hourlyElement) hourlyElement.style.display = 'block';
            this.createHourlyHeatmap(this.data.hourly);
        }
        
        // Show/hide camera legends
        const legendsElement = document.getElementById('cameraLegends');
        if (legendsElement) {
            legendsElement.style.display = this.showPerCamera ? 'flex' : 'none';
        }
        
        // Update stats label
        const labelElement = document.getElementById('totalActivityLabel');
        if (labelElement) {
            const label = this.currentView === 'daily' ? 'detections in the last 30 days' : 'detections in the last 24 hours';
            labelElement.textContent = label;
        }
    }
    
    // Create daily calendar heatmap (30 days)
    createDailyHeatmap(data) {
        const grid = document.getElementById('dailyHeatmapGrid');
        const monthLabels = document.getElementById('monthLabels');
        
        if (!grid) return;
        
        // Clear existing content
        grid.innerHTML = '';
        if (monthLabels) monthLabels.innerHTML = '';
        
        if (!data || !data.heatmap_data) return;
        
        // Create a map of dates to counts
        const dataMap = {};
        let totalActivity = 0;
        let maxCount = 0;
        let peakDay = { count: 0, date: null };
        
        data.heatmap_data.forEach(item => {
            const date = item.timestamp;
            dataMap[date] = item;
            totalActivity += item.count;
            if (item.count > maxCount) {
                maxCount = item.count;
            }
            if (item.count > peakDay.count) {
                peakDay = { count: item.count, date: new Date(item.timestamp) };
            }
        });
        
        // Update statistics
        this.updateStats(totalActivity, peakDay.count, peakDay.date);
        
        // Calculate start date (30 days ago)
        const today = new Date();
        const startDate = new Date(today);
        startDate.setDate(today.getDate() - 29);
        
        // Generate calendar squares
        for (let i = 0; i < 30; i++) {
            const date = new Date(startDate);
            date.setDate(startDate.getDate() + i);
            
            const square = document.createElement('div');
            square.className = 'heatmap-square';
            
            const dateKey = date.toISOString().split('T')[0];
            const item = dataMap[dateKey];
            const count = item ? item.count : 0;
            
            // Calculate activity level (0-4)
            const level = this.calculateLevel(count, maxCount);
            square.classList.add(`level-${level}`);
            
            // Add camera-specific styling if per-camera mode
            if (this.showPerCamera && item && item.camera_breakdown) {
                const dominantCamera = this.getDominantCamera(item.camera_breakdown);
                if (dominantCamera) {
                    square.classList.add(`camera-${dominantCamera}`);
                }
            }
            
            // Create tooltip
            const tooltip = this.createTooltip(count, date.toLocaleDateString(), item, 'date');
            square.title = tooltip;
            
            // Add click handler
            square.addEventListener('click', () => {
                if (window.jumpToDay) window.jumpToDay(date);
            });
            
            grid.appendChild(square);
        }
    }
    
    // Create hourly heatmap (24 hours)
    createHourlyHeatmap(data) {
        const grid = document.getElementById('hourlyHeatmapGrid');
        
        if (!grid) return;
        grid.innerHTML = '';
        
        if (!data || !data.heatmap_data) return;
        
        // Create a map of hours to counts
        const dataMap = {};
        let totalActivity = 0;
        let maxCount = 0;
        let peakHour = { count: 0, hour: null };
        
        data.heatmap_data.forEach(item => {
            const hour = item.hour;
            dataMap[hour] = item;
            totalActivity += item.count;
            if (item.count > maxCount) {
                maxCount = item.count;
            }
            if (item.count > peakHour.count) {
                peakHour = { count: item.count, hour: hour };
            }
        });
        
        // Update statistics
        const peakTime = peakHour.hour !== null ? `${peakHour.hour}:00` : '';
        this.updateStats(totalActivity, peakHour.count, peakTime);
        
        // Generate hourly squares
        for (let hour = 0; hour < 24; hour++) {
            const item = dataMap[hour];
            const count = item ? item.count : 0;
            
            const square = document.createElement('div');
            square.className = 'hourly-square';
            
            // Calculate activity level (0-4)
            const level = this.calculateLevel(count, maxCount);
            square.classList.add(`level-${level}`);
            
            // Add camera-specific styling if per-camera mode
            if (this.showPerCamera && item && item.camera_breakdown) {
                const dominantCamera = this.getDominantCamera(item.camera_breakdown);
                if (dominantCamera) {
                    square.classList.add(`camera-${dominantCamera}`);
                }
            }
            
            // Create tooltip
            const tooltip = this.createTooltip(count, `${hour}:00`, item, 'hour');
            square.title = tooltip;
            
            // Add click handler
            square.addEventListener('click', () => {
                if (window.jumpToHour) window.jumpToHour(hour);
            });
            
            grid.appendChild(square);
        }
    }
    
    // Calculate activity level (0-4)
    calculateLevel(count, maxCount) {
        let level = 0;
        if (count > 0) {
            if (maxCount <= 4) {
                level = Math.min(count, 4);
            } else {
                const percentage = count / maxCount;
                if (percentage <= 0.25) level = 1;
                else if (percentage <= 0.5) level = 2;
                else if (percentage <= 0.75) level = 3;
                else level = 4;
            }
        }
        return level;
    }
    
    // Create tooltip text
    createTooltip(count, timeText, item, timeType) {
        let tooltip = `${count} detection${count !== 1 ? 's' : ''} ${timeType === 'hour' ? 'at' : 'on'} ${timeText}`;
        if (this.showPerCamera && item && item.camera_breakdown) {
            tooltip += '\n' + Object.entries(item.camera_breakdown)
                .map(([camera, count]) => `${camera}: ${count}`)
                .join('\n');
        }
        return tooltip;
    }
    
    // Get dominant camera for styling
    getDominantCamera(cameraBreakdown) {
        let maxCount = 0;
        let dominantCamera = null;
        
        Object.entries(cameraBreakdown).forEach(([camera, count]) => {
            if (count > maxCount) {
                maxCount = count;
                dominantCamera = camera;
            }
        });
        
        return dominantCamera;
    }
    
    // Update statistics display
    updateStats(totalActivity, peakCount, peakTime) {
        const totalElement = document.getElementById('totalActivity');
        const peakElement = document.getElementById('peakActivity');
        const dateElement = document.getElementById('peakDate');
        
        if (totalElement) totalElement.textContent = totalActivity.toLocaleString();
        if (peakElement) peakElement.textContent = peakCount;
        if (dateElement) {
            if (peakTime instanceof Date) {
                dateElement.textContent = peakTime.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            } else {
                dateElement.textContent = peakTime;
            }
        }
    }
    
    // Switch to daily view
    switchToDaily() {
        this.currentView = 'daily';
        const dailyBtn = document.getElementById('dailyViewBtn');
        const hourlyBtn = document.getElementById('hourlyViewBtn');
        
        if (dailyBtn) dailyBtn.classList.add('active');
        if (hourlyBtn) hourlyBtn.classList.remove('active');
        
        this.renderCurrentView();
    }
    
    // Switch to hourly view
    switchToHourly() {
        this.currentView = 'hourly';
        const dailyBtn = document.getElementById('dailyViewBtn');
        const hourlyBtn = document.getElementById('hourlyViewBtn');
        
        if (dailyBtn) dailyBtn.classList.remove('active');
        if (hourlyBtn) hourlyBtn.classList.add('active');
        
        this.renderCurrentView();
    }
    
    // Toggle camera breakdown
    toggleCameraBreakdown() {
        const toggle = document.getElementById('perCameraToggle');
        if (toggle) {
            this.showPerCamera = toggle.checked;
            // Trigger update via main app if available
            if (window.mainApp && window.mainApp.updateHeatmap) {
                window.mainApp.updateHeatmap();
            }
        }
    }
    
    // Initialize with cameras
    initializeWithCameras(cameras) {
        this.generateCameraColors(cameras);
        this.applyDynamicColors();
        this.createCameraLegends();
    }
}

// Export for use in other modules
window.EnhancedHeatmap = EnhancedHeatmap; 