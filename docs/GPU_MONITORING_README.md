# GPU Monitoring for Foscam Detection Dashboard

The Foscam Detection Dashboard now includes real-time GPU monitoring similar to Green with Envy. This feature displays GPU performance metrics including utilization, memory usage, temperature, power consumption, and clock speeds.

## Features

- **Real-time GPU monitoring** with 5-minute rolling history
- **Visual charts** for GPU utilization, memory usage, temperature, and power consumption
- **Status cards** showing current values with color-coded indicators
- **Automatic GPU detection** (NVIDIA and AMD support)
- **Fallback system** using command-line tools if libraries aren't available
- **Responsive design** optimized for desktop and mobile viewing

## Installation

### 1. Install GPU Monitoring Dependencies

```bash
# Install GPU monitoring packages
pip install -r requirements-gpu.txt
```

### 2. System Dependencies

#### For NVIDIA GPUs:
```bash
# Ensure nvidia-smi is available (usually installed with NVIDIA drivers)
nvidia-smi --version

# If not available, install NVIDIA drivers:
# Ubuntu/Debian:
sudo apt install nvidia-driver-535  # or latest version

# CentOS/RHEL/Fedora:
sudo dnf install akmod-nvidia  # or nvidia-driver
```

#### For AMD GPUs (Optional):
```bash
# Install radeontop for AMD GPU monitoring
# Ubuntu/Debian:
sudo apt install radeontop

# CentOS/RHEL/Fedora:
sudo dnf install radeontop
```

### 3. Restart the Web Application

```bash
# Restart the service
./restart-webui.sh

# Or restart manually
source venv/bin/activate
cd src
python web_app.py
```

## Usage

Once installed, the GPU monitoring section will appear in your Foscam Detection Dashboard between the statistics cards and the detection heatmap.

### Dashboard Features

1. **GPU Status Cards**: Display current values for:
   - GPU utilization percentage
   - Memory usage (used/total MB)
   - Temperature (°C)
   - Power consumption (W)
   - Fan speed (%)
   - Clock speeds (Core/Memory MHz)

2. **Real-time Charts**: Show 5-minute rolling history for:
   - GPU utilization over time
   - Memory usage over time
   - Temperature over time
   - Power consumption over time

3. **Interactive Controls**:
   - **Pause/Resume**: Stop/start data collection
   - **Clear**: Reset chart data
   - **Auto-refresh**: Updates every 2 seconds

### Status Indicators

The dashboard uses color-coded indicators:

- **GPU Utilization**:
  - Gray: Low (< 25%)
  - Blue: Medium (25-50%)
  - Yellow: High (50-80%)
  - Red: Critical (> 80%)

- **Memory Usage**:
  - Green: Normal (< 70%)
  - Yellow: High (70-90%)
  - Red: Critical (> 90%)

- **Temperature**:
  - Green: Normal (< 60°C)
  - Yellow: Warm (60-80°C)
  - Red: Hot (> 80°C)

- **Power Usage**:
  - Green: Normal (< 70% of limit)
  - Yellow: High (70-90% of limit)
  - Red: Critical (> 90% of limit)

## API Endpoints

The GPU monitoring feature adds these API endpoints:

- `GET /api/gpu/current` - Get current GPU metrics
- `GET /api/gpu/history?minutes=N` - Get GPU history (1-60 minutes)
- `GET /api/gpu/stats` - Get GPU summary statistics

## Troubleshooting

### No GPU Data Showing

1. **Check GPU drivers are installed**:
   ```bash
   nvidia-smi  # For NVIDIA
   lspci | grep VGA  # List all graphics cards
   ```

2. **Verify dependencies are installed**:
   ```bash
   python -c "import pynvml; print('NVIDIA support available')"
   ```

3. **Check system permissions**:
   ```bash
   # Add user to video group if needed
   sudo usermod -a -G video $USER
   ```

### GPU Monitoring Shows "Offline"

1. **Check if GPU monitoring is running**:
   - Look for "GPU monitoring started" in the application logs
   - Check if `nvidia-smi` works from command line

2. **Restart the application**:
   ```bash
   ./restart-webui.sh
   ```

3. **Check application logs**:
   ```bash
   tail -f logs/webui.log
   ```

### Performance Issues

1. **Adjust update interval**: The default update interval is 2 seconds. You can modify this in `src/gpu_monitor.py`:
   ```python
   gpu_monitor = GPUMonitor(update_interval=5.0)  # 5 seconds
   ```

2. **Reduce history length**: Default is 5 minutes (300 data points). Modify in `src/static/js/gpu-metrics.js`:
   ```javascript
   this.maxDataPoints = 150; // 2.5 minutes
   ```

### Fallback Mode

If GPU libraries aren't available, the system automatically falls back to using command-line tools:

- **NVIDIA**: Uses `nvidia-smi` command
- **AMD**: Uses `radeontop` command (if available)
- **Generic**: Shows basic system information

## Technical Details

### Architecture

- **Backend**: Python module (`src/gpu_monitor.py`) with background thread
- **Frontend**: JavaScript module (`src/static/js/gpu-metrics.js`) with real-time charts
- **Storage**: In-memory rolling buffer (last 5 minutes)
- **Update frequency**: 1 second backend, 2 second frontend

### Data Flow

1. Background thread collects GPU metrics every second
2. Data stored in rolling buffer (300 samples max)
3. API endpoints serve current and historical data
4. Frontend updates displays every 2 seconds
5. Charts show real-time visualization

### Supported GPUs

- **NVIDIA**: GTX 10-series and newer, RTX series, Tesla, Quadro
- **AMD**: Modern Radeon cards (with `radeontop` support)
- **Intel**: Limited support through system commands

## Security Considerations

- GPU monitoring requires access to GPU hardware information
- No sensitive data is stored or transmitted
- All data is local to the system
- API endpoints are read-only

## Performance Impact

- **Memory usage**: ~1MB for 5 minutes of data
- **CPU usage**: <0.1% on modern systems
- **Network usage**: ~1KB per update (frontend only)
- **Disk usage**: No persistent storage

## Future Enhancements

Potential future features:
- GPU memory breakdown by process
- Historical data persistence
- Alert thresholds and notifications
- Multi-GPU support
- Integration with detection workload monitoring

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review application logs in `logs/webui.log`
3. Verify GPU drivers and dependencies are installed
4. Test GPU access with `nvidia-smi` or equivalent tools 