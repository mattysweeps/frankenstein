import os
import json
import sys
import tkinter as tk
import customtkinter as ctk
from midi_manager import MidiManager
from action_handler import ActionHandler

# Set appearance mode and color theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class Mpk249App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("MPK249 Desktop Control Center")
        self.geometry("950x700")
        self.resizable(True, True)

        # Initialize Handlers
        self.action_handler = ActionHandler()
        self.config_data = self.load_config()
        
        # State variables
        self.active_preset_name = self.config_data.get("active_preset", "Default Desktop Mappings")
        self.active_mappings = self.config_data.get("presets", {}).get(self.active_preset_name, {})
        self.is_connected = False
        self.is_logging_paused = False
        self.selected_mapping_key = None  # Key currently selected for editing

        # Setup GUI layout
        self.setup_ui()

        # Initialize and start MIDI Manager
        self.midi_manager = MidiManager(
            on_message_cb=self.handle_midi_input,
            on_status_cb=self.handle_connection_status
        )
        self.midi_manager.start()

        # Update initial UI states
        self.update_preset_selector()
        self.load_mappings_list()

    def load_config(self):
        """Loads configuration from JSON file. Falls back to default if file corrupt/missing."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error reading config: {e}", file=sys.stderr)
        
        # Default config structure if file not found
        return {
            "active_preset": "Default Desktop Mappings",
            "presets": {
                "Default Desktop Mappings": {}
            }
        }

    def save_config(self):
        """Saves current configuration to file."""
        try:
            self.config_data["active_preset"] = self.active_preset_name
            if "presets" not in self.config_data:
                self.config_data["presets"] = {}
            self.config_data["presets"][self.active_preset_name] = self.active_mappings
            
            with open(CONFIG_FILE, "w") as f:
                json.dump(self.config_data, f, indent=2)
        except Exception as e:
            self.log_to_monitor(f"System Error: Failed to save config: {e}")

    # ================= UI SETUP =================
    def setup_ui(self):
        # Grid Configuration (1 Column, Multi-Row)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # 1. Top Header Bar
        self.header_frame = ctk.CTkFrame(self, height=60, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="🎹 MPK249 Desktop Controller", 
            font=ctk.CTkFont(size=22, weight="bold")
        )
        self.title_label.grid(row=0, column=0, sticky="w", padx=20, pady=15)

        # Status indicator
        self.status_badge = ctk.CTkLabel(
            self.header_frame,
            text="🔴 Disconnected",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#cf4444",
            text_color="white",
            corner_radius=10,
            padx=10,
            pady=4
        )
        self.status_badge.grid(row=0, column=1, padx=(10, 20), pady=15)

        # Preset selection in header
        self.preset_label = ctk.CTkLabel(self.header_frame, text="Active Preset:")
        self.preset_label.grid(row=0, column=2, padx=(20, 5), pady=15)

        self.preset_dropdown = ctk.CTkOptionMenu(
            self.header_frame,
            values=[self.active_preset_name],
            command=self.change_active_preset
        )
        self.preset_dropdown.grid(row=0, column=3, padx=(0, 10), pady=15)

        self.btn_new_preset = ctk.CTkButton(
            self.header_frame, 
            text="+ New", 
            width=60, 
            command=self.create_new_preset
        )
        self.btn_new_preset.grid(row=0, column=4, padx=(0, 20), pady=15)

        # 2. Main Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)

        # Add tabs
        self.tab_dashboard = self.tabview.add("Dashboard")
        self.tab_mappings = self.tabview.add("Mappings Manager")
        self.tab_monitor = self.tabview.add("MIDI Monitor")

        self.setup_dashboard_tab()
        self.setup_mappings_tab()
        self.setup_monitor_tab()

    def setup_dashboard_tab(self):
        # 2 columns in Dashboard
        self.tab_dashboard.grid_columnconfigure((0, 1), weight=1, uniform="equal")
        self.tab_dashboard.grid_rowconfigure(0, weight=1)

        # Left Card: Live Midi Signal
        self.card_signal = ctk.CTkFrame(self.tab_dashboard, corner_radius=12)
        self.card_signal.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        self.card_signal.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.card_signal, 
            text="Last MIDI Signal", 
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=20)

        self.lbl_midi_ctrl_name = ctk.CTkLabel(
            self.card_signal, 
            text="No message received yet", 
            font=ctk.CTkFont(size=14, weight="normal")
        )
        self.lbl_midi_ctrl_name.grid(row=1, column=0, padx=20, pady=10)

        self.progress_midi_val = ctk.CTkProgressBar(self.card_signal)
        self.progress_midi_val.grid(row=2, column=0, sticky="ew", padx=30, pady=15)
        self.progress_midi_val.set(0)

        self.lbl_midi_val_number = ctk.CTkLabel(
            self.card_signal, 
            text="Value: --", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.lbl_midi_val_number.grid(row=3, column=0, padx=20, pady=10)

        self.lbl_action_fired = ctk.CTkLabel(
            self.card_signal, 
            text="Action: --", 
            font=ctk.CTkFont(size=12, slant="italic"),
            text_color="gray"
        )
        self.lbl_action_fired.grid(row=4, column=0, padx=20, pady=(10, 30))

        # Right Card: Quick Start / Instructions
        self.card_instructions = ctk.CTkFrame(self.tab_dashboard, corner_radius=12)
        self.card_instructions.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.card_instructions.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self.card_instructions, 
            text="Quick Instructions", 
            font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=20, pady=20)

        instructions_text = (
            "1. Connect your Akai MPK249 controller to your USB port.\n\n"
            "2. Make sure the status indicator at the top is green (🔴 -> 🟢).\n\n"
            "3. Switch to the 'Mappings Manager' tab to customize knobs, faders, buttons, and pads.\n\n"
            "4. Use 'MIDI Learn' to instantly capture a control without searching for its CC or note number.\n\n"
            "5. Set a mapping to simulate keypresses (e.g., Ctrl+C), execute volume commands, or run shell scripts."
        )

        self.txt_instructions = ctk.CTkLabel(
            self.card_instructions,
            text=instructions_text,
            justify="left",
            wraplength=380,
            font=ctk.CTkFont(size=13)
        )
        self.txt_instructions.grid(row=1, column=0, sticky="w", padx=20, pady=10)

    def setup_mappings_tab(self):
        # 2 columns: Left for Scrollable Mappings list, Right for Edit/Add Form
        self.tab_mappings.grid_columnconfigure(0, weight=3, uniform="mapping_tab")
        self.tab_mappings.grid_columnconfigure(1, weight=2, uniform="mapping_tab")
        self.tab_mappings.grid_rowconfigure(0, weight=1)

        # Left Frame: Mappings List
        self.list_container = ctk.CTkFrame(self.tab_mappings, corner_radius=10)
        self.list_container.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)
        self.list_container.grid_columnconfigure(0, weight=1)
        self.list_container.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self.list_container, 
            text="Active Mappings", 
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=15, pady=10)

        self.scroll_mappings = ctk.CTkScrollableFrame(self.list_container)
        self.scroll_mappings.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scroll_mappings.grid_columnconfigure(0, weight=1)

        # Right Frame: Edit/Add Mapping Form
        self.form_container = ctk.CTkFrame(self.tab_mappings, corner_radius=10)
        self.form_container.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        self.form_container.grid_columnconfigure((0, 1), weight=1)

        self.form_title = ctk.CTkLabel(
            self.form_container, 
            text="Add / Edit Mapping", 
            font=ctk.CTkFont(size=16, weight="bold")
        )
        self.form_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=10)

        # Form fields
        # Control ID and Learn Button
        ctk.CTkLabel(self.form_container, text="Control ID:").grid(row=1, column=0, sticky="w", padx=15, pady=5)
        self.entry_control_id = ctk.CTkEntry(self.form_container, placeholder_text="e.g. cc:12 or note:36")
        self.entry_control_id.grid(row=2, column=0, sticky="ew", padx=(15, 5), pady=5)

        self.btn_learn = ctk.CTkButton(
            self.form_container, 
            text="MIDI Learn", 
            command=self.start_midi_learn
        )
        self.btn_learn.grid(row=2, column=1, sticky="ew", padx=(5, 15), pady=5)

        # Description
        ctk.CTkLabel(self.form_container, text="Description:").grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        self.entry_description = ctk.CTkEntry(self.form_container, placeholder_text="e.g. Master Volume")
        self.entry_description.grid(row=4, column=0, columnspan=2, sticky="ew", padx=15, pady=5)

        # Action Type Dropdown
        ctk.CTkLabel(self.form_container, text="Action Type:").grid(row=5, column=0, columnspan=2, sticky="w", padx=15, pady=5)
        self.action_type_options = ["volume_set", "volume_up", "volume_down", "volume_mute", "keypress", "command", "mouse_click", "mouse_scroll"]
        self.dropdown_action_type = ctk.CTkOptionMenu(
            self.form_container,
            values=self.action_type_options,
            command=self.on_action_type_change
        )
        self.dropdown_action_type.grid(row=6, column=0, columnspan=2, sticky="ew", padx=15, pady=5)

        # Parameters Frame (Dynamically changed based on Action Type)
        self.param_label = ctk.CTkLabel(self.form_container, text="Parameters:")
        self.param_label.grid(row=7, column=0, columnspan=2, sticky="w", padx=15, pady=(10, 5))

        self.entry_param_val = ctk.CTkEntry(self.form_container, placeholder_text="Enter parameter value")
        self.entry_param_val.grid(row=8, column=0, columnspan=2, sticky="ew", padx=15, pady=5)
        self.lbl_param_hint = ctk.CTkLabel(
            self.form_container, 
            text="Hint: parameters info", 
            font=ctk.CTkFont(size=11, slant="italic"),
            text_color="gray"
        )
        self.lbl_param_hint.grid(row=9, column=0, columnspan=2, sticky="w", padx=15, pady=(2, 10))

        # Action Buttons
        self.btn_save_mapping = ctk.CTkButton(
            self.form_container, 
            text="Save Mapping", 
            fg_color="#2da44e", 
            hover_color="#2c974b",
            command=self.save_mapping_form
        )
        self.btn_save_mapping.grid(row=10, column=0, sticky="ew", padx=(15, 5), pady=15)

        self.btn_cancel_edit = ctk.CTkButton(
            self.form_container, 
            text="Clear / Cancel", 
            command=self.clear_mapping_form
        )
        self.btn_cancel_edit.grid(row=10, column=1, sticky="ew", padx=(5, 15), pady=15)

        # Trigger dynamic update initially
        self.on_action_type_change(self.dropdown_action_type.get())

    def setup_monitor_tab(self):
        self.tab_monitor.grid_columnconfigure(0, weight=1)
        self.tab_monitor.grid_rowconfigure(1, weight=1)

        # Controls row
        ctrl_frame = ctk.CTkFrame(self.tab_monitor)
        ctrl_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.btn_clear_log = ctk.CTkButton(ctrl_frame, text="Clear Log", command=self.clear_monitor_log, width=100)
        self.btn_clear_log.pack(side="left", padx=10, pady=5)

        self.chk_pause_log = ctk.CTkCheckBox(ctrl_frame, text="Pause Logging", command=self.toggle_logging)
        self.chk_pause_log.pack(side="left", padx=20, pady=5)

        # Text monitor
        self.txt_monitor = ctk.CTkTextbox(self.tab_monitor, wrap="none", font=ctk.CTkFont(family="monospace", size=12))
        self.txt_monitor.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt_monitor.configure(state="disabled")

    # ================= MIDI EVENT HANDLING =================
    def handle_midi_input(self, msg, control_id, value):
        """Processes MIDI inputs from the MIDI thread."""
        # Update Dashboard Visuals via main thread threadsafe call
        self.after(0, self.update_dashboard_signal, control_id, value)
        
        # Check if mapped action exists in the current preset
        if control_id in self.active_mappings:
            mapping = self.active_mappings[control_id]
            action_type = mapping.get("action_type")
            params = mapping.get("params", {})
            desc = mapping.get("description", "Unknown Action")
            
            # Update status in dashboard
            self.after(0, lambda: self.lbl_action_fired.configure(text=f"Fired: {desc} ({action_type})"))
            
            # Execute the action
            self.action_handler.execute(action_type, params, value)
        else:
            self.after(0, lambda: self.lbl_action_fired.configure(text="Action: (unmapped)"))

        # Log to the live midi monitor tab
        log_msg = f"MIDI Input | Type: {msg.type:<15} | Control ID: {control_id:<10} | Value: {value:<5}"
        self.after(0, self.log_to_monitor, log_msg)

    def handle_connection_status(self, is_connected, path):
        """Callback for device connection state changes."""
        self.is_connected = is_connected
        self.after(0, self.update_connection_status_ui, is_connected, path)

    def update_connection_status_ui(self, is_connected, path):
        if is_connected:
            self.status_badge.configure(
                text="🟢 Connected", 
                fg_color="#2da44e"
            )
            self.log_to_monitor(f"System | Device Connected: {path}")
        else:
            self.status_badge.configure(
                text="🔴 Disconnected", 
                fg_color="#cf4444"
            )
            self.log_to_monitor("System | Device Disconnected. Waiting for MPK249 to be plugged in...")

    def update_dashboard_signal(self, control_id, value):
        self.lbl_midi_ctrl_name.configure(text=f"Active Control: {control_id}")
        self.lbl_midi_val_number.configure(text=f"Value: {value}")
        # Scale progress bar 0-127 -> 0.0 - 1.0
        self.progress_midi_val.set(value / 127.0)

    # ================= PRESET MANAGEMENT =================
    def update_preset_selector(self):
        presets = list(self.config_data.get("presets", {}).keys())
        if not presets:
            presets = ["Default Desktop Mappings"]
        self.preset_dropdown.configure(values=presets)
        self.preset_dropdown.set(self.active_preset_name)

    def change_active_preset(self, preset_name):
        self.active_preset_name = preset_name
        self.active_mappings = self.config_data.get("presets", {}).get(preset_name, {})
        self.save_config()
        self.load_mappings_list()
        self.log_to_monitor(f"Preset | Switched to preset: {preset_name}")

    def create_new_preset(self):
        dialog = ctk.CTkInputDialog(text="Enter preset name:", title="New Preset")
        preset_name = dialog.get_input()
        if preset_name:
            preset_name = preset_name.strip()
            if preset_name:
                if "presets" not in self.config_data:
                    self.config_data["presets"] = {}
                if preset_name not in self.config_data["presets"]:
                    self.config_data["presets"][preset_name] = {}
                self.active_preset_name = preset_name
                self.active_mappings = self.config_data["presets"][preset_name]
                self.save_config()
                self.update_preset_selector()
                self.load_mappings_list()
                self.log_to_monitor(f"Preset | Created new preset: {preset_name}")

    # ================= MAPPINGS EDITOR FORM =================
    def on_action_type_change(self, choice):
        """Changes parameters label, input box configuration, and description hints dynamically."""
        self.entry_param_val.delete(0, tk.END)
        
        if choice in ["volume_up", "volume_down"]:
            self.param_label.configure(text="Step size (%):")
            self.entry_param_val.insert(0, "5")
            self.lbl_param_hint.configure(text="Hint: Integer percentage amount (e.g. 5 or 10).")
            self.entry_param_val.configure(state="normal")
            
        elif choice == "volume_set":
            self.param_label.configure(text="Parameters (Not required):")
            self.lbl_param_hint.configure(text="Hint: Maps 0-127 position on fader/knob to 0-100% volume.")
            self.entry_param_val.configure(state="disabled")
            
        elif choice == "volume_mute":
            self.param_label.configure(text="Parameters (Not required):")
            self.lbl_param_hint.configure(text="Hint: Toggles mute when control is pressed or turned.")
            self.entry_param_val.configure(state="disabled")
            
        elif choice == "keypress":
            self.param_label.configure(text="Key Combination:")
            self.entry_param_val.insert(0, "ctrl+alt+t")
            self.lbl_param_hint.configure(text="Hint: Connect keys with + (e.g. ctrl+alt+t, super+d, space).")
            self.entry_param_val.configure(state="normal")
            
        elif choice == "command":
            self.param_label.configure(text="Shell Command:")
            self.entry_param_val.insert(0, "google-chrome")
            self.lbl_param_hint.configure(text="Hint: Any command to execute (e.g. lock screen command or script).")
            self.entry_param_val.configure(state="normal")
            
        elif choice == "mouse_click":
            self.param_label.configure(text="Mouse Button:")
            self.entry_param_val.insert(0, "left")
            self.lbl_param_hint.configure(text="Hint: Enter 'left', 'right', or 'middle'.")
            self.entry_param_val.configure(state="normal")
            
        elif choice == "mouse_scroll":
            self.param_label.configure(text="Scroll Amount:")
            self.entry_param_val.insert(0, "1")
            self.lbl_param_hint.configure(text="Hint: Directional step size. positive to scroll up, negative down.")
            self.entry_param_val.configure(state="normal")

    def start_midi_learn(self):
        """Enables MIDI learn mode and updates button text."""
        self.btn_learn.configure(text="Listening...", fg_color="#d68a00")
        self.midi_manager.enable_midi_learn(self.on_midi_learned)

    def on_midi_learned(self, control_id, msg_type, channel):
        """Callback fired when MIDI Manager learns a new control."""
        self.after(0, self.update_learned_control, control_id)

    def update_learned_control(self, control_id):
        self.entry_control_id.delete(0, tk.END)
        self.entry_control_id.insert(0, control_id)
        self.btn_learn.configure(text="MIDI Learn", fg_color=["#3B8ED0", "#1F6AA5"])
        
        # Suggest description based on control ID
        self.entry_description.delete(0, tk.END)
        if control_id.startswith("cc:"):
            cc_num = control_id.split(":")[1]
            self.entry_description.insert(0, f"Knob/Fader CC {cc_num}")
        elif control_id.startswith("note:"):
            note_num = control_id.split(":")[1]
            self.entry_description.insert(0, f"Key/Pad Note {note_num}")

        self.log_to_monitor(f"MIDI Learn | Learned control ID: {control_id}")

    def save_mapping_form(self):
        """Saves or updates the mapping in the current preset from the form."""
        control_id = self.entry_control_id.get().strip()
        description = self.entry_description.get().strip()
        action_type = self.dropdown_action_type.get()
        param_text = self.entry_param_val.get().strip()

        if not control_id:
            tk.messagebox.showerror("Validation Error", "Control ID is required. Try using MIDI Learn.")
            return

        # Prepare parameters dictionary
        params = {}
        if action_type in ["volume_up", "volume_down"]:
            try:
                params["step"] = int(param_text)
            except ValueError:
                params["step"] = 5
        elif action_type == "keypress":
            params["keys"] = param_text
        elif action_type == "command":
            params["cmd"] = param_text
        elif action_type == "mouse_click":
            params["button"] = param_text if param_text else "left"
        elif action_type == "mouse_scroll":
            try:
                params["amount"] = int(param_text)
            except ValueError:
                params["amount"] = 1

        if not description:
            description = f"{action_type.capitalize()} on {control_id}"

        # Save mapping
        self.active_mappings[control_id] = {
            "action_type": action_type,
            "description": description,
            "params": params
        }
        
        self.save_config()
        self.load_mappings_list()
        self.clear_mapping_form()
        self.log_to_monitor(f"Mappings | Saved mapping for {control_id}")

    def edit_mapping(self, key):
        """Loads a mapping into the editing form."""
        if key not in self.active_mappings:
            return
        
        self.selected_mapping_key = key
        mapping = self.active_mappings[key]
        
        self.entry_control_id.delete(0, tk.END)
        self.entry_control_id.insert(0, key)
        
        self.entry_description.delete(0, tk.END)
        self.entry_description.insert(0, mapping.get("description", ""))
        
        action_type = mapping.get("action_type", "volume_set")
        self.dropdown_action_type.set(action_type)
        self.on_action_type_change(action_type)
        
        # Load parameters
        params = mapping.get("params", {})
        self.entry_param_val.delete(0, tk.END)
        
        if action_type in ["volume_up", "volume_down"]:
            self.entry_param_val.insert(0, str(params.get("step", 5)))
        elif action_type == "keypress":
            self.entry_param_val.insert(0, params.get("keys", ""))
        elif action_type == "command":
            self.entry_param_val.insert(0, params.get("cmd", ""))
        elif action_type == "mouse_click":
            self.entry_param_val.insert(0, params.get("button", "left"))
        elif action_type == "mouse_scroll":
            self.entry_param_val.insert(0, str(params.get("amount", 1)))

    def delete_mapping(self, key):
        """Deletes a mapping from the current preset."""
        if key in self.active_mappings:
            del self.active_mappings[key]
            self.save_config()
            self.load_mappings_list()
            if self.selected_mapping_key == key:
                self.clear_mapping_form()
            self.log_to_monitor(f"Mappings | Deleted mapping for {key}")

    def clear_mapping_form(self):
        self.selected_mapping_key = None
        self.entry_control_id.delete(0, tk.END)
        self.entry_description.delete(0, tk.END)
        self.dropdown_action_type.set("volume_set")
        self.on_action_type_change("volume_set")
        self.midi_manager.disable_midi_learn()
        self.btn_learn.configure(text="MIDI Learn", fg_color=["#3B8ED0", "#1F6AA5"])

    def load_mappings_list(self):
        """Renders the active mappings list in the GUI."""
        # Clear existing children of the scroll container
        for widget in self.scroll_mappings.winfo_children():
            widget.destroy()

        if not self.active_mappings:
            lbl_empty = ctk.CTkLabel(
                self.scroll_mappings, 
                text="No mappings configured yet for this preset.\nUse the form on the right to add some!", 
                text_color="gray",
                font=ctk.CTkFont(size=12, slant="italic")
            )
            lbl_empty.grid(row=0, column=0, padx=20, pady=40, sticky="ew")
            return

        row = 0
        for key, mapping in sorted(self.active_mappings.items()):
            # Create a card frame for each mapping
            card = ctk.CTkFrame(self.scroll_mappings, corner_radius=6, fg_color=("#e5e5e5", "#242424"))
            card.grid(row=row, column=0, sticky="ew", padx=5, pady=4)
            card.grid_columnconfigure(0, weight=1)

            # Left side: labels
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            lbl_title = ctk.CTkLabel(
                info_frame, 
                text=f"{key} → {mapping.get('description', '')}", 
                font=ctk.CTkFont(size=13, weight="bold")
            )
            lbl_title.pack(anchor="w")

            # Formulate detail string
            action_type = mapping.get("action_type", "")
            params = mapping.get("params", {})
            param_detail = ""
            if action_type in ["volume_up", "volume_down"]:
                param_detail = f" (Step: {params.get('step', 5)}%)"
            elif action_type == "keypress":
                param_detail = f" (Keys: {params.get('keys', '')})"
            elif action_type == "command":
                param_detail = f" (Cmd: {params.get('cmd', '')})"
            elif action_type == "mouse_click":
                param_detail = f" (Button: {params.get('button', '')})"
            elif action_type == "mouse_scroll":
                param_detail = f" (Amount: {params.get('amount', '')})"

            lbl_details = ctk.CTkLabel(
                info_frame, 
                text=f"Action: {action_type}{param_detail}", 
                font=ctk.CTkFont(size=11, slant="italic"),
                text_color="gray"
            )
            lbl_details.pack(anchor="w")

            # Right side: action buttons (Edit / Delete)
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(side="right", padx=10, pady=8)

            # Use local variable bindings in lambda closures
            btn_edit = ctk.CTkButton(
                btn_frame, 
                text="Edit", 
                width=50, 
                height=24,
                command=lambda k=key: self.edit_mapping(k)
            )
            btn_edit.pack(side="left", padx=2)

            btn_del = ctk.CTkButton(
                btn_frame, 
                text="Delete", 
                width=50, 
                height=24,
                fg_color="#cf4444", 
                hover_color="#b53535",
                command=lambda k=key: self.delete_mapping(k)
            )
            btn_del.pack(side="left", padx=2)

            row += 1

    # ================= LIVE MIDI MONITOR LOGGING =================
    def toggle_logging(self):
        self.is_logging_paused = self.chk_pause_log.get()

    def clear_monitor_log(self):
        self.txt_monitor.configure(state="normal")
        self.txt_monitor.delete("1.0", tk.END)
        self.txt_monitor.configure(state="disabled")

    def log_to_monitor(self, text):
        if self.is_logging_paused:
            return
        
        self.txt_monitor.configure(state="normal")
        self.txt_monitor.insert(tk.END, text + "\n")
        self.txt_monitor.see(tk.END)
        
        # Cap log length to prevent memory issues
        lines = self.txt_monitor.get("1.0", tk.END).splitlines()
        if len(lines) > 500:
            self.txt_monitor.delete("1.0", "150.0")
            
        self.txt_monitor.configure(state="disabled")

    def on_closing(self):
        """Handles application shutdown cleanly."""
        self.midi_manager.stop()
        self.destroy()

if __name__ == "__main__":
    app = Mpk249App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.on_closing()
