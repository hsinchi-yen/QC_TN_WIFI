#!/bin/bash

#################################################################################
# Copyright 2020 Technexion Ltd.
#
# Author: Ray Chang <ray.chang@technexion.com>
# Modified: Refactored to test both 5G and 2.4G bands with 3 attempts each
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#################################################################################
# date: 2025-12-04
# update optimized the wlan0 interface up time for descreased test time
#################################################################################
# date: 2025-12-06
# update: Enhanced parameter control and help system
# - Added comprehensive help system (-h/--help)
# - Added configurable iperf display interval (-i/--interval: 1, 5, or 10 seconds)
# - Enhanced duration parameter control (-d/--duration: l1/l2/l3 or custom seconds)
# - Added WiFi connection status display before each test attempt
# - Added RSSI monitoring before and after each test
# - Replaced hardcoded wlan0 with dynamic $IFACE variable for multi-driver support
# - Changed iperf output format from KBits/sec to MBits/sec (-f m)
# - Added support for fixed IP configuration and DHCP fallback
# - Improved error handling and user feedback
#################################################################################

# Function to check wlan0 interface availability
check_wlan0_interface() {
    echo "Checking wlan0 interface availability..."
    local timeout=10
    local count=0
    
    # Determine WiFi device and driver
    if [ -f /sys/bus/mmc/devices/mmc?\:0001/mmc?\:0001\:1/device ]; then
                    WIFI_DEV=$(cat /sys/bus/mmc/devices/mmc?\:0001/mmc?\:0001\:1/device)
    fi

    if [ "${WIFI_DEV}" = "0x0701" ] ;then
            WIFI_DRV=wlan
            IFACE=wlan0
    elif [ "${WIFI_DEV}" = "0x9159" ] ||[ "${WIFI_DEV}" = "0x0205" ] ;then
            WIFI_DRV=mlan
            IFACE=mlan0
            WPADRI='-Dnl80211'
    else
                WIFI_DRV=bcmdhd
                IFACE=wlan0
    fi
    
    if [ ifconfig $IFACE >/dev/null 2>&1 ]; then
        echo "$IFACE interface is already available."
        return 0
    else
        echo "$IFACE interface not found. Loading driver: $WIFI_DRV"
        modprobe $WIFI_DRV
    fi
    
    while [ $count -lt $timeout ]; do
        if ifconfig $IFACE >/dev/null 2>&1; then
            echo "$IFACE interface is available."
            return 0
        fi
        
        echo "Waiting for $IFACE interface... ($((count + 1))/$timeout seconds)"
        sleep 1
        count=$((count + 1))
    done
    
    # wlan0 interface not found after timeout
    echo ""
    echo "================================================"
    echo "ERROR: $IFACE interface is not up"
    echo "================================================"
    echo "$IFACE interface was not detected after $timeout seconds."
    echo ""
    echo "Diagnostic information:"
    echo "----------------------------------------"
    echo "dmesg output (mmc|wlan|qca related):"
    dmesg | grep -iE "mmc|wlan|qca|sdio|bluetooth|mlan"
    echo "----------------------------------------"
    echo ""
    echo "Test suspended. Please check hardware connections and driver status."
    echo "================================================"
    
    return 1
}

# Function to stop existing processes (from stop.sh)
stop_existing_processes() {
    echo "Stopping existing processes..."
    # Stop existing processes
    skill qcgui launchgui.sh fbcopy.sh 2>/dev/null || true
    skill Xfbdev startx.sh 2>/dev/null || true
    
    sleep 1
    skill -9 qcgui launchgui.sh 2>/dev/null || true
    echo "Existing processes stopped."
}

