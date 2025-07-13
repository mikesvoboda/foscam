# Foscam Logging System Setup

This document describes the comprehensive logging system for the Foscam Detection Dashboard, including centralized logging, rotation, and cleanup.

## 📁 Directory Structure

```
foscam/
├── logs/                           # Central logging directory
│   ├── webui.log                  # Web UI application logs
│   ├── webui_error.log            # Web UI error logs only
│   ├── webui_access.log           # HTTP access logs
│   ├── webui_uvicorn.log          # Uvicorn server logs
│   ├── webui_systemd.log          # Systemd service stdout
│   ├── webui_systemd_error.log    # Systemd service stderr
│   ├── crawler.log                # File crawler logs (when enabled)
│   ├── crawler_error.log          # Crawler error logs
│   ├── monitor.log                # File monitor logs (when enabled)
│   ├── logrotate.log              # Log rotation activities
│   ├── cleanup.log                # Log cleanup activities
│   └── logrotate.state            # Logrotate state file
├── logging_config.py              # Centralized logging configuration
├── logrotate.conf                 # Logrotate configuration
├── setup-logging.sh               # Initial logging setup script
├── manage-logs.sh                 # Log management utility
├── run-logrotate.sh               # Manual log rotation script
└── cleanup-old-logs.sh            # Log cleanup script
```

## 🚀 Quick Start

### Initial Setup
```bash
# Set up logging system
./setup-logging.sh

# View log status
./manage-logs.sh status

# Start services
./restart-webui.sh
```

### Common Operations
```bash
# View recent logs
./manage-logs.sh view webui 50

# Follow logs in real-time
./manage-logs.sh tail webui

# Check for errors
./manage-logs.sh errors

# Manual log rotation
./manage-logs.sh rotate

# Clean old logs
./manage-logs.sh clean
```

## 📊 Log Files Description

### Application Logs
- **webui.log**: Main web UI application logs (INFO, WARNING, ERROR)
- **webui_error.log**: Error logs only (ERROR, CRITICAL)
- **webui_access.log**: HTTP access logs with request details
- **webui_uvicorn.log**: Uvicorn server logs
- **webui_systemd.log**: Systemd service stdout
- **webui_systemd_error.log**: Systemd service stderr

### Future Service Logs
- **crawler.log**: File crawler logs (when implemented)
- **crawler_error.log**: Crawler error logs
- **monitor.log**: File monitor logs (when implemented)

### System Logs
- **logrotate.log**: Log rotation activities and status
- **cleanup.log**: Log cleanup activities
- **logrotate.state**: Logrotate internal state

## 🔄 Log Rotation

### Configuration
- **Frequency**: Daily at 2:00 AM
- **Retention**: 30 days
- **Compression**: Enabled (gzip)
- **Method**: Copy and truncate (preserves file handles)

### Rotation Rules
1. **Main logs**: Daily rotation, 30 days retention
2. **Error logs**: Daily rotation, immediate compression
3. **Access logs**: Daily rotation, delayed compression
4. **Uvicorn logs**: Daily rotation, 30 days retention

### Cron Jobs
```bash
# Daily log rotation at 2 AM
0 2 * * * /home/msvoboda/foscam/run-logrotate.sh >/dev/null 2>&1

# Weekly cleanup at 3 AM on Sunday
0 3 * * 0 /home/msvoboda/foscam/cleanup-old-logs.sh >/dev/null 2>&1
```

## 🧹 Log Cleanup

### Automatic Cleanup
- **Compressed logs**: Removed after 30 days
- **Old rotated logs**: Removed after 30 days
- **Frequency**: Weekly (Sunday 3:00 AM)

### Manual Cleanup
```bash
# Clean old logs manually
./cleanup-old-logs.sh

# Or use the management script
./manage-logs.sh clean
```

## 🛠️ Management Commands

### Log Management Script
```bash
# Show help
./manage-logs.sh help

# View log status
./manage-logs.sh status

# Follow logs in real-time
./manage-logs.sh tail [webui|crawler|monitor]

# View recent entries
./manage-logs.sh view [log_type] [number_of_lines]

# Show recent errors
./manage-logs.sh errors

# Manual log rotation
./manage-logs.sh rotate

# Clean old logs
./manage-logs.sh clean

# Show detailed statistics
./manage-logs.sh stats
```

