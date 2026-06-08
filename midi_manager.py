import os
import sys
import time
import threading
import glob
import mido

class MidiManager:
    def __init__(self, on_message_cb=None, on_status_cb=None):
        self.on_message_cb = on_message_cb
        self.on_status_cb = on_status_cb
        self.is_connected = False
        self.current_device = None
        self._stop_event = threading.Event()
        self._thread = None
        
        # MIDI Learn state
        self._learn_callback = None
        self._learn_lock = threading.Lock()

    def start(self):
        """Starts the MIDI monitor thread."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._connection_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the MIDI monitor thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)

    def enable_midi_learn(self, callback):
        """
        Enables MIDI learn mode. The next MIDI message received will be sent
        to `callback(control_id, msg_type, channel)` and will not execute any normal mapping actions.
        """
        with self._learn_lock:
            self._learn_callback = callback

    def disable_midi_learn(self):
        """Disables MIDI learn mode."""
        with self._learn_lock:
            self._learn_callback = None

    def find_mpk249_device(self):
        """Dynamically finds the MPK249 ALSA MIDI device path."""
        # 1. Check /proc/asound/cards to find cards with MPK249 or Akai
        try:
            if os.path.exists("/proc/asound/cards"):
                with open("/proc/asound/cards", "r") as f:
                    content = f.read()
                for line in content.splitlines():
                    if any(term in line.lower() for term in ["mpk249", "akai", "professional"]):
                        parts = line.strip().split()
                        if parts and parts[0].isdigit():
                            card_num = parts[0]
                            dev_path = f"/dev/snd/midiC{card_num}D0"
                            if os.path.exists(dev_path):
                                return dev_path
        except Exception as e:
            print(f"Error scanning /proc/asound/cards: {e}", file=sys.stderr)

        # 2. Fallback to searching /dev/snd/midiC*D0
        try:
            midi_files = glob.glob("/dev/snd/midiC*D0")
            if midi_files:
                # Prioritize card numbers > 0 (which are usually USB midi devices)
                midi_files.sort(key=lambda x: int(os.path.basename(x).replace("midiC", "").replace("D0", "")), reverse=True)
                return midi_files[0]
        except Exception:
            pass

        # 3. Hardcoded fallback
        if os.path.exists("/dev/snd/midiC1D0"):
            return "/dev/snd/midiC1D0"

        return None

    def _connection_loop(self):
        """Background thread loop to maintain MIDI connection and parse input."""
        parser = mido.Parser()
        
        while not self._stop_event.is_set():
            dev_path = self.find_mpk249_device()
            if not dev_path:
                if self.is_connected:
                    self.is_connected = False
                    self.current_device = None
                    if self.on_status_cb:
                        self.on_status_cb(False, None)
                time.sleep(2.0)
                continue

            try:
                # Open device file
                with open(dev_path, "rb") as f:
                    self.is_connected = True
                    self.current_device = dev_path
                    if self.on_status_cb:
                        self.on_status_cb(True, dev_path)
                    
                    # Set non-blocking read with a small sleep or read in chunks
                    # In Python, reading from /dev/snd/midiC*D0 is blocking unless we use select or read byte-by-byte
                    # To allow graceful exits, we read 1 byte at a time.
                    # On Linux, open() on these devices blocks, but since it's a daemon thread,
                    # it will be killed when main GUI terminates, or we can close the FD to force unblock.
                    while not self._stop_event.is_set():
                        data = f.read(1)
                        if not data:
                            break
                        parser.feed(data)
                        
                        for msg in parser.iter_pending():
                            self._handle_midi_message(msg)
                            
            except (OSError, PermissionError, IOError) as e:
                # Connection lost or permission error
                self.is_connected = False
                self.current_device = None
                if self.on_status_cb:
                    self.on_status_cb(False, None)
                time.sleep(2.0)

    def _handle_midi_message(self, msg):
        """Dispatches the MIDI message to callbacks."""
        control_id = None
        val = None
        
        # Identify type and construct control_id
        if msg.type in ['note_on', 'note_off']:
            control_id = f"note:{msg.note}"
            val = msg.velocity if msg.type == 'note_on' else 0
        elif msg.type == 'control_change':
            control_id = f"cc:{msg.control}"
            val = msg.value
        elif msg.type == 'pitchwheel':
            control_id = "pitchwheel"
            val = msg.pitch
        elif msg.type == 'program_change':
            control_id = f"program:{msg.program}"
            val = 127
            
        if not control_id:
            return

        # Check MIDI Learn first
        with self._learn_lock:
            if self._learn_callback:
                cb = self._learn_callback
                # Disable learn mode automatically on first received control message
                self._learn_callback = None
                
                # Execute in thread safety
                threading.Thread(target=cb, args=(control_id, msg.type, getattr(msg, 'channel', 0)), daemon=True).start()
                return

        # Regular Message Callback
        if self.on_message_cb:
            self.on_message_cb(msg, control_id, val)
