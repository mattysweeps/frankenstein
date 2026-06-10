# 🎹 MPK249 Desktop Controller

A beautiful, premium, and lightweight GUI application written in Python using CustomTkinter to control your desktop (Linux and macOS) using the **Akai Professional MPK249** MIDI controller.

---

## 🚀 Key Features

* **Cross-Platform Compatibility**: Fully supports **Linux (X11/Wayland)** and **macOS (Intel/Apple Silicon)**.
* **Automatic MIDI Discovery**: Auto-detects the MPK249 input ports on your system dynamically.
* **MIDI Learn Wizard**: No need to look up MIDI CC (Control Change) or note numbers. Just press "MIDI Learn", move any knob/fader or press any pad/key on the MPK249, and it will capture it instantly.
* **Premium Dark Mode GUI**: A high-fidelity dark-themed interface built using CustomTkinter, featuring real-time visual signal meters, tabs, and customizable menus.
* **Custom Desktop Triggers**:
  * **System Volume**: Smoothly set master volume via knobs/faders, or increase/decrease/mute using buttons (uses `amixer` on Linux and native `AppleScript` on macOS).
  * **Keyboard Shortcuts**: Simulate single keys or combinations (e.g., `ctrl+alt+t` on Linux, `cmd+space` on macOS).
  * **Shell Commands / Scripts**: Trigger arbitrary shell scripts or command-line tools using `command` or `script` actions.
  * **Mouse Control**: Emulate mouse clicks or directional scrolls.
* **Hot Reconnection**: Daemon listener thread dynamically detects if the controller is unplugged and automatically restores connection once it is plugged back in.
* **Preset Manager**: Save different sets of mappings (e.g., "Default Desktop Mappings", "Presentation Mode", "Media Control Mode") and swap them instantly.

---

## 📁 File Structure

* [app.py](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/app.py) — The main CustomTkinter GUI layout, tabs, forms, and preset management.
* [midi_manager.py](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/midi_manager.py) — Handles dynamic MIDI device port detection, background monitoring, and MIDI Learn mode.
* [action_handler.py](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/action_handler.py) — Simulates mouse/keyboard commands and system audio changes (platform-agnostic).
* [config.json](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/config.json) — Local configuration file containing active presets and user-customized mappings.
* [disable_autosuspend.sh](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/disable_autosuspend.sh) — Linux-only helper script to disable USB autosuspend power-saving features.
* [requirements.txt](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/requirements.txt) — Python dependencies with environment markers for cross-platform installations.
* [run.sh](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/run.sh) — Multi-platform launcher script.

---

## 🛠️ Installation & Execution

### 🐧 On Linux

1. **Install dependencies**:
   Run the following apt command to install sound and GUI system headers:
   ```bash
   sudo apt-get update
   sudo apt-get install -y libasound2-dev pkg-config python3-tk
   ```
2. **Configure USB Hub Power / Autosuspend (Highly Recommended)**:
   If your MPK249 is connected through a USB hub, Linux may put the hub port to sleep (suspend mode), dropping all MIDI signals.
   * Connect your MPK249 to the USB hub.
   * Run the power-management fix script:
     ```bash
     sudo ./disable_autosuspend.sh
     ```
3. **Run the launcher**:
   ```bash
   ./run.sh
   ```

### 🍎 On macOS (OSX)

1. **Install Python 3 & Tkinter** (via [Homebrew](https://brew.sh)):
   ```bash
   brew install python
   # Homebrew's Python installs Tkinter by default. If missing, run:
   brew install python-tk
   ```
2. **Grant Accessibility Permissions**:
   Since the app simulates keyboard hotkeys and mouse actions:
   * Go to **System Settings > Privacy & Security > Accessibility**.
   * Add and toggle ON your **Terminal** app (or iTerm2 / VS Code, whichever you use to launch the script).
3. **Run the launcher**:
   ```bash
   ./run.sh
   ```

---

## 🎹 How to Map Controls

1. Start `./run.sh` and ensure the indicator in the top right turns **🟢 Connected**.
2. Go to the **Mappings Manager** tab.
3. Under the **Add / Edit Mapping** form:
   * Click the **MIDI Learn** button.
   * Move any fader, knob, or press any pad/key on the MPK249. The **Control ID** and proposed **Description** will populate automatically.
4. Select the desired **Action Type** (e.g., `volume_set`, `keypress`, `script`, or `command`).
5. Fill in the **Parameters** (e.g., `cmd+space` for keypress on macOS, or `ctrl+alt+t` on Linux).
6. Click **Save Mapping**. Your new control is active immediately!
