import os
import sys
import time
import threading
import mido

class MidiManager:
    def __init__(self, on_message_cb=None, on_status_cb=None):
        self.on_message_cb = on_message_cb
        self.on_status_cb = on_status_cb
        self.is_connected = False
        
        # Dictionary of active ports: {port_name: port_object}
        self.open_ports = {}
        self.ports_lock = threading.Lock()
        
        self._stop_event = threading.Event()
        self._thread = None
        
        # MIDI Learn state
        self._learn_callback = None
        self._learn_lock = threading.Lock()

    def start(self):
        """Starts the MIDI monitor and autodetect loop."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the MIDI monitor loop and closes all ports."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        
        with self.ports_lock:
            for name, port in list(self.open_ports.items()):
                try:
                    port.close()
                except Exception:
                    pass
            self.open_ports.clear()
            self.is_connected = False

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

    def _monitor_loop(self):
        """Background thread loop to dynamically detect, open, and close MIDI ports."""
        while not self._stop_event.is_set():
            try:
                # Get all available system MIDI input port names
                all_inputs = mido.get_input_names()
            except Exception as e:
                print(f"Error querying MIDI inputs: {e}", file=sys.stderr)
                all_inputs = []

            # Filter for ports belonging to the MPK249
            target_ports = [name for name in all_inputs if any(term in name.lower() for term in ["mpk249", "akai"])]
            
            with self.ports_lock:
                # 1. Close ports that are no longer connected
                for name in list(self.open_ports.keys()):
                    if name not in target_ports:
                        print(f"MIDI | Port disconnected: {name}")
                        try:
                            self.open_ports[name].close()
                        except Exception:
                            pass
                        del self.open_ports[name]

                # 2. Open new ports that just connected
                for name in target_ports:
                    if name not in self.open_ports:
                        print(f"MIDI | Attempting to open port: {name}")
                        try:
                            # Open port with an asynchronous callback
                            port = mido.open_input(
                                name, 
                                callback=self._handle_midi_message
                            )
                            self.open_ports[name] = port
                            print(f"MIDI | Successfully opened port: {name}")
                        except Exception as e:
                            print(f"MIDI | Error opening port {name}: {e}", file=sys.stderr)

                # 3. Update connection status
                has_ports = len(self.open_ports) > 0
                if has_ports != self.is_connected:
                    self.is_connected = has_ports
                    if self.on_status_cb:
                        # Display a simplified combined path/name of active devices
                        paths_summary = ", ".join([n.split(":")[-1] for n in self.open_ports.keys()])
                        self.on_status_cb(self.is_connected, paths_summary if self.is_connected else None)

            # Check every 2 seconds
            time.sleep(2.0)

    def _handle_midi_message(self, msg):
        """Dispatches incoming MIDI messages from opened ports."""
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
                self._learn_callback = None
                
                # Execute learn callback in a separate thread so it doesn't block the MIDI thread
                threading.Thread(
                    target=cb, 
                    args=(control_id, msg.type, getattr(msg, 'channel', 0)), 
                    daemon=True
                ).start()
                return

        # Regular Message Callback
        if self.on_message_cb:
            self.on_message_cb(msg, control_id, val)
