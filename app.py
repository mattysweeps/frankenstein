import os
import json
import sys
import logging
import traceback
import math
import tkinter as tk
import customtkinter as ctk
from midi_manager import MidiManager
from action_handler import ActionHandler

# Configure logging to write to app.log and stdout
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.log")
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] (%(threadName)s) %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w"),
        logging.StreamHandler(sys.stdout)
    ]
)

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global handler for uncaught exceptions."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Uncaught exception in main loop:", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# Set appearance mode and color theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

class Mpk249App(ctk.CTk):
    def __init__(self):
        super().__init__()
        logging.info("Initializing MPK249 Control Center App")

        self.title("MPK249 Desktop Control Center")
        self.geometry("980x820")
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
        self.selected_canvas_control_id = None # Selected control on the visual schematic

        # Initialize default control values database
        self.control_values = {}
        for cc in range(12, 20): self.control_values[f"cc:{cc}"] = 0
        for cc in range(22, 30): self.control_values[f"cc:{cc}"] = 0
        for cc in range(32, 40): self.control_values[f"cc:{cc}"] = 0
        for cc in [114, 115, 116, 117, 118, 119]: self.control_values[f"cc:{cc}"] = 0
        self.control_values["cc:1"] = 0
        self.control_values["pitchwheel"] = 0

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
        logging.info(f"Loading config from {CONFIG_FILE}")
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                    logging.info("Config loaded successfully")
                    return data
            except Exception as e:
                logging.error(f"Error reading config: {e}", exc_info=True)
        
        # Default config structure if file not found
        logging.warning("Config file not found or corrupted, using empty defaults")
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
            logging.info(f"Config saved successfully to {CONFIG_FILE}")
        except Exception as e:
            logging.error(f"Failed to save config: {e}", exc_info=True)
            self.log_to_monitor(f"System Error: Failed to save config: {e}")

    # ================= UI SETUP =================
    def setup_ui(self):
        logging.debug("Setting up GUI widgets")
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

        # Right Card: Quick Start
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
            "3. Switch to the 'Mappings Manager' tab to see a complete, interactive layout of your controller.\n\n"
            "4. Simply click any control (pad, fader, knob, button, or key) on the visual schematic to map it!\n\n"
            "5. When you interact with the real keyboard, the corresponding control on the screen will light up or move in real-time."
        )

        self.txt_instructions = ctk.CTkLabel(
            self.card_instructions,
            text=instructions_text,
            justify="left",
            wraplength=380,
            font=ctk.CTkFont(size=13)
        )
        self.txt_instructions.grid(row=1, column=0, sticky="w", padx=20, pady=10)

    # ================= INTERACTIVE MIDI VISUALIZER CANVAS =================
    def setup_mappings_tab(self):
        # 1 Row for Visual Canvas (Row 0), 1 Row for Mappings Grid (Row 1)
        self.tab_mappings.grid_columnconfigure(0, weight=1)
        self.tab_mappings.grid_rowconfigure(0, weight=3) # canvas row (expands)
        self.tab_mappings.grid_rowconfigure(1, weight=2) # list/form row (expands)

        # --- Visual Canvas Frame ---
        self.canvas_frame = ctk.CTkFrame(self.tab_mappings, corner_radius=10)
        self.canvas_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 5))
        self.canvas_frame.grid_columnconfigure(0, weight=1)
        self.canvas_frame.grid_rowconfigure(1, weight=1)

        # Draw Title
        self.lbl_visual_title = ctk.CTkLabel(
            self.canvas_frame, 
            text="Interactive MPK249 Schematic — Click any control to map it (Resizes to fit window)", 
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#888"
        )
        self.lbl_visual_title.grid(row=0, column=0, sticky="w", padx=15, pady=(5, 2))

        # Setup Canvas (dynamic resizing)
        self.canvas = tk.Canvas(
            self.canvas_frame, 
            width=920, 
            height=280, 
            bg="#0f0f10", 
            bd=0, 
            highlightthickness=0
        )
        self.canvas.grid(row=1, column=0, padx=10, pady=(2, 10), sticky="nsew")
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Mapping tables to track shapes
        self.canvas_items = {}       # control_id -> item data dict
        self.canvas_to_control = {}  # canvas_widget_id -> control_id string

        # --- Lower Grid Mappings (List on left, Form on right) ---
        self.mappings_lower_frame = ctk.CTkFrame(self.tab_mappings, fg_color="transparent")
        self.mappings_lower_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        self.mappings_lower_frame.grid_columnconfigure(0, weight=3, uniform="lower")
        self.mappings_lower_frame.grid_columnconfigure(1, weight=2, uniform="lower")
        self.mappings_lower_frame.grid_rowconfigure(0, weight=1)

        # Left Frame: Mappings List
        self.list_container = ctk.CTkFrame(self.mappings_lower_frame, corner_radius=10)
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
        self.form_container = ctk.CTkFrame(self.mappings_lower_frame, corner_radius=10)
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

        self.on_action_type_change(self.dropdown_action_type.get())

    # ================= DYNAMIC SCHEMATIC GEOMETRY AND SCALING =================
    def get_scale_params(self):
        """Calculates scale factors and offsets to fit and center the schematic inside the canvas."""
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        # Fallback for initial mapping pass
        if canvas_w < 50 or canvas_h < 50:
            canvas_w = 920
            canvas_h = 280

        target_ratio = 920.0 / 280.0
        if canvas_w / canvas_h > target_ratio:
            h = canvas_h
            w = h * target_ratio
        else:
            w = canvas_w
            h = w / target_ratio

        scale = w / 920.0
        dx = (canvas_w - w) / 2
        dy = (canvas_h - h) / 2
        return scale, dx, dy

    def on_canvas_resize(self, event):
        """Callback triggered on Canvas resize config events to redraw schematic elements."""
        self.canvas.delete("all")
        self.canvas_items.clear()
        self.canvas_to_control.clear()
        self.draw_keyboard_schematic()
        
        # Restore selection highlight if active
        if self.selected_canvas_control_id:
            self.highlight_canvas_control(self.selected_canvas_control_id)

    def draw_keyboard_schematic(self):
        """Draws the vector schematic dynamically scaled to the current canvas dimensions."""
        scale, dx, dy = self.get_scale_params()

        # Helper coordinate scaling functions
        def sc(x, y):
            return dx + x * scale, dy + y * scale

        def sz(val):
            return val * scale

        # 1. Main Chassis Frame
        chassis_id = self.canvas.create_rectangle(sc(10, 10), sc(910, 270), fill="#181819", outline="#323235", width=sz(2))

        # 2. Section Separator panel lines
        self.canvas.create_line(sc(330, 10), sc(330, 180), fill="#252528", width=sz(1))
        self.canvas.create_line(sc(510, 10), sc(510, 180), fill="#252528", width=sz(1))

        # 3. LCD Display Panel
        self.canvas.create_rectangle(sc(350, 25), sc(490, 75), fill="#011f3d", outline="#023b75", width=sz(2))
        
        status_text = "Device: Connected" if self.is_connected else "Device: Standby"
        self.lcd_text_title = self.canvas.create_text(
            sc(420, 38), 
            text="MPK249 MIDI CTRL", 
            fill="#00ffff", 
            font=("Courier", max(4, int(10 * scale)), "bold")
        )
        self.lcd_text_status = self.canvas.create_text(
            sc(420, 58), 
            text=status_text, 
            fill="#00ffaa", 
            font=("Courier", max(4, int(9 * scale)))
        )

        # 4. Mod and Pitch Wheels (rendered at their current MIDI values)
        # Pitch Bend
        p_val = self.control_values.get("pitchwheel", 0)
        p_pct = (p_val + 8192) / 16383.0
        p_y = 95 - p_pct * 50
        
        p_id = self.canvas.create_rectangle(sc(25, 45), sc(45, 95), fill="#222", outline="#444", width=sz(1.5))
        p_ind = self.canvas.create_line(sc(25, p_y), sc(45, p_y), fill="#ff8c00", width=sz(2))
        self.canvas_items["pitchwheel"] = {
            "type": "wheel", "rect_id": p_id, "indicator_id": p_ind, 
            "original_color": "#222", "original_outline": "#444", "original_width": sz(1.5),
            "y_range": (45, 95), "name": "Pitch Bend Wheel"
        }
        self.canvas_to_control[p_id] = "pitchwheel"

        # Modulation Wheel
        m_val = self.control_values.get("cc:1", 0)
        m_pct = m_val / 127.0
        m_y = 95 - m_pct * 50
        
        m_id = self.canvas.create_rectangle(sc(55, 45), sc(75, 95), fill="#222", outline="#444", width=sz(1.5))
        m_ind = self.canvas.create_line(sc(55, m_y), sc(75, m_y), fill="#ff8c00", width=sz(2))
        self.canvas_items["cc:1"] = {
            "type": "wheel", "rect_id": m_id, "indicator_id": m_ind, 
            "original_color": "#222", "original_outline": "#444", "original_width": sz(1.5),
            "y_range": (45, 95), "name": "Modulation Wheel"
        }
        self.canvas_to_control[m_id] = "cc:1"

        # 5. Pads (4x4 matrix)
        for row in range(4):
            for col in range(4):
                pad_num = row * 4 + col + 1
                note_num = 36 + (row * 4 + col)
                control_id = f"note:{note_num}"
                
                px = 115 + col * 52
                py = 135 - row * 34
                
                pad_id = self.canvas.create_rectangle(sc(px, py), sc(px+42, py+26), fill="#121214", outline="#0088cc", width=sz(1.5))
                self.canvas.create_text(
                    sc(px+21, py+13), 
                    text=f"P{pad_num}", 
                    fill="#444449", 
                    font=("Arial", max(4, int(9 * scale)), "bold"), 
                    state="disabled"
                )
                
                self.canvas_items[control_id] = {
                    "type": "pad", "rect_id": pad_id,
                    "original_color": "#121214", "original_outline": "#0088cc", "original_width": sz(1.5),
                    "name": f"Pad {pad_num} (Note {note_num})"
                }
                self.canvas_to_control[pad_id] = control_id

        # 6. Transport Buttons
        transport_configs = [
            {"cc": "cc:114", "text": "LOOP", "x": 345, "fill": "#222"},
            {"cc": "cc:115", "text": "<<"  , "x": 372, "fill": "#222"},
            {"cc": "cc:116", "text": ">>"  , "x": 399, "fill": "#222"},
            {"cc": "cc:117", "text": "STOP", "x": 426, "fill": "#332222"},
            {"cc": "cc:118", "text": "PLAY", "x": 453, "fill": "#223322"},
            {"cc": "cc:119", "text": "REC" , "x": 480, "fill": "#441111"}
        ]
        for btn in transport_configs:
            bx = btn["x"]
            btn_id = self.canvas.create_rectangle(sc(bx, 90), sc(bx+23, 110), fill=btn["fill"], outline="#666", width=sz(1))
            self.canvas.create_text(
                sc(bx+11, 100), 
                text=btn["text"], 
                fill="#888", 
                font=("Arial", max(4, int(7 * scale)), "bold"), 
                state="disabled"
            )
            
            self.canvas_items[btn["cc"]] = {
                "type": "transport", "rect_id": btn_id,
                "original_color": btn["fill"], "original_outline": "#666", "original_width": sz(1.0),
                "name": f"Transport {btn['text']}"
            }
            self.canvas_to_control[btn_id] = btn["cc"]

        # 7. Knobs (K1 - K8)
        for i in range(8):
            cc_num = 22 + i
            control_id = f"cc:{cc_num}"
            kx = 535 + i * 46
            ky = 32
            
            knob_id = self.canvas.create_oval(sc(kx-12, ky-12), sc(kx+12, ky+12), fill="#1b1b1c", outline="#666", width=sz(2))
            
            val = self.control_values.get(control_id, 0)
            angle = -135 + (val / 127.0) * 270
            rad = math.radians(angle)
            px = kx + 12 * math.sin(rad)
            py = ky - 12 * math.cos(rad)
            
            pointer_id = self.canvas.create_line(sc(kx, ky), sc(px, py), fill="#ff8c00", width=sz(2))
            self.canvas.create_text(
                sc(kx, ky+20), 
                text=f"K{i+1}", 
                fill="#555", 
                font=("Arial", max(4, int(8 * scale))), 
                state="disabled"
            )

            self.canvas_items[control_id] = {
                "type": "knob", "rect_id": knob_id, "pointer_id": pointer_id, "center": (kx, ky),
                "original_color": "#1b1b1c", "original_outline": "#666", "original_width": sz(2.0),
                "name": f"Knob K{i+1} (CC {cc_num})"
            }
            self.canvas_to_control[knob_id] = control_id

        # 8. Faders (F1 - F8)
        for i in range(8):
            cc_num = 12 + i
            control_id = f"cc:{cc_num}"
            fx = 535 + i * 46
            y_start, y_end = 65, 135
            
            track_id = self.canvas.create_line(sc(fx, y_start), sc(fx, y_end), fill="#121213", width=sz(4))
            
            val = self.control_values.get(control_id, 0)
            y_pos = y_end - (val / 127.0) * (y_end - y_start)
            
            cap_id = self.canvas.create_rectangle(sc(fx-9, y_pos-4), sc(fx+9, y_pos+4), fill="#1c1c1f", outline="#ffaa00", width=sz(1.5))
            self.canvas.create_text(
                sc(fx, y_end+10), 
                text=f"F{i+1}", 
                fill="#555", 
                font=("Arial", max(4, int(8 * scale))), 
                state="disabled"
            )
            
            self.canvas_items[control_id] = {
                "type": "fader", "rect_id": cap_id, "track_id": track_id, "range": (y_start, y_end), "x": fx,
                "original_color": "#1c1c1f", "original_outline": "#ffaa00", "original_width": sz(1.5),
                "name": f"Fader F{i+1} (CC {cc_num})"
            }
            self.canvas_to_control[cap_id] = control_id

        # 9. Switches (S1 - S8)
        for i in range(8):
            cc_num = 32 + i
            control_id = f"cc:{cc_num}"
            sx = 535 + i * 46
            sy = 162
            
            switch_id = self.canvas.create_rectangle(sc(sx-7, sy-5), sc(sx+7, sy+5), fill="#18181a", outline="#888", width=sz(1.2))
            self.canvas.create_text(
                sc(sx, sy+13), 
                text=f"S{i+1}", 
                fill="#555", 
                font=("Arial", max(4, int(7 * scale))), 
                state="disabled"
            )
            
            self.canvas_items[control_id] = {
                "type": "switch", "rect_id": switch_id,
                "original_color": "#18181a", "original_outline": "#888", "original_width": sz(1.2),
                "name": f"Switch S{i+1} (CC {cc_num})"
            }
            self.canvas_to_control[switch_id] = control_id

        # 10. Keybed (White and Black Keys)
        white_notes = []
        black_notes = []
        for note in range(48, 97):
            if (note % 12) in [1, 3, 6, 8, 10]:
                black_notes.append(note)
            else:
                white_notes.append(note)

        white_key_width = 880.0 / len(white_notes)
        
        # White Keys
        for idx, note in enumerate(white_notes):
            x1 = 20 + idx * white_key_width
            x2 = x1 + white_key_width
            y1, y2 = 190, 265
            
            key_id = self.canvas.create_rectangle(sc(x1, y1), sc(x2, y2), fill="#f8f8fa", outline="#666", width=sz(1))
            control_id = f"note:{note}"
            
            self.canvas_items[control_id] = {
                "type": "key", "rect_id": key_id,
                "original_color": "#f8f8fa", "original_outline": "#666", "original_width": sz(1.0),
                "name": f"Key {note}"
            }
            self.canvas_to_control[key_id] = control_id

        # Black Keys
        white_lookup = {note: idx for idx, note in enumerate(white_notes)}
        black_width = white_key_width * 0.6
        black_height = 46
        
        for note in black_notes:
            base_note = note - 1
            if base_note in white_lookup:
                idx = white_lookup[base_note]
                x_center = 20 + (idx + 1) * white_key_width
                x1 = x_center - black_width / 2
                x2 = x_center + black_width / 2
                y1, y2 = 190, 190 + black_height
                
                key_id = self.canvas.create_rectangle(sc(x1, y1), sc(x2, y2), fill="#1c1c1f", outline="#000", width=sz(1))
                control_id = f"note:{note}"
                
                self.canvas_items[control_id] = {
                    "type": "key", "rect_id": key_id,
                    "original_color": "#1c1c1f", "original_outline": "#000", "original_width": sz(1.0),
                    "name": f"Key {note}"
                }
                self.canvas_to_control[key_id] = control_id

    def on_canvas_click(self, event):
        """Finds clicked item on the canvas schematic and opens it in the editor."""
        clicked_tags = self.canvas.find_withtag("current")
        if not clicked_tags:
            return
            
        canvas_id = clicked_tags[0]
        control_id = self.canvas_to_control.get(canvas_id)
        
        if not control_id:
            # Fallback for subelements
            closest_items = self.canvas.find_closest(event.x, event.y, halo=3)
            for item in closest_items:
                if item in self.canvas_to_control:
                    control_id = self.canvas_to_control[item]
                    break

        if control_id:
            logging.info(f"Canvas clicked: control_id={control_id}")
            self.select_control_by_id(control_id)

    def select_control_by_id(self, control_id):
        """Highlights control on visual canvas and populates the editor form."""
        self.highlight_canvas_control(control_id)
        
        self.entry_control_id.delete(0, tk.END)
        self.entry_control_id.insert(0, control_id)
        
        if control_id in self.active_mappings:
            self.edit_mapping(control_id)
        else:
            self.clear_mapping_form()
            self.entry_control_id.insert(0, control_id)
            
            desc = self.canvas_items[control_id]["name"] if control_id in self.canvas_items else "Custom Control"
            self.entry_description.insert(0, desc)
            
            if control_id.startswith("cc:"):
                cc_val = int(control_id.split(":")[1])
                if cc_val in range(12, 20): # Faders
                    self.dropdown_action_type.set("volume_set")
                    self.on_action_type_change("volume_set")
                else:
                    self.dropdown_action_type.set("keypress")
                    self.on_action_type_change("keypress")

    def highlight_canvas_control(self, control_id):
        """Highlights the selected control on the visual schematic."""
        scale, dx, dy = self.get_scale_params()

        # Clear previous highlight
        if self.selected_canvas_control_id and self.selected_canvas_control_id in self.canvas_items:
            old_item = self.canvas_items[self.selected_canvas_control_id]
            default_outline = old_item.get("original_outline", "#888")
            default_width = old_item.get("original_width", 1.0)
            self.canvas.itemconfig(old_item["rect_id"], outline=default_outline, width=default_width)

        self.selected_canvas_control_id = control_id

        # Apply orange border highlight scaled
        if control_id in self.canvas_items:
            item = self.canvas_items[control_id]
            self.canvas.itemconfig(item["rect_id"], outline="#ff6c00", width=2.5 * scale)

    def update_canvas_control(self, control_id, value):
        """Updates faders, knobs, pads, and keys visually on the canvas when physical inputs occur."""
        if control_id not in self.canvas_items:
            return

        # Store latest value in database
        self.control_values[control_id] = value

        item = self.canvas_items[control_id]
        ctl_type = item["type"]
        scale, dx, dy = self.get_scale_params()

        def sc(x, y):
            return dx + x * scale, dy + y * scale

        # Update LCD screen text
        self.canvas.itemconfig(self.lcd_text_status, text=f"{item['name'].split(' ')[0]} {control_id}: {value}")

        if ctl_type in ["pad", "key", "switch", "transport"]:
            rect_id = item["rect_id"]
            flash_color = "#00f3ff" if ctl_type == "pad" else "#4de680"
            if ctl_type == "transport" and control_id == "cc:119":
                flash_color = "#ff3333"
                
            self.canvas.itemconfig(rect_id, fill=flash_color)
            original_color = item["original_color"]
            self.after(150, lambda r=rect_id, c=original_color: self.canvas.itemconfig(r, fill=c))

        elif ctl_type == "knob":
            kx, ky = item["center"]
            angle = -135 + (value / 127.0) * 270
            rad = math.radians(angle)
            px = kx + 12 * math.sin(rad)
            py = ky - 12 * math.cos(rad)
            
            self.canvas.coords(item["pointer_id"], sc(kx, ky) + sc(px, py))

        elif ctl_type == "fader":
            y_start, y_end = item["range"]
            fx = item["x"]
            y_pos = y_end - (value / 127.0) * (y_end - y_start)
            
            self.canvas.coords(item["rect_id"], sc(fx-9, y_pos-4) + sc(fx+9, y_pos+4))

        elif ctl_type == "wheel":
            y_start, y_end = item["y_range"]
            pct = 0.5
            if control_id == "pitchwheel":
                pct = (value + 8192) / 16383.0
            else:
                pct = value / 127.0
                
            y_pos = y_end - pct * (y_end - y_start)
            
            if control_id == "pitchwheel":
                wx1, wx2 = 25, 45
            else:
                wx1, wx2 = 55, 75
                
            self.canvas.coords(item["indicator_id"], sc(wx1, y_pos) + sc(wx2, y_pos))

    # ================= MIDI EVENT HANDLING =================
    def handle_midi_input(self, msg, control_id, value):
        """Processes MIDI inputs from the MIDI thread."""
        try:
            logging.debug(f"Received MIDI Event -> Control ID: {control_id}, Value: {value}, Raw Msg: {msg}")
            
            self.after(0, self.update_dashboard_signal, control_id, value)
            self.after(0, self.update_canvas_control, control_id, value)
            
            if control_id in self.active_mappings:
                mapping = self.active_mappings[control_id]
                action_type = mapping.get("action_type")
                params = mapping.get("params", {})
                desc = mapping.get("description", "Unknown Action")
                
                self.after(0, lambda d=desc, a=action_type: self.lbl_action_fired.configure(text=f"Fired: {d} ({a})"))
                self.action_handler.execute(action_type, params, value)
            else:
                self.after(0, lambda: self.lbl_action_fired.configure(text="Action: (unmapped)"))

            log_msg = f"MIDI Input | Type: {msg.type:<15} | Control ID: {control_id:<10} | Value: {value:<5}"
            self.after(0, self.log_to_monitor, log_msg)
        except Exception as e:
            logging.error(f"Error handling MIDI input: {e}", exc_info=True)

    def handle_connection_status(self, is_connected, path):
        """Callback for device connection state changes."""
        self.is_connected = is_connected
        self.after(0, self.update_connection_status_ui, is_connected, path)

    def update_connection_status_ui(self, is_connected, path):
        if is_connected:
            self.status_badge.configure(text="🟢 Connected", fg_color="#2da44e")
            self.canvas.itemconfig(self.lcd_text_status, text="Device: Connected")
            self.log_to_monitor(f"System | Device Connected: {path}")
            logging.info(f"System status change: Connected to {path}")
        else:
            self.status_badge.configure(text="🔴 Disconnected", fg_color="#cf4444")
            self.canvas.itemconfig(self.lcd_text_status, text="Device: Disconnected")
            self.log_to_monitor("System | Device Disconnected. Waiting for MPK249...")
            logging.warning("System status change: Disconnected")

    def update_dashboard_signal(self, control_id, value):
        self.lbl_midi_ctrl_name.configure(text=f"Active Control: {control_id}")
        self.lbl_midi_val_number.configure(text=f"Value: {value}")
        if control_id == "pitchwheel":
            self.progress_midi_val.set((value + 8192) / 16383.0)
        else:
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
        logging.info(f"Switched active preset to '{preset_name}'")

    def create_new_preset(self):
        logging.info("Opening New Preset dialog")
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
                logging.info(f"Created and switched to new preset '{preset_name}'")

    # ================= MAPPINGS EDITOR FORM =================
    def on_action_type_change(self, choice):
        self.entry_param_val.delete(0, tk.END)
        logging.debug(f"Action type dropdown selection changed to {choice}")
        
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
        logging.info("Enabling MIDI learn mode")
        self.btn_learn.configure(text="Listening...", fg_color="#d68a00")
        self.midi_manager.enable_midi_learn(self.on_midi_learned)

    def on_midi_learned(self, control_id, msg_type, channel):
        logging.info(f"Control learned in background thread: control_id={control_id}, type={msg_type}")
        self.after(0, self.update_learned_control, control_id)

    def update_learned_control(self, control_id):
        self.entry_control_id.delete(0, tk.END)
        self.entry_control_id.insert(0, control_id)
        self.btn_learn.configure(text="MIDI Learn", fg_color=["#3B8ED0", "#1F6AA5"])
        
        self.highlight_canvas_control(control_id)

        self.entry_description.delete(0, tk.END)
        if control_id in self.canvas_items:
            desc = self.canvas_items[control_id]["name"]
        elif control_id.startswith("cc:"):
            cc_num = control_id.split(":")[1]
            desc = f"Knob/Fader CC {cc_num}"
        elif control_id.startswith("note:"):
            note_num = control_id.split(":")[1]
            desc = f"Key/Pad Note {note_num}"
        else:
            desc = "Custom Control"
            
        self.entry_description.insert(0, desc)
        self.log_to_monitor(f"MIDI Learn | Learned control ID: {control_id}")

    def save_mapping_form(self):
        control_id = self.entry_control_id.get().strip()
        description = self.entry_description.get().strip()
        action_type = self.dropdown_action_type.get()
        param_text = self.entry_param_val.get().strip()

        logging.info(f"Form submission: save mapping key={control_id}, action={action_type}")

        if not control_id:
            tk.messagebox.showerror("Validation Error", "Control ID is required. Try using MIDI Learn or clicking the schematic.")
            return

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
        if key not in self.active_mappings:
            return
        
        logging.info(f"Loading mapping '{key}' for editing")
        self.selected_mapping_key = key
        mapping = self.active_mappings[key]
        
        self.entry_control_id.delete(0, tk.END)
        self.entry_control_id.insert(0, key)
        
        self.entry_description.delete(0, tk.END)
        self.entry_description.insert(0, mapping.get("description", ""))
        
        action_type = mapping.get("action_type", "volume_set")
        self.dropdown_action_type.set(action_type)
        self.on_action_type_change(action_type)
        
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
        if key in self.active_mappings:
            logging.info(f"Deleting mapping for '{key}'")
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
        logging.debug("Redrawing mappings scroll container list")
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
            card = ctk.CTkFrame(self.scroll_mappings, corner_radius=6, fg_color=("#e5e5e5", "#242424"))
            card.grid(row=row, column=0, sticky="ew", padx=5, pady=4)
            card.grid_columnconfigure(0, weight=1)

            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            lbl_title = ctk.CTkLabel(
                info_frame, 
                text=f"{key} → {mapping.get('description', '')}", 
                font=ctk.CTkFont(size=13, weight="bold")
            )
            lbl_title.pack(anchor="w")

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

            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.pack(side="right", padx=10, pady=8)

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

    def setup_monitor_tab(self):
        self.tab_monitor.grid_columnconfigure(0, weight=1)
        self.tab_monitor.grid_rowconfigure(1, weight=1)

        ctrl_frame = ctk.CTkFrame(self.tab_monitor)
        ctrl_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.btn_clear_log = ctk.CTkButton(ctrl_frame, text="Clear Log", command=self.clear_monitor_log, width=100)
        self.btn_clear_log.pack(side="left", padx=10, pady=5)

        self.chk_pause_log = ctk.CTkCheckBox(ctrl_frame, text="Pause Logging", command=self.toggle_logging)
        self.chk_pause_log.pack(side="left", padx=20, pady=5)

        self.txt_monitor = ctk.CTkTextbox(self.tab_monitor, wrap="none", font=ctk.CTkFont(family="monospace", size=12))
        self.txt_monitor.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt_monitor.configure(state="disabled")

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
        
        lines = self.txt_monitor.get("1.0", tk.END).splitlines()
        if len(lines) > 500:
            self.txt_monitor.delete("1.0", "150.0")
            
        self.txt_monitor.configure(state="disabled")

    def on_closing(self):
        """Handles application shutdown cleanly."""
        logging.info("Application shutting down")
        self.midi_manager.stop()
        self.destroy()

if __name__ == "__main__":
    app = Mpk249App()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    try:
        app.mainloop()
    except KeyboardInterrupt:
        app.on_closing()
