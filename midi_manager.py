import os
import sys
import time
import logging
import threading
import mido

# Get logger from the system
logger = logging.getLogger(__name__)

class MidiManager:
    def __init__(self, on_message_cb=None, on_status_cb=None):
        self.on_message_cb = on_message_cb
        self.on_status_cb = on_status_cb
        self.is_connected = False
        
        # Dictionary of active ports: {port_name: port_object}
        self.open_ports = {}
        self.open_outputs = {}
        self.ports_lock = threading.Lock()
        
        self._stop_event = threading.Event()
        self._thread = None
        
        # MIDI Learn state
        self._learn_callback = None
        self._learn_lock = threading.Lock()

    def start(self):
        """Starts the MIDI monitor and autodetect loop."""
        logger.info("Starting MidiManager threads")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, name="MidiMonitorThread", daemon=True)
        self._thread.start()

    def stop(self):
        """Stops the MIDI monitor loop and closes all ports."""
        logger.info("Stopping MidiManager threads")
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
        
        with self.ports_lock:
            for name, port in list(self.open_ports.items()):
                logger.info(f"Closing port: {name}")
                try:
                    port.close()
                except Exception as e:
                    logger.error(f"Error closing port {name}: {e}")
            self.open_ports.clear()
            
            for name, port in list(self.open_outputs.items()):
                logger.info(f"Closing output port: {name}")
                try:
                    port.close()
                except Exception as e:
                    logger.error(f"Error closing output port {name}: {e}")
            self.open_outputs.clear()
            
            self.is_connected = False

    def enable_midi_learn(self, callback):
        """
        Enables MIDI learn mode. The next MIDI message received will be sent
        to `callback(control_id, msg_type, channel)` and will not execute any normal mapping actions.
        """
        logger.info("MIDI Learn enabled")
        with self._learn_lock:
            self._learn_callback = callback

    def disable_midi_learn(self):
        """Disables MIDI learn mode."""
        logger.info("MIDI Learn disabled")
        with self._learn_lock:
            self._learn_callback = None

    def send_midi_message(self, msg):
        """Sends a MIDI message to all open output ports."""
        with self.ports_lock:
            for name, port in self.open_outputs.items():
                try:
                    logger.debug(f"Sending MIDI message to output port {name}: {msg}")
                    port.send(msg)
                except Exception as e:
                    logger.error(f"Error sending MIDI message to output port {name}: {e}")

    def _monitor_loop(self):
        """Background thread loop to dynamically detect, open, and close MIDI ports."""
        logger.info("Entering MidiManager monitor loop")
        while not self._stop_event.is_set():
            try:
                # Get all available system MIDI input port names
                all_inputs = mido.get_input_names()
                logger.debug(f"Discovered MIDI inputs on system: {all_inputs}")
            except Exception as e:
                logger.error(f"Error querying MIDI inputs: {e}", exc_info=True)
                all_inputs = []

            try:
                # Get all available system MIDI output port names
                all_outputs = mido.get_output_names()
                logger.debug(f"Discovered MIDI outputs on system: {all_outputs}")
            except Exception as e:
                logger.error(f"Error querying MIDI outputs: {e}", exc_info=True)
                all_outputs = []

            # Filter for ports belonging to the MPK249
            target_ports = [name for name in all_inputs if any(term in name.lower() for term in ["mpk249", "akai"])]
            target_outputs = [name for name in all_outputs if any(term in name.lower() for term in ["mpk249", "akai"])]
            
            with self.ports_lock:
                # 1. Close ports that are no longer connected
                for name in list(self.open_ports.keys()):
                    if name not in target_ports:
                        logger.warning(f"Port disconnected: {name}")
                        try:
                            self.open_ports[name].close()
                        except Exception as e:
                            logger.error(f"Error closing stale port {name}: {e}")
                        del self.open_ports[name]

                # 2. Open new ports that just connected
                for name in target_ports:
                    if name not in self.open_ports:
                        logger.info(f"Attempting to open port: {name}")
                        try:
                            # Open port with an asynchronous callback
                            port = mido.open_input(
                                name, 
                                callback=self._handle_midi_message
                            )
                            self.open_ports[name] = port
                            logger.info(f"Successfully opened port: {name}")
                        except Exception as e:
                            logger.error(f"Error opening port {name}: {e}", exc_info=True)

                # 3. Close outputs that are no longer connected
                for name in list(self.open_outputs.keys()):
                    if name not in target_outputs:
                        logger.warning(f"Output port disconnected: {name}")
                        try:
                            self.open_outputs[name].close()
                        except Exception as e:
                            logger.error(f"Error closing stale output port {name}: {e}")
                        del self.open_outputs[name]

                # 4. Open new outputs
                for name in target_outputs:
                    if name not in self.open_outputs:
                        logger.info(f"Attempting to open output port: {name}")
                        try:
                            port = mido.open_output(name)
                            self.open_outputs[name] = port
                            logger.info(f"Successfully opened output port: {name}")
                        except Exception as e:
                            logger.error(f"Error opening output port {name}: {e}", exc_info=True)

                # 5. Update connection status
                has_ports = len(self.open_ports) > 0 or len(self.open_outputs) > 0
                if has_ports != self.is_connected:
                    self.is_connected = has_ports
                    logger.info(f"Connection status changed. Connected: {self.is_connected}")
                    if self.on_status_cb:
                        # Display a simplified combined path/name of active devices
                        paths_summary = ", ".join([n.split(":")[-1] for n in self.open_ports.keys()])
                        self.on_status_cb(self.is_connected, paths_summary if self.is_connected else None)

            # Check every 2 seconds
            time.sleep(2.0)

    def _handle_midi_message(self, msg):
        """Dispatches incoming MIDI messages from opened ports."""
        try:
            logger.debug(f"Raw MIDI message received in callback thread: {msg}")
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
                val = getattr(msg, 'program', 127)
            elif msg.type == 'sysex':
                # Represent SysEx data as a hex string (excluding F0 and F7, which mido.Message.data already does)
                data_hex = msg.data.hex() if hasattr(msg.data, 'hex') else ''.join(f'{b:02x}' for b in msg.data)
                control_id = f"sysex:{data_hex}"
                val = 127
            elif msg.type in ['start', 'stop', 'continue', 'songposition', 'songselect', 'tune_request', 'clock', 'reset']:
                control_id = f"system:{msg.type}"
                val = getattr(msg, 'pos', getattr(msg, 'song', 127))
                
            if not control_id:
                return

            # Check MIDI Learn first
            with self._learn_lock:
                if self._learn_callback:
                    cb = self._learn_callback
                    self._learn_callback = None
                    
                    logger.info(f"MIDI Learn triggered! Redirecting message {control_id} to learn callback.")
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
        except Exception as e:
            logger.error(f"Error in MIDI message processing callback: {e}", exc_info=True)
