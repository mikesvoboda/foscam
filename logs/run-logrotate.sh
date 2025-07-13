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
