# Foscam Detection Dashboard - Comprehensive Logging System

This document describes the advanced logging system for the Foscam Detection Dashboard, featuring daily log rotation, automatic cleanup, extensive request tracking, and integrated nginx logging.

## 🎯 **System Overview**

The Foscam logging system provides comprehensive monitoring and debugging capabilities with:

- **Daily Log Rotation** with 30-day automatic retention
- **Extensive Request Tracking** with performance monitoring 
- **Automatic Log Cleanup** to prevent disk space issues
- **Integrated Nginx Logging** for web server monitoring
- **Multi-Level Logging** (DEBUG, INFO, WARNING, ERROR)
- **Real-Time Performance Metrics** for all API endpoints

## 📁 **Directory Structure**

```
foscam/
├── logs/                           # Central logging directory
│   ├── webui.log                  # Main application logs with daily rotation
│   ├── webui_error.log            # Error-only logs (ERROR, CRITICAL)
│   ├── webui_access.log           # Uvicorn HTTP access logs
│   ├── webui_uvicorn.log          # Uvicorn server logs
│   ├── nginx_access.log           # Nginx access logs (detailed format)
│   ├── nginx_error.log            # Nginx error logs
│   ├── nginx.pid                  # Nginx process ID file
│   ├── nginx_*_temp/              # Nginx temporary directories
│   └── *.log.YYYY-MM-DD           # Rotated log files (auto-deleted after 30 days)
├── src/
│   ├── logging_config.py          # Centralized logging configuration
│   └── web_app.py                 # Application with extensive logging
└── nginx.conf                     # Nginx configuration with logging
```

## 🚀 **Quick Start**

### Starting Services with Logging
```bash
# Start both backend and nginx with logging enabled
./restart-webui.sh

# Check if logging is working
tail -f logs/webui.log

# Monitor real-time requests
tail -f logs/nginx_access.log
```

### Viewing Logs
```bash
# Application logs
tail -f logs/webui.log

# Error logs only
tail -f logs/webui_error.log

# Nginx access logs
tail -f logs/nginx_access.log

# All logs combined
tail -f logs/*.log
```

## 📊 **Logging Features**

### **Daily Rotation & Automatic Cleanup**
- **Rotation Time**: Every day at midnight
- **Retention Period**: 30 days
- **Auto-cleanup**: Files older than 30 days are automatically deleted
- **File Format**: `logfile.log.YYYY-MM-DD`

### **Extensive Request Tracking**
Every API request is logged with:
- **Client IP Address** (with 'unknown' fallback)
- **Request Parameters** (page, filters, etc.)
- **Response Time** in milliseconds
- **Success/Error Status** with detailed error information
- **Database Query Performance** tracking

### **Performance Monitoring**
- **API Endpoint Timing**: Duration tracking for all endpoints
- **Database Session Monitoring**: Connection time and cleanup
- **Error Rate Tracking**: Automatic error counting and reporting
- **Memory Usage**: Peak memory tracking for operations

## 🛠️ **Configuration Details**

### **Application Logging (src/logging_config.py)**

#### **Logger Setup**
```python
def setup_logger(service_name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Daily rotation with 30-day cleanup:
    - TimedRotatingFileHandler (when='midnight', backupCount=30)
    - Automatic old log file cleanup on startup
    - Detailed formatter with file:line information
    """
```

#### **Log Formatters**
- **Detailed Format**: `%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s`
- **Date Format**: `%Y-%m-%d %H:%M:%S`
- **Console Format**: Simplified for development

#### **Handler Configuration**
```python
# Main application logs
file_handler = TimedRotatingFileHandler(
    log_file, when='midnight', interval=1, backupCount=30
)

# Error-only logs  
error_handler = TimedRotatingFileHandler(
    error_file, when='midnight', interval=1, backupCount=30
)

# Console output for development
console_handler = StreamHandler()
```

### **Uvicorn Logging**
```python
def setup_uvicorn_logging(service_name: str = "webui") -> dict:
    """
    Uvicorn server logging with daily rotation:
    - Access logs: Request details with client IP
    - Server logs: Startup, shutdown, errors
    - Daily rotation with 30-day retention
    """
```

### **Nginx Logging (nginx.conf)**

#### **Access Log Format**
```nginx
log_format detailed '$remote_addr - $remote_user [$time_local] '
                   '"$request" $status $body_bytes_sent '
                   '"$http_referer" "$http_user_agent" '
                   '$request_time $upstream_response_time';

access_log /home/msvoboda/foscam/logs/nginx_access.log detailed;
```

#### **Error Logging**
```nginx
error_log /home/msvoboda/foscam/logs/nginx_error.log warn;
pid /home/msvoboda/foscam/logs/nginx.pid;
```

## 📈 **Extensive Logging Examples**

### **API Request Logging**
```
2025-07-14 01:49:02 - webui - INFO - web_app.py:601 - Documentation request - project README
2025-07-14 01:49:03 - webui - INFO - web_app.py:722 - Documentation served successfully - project README (duration: 0.028s)
```

### **Performance Monitoring**
```
2025-07-14 01:46:01 - webui - INFO - web_app.py:94 - Home page request from 127.0.0.1
2025-07-14 01:46:01 - webui - INFO - web_app.py:110 - Home page served successfully to 127.0.0.1 (duration: 0.001s)
```