### Direct Commands
```bash
# View recent web UI logs
tail -f logs/webui.log

# Check errors
grep ERROR logs/webui_error.log

# View systemd service logs
journalctl --user -u foscam-webui -f

# Check log sizes
du -sh logs/
```

## 📝 Logging Configuration

### Python Logging
The system uses a centralized logging configuration in `logging_config.py`:

```python
# Set up logger for a service
logger = setup_logger("webui", "INFO")

# Use logger in code
logger.info("Application started")
logger.error("Database connection failed")
```

### Log Levels
- **DEBUG**: Detailed diagnostic information
- **INFO**: General application events
- **WARNING**: Something unexpected happened
- **ERROR**: Application error occurred
- **CRITICAL**: Serious error, application may stop

### Log Format
```
2025-07-13 09:15:54 - webui - INFO - web_app.py:45 - Application started successfully
```

## 🔧 Systemd Integration

### Service Configuration
The systemd service is configured to log to both files and journald:

```ini
# File logging
StandardOutput=append:/home/msvoboda/foscam/logs/webui_systemd.log
StandardError=append:/home/msvoboda/foscam/logs/webui_systemd_error.log

# Journal logging
SyslogIdentifier=foscam-webui
```

### Service Management
```bash
# Restart service
./restart-webui.sh

# Check service status
systemctl --user status foscam-webui

# View service logs
journalctl --user -u foscam-webui -f
```

## 📈 Log Monitoring

### Key Metrics
- **Log file sizes**: Monitor for unusual growth
- **Error rates**: Check error logs for patterns
- **Service health**: Monitor systemd service status
- **Disk usage**: Ensure logs don't fill disk space

### Monitoring Commands
```bash
# Check log sizes
./manage-logs.sh status

# Monitor errors
./manage-logs.sh errors

# View service status
systemctl --user status foscam-webui

# Check disk usage
df -h
```

## ⚠️ Troubleshooting

### Common Issues

1. **Logs not rotating**
   ```bash
   # Check cron jobs
   crontab -l
   
   # Test logrotate
   ./run-logrotate.sh
   ```

2. **Logs growing too large**
   ```bash
   # Manual rotation
   ./manage-logs.sh rotate
   
   # Clean old logs
   ./manage-logs.sh clean
   ```

3. **Permission errors**
   ```bash
   # Fix permissions
   chmod 644 logs/*.log
   chmod 755 logs/
   ```

4. **Service not logging**
   ```bash
   # Check service status
   systemctl --user status foscam-webui
   
   # Reload service
   systemctl --user daemon-reload
   systemctl --user restart foscam-webui
   ```

### Log Analysis
```bash
# Find errors in logs
grep -i error logs/*.log

# Check service startup
journalctl --user -u foscam-webui --since "1 hour ago"

# Monitor log growth
watch -n 5 'ls -lh logs/'
```

## 🔐 Security and Permissions

### File Permissions
- **Log files**: 644 (readable by owner and group)
- **Directories**: 755 (executable by all, writable by owner)
- **Scripts**: 755 (executable)

### Security Considerations
- Logs may contain sensitive information
- Regular cleanup prevents disk space issues
- Compressed logs reduce storage requirements
- File rotation prevents log tampering

## 🚀 Future Enhancements

### Planned Features
1. **Centralized logging server**: Ship logs to external system
2. **Real-time monitoring**: Alerts for critical errors
3. **Log analysis**: Automated error pattern detection
4. **Metrics collection**: Application performance metrics
5. **Dashboard integration**: Log viewer in web UI

### Extension Points
- Add new services by using `setup_logger("service_name")`
- Extend logrotate configuration for new log types
- Add custom log analysis scripts
- Integrate with monitoring systems

## 📞 Support

For issues or questions:
1. Check logs: `./manage-logs.sh errors`
2. Verify service status: `systemctl --user status foscam-webui`
3. Review configuration: `./manage-logs.sh status`
4. Test rotation: `./manage-logs.sh rotate`

---

*Last updated: July 13, 2025* 