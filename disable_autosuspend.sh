#!/bin/bash

# Target vendor and product ID for Akai MPK249
TARGET_VID="09e8"
TARGET_PID="0024"

echo "Scanning USB devices for MPK249..."
FOUND=0

for dev in /sys/bus/usb/devices/*; do
    if [ -f "$dev/idVendor" ] && [ -f "$dev/idProduct" ]; then
        vid=$(cat "$dev/idVendor")
        pid=$(cat "$dev/idProduct")
        
        if [ "$vid" = "$TARGET_VID" ] && [ "$pid" = "$TARGET_PID" ]; then
            echo "----------------------------------------"
            echo "Found MPK249 at device path: $dev"
            echo "Current power control: $(cat $dev/power/control)"
            echo "Current autosuspend delay: $(cat $dev/power/autosuspend_delay_ms) ms"
            
            echo "Applying fix: Disabling USB autosuspend (setting control to 'on')..."
            sudo sh -c "echo on > $dev/power/control" 2>/dev/null
            
            if [ $? -eq 0 ]; then
                echo "Success! USB autosuspend disabled for MPK249."
            else
                echo "Failed to write. Please run this script with sudo:"
                echo "sudo ./disable_autosuspend.sh"
            fi
            FOUND=1
        fi
    fi
done

if [ $FOUND -eq 0 ]; then
    echo "MPK249 not found in USB devices list. Please plug it in and try again."
fi
