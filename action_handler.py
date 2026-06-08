import subprocess
import os
import sys
import platform
import threading
from pynput.keyboard import Controller as KeyboardController, Key
from pynput.mouse import Controller as MouseController, Button

class ActionHandler:
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()
        
        # Check system platform
        self.is_mac = (platform.system() == "Darwin")
        
        # Threading state for volume updates
        self._target_volume = None
        self._volume_lock = threading.Lock()
        self._volume_thread_active = False
        
        self._key_map = {
            "enter": Key.enter,
            "space": Key.space,
            "backspace": Key.backspace,
            "tab": Key.tab,
            "esc": Key.esc,
            "escape": Key.esc,
            "up": Key.up,
            "down": Key.down,
            "left": Key.left,
            "right": Key.right,
            "pgup": Key.page_up,
            "pgdn": Key.page_down,
            "home": Key.home,
            "end": Key.end,
            "capslock": Key.caps_lock,
            "shift": Key.shift,
            "ctrl": Key.ctrl,
            "control": Key.ctrl,
            "alt": Key.alt,
            "option": Key.alt, # macOS option key
            "super": Key.cmd,
            "meta": Key.cmd,
            "win": Key.cmd,
            "cmd": Key.cmd,
            "command": Key.cmd, # macOS command key
            "f1": Key.f1,
            "f2": Key.f2,
            "f3": Key.f3,
            "f4": Key.f4,
            "f5": Key.f5,
            "f6": Key.f6,
            "f7": Key.f7,
            "f8": Key.f8,
            "f9": Key.f9,
            "f10": Key.f10,
            "f11": Key.f11,
            "f12": Key.f12,
            "vol_up": Key.media_volume_up,
            "vol_down": Key.media_volume_down,
            "vol_mute": Key.media_volume_mute,
            "media_play_pause": Key.media_play_pause,
            "media_next": Key.media_next,
            "media_prev": Key.media_previous,
        }

    def execute(self, action_type, params, midi_value=None):
        """
        Executes a mapped desktop action.
        action_type: str ('volume_up', 'volume_down', 'volume_set', 'volume_mute', 
                          'keypress', 'command', 'mouse_scroll', 'mouse_click', 'mouse_move')
        params: dict or str depending on action
        midi_value: int (0-127) for continuous controls (faders/knobs)
        """
        try:
            if action_type == "volume_up":
                self.adjust_volume(step=params.get("step", 5))
            elif action_type == "volume_down":
                self.adjust_volume(step=-params.get("step", 5))
            elif action_type == "volume_set":
                if midi_value is not None:
                    # Map 0-127 to 0-100%
                    pct = int((midi_value / 127.0) * 100)
                    self.set_volume(pct)
            elif action_type == "volume_mute":
                self.toggle_mute()
            elif action_type == "keypress":
                keys_str = params.get("keys", "")
                self.simulate_keypress(keys_str)
            elif action_type == "command":
                cmd_str = params.get("cmd", "")
                self.run_command(cmd_str)
            elif action_type == "mouse_scroll":
                amount = params.get("amount", 1)
                self.mouse.scroll(0, amount)
            elif action_type == "mouse_click":
                btn = params.get("button", "left").lower()
                self.simulate_click(btn)
            elif action_type == "mouse_move":
                dx = params.get("dx", 0)
                dy = params.get("dy", 0)
                if midi_value is not None:
                    scale = (midi_value - 64) / 64.0  # -1.0 to 1.0
                    self.mouse.move(int(dx * scale), int(dy * scale))
                else:
                    self.mouse.move(dx, dy)
        except Exception as e:
            print(f"Error executing action {action_type}: {e}", file=sys.stderr)

    def adjust_volume(self, step=5):
        """Adjusts the system volume up or down asynchronously."""
        def target():
            try:
                if self.is_mac:
                    # Adjust volume on macOS using AppleScript
                    # Bound output volume settings (0 to 100)
                    cmd = (
                        'osascript -e "set volume output volume '
                        '((output volume of (get volume settings)) + {})"'.format(step)
                    )
                    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Adjust volume on Linux using ALSA amixer
                    sign = "+" if step > 0 else "-"
                    abs_step = abs(step)
                    subprocess.run(["amixer", "sset", "Master", f"{abs_step}%{sign}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error adjusting volume: {e}", file=sys.stderr)
        threading.Thread(target=target, daemon=True).start()

    def set_volume(self, percent):
        """Sets system volume to a specific percentage (0-100) asynchronously and thread-safely."""
        percent = max(0, min(100, percent))
        
        with self._volume_lock:
            self._target_volume = percent
            if not self._volume_thread_active:
                self._volume_thread_active = True
                threading.Thread(target=self._volume_worker, daemon=True).start()

    def _volume_worker(self):
        """Worker thread that executes volume updates without blocking the MIDI or GUI threads."""
        while True:
            with self._volume_lock:
                val = self._target_volume
                self._target_volume = None
                if val is None:
                    self._volume_thread_active = False
                    break
            
            try:
                if self.is_mac:
                    cmd = f'osascript -e "set volume output volume {val}"'
                    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(["amixer", "sset", "Master", f"{val}%"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error setting volume: {e}", file=sys.stderr)

    def toggle_mute(self):
        """Toggles system volume mute state asynchronously."""
        def target():
            try:
                if self.is_mac:
                    # Toggle mute on macOS using AppleScript
                    cmd = 'osascript -e "set volume output muted not (output muted of (get volume settings))"'
                    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    # Toggle mute on Linux using ALSA amixer
                    subprocess.run(["amixer", "sset", "Master", "toggle"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Error toggling mute: {e}", file=sys.stderr)
        threading.Thread(target=target, daemon=True).start()

    def run_command(self, cmd_str):
        """Runs a shell command in the background asynchronously."""
        if not cmd_str:
            return
        def target():
            try:
                subprocess.run(cmd_str, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                print(f"Failed to run command '{cmd_str}': {e}", file=sys.stderr)
        threading.Thread(target=target, daemon=True).start()

    def simulate_keypress(self, keys_str):
        """Simulates a keyboard shortcut (e.g. 'ctrl+alt+t' or 'cmd+space' or 'volume_up')."""
        if not keys_str:
            return
        
        parts = [p.strip().lower() for p in keys_str.split("+")]
        keys_to_press = []
        
        for part in parts:
            if part in self._key_map:
                keys_to_press.append(self._key_map[part])
            elif len(part) == 1:
                keys_to_press.append(part)
            else:
                for char in part:
                    keys_to_press.append(char)

        try:
            for k in keys_to_press:
                self.keyboard.press(k)
            for k in reversed(keys_to_press):
                self.keyboard.release(k)
        except Exception as e:
            print(f"Error simulating keypress '{keys_str}': {e}", file=sys.stderr)

    def simulate_click(self, btn):
        """Simulates mouse click."""
        button = Button.left
        if btn == "right":
            button = Button.right
        elif btn == "middle":
            button = Button.middle
        
        self.mouse.click(button)