### **Error Tracking**
```
2025-07-14 01:44:22 - webui - ERROR - web_app.py:391 - API cameras error: 'Camera' object has no attribute 'name' (duration: 0.002s)
2025-07-14 01:44:22 - webui - ERROR - web_app.py:392 - API cameras error traceback: Traceback (most recent call last):
  File "/home/msvoboda/foscam/src/web_app.py", line 377, in get_cameras
    "name": camera.name,
            ^^^^^^^^^^^
AttributeError: 'Camera' object has no attribute 'name'
```

### **Database Session Monitoring**
```
2025-07-14 01:45:15 - webui - DEBUG - web_app.py:37 - Database session created
2025-07-14 01:45:15 - webui - DEBUG - web_app.py:44 - Database session closed (duration: 0.003s)
```

## 🔍 **Monitoring Commands**

### **Real-Time Monitoring**
```bash
# Follow application logs
tail -f logs/webui.log

# Monitor API requests with timing
tail -f logs/webui.log | grep "duration:"

# Watch error logs
tail -f logs/webui_error.log

# Monitor nginx access
tail -f logs/nginx_access.log

# Combined monitoring
tail -f logs/webui.log logs/nginx_access.log
```

### **Log Analysis**
```bash
# Count requests by endpoint
grep -o "API [^:]*" logs/webui.log | sort | uniq -c

# Average response times
grep "duration:" logs/webui.log | grep -o "duration: [0-9.]*" | cut -d: -f2 | awk '{sum+=$1; n++} END {print "Average:", sum/n, "seconds"}'

# Error summary
grep ERROR logs/webui_error.log | cut -d- -f5- | sort | uniq -c

# Top client IPs
grep "request from" logs/webui.log | grep -o "[0-9]\+\.[0-9]\+\.[0-9]\+\.[0-9]\+" | sort | uniq -c | sort -nr
```

### **Log File Management**
```bash
# Check log file sizes
ls -lh logs/*.log

# View rotated logs
ls -la logs/*.log.*

# Check available disk space
df -h logs/

# Manual log cleanup (removes files >30 days)
python3 -c "from src.logging_config import cleanup_old_logs; cleanup_old_logs('webui')"
```

## 🎛️ **Configuration Options**

### **Log Levels**
- **DEBUG**: Detailed debugging information (database sessions, query details)
- **INFO**: General operational messages (requests, responses, timing)
- **WARNING**: Warning messages (invalid parameters, deprecated features)
- **ERROR**: Error messages (exceptions, failures)
- **CRITICAL**: Critical errors (system failures)

### **Customizing Log Retention**
```python
# Change retention period (default: 30 days)
def cleanup_old_logs(service_name: str, days_to_keep: int = 30):
    
# Change rotation frequency (daily, weekly, monthly)
file_handler = TimedRotatingFileHandler(
    log_file, 
    when='midnight',  # or 'W0' for weekly, 'M' for monthly
    interval=1,       # every 1 day
    backupCount=30    # keep 30 files
)
```

### **Environment Variables**
```bash
# Set log level
export FOSCAM_LOG_LEVEL=DEBUG

# Custom log directory
export FOSCAM_LOG_DIR=/custom/log/path
```

## 🚨 **Troubleshooting**

### **Common Issues**
1. **Permission Errors**: Ensure write permissions to `logs/` directory
2. **Disk Space**: Monitor disk usage; logs auto-cleanup after 30 days
3. **Missing Logs**: Check if services are running and logging_config is imported
4. **Rotation Failures**: Verify file permissions and disk space

### **Log File Not Rotating**
```bash
# Check if files are locked
lsof logs/webui.log

# Restart services to release file handles
./restart-webui.sh

# Manual rotation test
python3 -c "import logging.handlers; h = logging.handlers.TimedRotatingFileHandler('test.log', when='S', interval=1); h.doRollover()"
```

### **Performance Impact**
- **Minimal CPU overhead**: Asynchronous logging
- **Disk I/O**: Batched writes to reduce impact
- **Memory usage**: Log messages are not buffered extensively
- **Network impact**: None (local file logging only)

## 📋 **Log Analysis Tips**

### **Finding Performance Issues**
```bash
# Slow requests (>1 second)
grep "duration: [1-9]" logs/webui.log

# Database performance
grep "Database session" logs/webui.log | grep "duration:"

# Error patterns
grep ERROR logs/webui_error.log | cut -d: -f4- | sort | uniq -c | sort -nr
```

### **Monitoring Dashboard Health**
```bash
# Recent successful requests
grep "served successfully" logs/webui.log | tail -10

# Request volume per hour
grep "$(date +%Y-%m-%d)" logs/webui.log | cut -d' ' -f1-2 | cut -d: -f1-2 | uniq -c

# Error rate
total=$(grep "$(date +%Y-%m-%d)" logs/webui.log | wc -l)
errors=$(grep "$(date +%Y-%m-%d)" logs/webui_error.log | wc -l)
echo "Error rate: $(echo "scale=2; $errors * 100 / $total" | bc)%"
```

## 🎯 **Best Practices**

1. **Monitor log file sizes** regularly
2. **Set up alerts** for error rate spikes
3. **Use log levels appropriately** (avoid DEBUG in production)
4. **Archive important logs** before cleanup
5. **Monitor disk space** in `/logs` directory
6. **Review error patterns** weekly
7. **Test log rotation** during maintenance windows

## 🔗 **Related Files**

- `src/logging_config.py` - Logging configuration and setup
- `src/web_app.py` - Application with extensive logging integration
- `nginx.conf` - Nginx logging configuration  
- `restart-webui.sh` - Service startup script
- `logs/` - All log files and rotated archives 