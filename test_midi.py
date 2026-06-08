import sys
import os
import mido

device_path = "/dev/snd/midiC1D0"
if not os.path.exists(device_path):
    print(f"Device {device_path} not found")
    sys.exit(1)

print(f"Opening {device_path}...")
try:
    parser = mido.Parser()
    with open(device_path, "rb") as f:
        print("Successfully opened! Press keys or turn knobs on your MPK249 to test. Press Ctrl+C to exit.")
        while True:
            # Read single bytes
            data = f.read(1)
            if not data:
                break
            parser.feed(data)
            for msg in parser.iter_pending():
                print(f"Received MIDI: {msg}")
except KeyboardInterrupt:
    print("\nExited.")
except Exception as e:
    print(f"Error: {e}")