# Function to display help
show_help() {
    echo "WiFi Throughput Test Script"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  -h, --help              Show this help message"
    echo "  -d, --duration LEVEL    Set test duration level or custom seconds"
    echo "                          l0 = 10 seconds"
    echo "                          l1 = 30 seconds"
    echo "                          l2 = 120 seconds (default)"
    echo "                          l3 = 180 seconds"
    echo "                          <number> = custom duration in seconds"
    echo "  -i, --interval SECONDS  Set iperf display interval (1, 5, or 10)"
    echo "                          Default: 5 seconds"
    echo "  -c, --channel PRIORITY  Set WiFi band test priority"
    echo "                          ax = Test 5G band first (default)"
    echo "                          bgn = Test 2.4G band first"
    echo ""
    echo "TEST LEVELS:"
    echo "  l0 (10s)  : Rapid check test"
    echo "  l1 (30s)  : Quick verification test"
    echo "  l2 (120s) : Standard validation test (default)"
    echo "  l3 (180s) : Extended stress test"
    echo "  Custom    : Any duration in seconds (e.g., 60, 300, 3600)"
    echo ""
    echo "BAND PRIORITY:"
    echo "  ax (default) : Test 5G band first, then 2.4G band"
    echo "  bgn          : Test 2.4G band first, then 5G band"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                      # Use defaults (l2 duration, 5s interval, ax priority)"
    echo "  $0 -d l0               # Use 10s duration, 5s interval, ax priority"
    echo "  $0 -d l1 -c bgn        # Use 30s duration, test 2.4G first"
    echo "  $0 -d l3 -i 10 -c ax   # Use 180s duration, 10s interval, 5G first"
    echo "  $0 -c bgn              # Use default duration, test 2.4G first"
    echo "  $0 -d 90 -c ax         # Use 90s duration, test 5G first"
    echo ""
    exit 0
}

# Parse command line parameters
IPERF_DURATION=120  # Default to l2 (120 seconds)
IPERF_INTERVAL=5    # Default interval
BAND_PRIORITY="ax"  # Default to 5G first

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            ;;
        -d|--duration)
            if [ -z "$2" ]; then
                echo "Error: Duration parameter requires a value"
                echo "Use -h for help"
                exit 1
            fi
            case "$2" in
                "l0")
                    IPERF_DURATION=10
                    echo "Using level 0 duration: 10 seconds"
                    ;;
                "l1")
                    IPERF_DURATION=30
                    echo "Using level 1 duration: 30 seconds"
                    ;;
                "l2")
                    IPERF_DURATION=120
                    echo "Using level 2 duration: 120 seconds"
                    ;;
                "l3")
                    IPERF_DURATION=180
                    echo "Using level 3 duration: 180 seconds"
                    ;;
                *)
                    if [[ "$2" =~ ^[0-9]+$ ]]; then
                        IPERF_DURATION=$2
                        echo "Using custom duration: $2 seconds"
                    else
                        echo "Error: Invalid duration parameter: $2"
                        echo "Valid options: l0, l1, l2, l3, or a number"
                        echo "Use -h for help"
                        exit 1
                    fi
                    ;;
            esac
            shift 2
            ;;
        -i|--interval)
            if [ -z "$2" ]; then
                echo "Error: Interval parameter requires a value"
                echo "Use -h for help"
                exit 1
            fi
            case "$2" in
                "1"|"5"|"10")
                    IPERF_INTERVAL=$2
                    echo "Using display interval: $2 seconds"
                    ;;
                *)
                    echo "Error: Invalid interval parameter: $2"
                    echo "Valid options: 1, 5, or 10"
                    echo "Use -h for help"
                    exit 1
                    ;;
            esac
            shift 2
            ;;
        -c|--channel)
            if [ -z "$2" ]; then
                echo "Error: Channel priority parameter requires a value"
                echo "Use -h for help"
                exit 1
            fi
            case "$2" in
                "ax")
                    BAND_PRIORITY="ax"
                    echo "Using band priority: 5G first (ax)"
                    ;;
                "bgn")
                    BAND_PRIORITY="bgn"
                    echo "Using band priority: 2.4G first (bgn)"
                    ;;
                *)
                    echo "Error: Invalid channel priority parameter: $2"
                    echo "Valid options: ax, bgn"
                    echo "Use -h for help"
                    exit 1
                    ;;
            esac
            shift 2
            ;;
        *)
            echo "Error: Unknown parameter: $1"
            echo "Use -h for help"
            exit 1
            ;;
    esac
done

