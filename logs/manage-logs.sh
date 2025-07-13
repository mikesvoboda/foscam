#!/bin/bash

# Foscam Log Management Script
# Provides easy commands to view and manage logs

LOGS_DIR="/home/msvoboda/foscam/logs"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

show_help() {
    echo "🗂️ Foscam Log Management"
    echo "========================"
    echo ""
    echo "Usage: $0 <command> [options]"
    echo ""
    echo "Commands:"
    echo "  status     - Show log file status and sizes"
    echo "  tail       - Follow logs in real-time (default: webui)"
    echo "  view       - View recent log entries"
    echo "  errors     - Show recent errors across all logs"
    echo "  clean      - Clean up old logs manually"
    echo "  rotate     - Manually rotate logs"
    echo "  stats      - Show detailed log statistics"
    echo ""
    echo "Log Types:"
    echo "  webui      - Web UI application logs"
    echo "  crawler    - File crawler logs"
    echo "  monitor    - File monitor logs"
    echo "  access     - HTTP access logs"
    echo "  error      - Error logs only"
    echo "  systemd    - Systemd service logs"
    echo ""
    echo "Examples:"
    echo "  $0 tail webui           # Follow web UI logs"
    echo "  $0 view crawler 50      # View last 50 crawler log entries"
    echo "  $0 errors              # Show recent errors"
    echo "  $0 stats               # Show log statistics"
}

show_status() {
    echo "📊 Foscam Log Status"
    echo "===================="
    echo ""
    
    if [ ! -d "$LOGS_DIR" ]; then
        echo -e "${RED}❌ Logs directory not found: $LOGS_DIR${NC}"
        echo "Run './setup-logging.sh' to initialize logging"
        return 1
    fi
    
    echo -e "${BLUE}📁 Directory: $LOGS_DIR${NC}"
    echo ""
    
    # Show log files with sizes and modification times
    echo "Log Files:"
    printf "%-25s %-10s %-20s %s\n" "File" "Size" "Modified" "Status"
    echo "----------------------------------------------------------------"
    
    for log_file in "$LOGS_DIR"/*.log; do
        if [ -f "$log_file" ]; then
            filename=$(basename "$log_file")
            size=$(du -h "$log_file" | cut -f1)
            modified=$(stat -c %y "$log_file" | cut -d' ' -f1-2 | cut -d'.' -f1)
            
            # Check if file has recent activity (last 24 hours)
            if [ $(find "$log_file" -mtime -1 | wc -l) -eq 1 ]; then
                status="${GREEN}Active${NC}"
            else
                status="${YELLOW}Inactive${NC}"
            fi
            
            printf "%-25s %-10s %-20s %s\n" "$filename" "$size" "$modified" "$status"
        fi
    done
    
    echo ""
    
    # Show compressed logs
    compressed_logs=$(find "$LOGS_DIR" -name "*.gz" 2>/dev/null | wc -l)
    total_size=$(du -sh "$LOGS_DIR" 2>/dev/null | cut -f1)
    
    echo "Summary:"
    echo "  Active log files: $(ls -1 "$LOGS_DIR"/*.log 2>/dev/null | wc -l)"
    echo "  Compressed logs: $compressed_logs"
    echo "  Total size: $total_size"
}

tail_logs() {
    local log_type=${1:-webui}
    local log_file="$LOGS_DIR/${log_type}.log"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}❌ Log file not found: $log_file${NC}"
        echo "Available logs:"
        ls -1 "$LOGS_DIR"/*.log 2>/dev/null | xargs -n1 basename | sed 's/.log$//' | sed 's/^/  /'
        return 1
    fi
    
    echo -e "${GREEN}📜 Following $log_type logs (Ctrl+C to stop)${NC}"
    echo "================================================================"
    tail -f "$log_file"
}

view_logs() {
    local log_type=${1:-webui}
    local lines=${2:-20}
    local log_file="$LOGS_DIR/${log_type}.log"
    
    if [ ! -f "$log_file" ]; then
        echo -e "${RED}❌ Log file not found: $log_file${NC}"
        return 1
    fi
    
    echo -e "${GREEN}📜 Last $lines entries from $log_type logs${NC}"
    echo "================================================================"
    tail -n "$lines" "$log_file"
}

show_errors() {
    echo -e "${RED}🚨 Recent Errors (Last 50 entries)${NC}"
    echo "=================================="
    
    # Combine all error logs and show recent errors
    find "$LOGS_DIR" -name "*error.log" -exec tail -n 20 {} \; 2>/dev/null | \
        grep -E "(ERROR|CRITICAL|Exception|Traceback)" | \
        tail -n 50
    
    # Also check main logs for errors
    echo ""
    echo "Errors from main logs:"
    find "$LOGS_DIR" -name "*.log" ! -name "*error.log" -exec grep -l "ERROR\|Exception" {} \; 2>/dev/null | \
        while read log_file; do
            echo "  $(basename "$log_file"):"
            grep "ERROR\|Exception" "$log_file" | tail -n 5 | sed 's/^/    /'
        done
}

clean_logs() {
    echo "🧹 Cleaning up old logs..."
    
    # Run the cleanup script
    if [ -f "/home/msvoboda/foscam/cleanup-old-logs.sh" ]; then
        /home/msvoboda/foscam/cleanup-old-logs.sh
        echo "✅ Cleanup completed"
    else
        echo -e "${YELLOW}⚠️  Cleanup script not found${NC}"
        echo "Manually removing files older than 30 days..."
        find "$LOGS_DIR" -name "*.gz" -type f -mtime +30 -delete
        find "$LOGS_DIR" -name "*.log.*" -type f -mtime +30 -delete
        echo "✅ Manual cleanup completed"
    fi
    
    show_status
}

rotate_logs() {
    echo "🔄 Manually rotating logs..."
    
    if [ -f "/home/msvoboda/foscam/run-logrotate.sh" ]; then
        /home/msvoboda/foscam/run-logrotate.sh
        echo "✅ Log rotation completed"
    else
        echo -e "${RED}❌ Logrotate script not found${NC}"
        echo "Run './setup-logging.sh' to set up log rotation"
        return 1
    fi
}

show_stats() {
    echo "📈 Detailed Log Statistics"
    echo "=========================="
    
    # Use the Python logging config to get stats
    if [ -f "logging_config.py" ]; then
        cd /home/msvoboda/foscam
        python logging_config.py
    else
        echo -e "${YELLOW}⚠️  Logging configuration not found${NC}"
        show_status
    fi
}

# Main command handling
case "${1:-help}" in
    "status")
        show_status
        ;;
    "tail")
        tail_logs "$2"
        ;;
    "view")
        view_logs "$2" "$3"
        ;;
    "errors")
        show_errors
        ;;
    "clean")
        clean_logs
        ;;
    "rotate")
        rotate_logs
        ;;
    "stats")
        show_stats
        ;;
    "help"|*)
        show_help
        ;;
esac 