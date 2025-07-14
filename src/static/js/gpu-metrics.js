/**
 * GPU Metrics Module
 * Handles real-time GPU monitoring with charts and status updates
 */

class GPUMetrics {
    constructor() {
        this.isInitialized = false;
        this.isPaused = false;
        this.charts = {};
        this.updateInterval = null;
        this.currentData = null;
        this.historyData = [];
        this.maxDataPoints = 300; // 5 minutes at 1 second intervals
        
        // Chart colors
        this.colors = {
            primary: '#007bff',
            success: '#28a745',
            warning: '#ffc107',
            danger: '#dc3545',
            info: '#17a2b8',
            secondary: '#6c757d'
        };
    }

    // Initialize GPU metrics monitoring
    async initialize() {
        try {
            console.log('Initializing GPU metrics...');
            
            // Initialize charts
            this.initializeCharts();
            
            // Load initial data
            await this.loadInitialData();
            
            // Set up event listeners
            this.setupEventListeners();
            
            // Start periodic updates
            this.startUpdates();
            
            this.isInitialized = true;
            console.log('GPU metrics initialized successfully');
            
        } catch (error) {
            console.error('Error initializing GPU metrics:', error);
            this.showError('Failed to initialize GPU monitoring');
        }
    }

    // Initialize all charts
    initializeCharts() {
        // GPU Utilization Chart
        this.charts.utilization = this.createChart('gpuUtilizationChart', {
            label: 'GPU Usage (%)',
            color: this.colors.primary,
            max: 100
        });

        // Memory Usage Chart
        this.charts.memory = this.createChart('memoryUsageChart', {
            label: 'Memory Usage (%)',
            color: this.colors.warning,
            max: 100
        });

        // Temperature Chart
        this.charts.temperature = this.createChart('temperatureChart', {
            label: 'Temperature (°C)',
            color: this.colors.danger,
            max: 100
        });

        // Power Usage Chart
        this.charts.power = this.createChart('powerChart', {
            label: 'Power Usage (W)',
            color: this.colors.success,
            max: 500
        });
    }

