import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import shutil
from pathlib import Path

class ImageViewer:
    def __init__(self, parent, study_folder, viewer_id, main_app):
        self.study_folder = study_folder
        self.viewer_id = viewer_id
        self.main_app = main_app
        self.current_index = 0
        self.images = []
        self.selection_type = tk.StringVar()
        
        # Load images from folder
        self.load_images()
        
        # Create viewer frame with minimum width
        self.frame = ttk.LabelFrame(parent, text=f"Study: {os.path.basename(study_folder)}", padding=10)
        self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.frame.config(width=420)  # Minimum width to accommodate 400px image container
        
        # Close button
        close_frame = ttk.Frame(self.frame)
        close_frame.pack(anchor=tk.NE)
        ttk.Button(close_frame, text="✕", width=3, command=self.close_viewer).pack()
        
        # Radio buttons for selection type
        radio_frame = ttk.Frame(self.frame)
        radio_frame.pack(pady=5)
        
        self.raw_radio = ttk.Radiobutton(radio_frame, text="Raw", variable=self.selection_type, 
                                        value="raw", command=self.on_selection_change)
        self.raw_radio.pack(side=tk.LEFT, padx=5)
        
        self.gt_radio = ttk.Radiobutton(radio_frame, text="Ground Truth", variable=self.selection_type, 
                                       value="ground_truth", command=self.on_selection_change)
        self.gt_radio.pack(side=tk.LEFT, padx=5)
        
        # Image display with fixed size container
        self.image_container = ttk.Frame(self.frame, width=400, height=400)
        self.image_container.pack(pady=10, fill=tk.BOTH, expand=True)
        self.image_container.pack_propagate(False)  # Prevent container from shrinking
        
        self.image_label = ttk.Label(self.image_container)
        self.image_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)  # Center the image
        
        # Navigation controls
        nav_frame = ttk.Frame(self.frame)
        nav_frame.pack(pady=5)
        
        self.prev_btn = ttk.Button(nav_frame, text="◀ Previous", command=self.prev_image)
        self.prev_btn.pack(side=tk.LEFT, padx=5)
        
        self.next_btn = ttk.Button(nav_frame, text="Next ▶", command=self.next_image)
        self.next_btn.pack(side=tk.LEFT, padx=5)
        
        # Image counter
        self.counter_label = ttk.Label(self.frame, text="")
        self.counter_label.pack(pady=5)
        
        # Current filename
        self.filename_label = ttk.Label(self.frame, text="", foreground="blue")
        self.filename_label.pack(pady=2)
        
        # Display first image
        self.display_image()
        
    def load_images(self):
        """Load all PNG images from the study folder"""
        if os.path.exists(self.study_folder):
            self.images = [f for f in os.listdir(self.study_folder) 
                          if f.lower().endswith('.png')]
            self.images.sort()
        
    def display_image(self):
        """Display current image"""
        if not self.images:
            self.image_label.config(text="No PNG images found")
            self.counter_label.config(text="0/0")
            self.filename_label.config(text="")
            return
            
        # Update counter
        self.counter_label.config(text=f"{self.current_index + 1}/{len(self.images)}")
        
        # Update filename
        current_filename = self.images[self.current_index]
        self.filename_label.config(text=current_filename)
        
        # Check if this file has been processed
        if self.main_app.is_file_processed(self.study_folder, current_filename):
            self.filename_label.config(foreground="green")
        else:
            self.filename_label.config(foreground="blue")
        
        try:
            image_path = os.path.join(self.study_folder, current_filename)
            image = Image.open(image_path)
            
            # Get container dimensions (accounting for padding)
            container_width = 380  # 400 - 20 for padding
            container_height = 380  # 400 - 20 for padding
            
            # Calculate scaling to fit within container while maintaining aspect ratio
            img_width, img_height = image.size
            scale_w = container_width / img_width
            scale_h = container_height / img_height
            scale = min(scale_w, scale_h)  # Use smaller scale to ensure it fits
            
            # Calculate new dimensions
            new_width = int(img_width * scale)
            new_height = int(img_height * scale)
            
            # Resize image
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(image)
            self.image_label.config(image=photo, text="")
            self.image_label.image = photo  # Keep a reference
            
        except Exception as e:
            self.image_label.config(text=f"Error loading image: {str(e)}")
    
    def prev_image(self):
        """Navigate to previous image"""
        if self.images and self.current_index > 0:
            self.current_index -= 1
            self.display_image()
    
    def next_image(self):
        """Navigate to next image"""
        if self.images and self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.display_image()
    
    def close_viewer(self):
        """Close this viewer"""
        # Clear any selections from this viewer
        if self.main_app.current_selections["raw"] == self.viewer_id:
            self.main_app.current_selections["raw"] = None
        if self.main_app.current_selections["ground_truth"] == self.viewer_id:
            self.main_app.current_selections["ground_truth"] = None
            
        # Remove from main app's viewers dictionary
        if self.viewer_id in self.main_app.viewers:
            del self.main_app.viewers[self.viewer_id]
            
        # Destroy the frame
        self.frame.destroy()
        
        # Update main app status
        raw_status = "✓" if self.main_app.current_selections["raw"] else "✗"
        gt_status = "✓" if self.main_app.current_selections["ground_truth"] else "✗"
        self.main_app.status_label.config(text=f"Raw: {raw_status} | Ground Truth: {gt_status}")
    
    def on_selection_change(self):
        """Handle radio button selection"""
        if self.selection_type.get():
            self.main_app.update_selection(self.viewer_id, self.selection_type.get())
    
    def clear_selection(self):
        """Clear the radio button selection"""
        self.selection_type.set("")
    
    def get_current_image_info(self):
        """Get current image path and filename"""
        if self.images:
            filename = self.images[self.current_index]
            path = os.path.join(self.study_folder, filename)
            return path, filename
        return None, None

class MedicalImageApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Medical Image Matching and Labeling Tool")
        self.root.geometry("1400x800")
        
        self.viewers = {}
        self.current_selections = {"raw": None, "ground_truth": None}
        self.viewer_counter = 0
        self.patient_folders = {}  # Maps patient display names to paths
        self.current_patient_folder = None

        # NEW: patient navigation state
        self.patient_order = []          # list of patient display names (same strings as in Combobox)
        self.current_patient_index = -1  # index into patient_order
        
        # Predefined organs
        self.organs = ["Brain", "Heart", "Liver", "Kidney", "Lung", "Pancreas", "Spleen", "Stomach"]
        
        # Load tracking data
        self.processed_files = self.load_tracking_data()
        self.processed_patients = self.load_patient_tracking_data()
        
        # Load ID counter
        self.id_counter = self.load_id_counter()
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the main UI"""
        # Main controls frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Folder selection
        folder_frame = ttk.Frame(control_frame)
        folder_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(folder_frame, text="Root Folder:").pack(side=tk.LEFT)
        self.root_folder_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.root_folder_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(folder_frame, text="Browse", command=self.select_root_folder).pack(side=tk.LEFT)
        ttk.Button(folder_frame, text="Load Patients", command=self.load_patients).pack(side=tk.LEFT, padx=5)
        
        # Patient selection frame
        patient_frame = ttk.Frame(control_frame)
        patient_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(patient_frame, text="Patient:").pack(side=tk.LEFT)
        self.patient_var = tk.StringVar()
        self.patient_combo = ttk.Combobox(patient_frame, textvariable=self.patient_var, width=40)
        self.patient_combo.pack(side=tk.LEFT, padx=5)
        self.patient_combo.bind('<<ComboboxSelected>>', self.on_patient_selected)

        # NEW: patient navigation buttons
        patient_nav = ttk.Frame(patient_frame)
        patient_nav.pack(side=tk.LEFT, padx=5)
        ttk.Button(patient_nav, text="◀ Prev", command=self.prev_patient).pack(side=tk.LEFT)
        ttk.Button(patient_nav, text="Next ▶", command=self.next_patient).pack(side=tk.LEFT, padx=(5,0))

        ttk.Button(patient_frame, text="Load Studies", command=self.load_studies).pack(side=tk.LEFT, padx=5)
        
        # Study selection frame
        study_frame = ttk.Frame(control_frame)
        study_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(study_frame, text="Available Studies:").pack(side=tk.LEFT)
        self.study_var = tk.StringVar()
        self.study_combo = ttk.Combobox(study_frame, textvariable=self.study_var, width=40)
        self.study_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(study_frame, text="Open Viewer", command=self.open_viewer).pack(side=tk.LEFT)
        
        # Matching controls frame
        match_frame = ttk.Frame(control_frame)
        match_frame.pack(fill=tk.X, pady=5)
        
        # Mode switch
        ttk.Label(match_frame, text="Mode:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="has_gt")
        mode_frame = ttk.Frame(match_frame)
        mode_frame.pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(mode_frame, text="Has GT", variable=self.mode_var, value="has_gt").pack(side=tk.LEFT)
        ttk.Radiobutton(mode_frame, text="No GT", variable=self.mode_var, value="no_gt").pack(side=tk.LEFT, padx=(5,0))
        
        ttk.Label(match_frame, text="Organ:").pack(side=tk.LEFT, padx=(10,0))
        self.organ_var = tk.StringVar()
        organ_combo = ttk.Combobox(match_frame, textvariable=self.organ_var, values=self.organs, width=15)
        organ_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(match_frame, text="Save", command=self.save_match, 
                  style="Accent.TButton").pack(side=tk.LEFT, padx=10)
        
        # Status frame
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=5)
        
        self.status_label = ttk.Label(status_frame, text="Ready - Select patient folder to begin")
        self.status_label.pack(side=tk.LEFT)
        
        # Viewers container
        self.viewers_frame = ttk.Frame(self.root)
        self.viewers_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create scrollable frame for viewers
        canvas = tk.Canvas(self.viewers_frame)
        scrollbar = ttk.Scrollbar(self.viewers_frame, orient="horizontal", command=canvas.xview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(xscrollcommand=scrollbar.set)
        
        canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x")
        
    def select_root_folder(self):
        """Select root folder containing patient folders"""
        folder = filedialog.askdirectory(title="Select Root Folder Containing Patient Folders")
        if folder:
            self.root_folder_var.set(folder)
            
    def load_patients(self):
        """Load available patients from root folder"""
        root_folder = self.root_folder_var.get()
        if not root_folder or not os.path.exists(root_folder):
            messagebox.showerror("Error", "Please select a valid root folder")
            return

        patients = []

        # A patient is any folder directly under root that contains (anywhere below it)
        # at least one subfolder with PNGs.
        for patient_name in os.listdir(root_folder):
            patient_path = os.path.join(root_folder, patient_name)
            if not os.path.isdir(patient_path):
                continue

            has_studies = False  # reset per patient
            # Walk recursively and stop on first directory that has a PNG
            for dirpath, dirnames, filenames in os.walk(patient_path):
                if any(f.lower().endswith(".png") for f in filenames):
                    has_studies = True
                    break
            if has_studies:
                patients.append((patient_name, patient_path))

        if patients:
            # Optional: safe sort by numeric key if present; fallback to name
            def sort_key(item):
                name = item[0]
                digits = ''.join(filter(str.isdigit, name))
                return (0, int(digits)) if digits else (1, name.lower())

            patients.sort(key=sort_key)

            patient_display_names = []
            self.patient_folders = {}
            for patient_name, patient_path in patients:
                if self.is_patient_processed(patient_name):
                    display_name = f"✓ {patient_name}"
                else:
                    display_name = patient_name
                patient_display_names.append(display_name)
                self.patient_folders[display_name] = patient_path

            # Keep an ordered list for prev/next navigation
            self.patient_combo['values'] = patient_display_names
            self.patient_order = patient_display_names[:]
            self.current_patient_index = 0 if self.patient_order else -1

            self.status_label.config(text=f"Found {len(patients)} patients")
        else:
            messagebox.showwarning("Warning", "No patient folders with PNG studies found")
            self.status_label.config(text="No patients found")
    
    def on_patient_selected(self, event=None):
        """Handle patient selection change"""
        patient_display = self.patient_var.get()
        if patient_display and patient_display in self.patient_folders:
            self.current_patient_folder = self.patient_folders[patient_display]
            # Sync index with current selection
            try:
                self.current_patient_index = self.patient_order.index(patient_display)
            except ValueError:
                self.current_patient_index = -1
            # Close all existing viewers
            self.close_all_viewers()
            # Auto-load studies for selected patient
            self.load_studies()
            
    def close_all_viewers(self):
        """Close all open viewers"""
        for viewer in list(self.viewers.values()):
            viewer.close_viewer()
        self.viewers.clear()
        self.current_selections = {"raw": None, "ground_truth": None}
            
    def load_studies(self):
        """Load available studies from selected patient folder (search recursively)"""
        if not self.current_patient_folder or not os.path.exists(self.current_patient_folder):
            messagebox.showerror("Error", "Please select a patient first")
            return

        studies = []

        # Any directory under the patient folder that contains at least one PNG
        for dirpath, dirnames, filenames in os.walk(self.current_patient_folder):
            if any(f.lower().endswith(".png") for f in filenames):
                # Use a friendly display name relative to the patient folder
                rel_name = os.path.relpath(dirpath, self.current_patient_folder)
                # Avoid listing the patient root itself if PNGs sit directly there (unlikely but safe)
                display_name = rel_name if rel_name != "." else os.path.basename(dirpath)
                studies.append((display_name, dirpath))

        if studies:
            # Sort for consistent ordering
            studies.sort(key=lambda x: x[0].lower())
            study_names = [name for name, path in studies]
            self.study_combo['values'] = study_names
            self.study_paths = {name: path for name, path in studies}
            self.status_label.config(text=f"Found {len(studies)} studies - Opening viewers...")

            # Automatically open viewers for all found studies
            for study_name, study_path in studies:
                self.viewer_counter += 1
                viewer_id = self.viewer_counter
                viewer = ImageViewer(self.scrollable_frame, study_path, viewer_id, self)
                self.viewers[viewer_id] = viewer

            self.status_label.config(text=f"Opened {len(studies)} viewers - Ready to process")
        else:
            messagebox.showwarning("Warning", "No studies with PNG images found")
            self.status_label.config(text="No studies found")

    # ---------- NEW: patient navigation helpers ----------
    def select_patient_by_index(self, idx):
        """Select patient by index, update UI, and trigger the usual flow."""
        if not self.patient_order:
            messagebox.showwarning("Warning", "No patients loaded")
            return
        idx = idx % len(self.patient_order)  # wrap-around
        self.current_patient_index = idx
        name = self.patient_order[idx]
        # Set combobox visible value
        self.patient_var.set(name)
        # Trigger selection logic
        self.on_patient_selected()

    def prev_patient(self):
        """Jump to previous patient (wrap-around)."""
        if not self.patient_order:
            messagebox.showwarning("Warning", "No patients loaded")
            return
        next_idx = (self.current_patient_index - 1) % len(self.patient_order)
        self.select_patient_by_index(next_idx)

    def next_patient(self):
        """Jump to next patient (wrap-around)."""
        if not self.patient_order:
            messagebox.showwarning("Warning", "No patients loaded")
            return
        next_idx = (self.current_patient_index + 1) % len(self.patient_order)
        self.select_patient_by_index(next_idx)
    # -----------------------------------------------------
            
    def open_viewer(self):
        """Open a new image viewer for selected study"""
        study_name = self.study_var.get()
        if not study_name or study_name not in self.study_paths:
            messagebox.showerror("Error", "Please select a study")
            return
            
        study_path = self.study_paths[study_name]
        self.viewer_counter += 1
        viewer_id = self.viewer_counter
        
        viewer = ImageViewer(self.scrollable_frame, study_path, viewer_id, self)
        self.viewers[viewer_id] = viewer
        
        self.status_label.config(text=f"Opened viewer for {study_name}")
        
    def update_selection(self, viewer_id, selection_type):
        """Update selection tracking"""
        # Clear previous selection of this type
        if self.current_selections[selection_type]:
            old_viewer_id = self.current_selections[selection_type]
            if old_viewer_id in self.viewers and old_viewer_id != viewer_id:
                self.viewers[old_viewer_id].clear_selection()
        
        self.current_selections[selection_type] = viewer_id
        
        # Update status
        raw_status = "✓" if self.current_selections["raw"] else "✗"
        gt_status = "✓" if self.current_selections["ground_truth"] else "✗"
        self.status_label.config(text=f"Raw: {raw_status} | Ground Truth: {gt_status}")
        
    def save_match(self):
        """Save the matched pair of images or single raw image"""
        mode = self.mode_var.get()
        
        # Validate selections based on mode
        if mode == "has_gt":
            if not self.current_selections["raw"] or not self.current_selections["ground_truth"]:
                messagebox.showerror("Error", "Please select both raw and ground truth images")
                return
        elif mode == "no_gt":
            if not self.current_selections["raw"]:
                messagebox.showerror("Error", "Please select a raw image")
                return
            
        if not self.organ_var.get():
            messagebox.showerror("Error", "Please select an organ")
            return
            
        # Get image information
        raw_viewer = self.viewers[self.current_selections["raw"]]
        raw_path, raw_filename = raw_viewer.get_current_image_info()
        
        if not raw_path:
            messagebox.showerror("Error", "Could not get raw image information")
            return
        
        organ = self.organ_var.get()
        
        if mode == "has_gt":
            # Original matched pair logic
            gt_viewer = self.viewers[self.current_selections["ground_truth"]]
            gt_path, gt_filename = gt_viewer.get_current_image_info()
            
            if not gt_path:
                messagebox.showerror("Error", "Could not get ground truth image information")
                return
                
            # Create output directory structure
            output_base = os.path.join(os.getcwd(), "matched_images", organ)
            raw_output_dir = os.path.join(output_base, "raw_images")
            gt_output_dir = os.path.join(output_base, "ground_truth_images")
            
            os.makedirs(raw_output_dir, exist_ok=True)
            os.makedirs(gt_output_dir, exist_ok=True)
            
            # Generate ID and filenames
            self.id_counter += 1
            raw_output_name = f"{self.id_counter:03d}_raw.png"
            gt_output_name = f"{self.id_counter:03d}_ground_truth.png"
            
            raw_output_path = os.path.join(raw_output_dir, raw_output_name)
            gt_output_path = os.path.join(gt_output_dir, gt_output_name)
            
            try:
                # Copy files
                shutil.copy2(raw_path, raw_output_path)
                shutil.copy2(gt_path, gt_output_path)
                
                # Update tracking
                self.mark_file_processed(raw_viewer.study_folder, raw_filename)
                self.mark_file_processed(gt_viewer.study_folder, gt_filename)
                
                # Mark patient as processed
                self.mark_patient_processed()
                
                # Save tracking and ID counter
                self.save_tracking_data()
                self.save_patient_tracking_data()
                self.save_id_counter()
                
                # Refresh displays
                raw_viewer.display_image()
                gt_viewer.display_image()
                
                # Clear selections
                for viewer in self.viewers.values():
                    viewer.clear_selection()
                self.current_selections = {"raw": None, "ground_truth": None}
                
                self.status_label.config(text=f"Saved match {self.id_counter:03d} for {organ} - Ready for next")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save images: {str(e)}")
                
        elif mode == "no_gt":
            # Pure raw image logic
            output_base = os.path.join(os.getcwd(), "pure_raw_images", organ)
            os.makedirs(output_base, exist_ok=True)
            
            # Generate sequential filename for pure raw images
            existing_files = [f for f in os.listdir(output_base) if f.endswith('_raw.png')]
            next_id = len(existing_files) + 1
            raw_output_name = f"{next_id:03d}_raw.png"
            raw_output_path = os.path.join(output_base, raw_output_name)
            
            try:
                # Copy file
                shutil.copy2(raw_path, raw_output_path)
                
                # Update tracking
                self.mark_file_processed(raw_viewer.study_folder, raw_filename)
                self.mark_patient_processed()
                self.save_tracking_data()
                self.save_patient_tracking_data()
                
                # Refresh display
                raw_viewer.display_image()
                
                # Clear selections
                for viewer in self.viewers.values():
                    viewer.clear_selection()
                self.current_selections = {"raw": None, "ground_truth": None}
                
                self.status_label.config(text=f"Saved pure raw {next_id:03d} for {organ} - Ready for next")
                
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save image: {str(e)}")
            
    def mark_file_processed(self, study_folder, filename):
        """Mark a file as processed"""
        if study_folder not in self.processed_files:
            self.processed_files[study_folder] = set()
        self.processed_files[study_folder].add(filename)
        
    def is_file_processed(self, study_folder, filename):
        """Check if a file has been processed"""
        return study_folder in self.processed_files and filename in self.processed_files[study_folder]
        
    def load_tracking_data(self):
        """Load processed files tracking data"""
        tracking_file = "processed_files.json"
        if os.path.exists(tracking_file):
            try:
                with open(tracking_file, 'r') as f:
                    data = json.load(f)
                    # Convert lists back to sets
                    return {k: set(v) for k, v in data.items()}
            except:
                pass
        return {}
        
    def save_tracking_data(self):
        """Save processed files tracking data"""
        tracking_file = "processed_files.json"
        # Convert sets to lists for JSON serialization
        data = {k: list(v) for k, v in self.processed_files.items()}
        with open(tracking_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_id_counter(self):
        """Load the ID counter"""
        counter_file = "id_counter.json"
        if os.path.exists(counter_file):
            try:
                with open(counter_file, 'r') as f:
                    data = json.load(f)
                    return data.get('counter', 0)
            except:
                pass
        return 0
        
    def save_id_counter(self):
        """Save the ID counter"""
        counter_file = "id_counter.json"
        with open(counter_file, 'w') as f:
            json.dump({'counter': self.id_counter}, f, indent=2)

    def load_patient_tracking_data(self):
        """Load processed patients tracking data"""
        tracking_file = "processed_patients.json"
        if os.path.exists(tracking_file):
            try:
                with open(tracking_file, 'r') as f:
                    data = json.load(f)
                    return set(data)
            except:
                pass
        return set()
    
    def save_patient_tracking_data(self):
        """Save processed patients tracking data"""
        tracking_file = "processed_patients.json"
        with open(tracking_file, 'w') as f:
            json.dump(list(self.processed_patients), f, indent=2)
    
    def mark_patient_processed(self):
        """Mark the current patient as processed"""
        if self.current_patient_folder:
            patient_name = os.path.basename(self.current_patient_folder)
            self.processed_patients.add(patient_name)
    
    def is_patient_processed(self, patient_name):
        """Check if a patient has been processed"""
        return patient_name in self.processed_patients

    def run(self):
        """Run the application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = MedicalImageApp()
    app.run()