# Show current configuration
echo "Test Configuration:"
echo "  Duration: $IPERF_DURATION seconds"
echo "  Display Interval: $IPERF_INTERVAL seconds"
echo "  Band Priority: $BAND_PRIORITY ($([ "$BAND_PRIORITY" = "ax" ] && echo "5G first" || echo "2.4G first"))"
echo ""

CPUBURN=no
RETRY=no
IPERF_SERVER=192.168.200.2
IPERF_PORT_5G=5001    # Port for 5G band tests
IPERF_PORT_24G=5002   # Port for 2.4G band tests
WIFI_DRV=wlan
IFACE=wlan0
#NETWORK_MANAGER=connmanctl

# Test configuration
WIFI_5G_CONF="wifi5g.conf"
WIFI_24G_CONF="wifi24g.conf"
THROUGHPUT_5G_LIMIT=50  # 50M for 5G band
THROUGHPUT_24G_LIMIT=10 # 15M for 2.4G band
MAX_ATTEMPTS=3

# Global variables
CURRENT_BAND=""
CURRENT_THROUGHPUT_LIMIT=0

PLATFORM=$(tr </sys/firmware/devicetree/base/model '[:upper:]' '[:lower:]')
case "$PLATFORM" in
*"8m "*|*imx8mq*|*imx6ull*|*imx6*|*imx7*)
        WPADRI='-Dnl80211'
        ;;
esac

