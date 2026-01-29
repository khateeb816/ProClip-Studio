import os
import math
import threading
import customtkinter as ctk
from datetime import datetime
import random
import string
from tkinter import filedialog, messagebox, Canvas

from PIL import Image, ImageTk

# MoviePy 2.x imports
# MoviePy 2.x imports
from moviepy import VideoFileClip, AudioFileClip, CompositeAudioClip, concatenate_audioclips, ColorClip, CompositeVideoClip

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

# Professional Theme Constants
COLOR_BG_MAIN = "#181818" # Darkest background
COLOR_PANEL_BG = "#202020" # Sidebar/Panels
COLOR_ACCENT = "#3A3A3A" # Input fields/Frames
COLOR_PRIMARY = "#007ACC" # Primary Action (Blue)
COLOR_DANGER = "#D32F2F" # Stop/Delete
COLOR_TEXT = "#E0E0E0"
COLOR_TEXT_DIM = "#909090"
FONT_HEADER = ("Segoe UI", 16, "bold")
FONT_LABEL = ("Segoe UI", 12)
FONT_BTN = ("Segoe UI", 13)

class VideoClipperApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ProClip Studio") # Professional Name
        self.geometry("1280x800")
        self.minsize(1100, 700)
        self.configure(fg_color=COLOR_BG_MAIN)
        
        # Variables
        self.video_path = ctk.StringVar()
        self.audio_path = ctk.StringVar()
        self.output_path = ctk.StringVar()
        
        self.clip_duration = ctk.StringVar(value="60")
        self.audio_mode = ctk.StringVar(value="mix")
        self.aspect_ratio_mode = ctk.StringVar(value="Original (No Crop)")
        self.clip_count_mode = ctk.StringVar(value="auto")
        self.custom_clip_count = ctk.StringVar(value="5")
        
        self.status_msg = ctk.StringVar(value="Ready")
        
        # Editor State
        self.original_frame = None 
        self.tk_image = None
        self.scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.last_mouse_x = 0
        self.last_mouse_y = 0
        
        self.show_grid = False
        self.drag_mode = "pan" # "pan", "resize_tl", "resize_tr", "resize_bl", "resize_br"
        
        self.is_processing = False
        self.stop_event = threading.Event()
        
        self.input_widgets = [] 
        self._combine_layout()

        # Keyboard Bindings (Global)
        self.bind("<KeyPress>", self.on_key_press)

    def on_key_press(self, event):
        # Only active if not entry widget focused? Tkinter handles focus.
        # Check if focusing something else?
        if self.is_processing or not self.original_frame: return
        
        # Check widget focus to avoid capturing entry typing? 
        # But our main entries are numbers only generally.
        if isinstance(self.focus_get(), ctk.CTkEntry): return

        step = 5 if not (event.state & 0x0001) else 20 # Shift for faster? 
        # Actually shift is 1 in state usually? Let's just do 2px precision.
        step = 1 / self.scale # 1 screen pixel effective move
        
        if event.keysym == "Up": self.pan_y += step
        elif event.keysym == "Down": self.pan_y -= step
        elif event.keysym == "Left": self.pan_x += step
        elif event.keysym == "Right": self.pan_x -= step
        else: return # Ignore other keys
        
        self.draw_canvas()

    def _combine_layout(self):
        # 2-Column Layout (Inspector | Viewport)
        self.grid_columnconfigure(0, weight=0, minsize=350) # Sidebar Fixed Width
        self.grid_columnconfigure(1, weight=1) # Viewport Flexible
        self.grid_rowconfigure(0, weight=1)

        # --- Sidebar (Inspector) ---
        self.sidebar = ctk.CTkFrame(self, width=350, fg_color=COLOR_PANEL_BG, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        self._build_sidebar()

        # --- Viewport (Preview) ---
        self.preview_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.preview_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.preview_frame.grid_columnconfigure(0, weight=1)
        self.preview_frame.grid_rowconfigure(1, weight=1) # Canvas row

        self._build_preview()

    def _build_sidebar(self):
        # App Header
        header = ctk.CTkFrame(self.sidebar, height=50, fg_color="#2D2D2D", corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="PROJECT SETTINGS", font=("Segoe UI", 12, "bold"), text_color=COLOR_TEXT_DIM).pack(side="left", padx=20, pady=15)

        # Scrollable Content
        self.scroll_frame = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", scrollbar_button_color="#404040")
        self.scroll_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # 1. Media Source
        self._add_panel("MEDIA SOURCE")
        self._create_path_selector("Video Source", self.video_path, self.select_video, "mp4")
        self._create_path_selector("Background Audio", self.audio_path, self.select_audio, "music")
        
        # 2. Output Configuration
        self._add_panel("EXPORT CONFIGURATION")
        self._create_path_selector("Target Folder", self.output_path, self.select_output, "folder")
        
        # Audio Mixing
        self._create_label("Audio Mix Mode:")
        om_audio = ctk.CTkOptionMenu(self.scroll_frame, variable=self.audio_mode, values=["mix", "background", "original"], 
                                     fg_color=COLOR_ACCENT, button_color="#505050", text_color=COLOR_TEXT)
        om_audio.pack(fill="x", padx=15, pady=5)
        self.input_widgets.append(om_audio)

        # 3. Clip Logic
        self._add_panel("CLIP PARAMETERS")
        
        # Aspect Ratio
        self._create_label("Target Aspect Ratio:")
        self.ar_values = [
            "Original (No Crop)",
            "9:16 (TikTok, Reels, Shorts)",
            "16:9 (YouTube, Landscape)",
            "1:1 (Instagram Square)",
            "4:5 (Instagram Portrait)",
            "Free (Custom)"
        ]
        om_ar = ctk.CTkOptionMenu(self.scroll_frame, variable=self.aspect_ratio_mode, 
                          values=self.ar_values,
                          command=self.on_ar_change,
                          fg_color=COLOR_ACCENT, button_color="#505050", text_color=COLOR_TEXT)
        om_ar.pack(fill="x", padx=15, pady=5)
        self.input_widgets.append(om_ar)

        # Custom Dimensions (For Free Mode)
        self.custom_ar_frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        
        # Pixels Inputs
        dim_row = ctk.CTkFrame(self.custom_ar_frame, fg_color="transparent")
        dim_row.pack(fill="x", pady=5)
        
        self.var_crop_w = ctk.StringVar(value="500")
        self.var_crop_h = ctk.StringVar(value="500")
        
        self.entry_w = ctk.CTkEntry(dim_row, textvariable=self.var_crop_w, width=60, height=28, font=("Segoe UI", 11), fg_color="#303030", border_width=1)
        self.entry_w.pack(side="left", padx=(0,5))
        self.entry_w.bind("<Return>", self.update_from_entry)
        self.entry_w.bind("<FocusOut>", self.update_from_entry)
        
        ctk.CTkLabel(dim_row, text="x", text_color="gray").pack(side="left")
        
        self.entry_h = ctk.CTkEntry(dim_row, textvariable=self.var_crop_h, width=60, height=28, font=("Segoe UI", 11), fg_color="#303030", border_width=1)
        self.entry_h.pack(side="left", padx=(5,0))
        self.entry_h.bind("<Return>", self.update_from_entry)
        self.entry_h.bind("<FocusOut>", self.update_from_entry)
        
        apply_btn = ctk.CTkButton(dim_row, text="APPLY", width=50, height=28, font=("Segoe UI", 10), fg_color="#404040", hover_color="#505050", command=self.update_from_entry)
        apply_btn.pack(side="right")

        # Sliders
        ctk.CTkLabel(self.custom_ar_frame, text="Scale Limit", font=("Segoe UI", 10), text_color="gray").pack(anchor="w", pady=(5,0))
        self.slider_w = ctk.CTkSlider(self.custom_ar_frame, from_=0.1, to=1.0, number_of_steps=100, command=lambda v: self.draw_canvas())
        self.slider_w.set(0.8)
        self.slider_h = ctk.CTkSlider(self.custom_ar_frame, from_=0.1, to=1.0, number_of_steps=100, command=lambda v: self.draw_canvas())
        self.slider_h.set(0.8)
        
        self.slider_w.pack(fill="x", pady=(0,5))
        self.slider_h.pack(fill="x", pady=(0,5))
        
        self.input_widgets.extend([self.entry_w, self.entry_h, apply_btn, self.slider_w, self.slider_h])

        # Clip Settings
        self._add_panel("CLIP SETTINGS")
        
        # Duration
        ctk.CTkLabel(self.scroll_frame, text="Clip Duration (s):", font=FONT_LABEL, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15, pady=(5, 5))
        entry_dur = ctk.CTkEntry(self.scroll_frame, textvariable=self.clip_duration, fg_color=COLOR_ACCENT, border_width=0, text_color=COLOR_TEXT)
        entry_dur.pack(fill="x", padx=15, pady=2)
        self.input_widgets.append(entry_dur)

        # Clip Count / Limit
        ctk.CTkLabel(self.scroll_frame, text="Clips Mode:", font=FONT_LABEL, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15, pady=(10, 5))
        
        # Container for Clip Count controls to maintain order
        self.clips_container = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        self.clips_container.pack(fill="x", padx=0, pady=0)
        
        if self.clip_count_mode.get() not in ["Automatic", "Custom"]: self.clip_count_mode.set("Automatic")
            
        om_count = ctk.CTkOptionMenu(self.clips_container, variable=self.clip_count_mode, values=["Automatic", "Custom"],
                                     command=self.toggle_count,
                                     fg_color=COLOR_ACCENT, button_color="#505050", text_color=COLOR_TEXT)
        om_count.pack(fill="x", padx=15, pady=5)
        self.input_widgets.append(om_count)
        
        # Custom Count Entry
        self.custom_count_frame = ctk.CTkFrame(self.clips_container, fg_color="transparent")
        ctk.CTkLabel(self.custom_count_frame, text="Number of Clips:", font=("Segoe UI", 11), text_color="gray").pack(anchor="w")
        self.entry_count = ctk.CTkEntry(self.custom_count_frame, textvariable=self.custom_clip_count, fg_color=COLOR_ACCENT, border_width=0)
        self.entry_count.pack(fill="x", pady=2)
        self.input_widgets.append(self.entry_count)
        
        # Export Settings
        self._add_panel("EXPORT SETTINGS")
        
        # Quality (Resolution)
        self.quality_var = ctk.StringVar(value="Original")
        ctk.CTkLabel(self.scroll_frame, text="Resolution:", font=FONT_LABEL, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15, pady=(5, 5))
        
        res_values = ["Original", "4k", "1080p", "720p", "480p", "360p", "240p", "144p"]
        om_qual = ctk.CTkOptionMenu(self.scroll_frame, variable=self.quality_var, values=res_values,
                                    fg_color=COLOR_ACCENT, button_color="#505050", text_color=COLOR_TEXT)
        om_qual.pack(fill="x", padx=15, pady=5)
        self.input_widgets.append(om_qual)
        
        # FPS
        self.fps_var = ctk.StringVar(value="Source")
        ctk.CTkLabel(self.scroll_frame, text="FPS:", font=FONT_LABEL, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15, pady=(5, 5))
        om_fps = ctk.CTkOptionMenu(self.scroll_frame, variable=self.fps_var, values=["Source", "60", "30", "24"],
                                   fg_color=COLOR_ACCENT, button_color="#505050", text_color=COLOR_TEXT)
        om_fps.pack(fill="x", padx=15, pady=5)
        self.input_widgets.append(om_fps)
        
        # --- Footer Actions ---
        footer = ctk.CTkFrame(self.sidebar, fg_color="#252525", corner_radius=0, height=100)
        footer.pack(fill="x", side="bottom")
        
        self.status_lbl = ctk.CTkLabel(footer, textvariable=self.status_msg, font=("Consolas", 11), text_color="#00C853", anchor="w")
        self.status_lbl.pack(fill="x", padx=20, pady=(15, 5))

        self.generate_btn = ctk.CTkButton(footer, text="START RENDER", height=45, 
                                          font=("Segoe UI", 14, "bold"), fg_color=COLOR_PRIMARY, hover_color="#0063A5",
                                          corner_radius=4, command=self.start_generation_thread)
        self.generate_btn.pack(fill="x", padx=20, pady=(0, 10))

        self.stop_btn = ctk.CTkButton(footer, text="ABORT", height=30, 
                                      fg_color="transparent", text_color=COLOR_DANGER, hover_color="#331010", border_width=1, border_color=COLOR_DANGER,
                                      state="disabled", command=self.stop_generation)
        self.stop_btn.pack(fill="x", padx=20, pady=(0, 20))

    # ... (skipping unchanged toggle methods)


    def _build_preview(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self.preview_frame, height=50, fg_color="#252525", corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew")
        
        ctk.CTkLabel(toolbar, text="VIEWPORT", font=("Segoe UI", 12, "bold"), text_color=COLOR_TEXT_DIM).pack(side="left", padx=20)
        
        # Grid Toggle Removed as per request

        # Zoom Tools
        z_frame = ctk.CTkFrame(toolbar, fg_color="#333333", corner_radius=6)
        z_frame.pack(side="right", padx=10, pady=8)
        
        b1 = ctk.CTkButton(z_frame, text="-", width=30, height=24, fg_color="transparent", hover_color="#444", command=self.zoom_out)
        b1.pack(side="left", padx=2)
        
        # Split Fit Buttons
        btn_fw = ctk.CTkButton(z_frame, text="Fit W", width=40, height=24, fg_color="transparent",  hover_color="#444", font=("Segoe UI", 10), command=lambda: self.reset_view("w"))
        btn_fw.pack(side="left", padx=2)
        btn_fh = ctk.CTkButton(z_frame, text="Fit H", width=40, height=24, fg_color="transparent",  hover_color="#444", font=("Segoe UI", 10), command=lambda: self.reset_view("h"))
        btn_fh.pack(side="left", padx=2)
        
        b3 = ctk.CTkButton(z_frame, text="+", width=30, height=24, fg_color="transparent",  hover_color="#444", command=self.zoom_in)
        b3.pack(side="left", padx=2)
        self.zoom_btns = [b1, btn_fw, btn_fh, b3]

        # Canvas Container (Dark Background)
        self.canvas_container = ctk.CTkFrame(self.preview_frame, fg_color="#000000", corner_radius=0)
        self.canvas_container.grid(row=1, column=0, sticky="nsew")
        
        self.canvas = Canvas(self.canvas_container, bg="#050505", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", self.on_drag_start)
        self.canvas.bind("<B1-Motion>", self.on_drag_motion)
        self.canvas.bind("<MouseWheel>", self.on_scroll_zoom)
        self.canvas.bind("<Button-4>", self.on_scroll_zoom)
        self.canvas.bind("<Button-5>", self.on_scroll_zoom)
        self.canvas.bind("<Configure>", self.on_canvas_resize)

        # Instruction Overlay
        ctk.CTkLabel(self.preview_frame, text="SCROLL: Zoom | DRAG: Pan | ARROW: Precise | CORNERS: Resize", font=("Consolas", 10), text_color="#505050").grid(row=2, column=0, pady=5)

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.draw_canvas()

    def _add_panel(self, title):
        ctk.CTkLabel(self.scroll_frame, text=title, font=("Segoe UI", 11, "bold"), text_color="#007ACC").pack(anchor="w", padx=15, pady=(20, 5))
        ctk.CTkFrame(self.scroll_frame, height=1, fg_color="#303030").pack(fill="x", padx=15, pady=(0, 10))

    def _create_path_selector(self, label, var, cmd, icon_type="file"):
        lbl = ctk.CTkLabel(self.scroll_frame, text=label, font=FONT_LABEL, text_color=COLOR_TEXT_DIM)
        lbl.pack(anchor="w", padx=15, pady=(5,0))
        
        frame = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        frame.pack(fill="x", padx=15, pady=(2, 10))
        
        entry = ctk.CTkEntry(frame, textvariable=var, fg_color=COLOR_ACCENT, border_width=0, text_color=COLOR_TEXT, state="readonly", height=30)
        entry.pack(side="left", fill="x", expand=True)
        # Mouse click on entry to browse?
        entry.bind("<Button-1>", lambda e: cmd())
        
        btn = ctk.CTkButton(frame, text="...", width=35, height=30, fg_color="#404040", hover_color="#505050", command=cmd)
        btn.pack(side="right", padx=(5,0))
        self.input_widgets.append(btn)

    def _create_label(self, text):
        ctk.CTkLabel(self.scroll_frame, text=text, font=FONT_LABEL, text_color=COLOR_TEXT_DIM).pack(anchor="w", padx=15, pady=(5, 0))

    def toggle_count(self, choice=None):
        if self.is_processing: return
        # Logic for dropdown
        if self.clip_count_mode.get() == "Custom":
            self.custom_count_frame.pack(fill="x", padx=15, pady=5)
        else:
            self.custom_count_frame.pack_forget()

    def toggle_inputs(self, enable):
        state = "normal" if enable else "disabled"
        self.generate_btn.configure(state=state)
        # Recursive disable for created widgets
        for w in self.input_widgets:
            try: w.configure(state=state)
            except: pass
        for b in self.zoom_btns:
            b.configure(state=state)
        
        if enable: self.toggle_count()
        else: self.entry_count.configure(state="disabled")

    # --- Canvas Logic ---
    def load_frame(self):
        if not self.video_path.get(): return
        try:
            # Load video snippet
            clip = VideoFileClip(self.video_path.get())
            t = min(5.0, clip.duration / 2)
            frame = clip.get_frame(t)
            self.original_frame = Image.fromarray(frame)
            clip.close()
            
            # Reset view
            self.reset_view()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load video: {e}")

    def update_from_entry(self, event=None):
        if not self.original_frame: return
        try:
            target_w = int(self.var_crop_w.get())
            target_h = int(self.var_crop_h.get())
            
            # Constraints
            iw, ih = self.original_frame.size
            target_w = min(iw, max(10, target_w))
            target_h = min(ih, max(10, target_h))
            
            # Map back to sliders/canvas (0.0 - 1.0 relative to max canvas fit)
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            margin = 20
            max_c_w = cw - margin*2
            max_c_h = ch - margin*2
            
            # Target on canvas
            target_w_c = target_w * self.scale
            target_h_c = target_h * self.scale
            
            # Update sliders
            self.slider_w.set(min(1.0, target_w_c / max_c_w))
            self.slider_h.set(min(1.0, target_h_c / max_c_h))
            
            # Update strings to normalized
            self.var_crop_w.set(str(target_w))
            self.var_crop_h.set(str(target_h))
            
            self.draw_canvas()
            self.sidebar.focus_set() # Clear focus from entry
            
        except ValueError: pass

    def on_ar_change(self, choice):
        if "Free" in choice:
            self.custom_ar_frame.pack(fill="x", padx=15, pady=5)
            # Init values from current box if possible
            if self.original_frame:
                iw, ih = self.original_frame.size
                # If values empty
                if not self.var_crop_w.get():
                     self.var_crop_w.set(str(int(iw * 0.8)))
                     self.var_crop_h.set(str(int(ih * 0.8)))
        else:
            self.custom_ar_frame.pack_forget()
        self.draw_canvas()

    def reset_view(self, fit_mode="w"):
        if self.is_processing: return
        if not self.original_frame: return
        self.pan_x = 0
        self.pan_y = 0
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        iw, ih = self.original_frame.size
        
        # Calculate Box Sizes first
        ar = self.get_aspect_ratio()
        margin = 20
        max_box_w = cw - margin*2
        max_box_h = ch - margin*2
        
        if self.aspect_ratio_mode.get().startswith("Free"):
             box_w = max_box_w * self.slider_w.get()
             box_h = max_box_h * self.slider_h.get()
        else:
            if max_box_w / max_box_h > ar:
                box_h = max_box_h
                box_w = box_h * ar
            else:
                box_w = max_box_w
                box_h = box_w / ar
        
        # Logic: 
        # Fit W: Scale video so video width == box width
        # Fit H: Scale video so video height == box height
        
        if fit_mode == "w":
            self.scale = box_w / iw
        else:
            self.scale = box_h / ih
        
        self.draw_canvas()

    def zoom_in(self):
        if self.is_processing: return
        self.scale *= 1.02
        self.draw_canvas()
    
    def zoom_out(self):
        if self.is_processing: return
        self.scale *= 0.98
        self.draw_canvas()

    def on_scroll_zoom(self, event):
        if self.is_processing: return
        if event.delta > 0 or event.num == 4:
            self.zoom_in()
        else:
            self.zoom_out()

    def on_drag_start(self, event):
        if self.is_processing: return
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y

    def on_drag_motion(self, event):
        if self.is_processing: return
        dx = event.x - self.last_mouse_x
        dy = event.y - self.last_mouse_y
        self.pan_x += dx
        self.pan_y += dy
        self.last_mouse_x = event.x
        self.last_mouse_y = event.y
        self.draw_canvas()

    def on_canvas_resize(self, event):
        self.draw_canvas()

    def draw_canvas(self):
        if not self.original_frame: return
        self.canvas.delete("all")
        
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        cx = cw // 2
        cy = ch // 2
        
        # 1. Draw Image
        iw, ih = self.original_frame.size
        new_w = int(iw * self.scale)
        new_h = int(ih * self.scale)
        
        img_cx = cx + self.pan_x
        img_cy = cy + self.pan_y
        
        tl_x = int(img_cx - new_w // 2)
        tl_y = int(img_cy - new_h // 2)
        
        try:
            pil_img = self.original_frame.resize((new_w, new_h), Image.Resampling.BILINEAR)
            self.tk_image = ImageTk.PhotoImage(pil_img)
            self.canvas.create_image(tl_x, tl_y, image=self.tk_image, anchor="nw")
        except Exception: pass

        # 2. Draw Crop Overlay (Fixed at Center)
        ar = self.get_aspect_ratio()
        
        margin = 20
        max_box_w = cw - margin*2
        max_box_h = ch - margin*2
        
        if self.aspect_ratio_mode.get().startswith("Free"):
            # Use sliders for box size (relative to canvas max)
            box_w = max_box_w * self.slider_w.get()
            box_h = max_box_h * self.slider_h.get()
        else:
            if max_box_w / max_box_h > ar:
                # Limit by Height
                box_h = max_box_h
                box_w = box_h * ar
            else:
                # Limit by Width
                box_w = max_box_w
                box_h = box_w / ar
            
        self.box_w = box_w
        self.box_h = box_h
        
        # Box coords
        bx1 = cx - box_w/2
        by1 = cy - box_h/2
        bx2 = cx + box_w/2
        by2 = cy + box_h/2
        
        # Dimming
        dim_color = "#000000"
        stipple = "gray50" 
        
        self.canvas.create_rectangle(0, 0, cw, by1, fill=dim_color, stipple=stipple, outline="")
        self.canvas.create_rectangle(0, by2, cw, ch, fill=dim_color, stipple=stipple, outline="")
        self.canvas.create_rectangle(0, by1, bx1, by2, fill=dim_color, stipple=stipple, outline="")
        self.canvas.create_rectangle(bx2, by1, cw, by2, fill=dim_color, stipple=stipple, outline="")
        
        self.canvas.create_rectangle(bx1, by1, bx2, by2, outline="#00FF00", width=3)
        
    def get_aspect_ratio(self):
        mode = self.aspect_ratio_mode.get()
        # Parse verbose names
        if "9:16" in mode: return 9/16
        if "16:9" in mode: return 16/9
        if "1:1" in mode: return 1.0
        if "4:5" in mode: return 4/5
        # Original or Free
        if self.original_frame:
            w, h = self.original_frame.size
            return w/h
        return 16/9

    # --- File Actions ---
    def select_video(self):
        f = filedialog.askopenfilename(filetypes=[("Video", "*.mp4 *.mov *.avi *.mkv")])
        if f:
            self.video_path.set(f)
            self.load_frame()

    def select_audio(self):
        f = filedialog.askopenfilename(filetypes=[("Audio", "*.mp3 *.wav *.aac")])
        if f: self.audio_path.set(f)

    def select_output(self):
        f = filedialog.askdirectory()
        if f: self.output_path.set(f)

    # --- Generation Logic ---
    def stop_generation(self):
        if self.is_processing:
            self.stop_event.set()
            self.status_msg.set("Stopping...")

    def start_generation_thread(self):
        if self.is_processing: return
        if not self.video_path.get() or not self.output_path.get():
            messagebox.showerror("Error", "Select Video and Output Folder.")
            return
        
        try:
            dur = float(self.clip_duration.get())
            if dur <= 0: raise ValueError
        except:
            messagebox.showerror("Error", "Invalid Duration.")
            return

        self.is_processing = True
        self.stop_event.clear()
        
        self.toggle_inputs(False)
        self.generate_btn.configure(text="RENDERING...")
        self.stop_btn.configure(state="normal")
        self.status_msg.set("Initializing Render Engine...")
        
        threading.Thread(target=self.generate_clips, daemon=True).start()

    def generate_clips(self):
        try:
            # 1. Calculate Crop Geometry
            # Relative to Original Image
            # We displayed image at (img_cx, img_cy) with size (new_w, new_h)
            # Crop Box was at (cx, cy) with size (box_w, box_h)
            
            # Center of canvas
            cw = self.canvas.winfo_width()
            ch = self.canvas.winfo_height()
            cx = cw / 2
            cy = ch / 2
            
            # Where is the image top-left?
            iw, ih = self.original_frame.size
            current_w = iw * self.scale
            current_h = ih * self.scale
            
            img_cx = cx + self.pan_x
            img_cy = cy + self.pan_y
            
            img_tl_x = img_cx - current_w / 2
            img_tl_y = img_cy - current_h / 2
            
            # Where is box top-left?
            box_tl_x = cx - self.box_w / 2
            box_tl_y = cy - self.box_h / 2
            
            # Intersection (Relative to Image TL)
            crop_x_display = box_tl_x - img_tl_x
            crop_y_display = box_tl_y - img_tl_y
            
            # Convert to Original Scale
            # real_x = display_x / scale
            real_x = crop_x_display / self.scale
            real_y = crop_y_display / self.scale
            real_w = self.box_w / self.scale
            real_h = self.box_h / self.scale
            
            print(f"Crop: x={real_x}, y={real_y}, w={real_w}, h={real_h}")
            
            # Proceed with MoviePy
            video_path = self.video_path.get()
            output_dir = self.output_path.get()
            audio_path = self.audio_path.get()
            dur = float(self.clip_duration.get())
            
            video = VideoFileClip(video_path)
            
            # Audio Prep
            bg_audio = None
            if self.audio_mode.get() in ["mix", "background"] and audio_path:
                try:
                    bg_audio = AudioFileClip(audio_path)
                except: pass

            # Smart Clip Logic
            # 1. If video is shorter than duration, loop it.
            if video.duration < dur:
                # Calculate how many times we need to loop
                # Example: Vid=10s, Dur=60s. Need 6 loops.
                repeats = math.ceil(dur / video.duration)
                # Concatenate
                # Note: concatenate_videoclips might be heavy for memory if video is large.
                # But for shorter clips it's okay.
                # Use compose method to avoid glitches? method="compose"
                from moviepy import concatenate_videoclips
                video_looped = concatenate_videoclips([video] * repeats)
                # Now crop/cut to exact dur
                # We replace 'video' with this looped version effectively for this clip?
                # Actually, if video < dur, we probably only want 1 clip of length 'dur'.
                # So we treat this as the source.
                video = video_looped
                # Re-calculate limits?
                # If we simply loop, video.duration increases.
                # start=0, end=dur.
            
            max_clips_possible = math.floor(video.duration / dur)
            # If after looping, we have enough for 1 clip?
            
            count_mode = self.clip_count_mode.get()
            requested_count = int(self.custom_clip_count.get()) if count_mode == "Custom" else max_clips_possible
            
            # If automatic, we usually take max_clips_possible.
            # If custom, we try to get 'requested_count'.
            # If video is long enough for N clips, take them.
            # If remainder exists?
            
            total = requested_count
            # Safety cap?
            if count_mode == "Automatic":
                total = max_clips_possible
                # If remainder is significant? User didn't ask.
            
            if total < 1: total = 1 # At least one

            ar_name = self.aspect_ratio_mode.get().split(" ")[0].replace(":", "-")
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            
            # Audio Cache Initialization
            bg_cache = {}
            
            # Export Settings
            resolution_mode = self.quality_var.get()
            fps_choice = self.fps_var.get()
            
            # Map quality to settings
            bitrate = "8000k" # default high
            preset = "medium" # default medium
            target_res_val = None 
            
            if resolution_mode != "Original":
                if "4k" in resolution_mode: 
                    target_res_val = 2160
                    bitrate = "20000k"
                elif "1080p" in resolution_mode:
                    target_res_val = 1080
                    bitrate = "8000k"
                elif "720p" in resolution_mode:
                    target_res_val = 720
                    bitrate = "4000k"
                elif "480p" in resolution_mode:
                    target_res_val = 480
                    bitrate = "2500k"
                elif "360p" in resolution_mode:
                    target_res_val = 360
                    bitrate = "1000k"
                elif "240p" in resolution_mode:
                    target_res_val = 240
                    bitrate = "500k"
                elif "144p" in resolution_mode:
                    target_res_val = 144
                    bitrate = "300k"

            out_fps = video.fps
            if fps_choice != "Source":
                out_fps = float(fps_choice)

            for i in range(total):
                if self.stop_event.is_set(): break
                self.status_msg.set(f"Exporting Clip {i+1}/{total}...")
                
                # Calculate Time Range
                start = i * dur
                end = start + dur
                
                # Check overflow
                if end > video.duration:
                    # Strategy: Backtrack
                    # If we need a clip of 'dur' length ending at video.duration:
                    start = max(0, video.duration - dur)
                    end = video.duration
                    
                    # If even that is not enough (shouldn't happen if we looped short video),
                    # but if video > dur but < (i+1)*dur...
                    # Wait, if `count` is high, we might run out of video completely even with backtracking?
                    # "Backtrack" only makes sense for the *last partial segment*.
                    # If we simply requested 100 clips from 1min video, we'd just get duplicates of the end?
                    # Let's assume we stop if start < previous_end?
                    # User said: "duplicate the video cut it and complete the desired duration" context was for short video.
                    # For end of video: "grab 10 sec from back".
                    # This implies valid overlap.
                    
                    # If start < 0 (should use loop logic ideally, but handled above), set to 0.
                
                clip = video.subclipped(start, end)
                
                # Check bounds
                if not self.aspect_ratio_mode.get().startswith("Original"):
                    # New Composite Logic:
                    # 1. Output Size = real_w x real_h
                    # 2. Video Size = video.w x video.h
                    # 3. Video Position checks:
                    #    x1, y1 are the top-left of the BOX relative to VIDEO.
                    #    If x1 < 0, it means Box starts BEFORE Video (Video starts straight or shifted right in box).
                    #    Wait, `real_x` = box_tl - img_tl (all scaled to real).
                    #    If box is over image, real_x > 0.
                    #    If box is to the left of image (padding left), real_x < 0.
                    #    
                    #    We want to place the Video onto the Black Box.
                    #    Box is (0, 0) to (w, h) in Output coord system.
                    #    Video top-left in Output system?
                    #    If real_x = 100 (Box starts 100px inside video), then Video top-left is at -100 in Box system.
                    #    So pos = (-real_x, -real_y).
                    
                    bg_w = int(real_w)
                    bg_h = int(real_h)
                    
                    # Force Even Dimensions (Required by libx264)
                    if bg_w % 2 != 0: bg_w -= 1
                    if bg_h % 2 != 0: bg_h -= 1
                    
                    if bg_w > 0 and bg_h > 0:
                        # Background
                        bg = ColorClip(size=(bg_w, bg_h), color=(0,0,0), duration=clip.duration)
                        
                        # Foreground Video Position
                        vid_pos = (-int(real_x), -int(real_y))
                        
                        clip = CompositeVideoClip([bg, clip.with_position(vid_pos)], size=(bg_w, bg_h))
                
                # Resolution Resize (Restored & Fixed)
                if target_res_val is not None:
                    curr_w, curr_h = clip.size
                    
                    if curr_w >= curr_h:
                        # Landscape: Set Height
                        clip = clip.resized(height=target_res_val)
                    else:
                        # Portrait: Set Width
                        clip = clip.resized(width=target_res_val)
                    
                    # Ensure final resized dimensions are even
                    rw, rh = clip.size
                    new_rw = int(rw) if int(rw) % 2 == 0 else int(rw) - 1
                    new_rh = int(rh) if int(rh) % 2 == 0 else int(rh) - 1
                    
                    if new_rw != int(rw) or new_rh != int(rh):
                        clip = clip.cropped(width=new_rw, height=new_rh, x_center=rw/2, y_center=rh/2)
                
                # Audio
                final_audio = None
                if bg_audio:
                     # Check cache
                     if dur not in bg_cache:
                         if bg_audio.duration < dur:
                             n = math.ceil(dur / bg_audio.duration)
                             bg_cache[dur] = concatenate_audioclips([bg_audio]*n).subclipped(0, dur)
                         else:
                             bg_cache[dur] = bg_audio.subclipped(0, dur)
                     
                     bg_seg = bg_cache[dur]
                     
                     if self.audio_mode.get() == "background":
                         final_audio = bg_seg
                     elif self.audio_mode.get() == "mix":
                         final_audio = CompositeAudioClip([clip.audio, bg_seg]) if clip.audio else bg_seg
                
                if final_audio:
                    clip = clip.with_audio(final_audio)
                elif self.audio_mode.get() == "original":
                    pass # Keep orig



                # Filename format: DDMMYYYYHHMMSS-RANDOMTEXT-CLIP-N.mp4
                now_ts = datetime.now().strftime("%d%m%Y%H%M%S")
                rand_txt = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                filename = f"{now_ts}-{rand_txt}-CLIP-{i+1}.mp4"

                out_file = os.path.join(output_dir, filename)
                
                # Compatibility Fix: Force yuv420p and aac for Windows support
                clip.write_videofile(
                    out_file, 
                    codec="libx264", 
                    audio_codec="aac",
                    bitrate=bitrate, 
                    audio_bitrate="192k",
                    preset="medium", 
                    fps=out_fps, 
                    threads=4,
                    ffmpeg_params=[
                        "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart"
                    ],
                    logger=None
                )
                
                clip.close()
                if final_audio: final_audio.close()
            
            video.close()
            if bg_audio: bg_audio.close()
            
            if not self.stop_event.is_set():
                self.status_msg.set("Done!")
                if count_mode == "custom" and requested_count > max_clips:
                     messagebox.showinfo("Completed", f"Video was too short for {requested_count} clips.\nGenerated {total} possible clips.")
                else:
                     messagebox.showinfo("Success", f"Generated {total} clips.")
            else:
                self.status_msg.set("Stopped.")

        except Exception as e:
            self.status_msg.set("Error")
            messagebox.showerror("Error", str(e))
            import traceback
            traceback.print_exc()
        finally:
            self.is_processing = False
            self.toggle_inputs(True)
            self.generate_btn.configure(text="START RENDER")
            self.stop_btn.configure(state="disabled")

if __name__ == "__main__":
    app = VideoClipperApp()
    app.mainloop()
