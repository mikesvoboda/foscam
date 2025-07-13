#!/bin/bash

# Foscam Web UI Restart Script
# This script provides a single command to restart the web UI service
# The systemd service now handles duplicate process cleanup automatically

echo "🔄 Restarting Foscam Web UI Service..."

# Check if logging is set up
if [ ! -d "logs" ]; then
    echo "📁 Logs directory not found, setting up logging..."
    ./setup-logging.sh
fi

# Function to check if port 8000 is in use
check_port() {
    if lsof -i:8000 >/dev/null 2>&1; then
        echo "⚠️  Port 8000 is currently in use"
        lsof -i:8000 | head -2
        echo ""
        return 0
    else
        echo "✅ Port 8000 is available"
        return 1
    fi
}

# Function to show service status
show_status() {
    echo "📊 Service Status:"
    systemctl --user status foscam-webui --no-pager --lines=5
    echo ""
}

echo "🔍 Checking current state..."
check_port

# Reload systemd user daemon to pick up any changes
echo "🔄 Reloading systemd daemon..."
systemctl --user daemon-reload

# Stop the service (this will also cleanup any duplicates)
echo "🛑 Stopping foscam-webui service..."
systemctl --user stop foscam-webui

# Wait a moment for cleanup
sleep 3

# Double-check port is free
echo "🔍 Verifying port cleanup..."
if check_port; then
    echo "🧹 Force cleaning remaining processes..."
    pkill -f "python.*src/web_app.py" || true
    sleep 2
fi

# Start the service
echo "🚀 Starting foscam-webui service..."
systemctl --user start foscam-webui

# Wait for startup
sleep 5

# Show final status
show_status

# Check if service is running properly
if systemctl --user is-active --quiet foscam-webui; then
    echo "✅ Web UI restart complete!"
    echo "📊 Access the dashboard at: http://localhost:8000"
    
    # Show recent logs
    echo ""
    echo "📋 Recent logs:"
    journalctl --user -u foscam-webui --no-pager --lines=5
else
    echo "❌ Service failed to start properly"
    echo "📋 Error logs:"
    journalctl --user -u foscam-webui --no-pager --lines=10
fi

echo ""
echo "🛠️  Useful commands:"
echo "  View logs: journalctl --user -u foscam-webui -f"
echo "  Stop service: systemctl --user stop foscam-webui"
echo "  Start service: systemctl --user start foscam-webui"
echo "  Enable on boot: systemctl --user enable foscam-webui"
echo "  Check status: systemctl --user status foscam-webui" 