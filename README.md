# 🎹 MPK249 Desktop Controller

A beautiful, premium, and lightweight GUI application written in Python using CustomTkinter to control your Linux desktop using the **Akai Professional MPK249** MIDI controller.

## 🚀 Key Features

* **Automatic MIDI Discovery**: Auto-detects the MPK249 ALSA MIDI device path (`/dev/snd/midiC*D0`) dynamically from `/proc/asound/cards`.
* **Zero C-Dependency MIDI Parsing**: Operates via a robust pure-Python byte-level stream parser, avoiding compilation errors and ensuring instant compatibility with Python 3.14+.
* **MIDI Learn Wizard**: No need to look up MIDI CC (Control Change) or note numbers. Just press "MIDI Learn", move any knob/fader or press any pad/key on the MPK249, and it will capture it instantly.
* **Premium Dark Mode GUI**: A high-fidelity dark-themed interface built using CustomTkinter, featuring real-time visual signal meters, tabs, and customizable menus.
* **Custom Desktop Triggers**:
  * **System Volume**: Smoothly set master volume via knobs/faders, or increase/decrease/mute using buttons.
  * **Keyboard Shortcuts**: Simulate single keys or combinations (e.g., `ctrl+alt+t` to open a terminal, `super+d` to show desktop).
  * **Shell Commands**: Trigger arbitrary bash scripts or command-line tools.
  * **Mouse Control**: Emulate mouse clicks or scrolls.
* **Hot Reconnection**: Daemon listener thread dynamically detects if the controller is unplugged and automatically restores connection once it is plugged back in.
* **Preset Manager**: Save different sets of mappings (e.g., "Default Desktop Mappings", "Presentation Mode", "Media Control Mode") and swap them instantly.

---

## 📁 File Structure

The project contains the following components:
* [app.py](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/app.py) — The main CustomTkinter GUI wrapper, layout tabs, settings forms, and preset management.
* [midi_manager.py](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/midi_manager.py) — Handles dynamic MIDI device path detection, a background listener thread, raw bytes parsing, and MIDI Learn mode.
* [action_handler.py](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/action_handler.py) — Simulates mouse/keyboard commands and system audio changes via `amixer` and `pynput`.
* [config.json](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/config.json) — Local configuration file containing active presets and user-customized mappings.
* [requirements.txt](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/requirements.txt) — Pure-python dependency lists.
* [run.sh](file:///home/mattysweeps/src/github.com/mattysweeps/frankenstein/run.sh) — Executive launcher script.

---

## 🛠️ Installation & Execution

Simply run the launcher script in the repository folder:

```bash
./run.sh
```

The launcher will automatically:
1. Initialize a Python virtual environment (`.venv`).
2. Upgrade `pip` and install all necessary dependencies.
3. Start the GUI control center.

---

## 🎹 How to Map Controls

1. Start `./run.sh` and ensure the indicator in the top right turns **🟢 Connected**.
2. Go to the **Mappings Manager** tab.
3. Under the **Add / Edit Mapping** form:
   * Click the **MIDI Learn** button.
   * Move any fader, knob, or press any pad/key on the MPK249. The **Control ID** and proposed **Description** will populate automatically.
4. Select the desired **Action Type** (e.g., `volume_set`, `keypress`, or `command`).
5. Fill in the **Parameters** (e.g., `super+d` for keypress, or a shell command to execute).
6. Click **Save Mapping**. Your new control is active immediately!
