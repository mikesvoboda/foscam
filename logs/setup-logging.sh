#!/bin/bash

# Foscam Logging Setup Script
# Sets up centralized logging with rotation and compression

echo "🗂️ Setting up Foscam Logging System..."

# Get the absolute path of the foscam directory
FOSCAM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGS_DIR="$FOSCAM_DIR/logs"
LOGROTATE_CONFIG="$LOGS_DIR/logrotate.conf"

# Create logs directory
echo "📁 Creating logs directory..."
mkdir -p "$LOGS_DIR"

# Set proper permissions
chmod 755 "$LOGS_DIR"

# Test logging configuration
echo "🧪 Testing logging configuration..."
cd "$FOSCAM_DIR"
python src/logging_config.py

# Set up logrotate
echo "🔄 Setting up log rotation..."

# Create a user-specific logrotate script
LOGROTATE_SCRIPT="$FOSCAM_DIR/run-logrotate.sh"

cat > "$LOGROTATE_SCRIPT" << 'EOF'
#!/bin/bash
# User logrotate script for Foscam logs

FOSCAM_DIR="/home/msvoboda/foscam"
LOGROTATE_CONFIG="$FOSCAM_DIR/logrotate.conf"
LOGROTATE_STATE="$FOSCAM_DIR/logs/logrotate.state"

# Run logrotate with our config
/usr/sbin/logrotate -s "$LOGROTATE_STATE" "$LOGROTATE_CONFIG"

# Check if rotation was successful
if [ $? -eq 0 ]; then
    echo "$(date): Logrotate completed successfully" >> "$FOSCAM_DIR/logs/logrotate.log"
else
    echo "$(date): Logrotate failed with exit code $?" >> "$FOSCAM_DIR/logs/logrotate.log"
fi
EOF

chmod +x "$LOGROTATE_SCRIPT"

# Set up crontab entry for logrotate
echo "⏰ Setting up cron job for log rotation..."

# Check if cron entry already exists
if ! crontab -l 2>/dev/null | grep -q "run-logrotate.sh"; then
    # Add logrotate to crontab (run daily at 2 AM)
    (crontab -l 2>/dev/null; echo "0 2 * * * $LOGROTATE_SCRIPT >/dev/null 2>&1") | crontab -
    echo "✅ Added daily logrotate cron job at 2 AM"
else
    echo "✅ Logrotate cron job already exists"
fi

# Test logrotate configuration
echo "🔍 Testing logrotate configuration..."
/usr/sbin/logrotate -d "$LOGROTATE_CONFIG"

if [ $? -eq 0 ]; then
    echo "✅ Logrotate configuration is valid"
else
    echo "❌ Logrotate configuration has errors"
    exit 1
fi

# Create initial log files to test
echo "📝 Creating initial test log files..."
touch "$LOGS_DIR/webui.log"
touch "$LOGS_DIR/webui_error.log"
touch "$LOGS_DIR/webui_access.log"
touch "$LOGS_DIR/webui_uvicorn.log"

# Set proper permissions
chmod 644 "$LOGS_DIR"/*.log

# Clean up old logs script
CLEANUP_SCRIPT="$FOSCAM_DIR/cleanup-old-logs.sh"

cat > "$CLEANUP_SCRIPT" << 'EOF'
#!/bin/bash
# Clean up logs older than 30 days

LOGS_DIR="/home/msvoboda/foscam/logs"

echo "$(date): Starting cleanup of logs older than 30 days..." >> "$LOGS_DIR/cleanup.log"

# Find and remove compressed logs older than 30 days
find "$LOGS_DIR" -name "*.gz" -type f -mtime +30 -exec rm -f {} \; 2>/dev/null

# Find and remove uncompressed old logs (safety net)
find "$LOGS_DIR" -name "*.log.*" -type f -mtime +30 -exec rm -f {} \; 2>/dev/null

echo "$(date): Cleanup completed" >> "$LOGS_DIR/cleanup.log"
EOF

chmod +x "$CLEANUP_SCRIPT"

# Add cleanup to crontab (run weekly)
if ! crontab -l 2>/dev/null | grep -q "cleanup-old-logs.sh"; then
    (crontab -l 2>/dev/null; echo "0 3 * * 0 $CLEANUP_SCRIPT >/dev/null 2>&1") | crontab -
    echo "✅ Added weekly log cleanup cron job"
else
    echo "✅ Log cleanup cron job already exists"
fi

# Show current crontab
echo "📅 Current cron jobs:"
crontab -l

echo ""
echo "✅ Logging setup complete!"
echo ""
echo "📊 Logging Configuration Summary:"
echo "  📁 Logs Directory: $LOGS_DIR"
echo "  🔄 Log Rotation: Daily at 2 AM"
echo "  🗜️  Compression: Enabled for rotated logs"
echo "  📅 Retention: 30 days"
echo "  🧹 Cleanup: Weekly removal of files older than 30 days"
echo ""
echo "📋 Log Files:"
echo "  • webui.log - Main web UI logs"
echo "  • webui_error.log - Error logs only"
echo "  • webui_access.log - HTTP access logs"
echo "  • webui_uvicorn.log - Uvicorn server logs"
echo "  • crawler.log - File crawler logs (when enabled)"
echo "  • monitor.log - File monitor logs (when enabled)"
echo ""
echo "🛠️  Management Commands:"
echo "  View logs: tail -f $LOGS_DIR/webui.log"
echo "  Test logrotate: $LOGROTATE_SCRIPT"
echo "  Manual cleanup: $CLEANUP_SCRIPT"
echo "  Log stats: python logging_config.py" 