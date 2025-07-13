#!/bin/bash

# Camera Detection System with AI Analysis - Foscam Edition
# Enhanced startup script with T5-XL model support

echo "🎥 Starting Foscam Camera Detection System with AI Analysis..."
echo "=============================================================="

# Check if running in virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
else
    echo "⚠️  No virtual environment detected. Consider using one:"
    echo "    python -m venv venv"
    echo "    source venv/bin/activate"
    echo ""
fi

# Check Python version
python_version=$(python --version 2>&1 | awk '{print $2}')
echo "🐍 Python version: $python_version"

# Check for CUDA availability
echo "🔍 Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    echo "✅ NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,memory.used --format=csv,noheader,nounits | head -1
    
    # Check GPU memory
    gpu_memory=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
    echo "💾 GPU Memory: ${gpu_memory}MB"
    
    if [ "$gpu_memory" -lt 16384 ]; then
        echo "⚠️  WARNING: GPU has less than 16GB memory. T5-XL model may run slowly."
        echo "    Consider using a smaller model or enabling more aggressive quantization."
    fi
else
    echo "⚠️  No NVIDIA GPU detected. Will run on CPU (very slow)."
fi

# Check if foscam directory exists
if [ ! -d "foscam" ]; then
    echo "❌ Foscam directory not found!"
    echo "   Please ensure your foscam data is in the 'foscam' directory"
    echo "   Expected structure: foscam/camera_location/device_name/snap|record/"
    exit 1
fi

# Count foscam cameras
camera_count=$(find foscam -maxdepth 2 -type d -name "FoscamCamera_*" -o -name "R2_*" -o -name "R2C_*" | wc -l)
echo "📷 Found $camera_count foscam camera devices"

# Check for existing database
if [ -f "foscam_detections.db" ]; then
    echo "📊 Existing database found: foscam_detections.db"
else
    echo "🆕 Will create new database: foscam_detections.db"
fi

# Model configuration
echo ""
echo "🤖 AI Model Configuration:"
echo "   Model: Salesforce/blip2-t5-xl (T5-XL)"
echo "   Expected VRAM: 18-22GB"
echo "   Features: 5-aspect analysis, structured output, enhanced alerts"
echo ""

# Parse command line arguments
CRAWLER_MODE=false
MONITOR_MODE=false
WEB_MODE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --crawler)
            CRAWLER_MODE=true
            shift
            ;;
        --monitor)
            MONITOR_MODE=true
            shift
            ;;
        --web)
            WEB_MODE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --crawler   Run foscam directory crawler to process existing files"
            echo "  --monitor   Run file monitor to watch for new files"
            echo "  --web       Run web dashboard only"
            echo "  --help      Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --crawler     # Process all existing foscam files"
            echo "  $0 --monitor     # Monitor for new files"
            echo "  $0 --web         # Start web dashboard"
            echo "  $0               # Interactive mode (choose what to run)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Interactive mode if no arguments provided
if [ "$CRAWLER_MODE" = false ] && [ "$MONITOR_MODE" = false ] && [ "$WEB_MODE" = false ]; then
    echo "Choose what to run:"
    echo "1) Crawler - Process existing foscam files"
    echo "2) Monitor - Watch for new files"
    echo "3) Web Dashboard - View results"
    echo "4) All - Run crawler first, then monitor + web"
    echo ""
    read -p "Enter your choice (1-4): " choice
    
    case $choice in
        1)
            CRAWLER_MODE=true
            ;;
        2)
            MONITOR_MODE=true
            ;;
        3)
            WEB_MODE=true
            ;;
        4)
            CRAWLER_MODE=true
            MONITOR_MODE=true
            WEB_MODE=true
            ;;
        *)
            echo "Invalid choice. Running monitor mode by default."
            MONITOR_MODE=true
            ;;
    esac
fi

# Install/check dependencies
echo "📦 Checking dependencies..."
if ! python -c "import torch, transformers, fastapi" 2>/dev/null; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    
    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies!"
        exit 1
    fi
fi

echo "✅ Dependencies OK"
echo ""

# Function to run crawler
run_crawler() {
    echo "🔍 Starting Foscam Directory Crawler..."
    echo "This will process all existing foscam files with AI analysis."
    echo ""
    python foscam_crawler.py
}

# Function to run monitor
run_monitor() {
    echo "👁️  Starting Foscam File Monitor..."
    echo "This will watch for new files and process them in real-time."
    echo ""
    python file_monitor.py
}

# Function to run web dashboard
run_web() {
    echo "🌐 Starting Web Dashboard..."
    echo "Access the dashboard at: http://localhost:8000"
    echo ""
    python web_app.py
}

# Execute based on mode
if [ "$WEB_MODE" = true ] && [ "$MONITOR_MODE" = false ] && [ "$CRAWLER_MODE" = false ]; then
    # Web only mode
    run_web
elif [ "$CRAWLER_MODE" = true ]; then
    # Run crawler first
    run_crawler
    
    if [ "$MONITOR_MODE" = true ] || [ "$WEB_MODE" = true ]; then
        echo ""
        echo "📊 Crawler completed. Starting additional services..."
        echo ""
        
        # Start monitor and web in background if requested
        if [ "$MONITOR_MODE" = true ]; then
            echo "Starting file monitor in background..."
            python file_monitor.py &
            MONITOR_PID=$!
        fi
        
        if [ "$WEB_MODE" = true ]; then
            echo "Starting web dashboard..."
            python web_app.py &
            WEB_PID=$!
        fi
        
        # Wait for processes
        if [ "$MONITOR_MODE" = true ] && [ "$WEB_MODE" = true ]; then
            echo "✅ All services started!"
            echo "   📊 Web Dashboard: http://localhost:8000"
            echo "   👁️  File Monitor: Running in background"
            echo ""
            echo "Press Ctrl+C to stop all services"
            wait
        elif [ "$MONITOR_MODE" = true ]; then
            wait $MONITOR_PID
        elif [ "$WEB_MODE" = true ]; then
            wait $WEB_PID
        fi
    fi
elif [ "$MONITOR_MODE" = true ] && [ "$WEB_MODE" = false ]; then
    # Monitor only mode
    run_monitor
else
    # Default: run monitor
    run_monitor
fi

echo ""
echo "🏁 Foscam Camera Detection System stopped" 