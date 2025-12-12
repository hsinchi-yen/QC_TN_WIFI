#!/bin/sh

RSSI_LIMIT=-60

# Stop existing processes function
stop_existing_processes() {
    echo "Stopping existing processes..."
    # Stop existing processes
    skill qcgui launchgui.sh fbcopy.sh 2>/dev/null || true
    skill Xfbdev startx.sh 2>/dev/null || true
    
    sleep 1
    skill -9 qcgui launchgui.sh 2>/dev/null || true
    echo "Existing processes stopped."
}

# BT_MAC can be set from external variable or command-line argument
# Usage: BT_MAC=E8:48:B8:C8:20:00 bash bt_ping.sh
#    or: bash bt_ping.sh E8:48:B8:C8:20:00
# If not set, will use scan result
BT_TARGET_MAC=${BT_MAC:-""}
# Check if MAC is provided as command-line argument
if [ -n "$1" ]; then
    BT_TARGET_MAC="$1"
fi

WIFI_DEV=/sys/bus/mmc/devices/mmc?\:0001/mmc?\:0001\:1/device
WIFI_CHIP_ID=$(cat $WIFI_DEV)
platform=$(tr </sys/firmware/devicetree/base/model '[:upper:]' '[:lower:]')
case "$platform" in
*tep1-imx7*|*pico-imx6ul*|*axon-imx6*)      BT_UART_TTY=/dev/ttymxc4 ;;
*pico-imx6*)                                BT_UART_TTY=/dev/ttymxc1 ;;
*edm1-imx6sx*)                              BT_UART_TTY=/dev/ttymxc5 ;;
*pico-imx7*|*edm1-imx7*)                    BT_UART_TTY=/dev/ttymxc6 ;;
*edm1-cf-imx6p*|*edm1-cf-imx6*|*edm1-imx6*) BT_UART_TTY=/dev/ttymxc2 ;;
*"8m "*|*imx8mq*|*sbc-imx6*)                BT_UART_TTY=/dev/ttymxc1; WIFI_CHIP_ID=0x0701 ;;
*edm-g-imx8m[mn]*)                          BT_UART_TTY=/dev/ttymxc2 ;;
*imx8mm*|*imx8mp*)                          BT_UART_TTY=/dev/ttymxc0 ;;
*axon-am62[ax]*)                            BT_UART_TTY=/dev/ttyS1 ;;
*imx93*|*mx91*)                             BT_UART_TTY=/dev/ttyLP4 ;;
esac

is_scanresult() {
        macaddr=$(hcitool -i $1 scan --length=5 | grep -E "..:..:..:..:..:.." | cut -f2)
        if [ -n "$macaddr" ]; then
                echo "${macaddr}"
                return 0
        else
                return 1
        fi
}

if ( ! hciconfig | grep -q UART )
then
        while [ -z "$WIFI_CHIP_ID" ]
        do
                sleep 2
        done

        if [ "$WIFI_CHIP_ID" = "0x9159" ] || [ "$WIFI_CHIP_ID" == "0x0205" ]; then
                IFACE=mlan0
        else
                IFACE=wlan0
        fi

        while ( ! $(ls /sys/class/net/ | grep -q $IFACE) ); do
                sleep 1
        done

        if [ "$WIFI_CHIP_ID" == "0xa9a6" ]; then
                echo Detect wifi chip is AP6212
                brcm_patchram_plus -timeout=6.0 -patchram auto -baudrate 3000000 -no2bytes -tosleep=2000 -enable_hci $BT_UART_TTY &
        elif [ "$WIFI_CHIP_ID" == "0x4335"  ]; then
                echo Detect wifi chip is AP6335
                brcm_patchram_plus -timeout=6.0 -patchram=/lib/firmware/brcm/bcm4339a0.hcd -baudrate 3000000 -no2byte -tosleep=2000 -enable_hci $BT_UART_TTY &
        elif [ "$WIFI_CHIP_ID" == "0x4330"  ]; then
                echo Detect wifi chip is BCM4330
                brcm_patchram_plus -timeout=6.0 -patchram=/lib/firmware/brcm/bcm4330.hcd -baudrate 3000000 -no2byte -tosleep=2000 -enable_hci $BT_UART_TTY &
        elif [ "$WIFI_CHIP_ID" == "0x0701" ]; then
                sleep 1
                hciattach -t 30 $BT_UART_TTY qca 3000000 flow > /dev/null 2>&1
        elif [ "$WIFI_CHIP_ID" == "0x9159" ] || [ "$WIFI_CHIP_ID" == "0x0205" ]; then
                usleep 500000
                hciattach $BT_UART_TTY any 3000000 flow > /dev/null 2>&1
        else
                echo Do not detect valid model of WIFI chip
        fi
fi

dev=0
ok=0

# wait BT interface ready at most 13sec
wait_loop=0
while ( ! hciconfig -a | grep -q UART)
do
        if [ $wait_loop -eq 13 ]
        then
                break
        fi
        sleep 1
        wait_loop=$(expr $wait_loop + 1)
done

