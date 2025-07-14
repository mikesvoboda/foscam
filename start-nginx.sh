#!/bin/bash

# Foscam Dashboard Nginx Startup Script
echo "🌐 Starting Nginx for Foscam Dashboard..."

# Check if nginx is installed
if ! command -v nginx &> /dev/null; then
    echo "❌ Nginx is not installed. Install with: sudo dnf install nginx"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Stop any existing nginx processes using our config
echo "🛑 Stopping any existing nginx processes..."
if [ -f logs/nginx.pid ]; then
    nginx -s quit -c $(pwd)/nginx.conf 2>/dev/null || true
    sleep 2
fi

# Kill any nginx processes that might be hanging
pkill -f "nginx.*$(pwd)" 2>/dev/null || true

# Test the nginx configuration
echo "🔍 Testing nginx configuration..."
nginx -t -c $(pwd)/nginx.conf

if [ $? -ne 0 ]; then
    echo "❌ Nginx configuration test failed!"
    exit 1
fi

# Start nginx
echo "🚀 Starting nginx..."
nginx -c $(pwd)/nginx.conf

if [ $? -eq 0 ]; then
    echo "✅ Nginx started successfully!"
    echo "📊 Dashboard available at: http://localhost:8080"
    echo "📊 Backend still running at: http://localhost:8000"
    echo ""
    echo "📋 Log files:"
    echo "  Access: $(pwd)/logs/nginx_access.log"
    echo "  Error:  $(pwd)/logs/nginx_error.log"
    echo ""
    echo "🛠️  Commands:"
    echo "  Stop:   nginx -s quit -c $(pwd)/nginx.conf"
    echo "  Reload: nginx -s reload -c $(pwd)/nginx.conf"
    echo "  Logs:   tail -f $(pwd)/logs/nginx_access.log"
else
    echo "❌ Failed to start nginx!"
    exit 1
fi 