    // Create a chart instance
    createChart(canvasId, config) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.error(`Canvas not found: ${canvasId}`);
            return null;
        }

        const ctx = canvas.getContext('2d');
        
        // Simple chart implementation (you could use Chart.js here)
        return {
            canvas: canvas,
            ctx: ctx,
            config: config,
            data: [],
            draw: this.drawChart.bind(this)
        };
    }

    // Draw chart (simple implementation)
    drawChart(chart) {
        const ctx = chart.ctx;
        const canvas = chart.canvas;
        const data = chart.data;
        const config = chart.config;

        // Clear canvas
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (data.length === 0) {
            // Show "No data" message
            ctx.fillStyle = '#6c757d';
            ctx.font = '14px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('No data available', canvas.width / 2, canvas.height / 2);
            return;
        }

        // Set up chart dimensions
        const padding = 40;
        const chartWidth = canvas.width - 2 * padding;
        const chartHeight = canvas.height - 2 * padding;

        // Draw grid
        ctx.strokeStyle = '#e9ecef';
        ctx.lineWidth = 1;
        
        // Horizontal grid lines
        for (let i = 0; i <= 4; i++) {
            const y = padding + (i * chartHeight / 4);
            ctx.beginPath();
            ctx.moveTo(padding, y);
            ctx.lineTo(padding + chartWidth, y);
            ctx.stroke();
        }

        // Vertical grid lines
        for (let i = 0; i <= 10; i++) {
            const x = padding + (i * chartWidth / 10);
            ctx.beginPath();
            ctx.moveTo(x, padding);
            ctx.lineTo(x, padding + chartHeight);
            ctx.stroke();
        }

        // Draw axes
        ctx.strokeStyle = '#343a40';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(padding, padding);
        ctx.lineTo(padding, padding + chartHeight);
        ctx.lineTo(padding + chartWidth, padding + chartHeight);
        ctx.stroke();

        // Draw data line
        if (data.length > 1) {
            ctx.strokeStyle = config.color;
            ctx.lineWidth = 2;
            ctx.beginPath();

            const maxValue = config.max;
            const stepX = chartWidth / (this.maxDataPoints - 1);

            for (let i = 0; i < data.length; i++) {
                const x = padding + (i * stepX);
                const y = padding + chartHeight - (data[i] / maxValue * chartHeight);
                
                if (i === 0) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
            
            ctx.stroke();

            // Fill area under curve
            ctx.fillStyle = config.color + '20';
            ctx.lineTo(padding + (data.length - 1) * stepX, padding + chartHeight);
            ctx.lineTo(padding, padding + chartHeight);
            ctx.fill();
        }

        // Draw Y-axis labels
        ctx.fillStyle = '#6c757d';
        ctx.font = '12px Arial';
        ctx.textAlign = 'right';
        for (let i = 0; i <= 4; i++) {
            const value = Math.round(config.max * (4 - i) / 4);
            const y = padding + (i * chartHeight / 4) + 4;
            ctx.fillText(value.toString(), padding - 10, y);
        }

        // Draw current value
        if (data.length > 0) {
            const currentValue = data[data.length - 1];
            ctx.fillStyle = config.color;
            ctx.font = 'bold 14px Arial';
            ctx.textAlign = 'left';
            ctx.fillText(`Current: ${currentValue.toFixed(1)}`, padding + 10, padding + 20);
        }
    }

    // Load initial data
    async loadInitialData() {
        try {
            // Load current metrics
            const currentResponse = await fetch('/api/gpu/current');
            const currentResult = await currentResponse.json();
            
            if (currentResult.success) {
                this.currentData = currentResult.data;
                this.updateUI();
            }

            // Load history
            const historyResponse = await fetch('/api/gpu/history?minutes=5');
            const historyResult = await historyResponse.json();
            
            if (historyResult.success) {
                this.historyData = historyResult.data;
                this.updateCharts();
            }

        } catch (error) {
            console.error('Error loading initial GPU data:', error);
            this.showError('Failed to load GPU data');
        }
    }

    // Update UI with current data
    updateUI() {
        if (!this.currentData) return;

        const data = this.currentData;

        // Update GPU info
        document.getElementById('gpuName').textContent = data.gpu_name || 'Unknown GPU';
        document.getElementById('gpuDriver').textContent = `Driver: ${data.driver_version || 'Unknown'}`;

        // Update status values
        this.updateStatusValue('gpuUsage', data.gpu_utilization, '%', this.getUsageColor(data.gpu_utilization));
        this.updateStatusValue('memoryUsage', data.memory_utilization, '%', this.getMemoryColor(data.memory_utilization));
        this.updateStatusValue('temperature', data.temperature, '°C', this.getTemperatureColor(data.temperature));
        this.updateStatusValue('powerUsage', data.power_usage, 'W', this.getPowerColor(data.power_usage, data.power_limit));
        this.updateStatusValue('fanSpeed', data.fan_speed, '%');

        // Update memory details
        document.getElementById('memoryUsed').textContent = Math.round(data.memory_used || 0);
        document.getElementById('memoryTotal').textContent = Math.round(data.memory_total || 0);

        // Update power limit
        document.getElementById('powerLimit').textContent = Math.round(data.power_limit || 0) + 'W';

        // Update clocks
        document.getElementById('coreClock').textContent = data.core_clock || 0;
        document.getElementById('memoryClock').textContent = data.memory_clock || 0;

        // Update status indicator
        this.updateStatusIndicator();

        // Update footer info
        const lastUpdated = new Date(data.timestamp).toLocaleTimeString();
        document.getElementById('lastUpdated').textContent = `Last updated: ${lastUpdated}`;
    }

    // Update status value with color coding
    updateStatusValue(elementId, value, unit, colorClass = null) {
        const element = document.getElementById(elementId);
        if (element) {
            element.textContent = `${Math.round(value || 0)}${unit}`;
            
            // Remove existing color classes
            element.classList.remove('temperature-normal', 'temperature-warm', 'temperature-hot',
                                   'gpu-usage-low', 'gpu-usage-medium', 'gpu-usage-high', 'gpu-usage-critical',
                                   'memory-normal', 'memory-high', 'memory-critical',
                                   'power-normal', 'power-high', 'power-critical');
            
            // Add new color class
            if (colorClass) {
                element.classList.add(colorClass);
            }
        }
    }

    // Get color class for GPU usage
    getUsageColor(usage) {
        if (usage < 25) return 'gpu-usage-low';
        if (usage < 50) return 'gpu-usage-medium';
        if (usage < 80) return 'gpu-usage-high';
        return 'gpu-usage-critical';
    }

    // Get color class for memory usage
    getMemoryColor(usage) {
        if (usage < 70) return 'memory-normal';
        if (usage < 90) return 'memory-high';
        return 'memory-critical';
    }

    // Get color class for temperature
    getTemperatureColor(temp) {
        if (temp < 60) return 'temperature-normal';
        if (temp < 80) return 'temperature-warm';
        return 'temperature-hot';
    }

    // Get color class for power usage
    getPowerColor(usage, limit) {
        if (!limit) return 'power-normal';
        const percentage = (usage / limit) * 100;
        if (percentage < 70) return 'power-normal';
        if (percentage < 90) return 'power-high';
        return 'power-critical';
    }

    // Update status indicator
    updateStatusIndicator() {
        const indicator = document.getElementById('gpuStatus');
        if (!indicator) return;

        if (this.currentData) {
            indicator.textContent = 'Online';
            indicator.className = 'status-indicator online';
        } else {
            indicator.textContent = 'Offline';
            indicator.className = 'status-indicator offline';
        }
    }

    // Update charts with history data
    updateCharts() {
        if (!this.historyData || this.historyData.length === 0) return;

        // Update chart data
        this.charts.utilization.data = this.historyData.map(d => d.gpu_utilization || 0);
        this.charts.memory.data = this.historyData.map(d => d.memory_utilization || 0);
        this.charts.temperature.data = this.historyData.map(d => d.temperature || 0);
        this.charts.power.data = this.historyData.map(d => d.power_usage || 0);

        // Redraw charts
        Object.values(this.charts).forEach(chart => {
            if (chart) chart.draw(chart);
        });

        // Update monitoring duration
        document.getElementById('monitoringDuration').textContent = 
            `Monitoring: ${this.historyData.length} samples`;
    }

    // Set up event listeners
    setupEventListeners() {
        // Pause/Resume button
        const pauseBtn = document.getElementById('pauseGpuBtn');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => this.togglePause());
        }

        // Clear button
        const clearBtn = document.getElementById('clearGpuBtn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => this.clearData());
        }
    }

    // Toggle pause/resume
    togglePause() {
        this.isPaused = !this.isPaused;
        const pauseBtn = document.getElementById('pauseGpuBtn');
        
        if (this.isPaused) {
            pauseBtn.textContent = '▶️ Resume';
            pauseBtn.classList.add('active');
            this.stopUpdates();
        } else {
            pauseBtn.textContent = '⏸️ Pause';
            pauseBtn.classList.remove('active');
            this.startUpdates();
        }
    }

    // Clear all data
    clearData() {
        this.historyData = [];
        Object.values(this.charts).forEach(chart => {
            if (chart) {
                chart.data = [];
                chart.draw(chart);
            }
        });
        document.getElementById('monitoringDuration').textContent = 'Monitoring: 0 samples';
    }

    // Start periodic updates
    startUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }

        this.updateInterval = setInterval(async () => {
            if (!this.isPaused) {
                await this.updateData();
            }
        }, 2000); // Update every 2 seconds
    }

    // Stop periodic updates
    stopUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    // Update data from API
    async updateData() {
        try {
            const response = await fetch('/api/gpu/current');
            const result = await response.json();
            
            if (result.success) {
                this.currentData = result.data;
                this.updateUI();
                
                // Add to history
                this.historyData.push(result.data);
                
                // Limit history size
                if (this.historyData.length > this.maxDataPoints) {
                    this.historyData.shift();
                }
                
                this.updateCharts();
            }
        } catch (error) {
            console.error('Error updating GPU data:', error);
        }
    }

    // Show error message
    showError(message) {
        const container = document.querySelector('.gpu-metrics-container');
        if (container) {
            const errorDiv = document.createElement('div');
            errorDiv.className = 'gpu-error';
            errorDiv.textContent = message;
            container.appendChild(errorDiv);
            
            // Remove error after 5 seconds
            setTimeout(() => {
                errorDiv.remove();
            }, 5000);
        }
    }

    // Get summary statistics
    getSummaryStats() {
        if (!this.historyData || this.historyData.length === 0) {
            return null;
        }

        const stats = {
            gpu_utilization: this.calculateStats(this.historyData.map(d => d.gpu_utilization || 0)),
            memory_utilization: this.calculateStats(this.historyData.map(d => d.memory_utilization || 0)),
            temperature: this.calculateStats(this.historyData.map(d => d.temperature || 0)),
            power_usage: this.calculateStats(this.historyData.map(d => d.power_usage || 0))
        };

        return stats;
    }

    // Calculate statistics for a data array
    calculateStats(data) {
        if (data.length === 0) return { min: 0, max: 0, avg: 0, current: 0 };

        const min = Math.min(...data);
        const max = Math.max(...data);
        const avg = data.reduce((a, b) => a + b, 0) / data.length;
        const current = data[data.length - 1];

        return { min, max, avg, current };
    }

    // Cleanup
    destroy() {
        this.stopUpdates();
        this.isInitialized = false;
        console.log('GPU metrics destroyed');
    }
}

// Create global instance
window.gpuMetrics = new GPUMetrics(); 