is_ap_connected() {
        if [ "$IFACE" = "wlan0" ]; then
                getlink=$(iwconfig $IFACE | grep -qE 'Link Quality|Security mode|..:..:..:..:..:..' && echo 1 || echo 0)
        else
                getlink=$(cat /proc/net/wireless | grep -E ".\.|mlan0" | awk '{print$3}' | cut -d. -f1)
        fi
        if [ $getlink -eq 0 ]; then
                pid=$(ps | grep "wpa_supplicant" | grep -v "grep" | awk '{print $1}')
                [ -n "$pid" ] && kill $pid > /dev/null 2>&1
                for n in $(seq 1 2); do
                        if [ ${#OTHERIF[@]} -gt 0 -a -n "${OTHERIF[0]}" ]; then
                                while ( ifconfig | grep -q ${OTHERIF[0]} ); do
                                        usleep 300000
                                done
                        fi
                        ifconfig $IFACE up > /dev/null 2>&1
                        usleep 100000
                        # Suppress all wpa_supplicant output including debug messages
                        wpa_supplicant ${WPADRI} -i $IFACE -c $1 -B -q >/dev/null 2>&1
                        for i in $(seq 1 15); do
                                if [ "$IFACE" = "wlan0" ]; then
                                        getlink=$(iwconfig $IFACE | grep -qE 'Link Quality|Security mode|..:..:..:..:..:..' && echo 1 || echo 0)
                                else
                                        getlink=$(cat /proc/net/wireless | grep -E ".\.|mlan0" | awk '{print$3}' | cut -d. -f1)
                                fi
                                if [ $getlink -ne 0 ]; then
                                        return 0
                                else
                                        sleep 1
                                fi
                                usleep 500
                        done
                        disconnect
                done
                return 1
        else
                return 0
        fi
}

disconnect() {
        pid1=$(ps | grep "wpa_supplicant" | grep -v "grep" | awk '{print $1}')
        [ -n "$pid1" ] && kill $pid1 > /dev/null 2>&1
        if ( ifconfig -a | awk '{print $1}' | grep -q $IFACE ); then
                usleep 300000
                ifconfig $IFACE down
        fi
        sleep 1
}

getipaddr() {
        echo $(ifconfig $IFACE | grep inet | cut -d ':' -f2 | cut -d ' ' -f1)
}

is_ipget() {
        for i in $(seq 1 20); do
                ipaddr=$(getipaddr)
                [ -n "$ipaddr" ] && return 0
                udhcpc -qi $IFACE >/dev/null 2>&1 &
                local dhcp_pid=$!
                sleep 0.5
                kill $dhcp_pid >/dev/null 2>&1
        done
        return 1
}

led_on() {
        if [ -f /sys/class/leds/status/brightness ]; then
                echo 1 >/sys/class/leds/status/brightness
        elif [ -f /sys/class/leds/gpio-led/brightness ]; then
                echo 1 >/sys/class/leds/gpio-led/brightness
        fi
}

led_off() {
        if [ -f /sys/class/leds/status/brightness ]; then
                echo 0 >/sys/class/leds/status/brightness
        elif [ -f /sys/class/leds/gpio-led/brightness ]; then
                echo 0 >/sys/class/leds/gpio-led/brightness
        fi
}

led_blink() {
        while true; do
                led_on
                usleep 150000
                led_off
                usleep 150000
        done
}

# Display wifi connection information
display_wifi_info() {
        local config_file=$1
        local band=$2
        local threshold=$3
        
        echo "========================================"
        echo "WiFi Connection Information - $band Band"
        echo "========================================"
        echo "Configuration File: $config_file"
        echo "Throughput Threshold: $threshold MBits/sec"
        echo "Iperf Test Duration: $IPERF_DURATION seconds"
        echo "Iperf Display Interval: $IPERF_INTERVAL seconds"
        
        # Extract SSID from config file
        local ssid=$(grep "ssid=" "$config_file" | cut -d'"' -f2)
        echo "Target SSID: $ssid"
        
        echo "========================================"
}

# Get RSSI value from $IFACE interface
get_rssi() {
        local rssi_output=$(iwpriv $IFACE getRSSI 2>/dev/null)
        if [ -n "$rssi_output" ]; then
                local rssi_value=$(echo "$rssi_output" | grep -o 'rssi=-[0-9]*' | cut -d'=' -f2)
                if [ -n "$rssi_value" ]; then
                        echo "$rssi_value"
                else
                        echo "N/A"
                fi
        else
                echo "N/A"
        fi
}

# Perform a single throughput test
perform_single_test() {
        local attempt=$1
        local iperf_port=$2  # Add port parameter
        
        echo "  Attempt $attempt: Preparing iperf test ($IPERF_DURATION seconds)..."
        echo "  Using iperf server port: $iperf_port"
        
        # Display WiFi connection status before test
        echo "  WiFi Connection Status:"
        iwconfig $IFACE 2>/dev/null | grep -E "ESSID|Frequency|Bit Rate|Link Quality|Signal level" | sed 's/^/    /'
        
        # Get and display RSSI before test
        local rssi=$(get_rssi)
        echo "    RSSI: ${rssi} dBm"
        echo ""
        
        echo "  Starting iperf test now..."
        
        # Run iperf test with configurable duration and port
        iperf -c "$IPERF_SERVER" -p "$iperf_port" -f m -t $IPERF_DURATION -i $IPERF_INTERVAL -P 3 -w 128k -l 24000 | tee /tmp/iperflog 2>&1
        sleep 0.5
        sync
        sleep 0.5
        
        # Get RSSI after test for comparison
        local rssi_after=$(get_rssi)
        
        # Extract throughput result with error handling for abnormal patterns
        # First attempt: last 3 lines
        local throughput=$(tail -n3 </tmp/iperflog | grep SUM | tail -1 | awk '{printf("%d",$6)}' 2>/dev/null)
        
        # If extraction fails or gets 0, try searching more lines (abnormal pattern)
        if [ -z "$throughput" ] || [ "$throughput" -eq 0 ]; then
                echo "    Warning: Initial extraction failed, searching more lines for [SUM] pattern..."
                # Try last 10 lines
                throughput=$(tail -n10 </tmp/iperflog | grep SUM | tail -1 | awk '{printf("%d",$6)}' 2>/dev/null)
                
                if [ -z "$throughput" ] || [ "$throughput" -eq 0 ]; then
                        echo "    Warning: Still no valid data, searching last 20 lines..."
                        # Try last 20 lines
                        throughput=$(tail -n20 </tmp/iperflog | grep SUM | tail -1 | awk '{printf("%d",$6)}' 2>/dev/null)
                        
                        if [ -z "$throughput" ] || [ "$throughput" -eq 0 ]; then
                                echo "    Warning: Searching entire log for last [SUM] entry..."
                                # Final attempt: search entire log
                                throughput=$(grep SUM </tmp/iperflog | tail -1 | awk '{printf("%d",$6)}' 2>/dev/null)
                        fi
                fi
        fi
        
        # Handle case where throughput extraction completely fails
        if [ -z "$throughput" ] || [ "$throughput" -eq 0 ]; then
                echo "    Result: FAILED (No valid throughput data after multiple attempts) - RSSI after test: ${rssi_after} dBm"
                echo "    Debug: Last 20 lines of iperf log:"
                tail -n20 </tmp/iperflog | sed 's/^/      /'
                return 1
        fi
        
        # Check if throughput meets threshold
        if [ "$throughput" -ge "$CURRENT_THROUGHPUT_LIMIT" ]; then
                echo "    Result: PASSED ($throughput MBits/sec >= $CURRENT_THROUGHPUT_LIMIT MBits/sec) - RSSI after test: ${rssi_after} dBm"
                return 0
        else
                echo "    Result: FAILED ($throughput MBits/sec < $CURRENT_THROUGHPUT_LIMIT MBits/sec) - RSSI after test: ${rssi_after} dBm"
                return 1
        fi
}

# Test a specific band with 2 attempts
test_band() {
        local config_file=$1
        local band=$2
        local threshold=$3
        local iperf_port=$4  # Add port parameter
        
        CURRENT_BAND=$band
        CURRENT_THROUGHPUT_LIMIT=$threshold
        
        echo ""
        echo "=========================================="
        echo "Starting $band Band Test"
        echo "=========================================="
        
        # Display connection info before testing
        display_wifi_info "$config_file" "$band" "$threshold"
        
        # Disconnect any existing connection
        disconnect
        
        
        # Connect to the AP
        echo "Connecting to $band band WiFi..."
        if ( is_ap_connected "$config_file" ); then
                if ( is_ipget ); then
                        echo "Connected successfully. IP address: $(getipaddr)"
                        
                        # Wait for driver to properly update connection information
                        echo "Waiting for connection to stabilize..."
                        sleep 0.5
                        
                        # Display updated connection info
                        #echo ""
                        #echo "Connection established:"
                        #iwconfig $IFACE 2>/dev/null | grep -E "ESSID|Frequency|Bit Rate|Link Quality|Signal level"
                        #echo ""
                        
                        # Perform up to 3 throughput tests (early exit on first pass)
                        local passed_tests=0
                        local failed_tests=0
                        local test_passed=0
                        
                        echo "Performing throughput tests (up to $MAX_ATTEMPTS attempts, early exit on pass):"
                        for attempt in $(seq 1 $MAX_ATTEMPTS); do
                                if perform_single_test $attempt $iperf_port; then
                                        passed_tests=$((passed_tests + 1))
                                        test_passed=1
                                        echo "  Test passed on attempt $attempt - skipping remaining attempts"
                                        break  # Exit early on first pass
                                else
                                        failed_tests=$((failed_tests + 1))
                                        if [ $attempt -lt $MAX_ATTEMPTS ]; then
                                                echo "  Attempt $attempt failed - reconnecting WiFi for next attempt"
                                                echo "  Disconnecting from $band band..."
                                                disconnect
                                                sleep 2
                                                
                                                echo "  Reconnecting to $band band..."
                                                if ( is_ap_connected "$config_file" ); then
                                                        if ( is_ipget ); then
                                                                echo "  Reconnected successfully. IP address: $(getipaddr)"
                                                                sleep 1
                                                        else
                                                                echo "  ERROR: Failed to get IP address after reconnection"
                                                                echo "  Continuing to next attempt anyway..."
                                                                sleep 1
                                                        fi
                                                else
                                                        echo "  ERROR: Failed to reconnect to WiFi"
                                                        echo "  Continuing to next attempt anyway..."
                                                        sleep 1
                                                fi
                                        fi
                                fi
                        done
                        
                        # Display final WiFi connection status
                        echo ""
                        echo "Final WiFi Connection Status:"
                        iwconfig $IFACE 2>/dev/null | grep -E "ESSID|Frequency|Bit Rate|Link Quality|Signal level"
                        
                        # Evaluate results
                        echo ""
                        echo "Test Summary for $band Band:"
                        echo "  Passed: $passed_tests"
                        echo "  Failed: $failed_tests"
                        echo "  Total Attempts: $((passed_tests + failed_tests))"
                        
                        if [ $test_passed -eq 1 ]; then
                                echo -e "  \033[0;32mOVERALL RESULT: PASSED\033[0m (At least one test met threshold)"
                                return 0
                        else
                                echo -e "  \033[0;31mOVERALL RESULT: FAILED\033[0m (All $MAX_ATTEMPTS attempts failed)"
                                return 1
                        fi
                else
                        echo -e "\033[0;31mERROR: Failed to get IP address for $band band\033[0m"
                        return 1
                fi
        else
                echo -e "\033[0;31mERROR: Failed to connect to $band band WiFi\033[0m"
                return 1
        fi
}

# WiFi reset function to clear previous settings and ensure correct network
reset_wifi_connection() {
        local config_file=$1
        echo "Resetting WiFi connection to ensure clean state..."
        
        # Step 0: Kill existing wpa_supplicant processes
        local wpa_pid=$(ps | grep "wpa_supplicant -B -i $IFACE" | grep -v grep | awk '{print $1}')
        if [ -n "$wpa_pid" ]; then
                echo "Killing existing wpa_supplicant process: $wpa_pid"
                kill $wpa_pid > /dev/null 2>&1
                sleep 1
        fi
        
        # Step 1: Interface down
        echo "Bringing $IFACE interface down..."
        ifconfig $IFACE down
        sleep 1
        # Clear previous IP address and kill any existing udhcpc
        killall -9 udhcpc >/dev/null 2>&1 || true
        udhcpc -qi $IFACE >/dev/null 2>&1 &
        c_ipid=$!
        sleep 1
        kill $c_ipid >/dev/null 2>&1 || true
        
        # Step 2: Interface up
        echo "Bringing $IFACE interface up..."
        ifconfig $IFACE up
        usleep 1000
        
        # Step 3: Reconnect WiFi using existing functions
        echo "Reconnecting to WiFi using configuration: $config_file"
        if ( is_ap_connected "$config_file" ); then
                if ( is_ipget ); then
                        # Step 4: Check if network is in correct range
                        local current_ip=$(getipaddr)
                        if [[ "$current_ip" =~ ^192\.168\.200\.[0-9]+$ ]]; then
                                echo "Successfully connected with correct IP: $current_ip"
                                return 0
                        else
                                echo "ERROR: Connected but IP is not in 192.168.200.x range: $current_ip"
                                return 1
                        fi
                else
                        echo "ERROR: Failed to obtain IP address"
                        return 1
                fi
        else
                echo "ERROR: Failed to connect to WiFi"
                return 1
        fi
}

# Function removed - no longer needed for automated testing

# Main execution
main() {

        # Stop existing processes after interface check
        stop_existing_processes

        # Check wlan0 interface availability first
        if ! check_wlan0_interface; then
                exit 1
        fi
              
        echo ""
        echo "================================================"
        echo "Starting WiFi Validation Test..."
        echo "================================================"

        # Record start time
        local start_time=$(date +%s)
        local start_time_formatted=$(date "+%Y-%m-%d %H:%M:%S")
        
        echo "============================================"
        echo "WiFi Throughput Test Script"
        if [ "$BAND_PRIORITY" = "bgn" ]; then
                echo "Testing order: 2.4G (bgn) first, then 5G (ax)"
        else
                echo "Testing order: 5G (ax) first, then 2.4G (bgn)"
        fi
        echo "Max attempts per band: $MAX_ATTEMPTS"
        echo "Iperf duration: $IPERF_DURATION seconds"
        echo "Iperf interval: $IPERF_INTERVAL seconds"
        echo "============================================"
        
        # Check if configuration files exist
        if [ ! -f "$WIFI_5G_CONF" ]; then
                echo -e "\033[0;31mERROR: $WIFI_5G_CONF not found!\033[0m"
                exit 1
        fi
        
        if [ ! -f "$WIFI_24G_CONF" ]; then
                echo -e "\033[0;31mERROR: $WIFI_24G_CONF not found!\033[0m"
                exit 1
        fi
        
        if [ "$CPUBURN" == "yes" ]; then
                killall stress-ng 2>/dev/null
        fi
        
        led_on
        
        PID_THIS=$$
        echo "PID is: $PID_THIS"
        
        macaddr=$(cat /sys/bus/sdio/devices/*/net/$IFACE/address 2>/dev/null || echo "Unknown")
        mac=${macaddr//:/}
        echo "MAC address: $macaddr"
        
        if [ "$CPUBURN" == "yes" ]; then
                stress-ng -c 0 -l 80 &
        fi
        
        # Check current network and reset if needed
        echo ""
        echo "Checking current network connection..."
        local current_ip=$(getipaddr)
        if [[ ! "$current_ip" =~ ^192\.168\.200\.[0-9]+$ ]]; then
                echo "Current IP ($current_ip) is not in target network range"
                echo "Performing WiFi reset to ensure clean connection..."
                # Use the first test band configuration for initial connection
                local initial_config="$WIFI_5G_CONF"
                if [ "$BAND_PRIORITY" = "bgn" ]; then
                        initial_config="$WIFI_24G_CONF"
                        echo "Using 2.4G configuration for initial connection (bgn priority)"
                else
                        echo "Using 5G configuration for initial connection (ax priority)"
                fi
                if ! reset_wifi_connection "$initial_config"; then
                        echo -e "\033[0;31mERROR: Failed to reset WiFi connection\033[0m"
                        exit 1
                fi
        else
                echo "Current IP ($current_ip) is already in correct network range"
        fi
        
        local overall_result=0
        
        # Test bands based on priority setting
        if [ "$BAND_PRIORITY" = "bgn" ]; then
                # Test 2.4G band first
                echo "Testing 2.4G band first (bgn priority)"
                if test_band "$WIFI_24G_CONF" "2.4G" "$THROUGHPUT_24G_LIMIT" "$IPERF_PORT_24G"; then
                        echo ""
                else
                        overall_result=1
                fi
                
                # Disconnect before testing next band
                disconnect
                sleep 1
                
                # Test 5G band second
                if test_band "$WIFI_5G_CONF" "5G" "$THROUGHPUT_5G_LIMIT" "$IPERF_PORT_5G"; then
                        echo ""
                else
                        overall_result=1
                fi
        else
                # Default: Test 5G band first (ax priority)
                echo "Testing 5G band first (ax priority)"
                if test_band "$WIFI_5G_CONF" "5G" "$THROUGHPUT_5G_LIMIT" "$IPERF_PORT_5G"; then
                        echo ""
                else
                        overall_result=1
                fi
                
                # Disconnect before testing next band
                disconnect
                sleep 1
                
                # Test 2.4G band second
                if test_band "$WIFI_24G_CONF" "2.4G" "$THROUGHPUT_24G_LIMIT" "$IPERF_PORT_24G"; then
                        echo ""
                else
                        overall_result=1
                fi
        fi
        

        
        # Final cleanup
        disconnect
        led_off
        
        # Calculate elapsed time
        local end_time=$(date +%s)
        local end_time_formatted=$(date "+%Y-%m-%d %H:%M:%S")
        local elapsed_seconds=$((end_time - start_time))
        local elapsed_minutes=$((elapsed_seconds / 60))
        local remaining_seconds=$((elapsed_seconds % 60))
        
        # Final results
        echo ""
        echo "================================================"
        echo "WiFi Validation Test Completed"
        echo "================================================"
        echo "Total elapsed time: ${elapsed_minutes}m ${remaining_seconds}s"
        echo ""
        
        if [ $overall_result -eq 0 ]; then
            echo "WiFi Test Result: PASSED"
            echo "All WiFi validation tests completed successfully."
        else
            echo "WiFi Test Result: FAILED"
            echo "One or more WiFi validation tests failed."
            echo "Please check the test output above for details."
        fi
        
        echo "================================================"
        
        exit $overall_result
}

# Run main function
main "$@"