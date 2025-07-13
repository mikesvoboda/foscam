#!/bin/bash
# Foscam AI Monitoring System - Virtual Environment Activation Script

echo "🔧 Activating Foscam AI Monitoring System virtual environment..."
source venv/bin/activate

echo "✅ Virtual environment activated!"
echo "📦 Python version: $(python --version)"
echo "📍 Working directory: $(pwd)"
echo ""
echo "🚀 Ready to run Foscam AI monitoring system!"
echo ""
echo "Available commands:"
echo "  python foscam_crawler.py     - Run batch processing of existing media"
echo "  python file_monitor.py       - Run real-time file monitoring"
echo "  python web_app.py            - Start web dashboard"
echo "  python test_foscam_setup.py  - Test system setup"
echo ""
echo "To deactivate: deactivate"
echo "" 