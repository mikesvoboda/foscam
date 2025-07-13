# Foscam Web UI Systemd Setup

This document describes the systemd user service setup for the Foscam Web UI with automatic duplicate process handling.

## Service Configuration

The systemd service is configured to automatically handle duplicate processes and ensure clean restarts.

### Service File Location
```
~/.config/systemd/user/foscam-webui.service
```

### Key Features

1. **Automatic Duplicate Process Cleanup**
   - Kills existing `web_app.py` processes before starting
   - Frees up port 8000 if it's in use
   - Uses `ExecStartPre` to run cleanup commands

2. **Proper Process Management**
   - Automatic restart on failure
   - Graceful shutdown with cleanup
   - Proper logging to systemd journal

3. **Pre-start Checks**
   - `pkill -f "python.*web_app.py"` - Kills any existing web app processes
   - `lsof -ti:8000 | xargs -r kill` - Kills any processes using port 8000

## Commands

### Basic Service Management
```bash
# Start the service
systemctl --user start foscam-webui

# Stop the service
systemctl --user stop foscam-webui

# Restart the service
systemctl --user restart foscam-webui

# Check status
systemctl --user status foscam-webui

# Enable on boot
systemctl --user enable foscam-webui

# View logs
journalctl --user -u foscam-webui -f
```

### Convenient Scripts

#### `restart-webui.sh`
- One-command restart with status checking
- Automatic duplicate process detection and cleanup
- Shows service status and recent logs
- Enhanced error reporting

Usage:
```bash
./restart-webui.sh
```

#### `kill-web-processes.sh`
- Manual cleanup of duplicate processes
- Useful for troubleshooting
- Shows before/after port status

Usage:
```bash
./kill-web-processes.sh
```

## Duplicate Process Handling

The service automatically handles duplicate processes in several ways:

1. **Pre-start Cleanup**: Before starting, it kills any existing web processes
2. **Port Cleanup**: Frees up port 8000 if it's in use
3. **Graceful Shutdown**: Properly terminates processes on service stop
4. **Restart Protection**: Prevents multiple instances from running

## Troubleshooting

### If the service fails to start:

1. Check the logs:
   ```bash
   journalctl --user -u foscam-webui --no-pager -n 20
   ```

2. Manually clean up processes:
   ```bash
   ./kill-web-processes.sh
   ```

3. Check port availability:
   ```bash
   lsof -i:8000
   ```

4. Restart the service:
   ```bash
   ./restart-webui.sh
   ```

### Common Issues

- **Port already in use**: The service now automatically handles this
- **Multiple Python processes**: Pre-start cleanup kills duplicates
- **Service won't stop**: Enhanced timeout and kill modes handle this

## Web UI Access

Once the service is running, access the web UI at:
- http://localhost:8000
- http://0.0.0.0:8000

## File Crawler Services (Future)

The systemd setup is ready to be extended for the file crawler services:
- `foscam-crawler.service` - For bulk processing
- `foscam-monitor.service` - For real-time monitoring

These will be implemented when ready to enable the full system.

## Service Dependencies

The service requires:
- Python virtual environment at `/home/msvoboda/foscam/venv`
- Working directory at `/home/msvoboda/foscam`
- `web_app.py` file in the working directory
- Network connectivity (waits for `network.target`)

## Logging

All service output is logged to the systemd journal with identifier `foscam-webui`.

View logs with:
```bash
journalctl --user -u foscam-webui -f
``` 