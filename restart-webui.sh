#!/bin/bash

# Foscam Web UI Restart Script (with Nginx)
# This script manages both the FastAPI backend and Nginx frontend

echo "🔄 Restarting Foscam Web UI with Nginx..."

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "❌ Nginx is not installed. Install with: sudo dnf install nginx"
    exit 1
fi

# Function to check if ports are in use
check_ports() {
    echo "🔍 Checking port status..."
    
    if lsof -i:7999 >/dev/null 2>&1; then
        echo "⚠️  Port 7999 (Backend) is currently in use"
        lsof -i:7999 | head -2
    else
        echo "✅ Port 7999 (Backend) is available"
    fi
    
    if lsof -i:8000 >/dev/null 2>&1; then
        echo "⚠️  Port 8000 (Nginx) is currently in use"
        lsof -i:8000 | head -2
    else
        echo "✅ Port 8000 (Nginx) is available"
    fi
    echo ""
}

# Function to stop services
stop_services() {
    echo "🛑 Stopping services..."
    
    # Stop nginx first
    if [ -f logs/nginx.pid ]; then
        echo "  Stopping nginx..."
        nginx -s quit -e /home/msvoboda/foscam/logs/nginx_error.log -c $(pwd)/nginx.conf 2>/dev/null || true
        sleep 2
    fi
    
    # Kill any hanging nginx processes
    pkill -f "nginx.*$(pwd)" 2>/dev/null || true
    
    # Stop FastAPI backend
    echo "  Stopping FastAPI backend..."
    systemctl --user stop foscam-webui
    sleep 2
    
    # Force cleanup if needed
    pkill -f "python.*src/web_app.py" || true
}

# Function to start services
start_services() {
    echo "🚀 Starting services..."
    
    # Start FastAPI backend first
    echo "  Starting FastAPI backend on port 7999..."
    systemctl --user daemon-reload
    systemctl --user start foscam-webui
    
    # Wait for backend to be ready
    echo "  Waiting for backend to start..."
    for i in {1..30}; do
        if curl -s http://localhost:7999/api/gpu/current >/dev/null 2>&1; then
            echo "  ✅ Backend is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "  ❌ Backend failed to start within 30 seconds"
            return 1
        fi
        sleep 1
    done
    
    # Test nginx configuration
    echo "  Testing nginx configuration..."
    nginx -t -e /home/msvoboda/foscam/logs/nginx_error.log -c $(pwd)/nginx.conf
    if [ $? -ne 0 ]; then
        echo "  ❌ Nginx configuration test failed!"
        return 1
    fi
    
    # Start nginx
    echo "  Starting nginx on port 8000..."
    nginx -e /home/msvoboda/foscam/logs/nginx_error.log -c $(pwd)/nginx.conf
    if [ $? -ne 0 ]; then
        echo "  ❌ Failed to start nginx!"
        return 1
    fi
    
    echo "  ✅ Nginx started successfully"
}

# Function to show service status
show_status() {
    echo "📊 Service Status:"
    echo "  FastAPI Backend:"
    systemctl --user status foscam-webui --no-pager --lines=3 | grep -E "(Active|Main PID)" || echo "    Not running"
    
    echo "  Nginx:"
    if [ -f logs/nginx.pid ] && kill -0 $(cat logs/nginx.pid) 2>/dev/null; then
        echo "    Active: active (running) since $(date)"
        echo "    Main PID: $(cat logs/nginx.pid)"
    else
        echo "    Not running"
    fi
    echo ""
}

# Main execution
check_ports
stop_services
sleep 3
check_ports

if start_services; then
    echo ""
    echo "✅ Foscam Web UI with Nginx restart complete!"
    echo ""
    echo "🌐 Access Points:"
    echo "  Main Dashboard: http://localhost:8000 (Nginx)"
    echo "  Direct Backend: http://localhost:7999 (FastAPI)"
    echo ""
    echo "📋 Log Files:"
    echo "  Nginx Access: $(pwd)/logs/nginx_access.log"
    echo "  Nginx Error:  $(pwd)/logs/nginx_error.log"
    echo "  Backend:      journalctl --user -u foscam-webui -f"
    echo ""
    show_status
else
    echo "❌ Failed to start services"
    echo "📋 Error logs:"
    journalctl --user -u foscam-webui --no-pager --lines=5
    if [ -f logs/nginx_error.log ]; then
        echo "Nginx errors:"
        tail -5 logs/nginx_error.log
    fi
    exit 1
fi

echo "🛠️  Useful commands:"
echo "  View backend logs: journalctl --user -u foscam-webui -f"
echo "  View nginx logs:   tail -f logs/nginx_access.log"
echo "  Stop services:     nginx -s quit -e /home/msvoboda/foscam/logs/nginx_error.log -c $(pwd)/nginx.conf && systemctl --user stop foscam-webui"
echo "  Reload nginx:      nginx -s reload -e /home/msvoboda/foscam/logs/nginx_error.log -c $(pwd)/nginx.conf" 