hciif=$(hciconfig -a | grep "Bus: UART" | cut -d ':' -f1)
if [ -n "$hciif" ]
then
       # Stop existing processes before BT test
       stop_existing_processes
       
       # Ensure BT device is up
       echo "Checking BT device status..."
       hciconfig $hciif up
       sleep 1
       
       # Verify BT device is up
       bt_status=$(hciconfig $hciif | grep -c "UP RUNNING")
       if [ "$bt_status" -eq 0 ]; then
               echo "Error: BT device failed to come up"
               echo "Bluetooth Test Result: FAILED (Device not ready)"
               exit 1
       fi
       echo "BT device is up and ready"
       
       # Use external BT_MAC if provided, otherwise scan for devices
       if [ -n "$BT_TARGET_MAC" ]; then
                echo "Using external BT MAC: $BT_TARGET_MAC"
                macaddr="$BT_TARGET_MAC"
       else
                echo "Scanning for BT devices..."
                macaddr=$(is_scanresult $hciif)
       fi
       
       if [ -n "$macaddr" ]; then
                # Wait 1 second before starting test
                echo "Target MAC found, waiting 1 second before test..."
                sleep 1
                
                dev=1
                for mac in ${macaddr}; do
                        echo "Testing Bluetooth device: ${mac}"
                        
                        # Perform l2ping test with 3 attempts (no hcitool cc needed)
                        echo "Starting Bluetooth l2ping test (max 3 attempts)..."
                        echo "Target MAC: ${mac}"
                                
                                passed_tests=0
                                failed_tests=0
                                MAX_ATTEMPTS=3
                                
                                for attempt in $(seq 1 $MAX_ATTEMPTS); do
                                        echo ""
                                        echo "Attempt $attempt/$MAX_ATTEMPTS:"
                                        
                                        # Run l2ping and display output while saving to log file
                                        l2ping -c 10 -i 0.5 -s 44 ${mac} | tee /tmp/btpinglog 2>&1
                                        
                                        # Extract statistics from log file
                                        stats=$(grep -E "sent.*received.*loss" /tmp/btpinglog)
                                        echo "L2ping result: $stats"
                                        
                                        # Check for packet loss
                                        if echo "$stats" | grep -q "0% loss"; then
                                                echo "Attempt $attempt: PASSED"
                                                passed_tests=$((passed_tests + 1))
                                                ok=1
                                                echo "Test passed on attempt $attempt - skipping remaining attempts"
                                                break
                                        else
                                                echo "Attempt $attempt: FAILED"
                                                failed_tests=$((failed_tests + 1))
                                                if [ $attempt -lt $MAX_ATTEMPTS ]; then
                                                        echo "Retrying..."
                                                        sleep 1
                                                fi
                                        fi
                                done
                                
                                # Final result
                                echo ""
                                echo "Test Summary:"
                                echo "  Passed: $passed_tests"
                                echo "  Failed: $failed_tests"
                                echo "  Total Attempts: $((passed_tests + failed_tests))"
                                
                                if [ $passed_tests -gt 0 ]; then
                                        echo "Bluetooth Test Result: PASSED (At least one attempt succeeded)"
                                        ok=1
                                else
                                        echo "Bluetooth Test Result: FAILED (All $MAX_ATTEMPTS attempts failed)"
                                        ok=0
                                fi
                                
                                break
                done
        fi
        
        # Shutdown BT device after test
        echo ""
        echo "Shutting down BT device and cleaning up processes..."
        
        # Step 1: Advanced BT shutdown - Disable scanning and advertising first
        echo "Disabling BT radio operations..."
        hciconfig $hciif noscan 2>/dev/null || true
        hciconfig $hciif nopage 2>/dev/null || true
        hciconfig $hciif noleadv 2>/dev/null || true
        
        # Step 2: Reset BT controller to clear all connections and state
        echo "Resetting BT controller..."
        hciconfig $hciif reset 2>/dev/null || true
        sleep 0.5
        
        # Step 3: Disable BT radio completely
        echo "Disabling BT radio..."
        rfkill block bluetooth 2>/dev/null || true
        sleep 0.3
        
        # Step 4: Bring down the HCI interface
        echo "Bringing down HCI interface..."
        hciconfig $hciif down 2>/dev/null || true
        sleep 0.5
        
        # Step 5: Force detach and kill processes immediately
        echo "Terminating Bluetooth processes..."
        killall -9 hciattach 2>/dev/null || true
        killall -9 brcm_patchram_plus 2>/dev/null || true
        sleep 0.3
        
        # Step 6: Unblock rfkill to allow WiFi to use full resources
        echo "Unblocking rfkill for WiFi..."
        rfkill unblock bluetooth 2>/dev/null || true
        sleep 0.2
        
        # Step 7: Verify hci interface is no longer present
        if hciconfig -a 2>/dev/null | grep -q "$hciif"; then
                echo "Warning: $hciif still exists, forcing removal..."
                # Force cleanup
                killall -9 hciattach brcm_patchram_plus 2>/dev/null || true
                sleep 0.5
        fi
        
        # Final verification
        if ! hciconfig -a 2>/dev/null | grep -q "$hciif"; then
                echo "BT device successfully removed (hci interface not found)"
                echo "WiFi can now use full 2.4G spectrum"
        else
                echo "Warning: BT device may still be present"
                hciconfig -a
        fi
fi