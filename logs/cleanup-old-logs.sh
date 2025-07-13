#!/bin/bash
# Clean up logs older than 30 days

LOGS_DIR="/home/msvoboda/foscam/logs"

echo "$(date): Starting cleanup of logs older than 30 days..." >> "$LOGS_DIR/cleanup.log"

# Find and remove compressed logs older than 30 days
find "$LOGS_DIR" -name "*.gz" -type f -mtime +30 -exec rm -f {} \; 2>/dev/null

# Find and remove uncompressed old logs (safety net)
find "$LOGS_DIR" -name "*.log.*" -type f -mtime +30 -exec rm -f {} \; 2>/dev/null

echo "$(date): Cleanup completed" >> "$LOGS_DIR/cleanup.log"
