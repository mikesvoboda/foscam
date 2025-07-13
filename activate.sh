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
echo "  python src/foscam_crawler.py     - Run batch processing of existing media"
echo "  python src/file_monitor.py       - Run real-time file monitoring"
echo "  python src/web_app.py            - Start web dashboard"
echo "  python tests/test_foscam_setup.py  - Test system setup"
echo ""
echo "To deactivate: deactivate"
echo "" 