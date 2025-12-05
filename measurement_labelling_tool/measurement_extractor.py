import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import os
from pathlib import Path
from datetime import datetime

# ============================================================================
# CONFIGURATION - POPULATE MEASUREMENT SCHEMAS HERE
# ============================================================================
ORGAN_MEASUREMENTS = {
    "Bladder": ["transverse_diameter", "AP_diameter"],
    "Endometrium": [],
    "Left Kidney": ["Length","Thickness"],
    "Right Kidney": ["Length","Thickness"],
    "Liver": ["Liver_Diameter"],
    "Liver GB": ["Liver_Diameter", "GB_Length", "GB_Width"],
    "Prostate": ["Width", "Height"],
    "Spleen": ["Diameter"],
    "Left Ovary": [],
    "Right Ovary": [],
    "Uterus": ["Length", "Width"]
}

# ============================================================================
# MAIN APPLICATION
# ============================================================================

class MedicalImageAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("Medical Image Annotation Tool")
        self.root.state('zoomed')
        
        # Config file for remembering paths
        self.config_file = "annotation_config.json"
        
        # Data structures
        self.images_data = []
        self.current_index = 0
        self.main_dir = ""
        self.supp_dir = ""
        self.output_path = ""
        self.progress_file = ""
        self.completed_images = set()
        self.flagged_images = {}
        self.last_units = {}  # Remember last used unit for each measurement
        
        self.setup_ui()
        
        # Load saved configuration and auto-load if paths exist
        self.load_config()
        
    def setup_ui(self):
        # Top frame - Directory selection
        top_frame = ttk.Frame(self.root, padding="10")
        top_frame.pack(fill=tk.X)
        
        ttk.Button(top_frame, text="Select Main Directory", 
                   command=self.select_main_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Select Supplementary Directory", 
                   command=self.select_supp_dir).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Select Output Path", 
                   command=self.select_output_path).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_frame, text="Reload Data", 
                   command=self.load_data).pack(side=tk.LEFT, padx=5)
        
        self.status_label = ttk.Label(top_frame, text="No data loaded", foreground="red")
        self.status_label.pack(side=tk.LEFT, padx=20)
        
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Image list
        left_panel = ttk.Frame(main_container, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 10))
        
        ttk.Label(left_panel, text="Images", font=("Arial", 12, "bold")).pack(pady=5)
        
        # Search/Filter
        filter_frame = ttk.Frame(left_panel)
        filter_frame.pack(fill=tk.X, pady=5)
        ttk.Label(filter_frame, text="Filter:").pack(side=tk.LEFT)
        self.filter_var = tk.StringVar()
        self.filter_var.trace('w', self.filter_images)
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Image listbox with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.image_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, 
                                        font=("Arial", 9))
        self.image_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.image_listbox.bind('<<ListboxSelect>>', self.on_image_select)
        scrollbar.config(command=self.image_listbox.yview)
        
        # Progress info
        self.progress_label = ttk.Label(left_panel, text="Progress: 0/0", 
                                       font=("Arial", 10))
        self.progress_label.pack(pady=5)
        
        # Right panel - Image display and annotation
        right_panel = ttk.Frame(main_container)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Image display
        image_frame = ttk.LabelFrame(right_panel, text="Ground Truth Image", padding="10")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.image_label = ttk.Label(image_frame, text="No image loaded", 
                                     background="gray", anchor="center")
        self.image_label.pack(fill=tk.BOTH, expand=True)
        
        # Set maximum size for image display
        self.max_image_width = 600
        self.max_image_height = 450
        
        # Annotation panel - now with fixed height to prevent overflow
        annotation_frame = ttk.LabelFrame(right_panel, text="Annotations", padding="10")
        annotation_frame.pack(fill=tk.BOTH, expand=False, pady=(0, 5))
        
        # Create main horizontal layout: measurements on left, controls on right
        annotation_main = ttk.Frame(annotation_frame)
        annotation_main.pack(fill=tk.BOTH, expand=True)
        
        # Left side - Measurements (scrollable with MAX HEIGHT)
        measurements_container = ttk.Frame(annotation_main)
        measurements_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Create scrollable frame for measurements with FIXED HEIGHT
        self.measurements_canvas = tk.Canvas(measurements_container, height=275, highlightthickness=0)
        scrollbar = ttk.Scrollbar(measurements_container, orient="vertical", command=self.measurements_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.measurements_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.measurements_canvas.configure(scrollregion=self.measurements_canvas.bbox("all"))
        )
        
        self.measurements_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.measurements_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.measurements_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Info row
        info_row = ttk.Frame(self.scrollable_frame)
        info_row.pack(fill=tk.X, pady=5)
        
        self.organ_label = ttk.Label(info_row, text="Organ: N/A", font=("Arial", 11, "bold"))
        self.organ_label.pack(side=tk.LEFT, padx=10)
        
        self.mask_label = ttk.Label(info_row, text="Has Mask: Unknown", font=("Arial", 10))
        self.mask_label.pack(side=tk.LEFT, padx=10)
        
        # Measurements will be added dynamically
        self.measurement_entries = {}
        
        # Right side - Controls (Flag section + Navigation buttons) with PROPER PACKING
        controls_container = ttk.Frame(annotation_main)
        controls_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=False, padx=(10, 0))
        
        # Flag section
        flag_frame = ttk.LabelFrame(controls_container, text="Flagging", padding="10")
        flag_frame.pack(fill=tk.X, pady=(0, 10), expand=False)
        
        self.flag_var = tk.BooleanVar()
        ttk.Checkbutton(flag_frame, text="Flag this image", variable=self.flag_var,
                       command=self.toggle_flag).pack(anchor=tk.W)
        
        ttk.Label(flag_frame, text="Comment:").pack(anchor=tk.W, pady=(5, 0))
        self.flag_comment = tk.Text(flag_frame, height=3, width=30)
        self.flag_comment.pack(fill=tk.X, pady=5)
        
        # Navigation and action buttons - HORIZONTAL LAYOUT
        prev_btn = ttk.Button(info_row, text="← Prev", 
                   command=self.previous_image, width=12)
        prev_btn.pack(side=tk.LEFT, padx=2, expand=False)
        
        next_btn = ttk.Button(info_row, text="Next →", 
                   command=self.next_image, width=12)
        next_btn.pack(side=tk.LEFT, padx=2, expand=False)
        
        save_complete_btn = ttk.Button(info_row, text="💾 Save & Complete", 
                   command=self.save_and_complete, width=18)
        save_complete_btn.pack(side=tk.LEFT, padx=2, expand=False)
        
        self.save_status_label = ttk.Label(info_row, text="", foreground="green", font=("Arial", 8))
        self.save_status_label.pack(side=tk.LEFT, padx=5)
        
        # Keyboard shortcuts
        self.root.bind('<Left>', lambda e: self.previous_image())
        self.root.bind('<Right>', lambda e: self.next_image())
        self.root.bind('<Up>', lambda e: self.previous_image())
        self.root.bind('<Down>', lambda e: self.next_image())
        self.root.bind('<Control-s>', lambda e: self.save_and_complete())
    
    def save_config(self):
        """Save directory paths to config file"""
        config = {
            "main_dir": self.main_dir,
            "supp_dir": self.supp_dir,
            "output_path": self.output_path
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
    
    def load_config(self):
        """Load saved directory paths and auto-load data"""
        if not os.path.exists(self.config_file):
            return
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.main_dir = config.get("main_dir", "")
            self.supp_dir = config.get("supp_dir", "")
            self.output_path = config.get("output_path", "")
            
            # Auto-load if all paths exist
            if all([
                self.main_dir and os.path.exists(self.main_dir),
                self.supp_dir and os.path.exists(self.supp_dir),
                self.output_path
            ]):
                self.progress_file = self.output_path.replace('.json', '_progress.json')
                self.load_data()
                self.status_label.config(text="Auto-loaded from previous session", foreground="blue")
        except Exception as e:
            print(f"Error loading config: {e}")
    
    def select_main_dir(self):
        initial_dir = self.main_dir if self.main_dir and os.path.exists(self.main_dir) else None
        self.main_dir = filedialog.askdirectory(
            title="Select Main Directory (matched_images)",
            initialdir=initial_dir
        )
        if self.main_dir:
            self.save_config()
            messagebox.showinfo("Success", f"Main directory selected:\n{self.main_dir}")
    
    def select_supp_dir(self):
        initial_dir = self.supp_dir if self.supp_dir and os.path.exists(self.supp_dir) else None
        self.supp_dir = filedialog.askdirectory(
            title="Select Supplementary Directory",
            initialdir=initial_dir
        )
        if self.supp_dir:
            self.save_config()
            messagebox.showinfo("Success", f"Supplementary directory selected:\n{self.supp_dir}")
    
    def select_output_path(self):
        initial_file = self.output_path if self.output_path else None
        initial_dir = os.path.dirname(initial_file) if initial_file and os.path.exists(os.path.dirname(initial_file)) else None
        
        self.output_path = filedialog.asksaveasfilename(
            title="Select Output File Location",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialdir=initial_dir,
            initialfile=os.path.basename(initial_file) if initial_file else "annotations.json"
        )
        if self.output_path:
            self.progress_file = self.output_path.replace('.json', '_progress.json')
            self.save_config()
            messagebox.showinfo("Success", f"Output path selected:\n{self.output_path}")
    
    def normalize_organ_name(self, name):
        """Normalize organ names for matching (case-insensitive, handle spaces/underscores)"""
        return name.lower().replace('_', ' ').replace('-', ' ').strip()
    
    def normalize_filename(self, filename):
        """Normalize filenames for matching (case-insensitive, handle spaces/underscores)"""
        return filename.lower().replace('_', ' ').replace('-', ' ').strip()
    
    def find_supplementary_organ_dir(self, organ_name, supp_dir):
        """Find matching supplementary organ directory with special handling for Liver/Liver GB"""
        normalized_organ = self.normalize_organ_name(organ_name)
        
        # Special case: Both "Liver" and "Liver GB" should look in "LiverGB" folder
        if normalized_organ in ['liver', 'liver gb']:
            for supp_organ_dir in supp_dir.iterdir():
                if not supp_organ_dir.is_dir():
                    continue
                normalized_supp = self.normalize_organ_name(supp_organ_dir.name)
                if normalized_supp in ['livergb', 'liver gb']:
                    return supp_organ_dir
        
        # Standard matching for other organs
        for supp_organ_dir in supp_dir.iterdir():
            if not supp_organ_dir.is_dir():
                continue
            normalized_supp = self.normalize_organ_name(supp_organ_dir.name)
            if normalized_supp == normalized_organ:
                return supp_organ_dir
        
        return None
    
    def load_data(self):
        if not all([self.main_dir, self.supp_dir, self.output_path]):
            messagebox.showerror("Error", "Please select all directories and output path first!")
            return
        
        self.images_data = []
        matched_dir = Path(self.main_dir)
        supp_dir = Path(self.supp_dir)
        
        # Scan matched_images directory
        for organ_dir in matched_dir.iterdir():
            if not organ_dir.is_dir():
                continue
            
            organ_name = organ_dir.name
            gt_dir = organ_dir / "ground_truth_images"
            raw_dir = organ_dir / "raw_images"
            
            if not gt_dir.exists():
                continue
            
            # Process each ground truth image
            for gt_file in gt_dir.iterdir():
                if not gt_file.is_file():
                    continue
                
                filename = gt_file.stem  # Without extension
                if not filename.endswith('_gt'):
                    continue
                
                # Parse filename: match_<patient>_<organ>_<id>_gt
                base_name = filename[:-3]  # Remove '_gt'
                raw_filename = base_name + '_raw'
                
                # Find corresponding raw image in main directory
                raw_path = None
                for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']:
                    potential_raw = raw_dir / (raw_filename + ext)
                    if potential_raw.exists():
                        raw_path = str(potential_raw)
                        break
                
                # Check for supplementary images using normalized matching
                supp_raw_path = None
                supp_gt_path = None
                has_mask = False
                
                supp_organ_dir = self.find_supplementary_organ_dir(organ_name, supp_dir)
                
                if supp_organ_dir:
                    supp_raws = supp_organ_dir / "raws"
                    supp_gts = supp_organ_dir / "ground_truths"
                    
                    # Try to find supplementary raw with fuzzy matching
                    if supp_raws.exists():
                        # First try exact match
                        found = False
                        for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']:
                            potential_supp_raw = supp_raws / (raw_filename + ext)
                            if potential_supp_raw.exists():
                                supp_raw_path = str(potential_supp_raw)
                                has_mask = True
                                found = True
                                break
                        
                        # If not found, try fuzzy matching (normalize spaces/underscores)
                        if not found:
                            normalized_raw_filename = self.normalize_filename(raw_filename)
                            for supp_file in supp_raws.iterdir():
                                if supp_file.is_file():
                                    supp_stem = supp_file.stem
                                    if self.normalize_filename(supp_stem) == normalized_raw_filename:
                                        supp_raw_path = str(supp_file)
                                        has_mask = True
                                        break
                    
                    # Try to find supplementary ground truth with fuzzy matching
                    if supp_gts.exists():
                        # First try exact match with _mask suffix
                        found = False
                        mask_filename = raw_filename + '_mask'
                        for ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff']:
                            potential_supp_gt = supp_gts / (mask_filename + ext)
                            if potential_supp_gt.exists():
                                supp_gt_path = str(potential_supp_gt)
                                found = True
                                break
                        
                        # If not found, try fuzzy matching with _mask suffix
                        if not found:
                            normalized_mask_filename = self.normalize_filename(mask_filename)
                            for supp_file in supp_gts.iterdir():
                                if supp_file.is_file():
                                    supp_stem = supp_file.stem
                                    if self.normalize_filename(supp_stem) == normalized_mask_filename:
                                        supp_gt_path = str(supp_file)
                                        break
                
                image_data = {
                    "main_gt_path": str(gt_file),
                    "main_raw_path": raw_path,
                    "supp_raw_path": supp_raw_path,
                    "supp_gt_path": supp_gt_path,
                    "organ_name": organ_name,
                    "has_mask": has_mask,
                    "filename": filename,
                    "measurements": {}
                }
                
                self.images_data.append(image_data)
        
        if not self.images_data:
            messagebox.showerror("Error", "No images found in the specified directories!")
            return
        
        # Load existing output and progress
        self.load_progress()
        self.load_existing_output()
        
        # Populate listbox after loading all progress data
        self.populate_listbox()
        
        # Find first incomplete image or start at beginning
        next_index = 0
        for i, img_data in enumerate(self.images_data):
            if img_data['filename'] not in self.completed_images:
                next_index = i
                break
        
        self.current_index = next_index
        self.display_image(next_index)
        
        self.status_label.config(text=f"Loaded {len(self.images_data)} images", foreground="green")
        self.update_progress_label()
    
    def populate_listbox(self):
        self.image_listbox.delete(0, tk.END)
        filter_text = self.filter_var.get().lower()
        
        for i, img_data in enumerate(self.images_data):
            display_text = f"{img_data['filename']}"
            
            if filter_text and filter_text not in display_text.lower():
                continue
            
            # Add checkmark if completed
            if img_data['filename'] in self.completed_images:
                display_text = "✓ " + display_text
            
            # Add flag indicator
            if img_data['filename'] in self.flagged_images:
                display_text = "🚩 " + display_text
            
            self.image_listbox.insert(tk.END, display_text)
    
    def filter_images(self, *args):
        self.populate_listbox()
    
    def on_image_select(self, event):
        selection = self.image_listbox.curselection()
        if not selection:
            return
        
        # Map filtered index to actual index
        filter_text = self.filter_var.get().lower()
        actual_index = 0
        filtered_count = 0
        
        for i, img_data in enumerate(self.images_data):
            if filter_text and filter_text not in img_data['filename'].lower():
                continue
            
            if filtered_count == selection[0]:
                actual_index = i
                break
            filtered_count += 1
        
        self.display_image(actual_index)
    
    def display_image(self, index):
        if not self.images_data or index < 0 or index >= len(self.images_data):
            return
        
        self.current_index = index
        img_data = self.images_data[index]
        
        # Display image
        try:
            image_path = img_data['main_gt_path']
            img = Image.open(image_path)
            
            # Resize to fit display with max constraints
            img.thumbnail((self.max_image_width, self.max_image_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Keep reference
        except Exception as e:
            self.image_label.config(text=f"Error loading image: {str(e)}")
        
        # Update info
        self.organ_label.config(text=f"Organ: {img_data['organ_name']}")
        mask_status = "Yes ✓" if img_data['has_mask'] else "No ✗"
        mask_color = "green" if img_data['has_mask'] else "red"
        self.mask_label.config(text=f"Has Mask: {mask_status}", foreground=mask_color)
        
        # Clear previous measurement fields
        for widget in self.scrollable_frame.winfo_children():
            if widget != self.scrollable_frame.winfo_children()[0]:  # Keep info row
                widget.destroy()
        
        self.measurement_entries = {}
        
        # Create measurement fields
        organ_name = img_data['organ_name']
        measurements = ORGAN_MEASUREMENTS.get(organ_name, [])
        
        if measurements:
            entry_list = []
            for i, measurement in enumerate(measurements):
                row = ttk.Frame(self.scrollable_frame)
                row.pack(fill=tk.X, pady=5)
                
                ttk.Label(row, text=f"{measurement}:", width=20).pack(side=tk.LEFT, padx=5)
                
                entry = ttk.Entry(row, width=15)
                entry.pack(side=tk.LEFT, padx=5)
                entry_list.append(entry)
                
                # Unit dropdown - use last remembered unit or default to cm
                default_unit = self.last_units.get(measurement, "cm")
                unit_var = tk.StringVar(value=default_unit)
                unit_combo = ttk.Combobox(row, textvariable=unit_var, 
                                          values=["cm", "mm"], width=5, state="readonly")
                unit_combo.pack(side=tk.LEFT, padx=5)
                
                # Save unit preference when changed
                def on_unit_change(e, m=measurement):
                    self.last_units[m] = unit_var.get()
                
                unit_combo.bind('<<ComboboxSelected>>', on_unit_change)
                
                self.measurement_entries[measurement] = {
                    'entry': entry,
                    'unit': unit_var
                }
                
                # Load existing values (saved values override remembered units)
                if measurement in img_data.get('measurements', {}):
                    saved_data = img_data['measurements'][measurement]
                    entry.insert(0, str(saved_data.get('value', '')))
                    saved_unit = saved_data.get('unit', default_unit)
                    unit_var.set(saved_unit)
                    self.last_units[measurement] = saved_unit
            
            # Add tab cycling between entry fields
            for idx, entry in enumerate(entry_list):
                def on_tab(e, current_idx=idx, entries=entry_list):
                    next_idx = (current_idx + 1) % len(entries)
                    entries[next_idx].focus()
                    return 'break'
                entry.bind('<Tab>', on_tab)
            
            # Store entry list for tab navigation from outside
            self.current_entry_list = entry_list
            
            # Focus first measurement entry when image loads
            if entry_list:
                self.root.after(100, lambda: entry_list[0].focus())
        else:
            ttk.Label(self.scrollable_frame, 
                     text=f"No measurements defined for {organ_name}", 
                     foreground="orange").pack(pady=10)
            self.current_entry_list = []
        
        # Load flag status
        self.flag_var.set(img_data['filename'] in self.flagged_images)
        self.flag_comment.delete('1.0', tk.END)
        if img_data['filename'] in self.flagged_images:
            self.flag_comment.insert('1.0', self.flagged_images[img_data['filename']])
        
        # Bind tab on flag comment to go to first measurement
        def on_flag_tab(e):
            if self.current_entry_list:
                self.current_entry_list[0].focus()
                return 'break'
        self.flag_comment.bind('<Tab>', on_flag_tab)
        
        # Highlight in listbox
        self.highlight_current_in_listbox()
        self.update_progress_label()
    
    def highlight_current_in_listbox(self):
        # Find and select current item in listbox
        filter_text = self.filter_var.get().lower()
        filtered_index = 0
        
        for i, img_data in enumerate(self.images_data):
            if filter_text and filter_text not in img_data['filename'].lower():
                continue
            
            if i == self.current_index:
                self.image_listbox.selection_clear(0, tk.END)
                self.image_listbox.selection_set(filtered_index)
                self.image_listbox.see(filtered_index)
                break
            filtered_index += 1
    
    def save_current_annotation(self, auto_save=False):
        """Save current annotation. If auto_save=True, only saves if there are values."""
        if not self.images_data or self.current_index >= len(self.images_data):
            return False
        
        img_data = self.images_data[self.current_index]
        
        # Validate and save measurements
        measurements = {}
        has_any_value = False
        
        for measurement_name, widgets in self.measurement_entries.items():
            value_text = widgets['entry'].get().strip()
            if value_text:
                has_any_value = True
                # Validate numeric
                try:
                    value = float(value_text)
                    measurements[measurement_name] = {
                        'value': value,
                        'unit': widgets['unit'].get()
                    }
                except ValueError:
                    if not auto_save:  # Only show error on manual save
                        messagebox.showerror("Validation Error", 
                                           f"Invalid numeric value for {measurement_name}")
                    return False
        
        # If auto_save and no values, don't save null entries
        if auto_save and not has_any_value:
            return False
        
        img_data['measurements'] = measurements
        return True
    
    def manual_save(self):
        """Manually triggered save that writes to JSON"""
        if self.save_current_annotation(auto_save=False):
            self.save_output()
            self.save_status_label.config(text="✓ Saved!", foreground="green")
            # Clear the status message after 2 seconds
            self.root.after(2000, lambda: self.save_status_label.config(text=""))
        return True
    
    def save_and_complete(self):
        """Save and mark complete in one action"""
        if self.save_current_annotation(auto_save=False):
            self.save_output()
            self.mark_complete()
            self.save_status_label.config(text="✓ Saved & Completed!", foreground="green")
            # Clear the status message after 2 seconds
            self.root.after(2000, lambda: self.save_status_label.config(text=""))
        return True
    
    def toggle_flag(self):
        if not self.images_data:
            return
        
        img_data = self.images_data[self.current_index]
        filename = img_data['filename']
        
        if self.flag_var.get():
            comment = self.flag_comment.get('1.0', tk.END).strip()
            self.flagged_images[filename] = comment
        else:
            if filename in self.flagged_images:
                del self.flagged_images[filename]
        
        self.populate_listbox()
    
    def mark_complete(self):
        if not self.images_data:
            return
        
        # Save current annotation without validation
        if not self.save_current_annotation():
            return
        
        filename = self.images_data[self.current_index]['filename']
        self.completed_images.add(filename)
        self.save_progress()
        self.populate_listbox()
        self.update_progress_label()
        
        # Move to next image
        if self.current_index < len(self.images_data) - 1:
            self.next_image()
    
    def next_image(self):
        if self.current_index < len(self.images_data) - 1:
            self.save_current_annotation(auto_save=True)
            self.display_image(self.current_index + 1)
    
    def previous_image(self):
        if self.current_index > 0:
            self.save_current_annotation(auto_save=True)
            self.display_image(self.current_index - 1)
    
    def update_progress_label(self):
        total = len(self.images_data)
        completed = len(self.completed_images)
        self.progress_label.config(text=f"Progress: {completed}/{total} ({completed*100//total if total > 0 else 0}%)")
    
    def save_output(self):
        if not self.output_path:
            return
        
        output_data = []
        for img_data in self.images_data:
            # Only include entries that have measurements or are flagged/completed
            has_content = (
                img_data.get('measurements') or 
                img_data['filename'] in self.flagged_images or 
                img_data['filename'] in self.completed_images
            )
            
            if has_content:
                # Extract relative paths
                main_gt_path = img_data['main_gt_path'].replace('\\', '/')
                main_raw_path = img_data['main_raw_path'].replace('\\', '/') if img_data['main_raw_path'] else None
                supp_raw_path = img_data['supp_raw_path'].replace('\\', '/') if img_data['supp_raw_path'] else None
                supp_gt_path = img_data['supp_gt_path'].replace('\\', '/') if img_data['supp_gt_path'] else None
                
                # Extract from Data-Images-Combined
                if 'Data-Images-Combined' in main_gt_path:
                    main_gt_path = '/Data-Images-Combined/' + main_gt_path.split('Data-Images-Combined/', 1)[-1]
                if main_raw_path and 'Data-Images-Combined' in main_raw_path:
                    main_raw_path = '/Data-Images-Combined/' + main_raw_path.split('Data-Images-Combined/', 1)[-1]
                
                # Extract from segmentation_dataset
                if supp_raw_path and 'segmentation_dataset' in supp_raw_path:
                    supp_raw_path = '/segmentation_dataset/' + supp_raw_path.split('segmentation_dataset/', 1)[-1]
                if supp_gt_path and 'segmentation_dataset' in supp_gt_path:
                    supp_gt_path = '/segmentation_dataset/' + supp_gt_path.split('segmentation_dataset/', 1)[-1]
                
                entry = {
                    "main_gt_path": main_gt_path,
                    "main_raw_path": main_raw_path,
                    "supp_raw_path": supp_raw_path,
                    "supp_gt_path": supp_gt_path,
                    "organ_name": img_data['organ_name'],
                    "has_mask": img_data['has_mask'],
                    "measurements": img_data.get('measurements', {}),
                    "flagged": img_data['filename'] in self.flagged_images,
                    "flag_comment": self.flagged_images.get(img_data['filename'], ""),
                    "completed": img_data['filename'] in self.completed_images
                }
                output_data.append(entry)
        
        with open(self.output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
    
    def save_progress(self):
        if not self.progress_file:
            return
        
        progress_data = {
            "completed_images": list(self.completed_images),
            "flagged_images": self.flagged_images,
            "last_updated": datetime.now().isoformat()
        }
        
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
    
    def load_progress(self):
        if not self.progress_file or not os.path.exists(self.progress_file):
            return
        
        try:
            with open(self.progress_file, 'r') as f:
                progress_data = json.load(f)
            
            self.completed_images = set(progress_data.get('completed_images', []))
            self.flagged_images = progress_data.get('flagged_images', {})
        except Exception as e:
            print(f"Error loading progress: {e}")
    
    def load_existing_output(self):
        """Load existing annotations if output file exists"""
        if not self.output_path or not os.path.exists(self.output_path):
            return
        
        try:
            with open(self.output_path, 'r') as f:
                existing_data = json.load(f)
            
            # Map existing data back to images_data
            for img_data in self.images_data:
                for existing in existing_data:
                    # Extract relative paths for comparison
                    img_main_gt = img_data['main_gt_path'].replace('\\', '/')
                    existing_main_gt = existing['main_gt_path'].replace('\\', '/')
                    
                    # Compare using relative paths from Data-Images-Combined
                    if 'Data-Images-Combined' in img_main_gt and 'Data-Images-Combined' in existing_main_gt:
                        img_rel = img_main_gt.split('Data-Images-Combined/', 1)[-1]
                        existing_rel = existing_main_gt.split('Data-Images-Combined/', 1)[-1]
                        if img_rel == existing_rel:
                            img_data['measurements'] = existing.get('measurements', {})
                            if existing.get('flagged'):
                                self.flagged_images[img_data['filename']] = existing.get('flag_comment', '')
                            if existing.get('completed'):
                                self.completed_images.add(img_data['filename'])
                            break
                    elif existing['main_gt_path'] == img_data['main_gt_path']:
                        # Fallback to exact match
                        img_data['measurements'] = existing.get('measurements', {})
                        if existing.get('flagged'):
                            self.flagged_images[img_data['filename']] = existing.get('flag_comment', '')
                        if existing.get('completed'):
                            self.completed_images.add(img_data['filename'])
                        break
        except Exception as e:
            print(f"Error loading existing output: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = MedicalImageAnnotator(root)
    root.mainloop()
