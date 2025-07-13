#!/bin/bash

# Kill Web Processes Script
# This script manually kills any duplicate web processes

echo "🧹 Foscam Web Process Cleanup"
echo "==============================="

# Function to check if port 8000 is in use
check_port() {
    if lsof -i:8000 >/dev/null 2>&1; then
        echo "⚠️  Port 8000 is currently in use:"
        lsof -i:8000
        echo ""
        return 0
    else
        echo "✅ Port 8000 is available"
        return 1
    fi
}

# Function to kill processes by pattern
kill_web_processes() {
    echo "🔍 Looking for web_app.py processes..."
    if pgrep -f "python.*src/web_app.py" >/dev/null; then
        echo "Found web_app.py processes:"
        pgrep -f -l "python.*src/web_app.py"
        echo ""
        echo "🛑 Killing web_app.py processes..."
        pkill -f "python.*src/web_app.py"
        sleep 2
        echo "✅ Done"
    else
        echo "✅ No web_app.py processes found"
    fi
    echo ""
}

# Function to kill processes by port
kill_port_processes() {
    echo "🔍 Looking for processes using port 8000..."
    if lsof -ti:8000 >/dev/null 2>&1; then
        echo "Found processes using port 8000:"
        lsof -i:8000
        echo ""
        echo "🛑 Killing processes on port 8000..."
        lsof -ti:8000 | xargs -r kill
        sleep 2
        echo "✅ Done"
    else
        echo "✅ No processes found on port 8000"
    fi
    echo ""
}

# Show initial state
echo "🔍 Initial state:"
check_port
echo ""

# Kill by process name
kill_web_processes

# Kill by port
kill_port_processes

# Show final state
echo "🔍 Final state:"
check_port

echo ""
echo "🎯 Cleanup complete!"
echo "You can now start the web UI service with:"
echo "  systemctl --user start foscam-webui"
echo "  or"
echo "  ./restart-webui.sh" 