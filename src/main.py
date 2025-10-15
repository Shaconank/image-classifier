import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import json
import shutil

import numpy as np
try:
    import cv2
    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False


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
        self.frame = ttk.LabelFrame(parent,text=f"Study: {os.path.basename(study_folder)}",padding=10)
        self.frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.frame.config(width=420, height=520)  
        self.frame.pack_propagate(False)
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
        self.image_container = ttk.Frame(self.frame, width=300, height=250)
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
        """Handle radio button selection (enforce global mutual exclusivity)."""
        val = self.selection_type.get()
        if val in ("raw", "ground_truth"):
            self.main_app.update_selection(self.viewer_id, val)


    def clear_selection(self, only_if_value=None):
        """
        Clear the radio button selection.
        If only_if_value is provided, clear only if the current value matches it.
        This prevents wiping a viewer's *new* role when it previously held another.
        """
        if only_if_value is None or self.selection_type.get() == only_if_value:
            self.selection_type.set("")

    def get_current_image_info(self):
        """Get current image path and filename"""
        if self.images:
            filename = self.images[self.current_index]
            path = os.path.join(self.study_folder, filename)
            return path, filename
        return None, None

    # NEW: jump to a given filename inside this study (if present)
    def jump_to_file(self, filename):
        if not self.images:
            return False
        try:
            idx = self.images.index(filename)
        except ValueError:
            return False
        self.current_index = idx
        self.display_image()
        return True


class MedicalImageApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Medical Image Matching and Labeling Tool")
        self.root.geometry("1400x900")

        self.viewers = {}
        self.current_selections = {"raw": None, "ground_truth": None}
        self.viewer_counter = 0
        self.patient_folders = {}  # Maps patient display names to paths
        self.current_patient_folder = None

        # patient navigation state
        self.patient_order = []          # list of patient display names (same strings as in Combobox)
        self.current_patient_index = -1  # index into patient_order

        # Predefined organs
        self.organs = ["Liver","Liver GB", "Right Kidney","Left Kidney","Right Ovary","Left Ovary","Pancreas", "Spleen","Uterus","Endometrium","Bladder","Prostate"]

        # Load tracking data
        self.processed_files = self.load_tracking_data()
        self.processed_patients = self.load_patient_tracking_data()

        # Load ID counter
        self.id_counter = self.load_id_counter()

        # Recommendations memory
        self._recommendations = []   # list of dicts: {"score":int, "raw":path, "gt":path}

        # Internal flags
        self._updating_reco_table = False

        self.setup_ui()

    def setup_ui(self):
        """Setup the main UI"""
        # Main controls frame
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Combined row: Root Folder + Patient + Navigation + Load buttons
        top_controls = ttk.Frame(control_frame)
        top_controls.pack(fill=tk.X, pady=5)

        # Root Folder
        ttk.Label(top_controls, text="Root Folder:").pack(side=tk.LEFT)
        self.root_folder_var = tk.StringVar()
        ttk.Entry(top_controls, textvariable=self.root_folder_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Button(top_controls, text="Browse", command=self.select_root_folder).pack(side=tk.LEFT)
        ttk.Button(top_controls, text="Load Patients", command=self.load_patients).pack(side=tk.LEFT, padx=5)

        # Spacer
        ttk.Label(top_controls, text="    ").pack(side=tk.LEFT)

        # Patient selection
        ttk.Label(top_controls, text="Patient:").pack(side=tk.LEFT)
        self.patient_var = tk.StringVar()
        self.patient_combo = ttk.Combobox(top_controls, textvariable=self.patient_var, width=25)
        self.patient_combo.pack(side=tk.LEFT, padx=5)
        self.patient_combo.bind('<<ComboboxSelected>>', self.on_patient_selected)

        # Patient navigation
        ttk.Button(top_controls, text="◀ Prev", command=self.prev_patient).pack(side=tk.LEFT, padx=(5, 2))
        ttk.Button(top_controls, text="Next ▶", command=self.next_patient).pack(side=tk.LEFT, padx=(2, 5))

        # Load Studies button
        ttk.Button(top_controls, text="Load Studies", command=self.load_studies).pack(side=tk.LEFT, padx=5)

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
        ttk.Radiobutton(mode_frame, text="No GT", variable=self.mode_var, value="no_gt").pack(side=tk.LEFT, padx=(5, 0))

        ttk.Label(match_frame, text="Organ:").pack(side=tk.LEFT, padx=(10, 0))
        self.organ_var = tk.StringVar()
        organ_combo = ttk.Combobox(match_frame, textvariable=self.organ_var, values=self.organs, width=15)
        organ_combo.pack(side=tk.LEFT, padx=5)

        ttk.Button(match_frame, text="Save", command=self.save_match, style="Accent.TButton").pack(side=tk.LEFT, padx=10)
        ttk.Button(match_frame, text="Find Recommendations", command=self.find_recommendations).pack(side=tk.LEFT, padx=5)

        # Status frame
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_label = ttk.Label(status_frame, text="Ready - Select patient folder to begin")
        self.status_label.pack(side=tk.LEFT)

        # Paned window
        self.main_panes = ttk.Panedwindow(self.root, orient=tk.VERTICAL)
        self.main_panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Top pane: viewers scrollable area
        self.viewers_outer = ttk.Frame(self.main_panes)
        self.main_panes.add(self.viewers_outer, weight=3)

        self.viewers_outer.grid_rowconfigure(0, weight=1)
        self.viewers_outer.grid_columnconfigure(0, weight=1)

        self.viewers_canvas = tk.Canvas(self.viewers_outer, highlightthickness=0)
        self.viewers_canvas.grid(row=0, column=0, sticky="nsew")

        self.viewers_scroll_x = ttk.Scrollbar(
            self.viewers_outer, orient="horizontal", command=self.viewers_canvas.xview
        )
        self.viewers_scroll_x.grid(row=1, column=0, sticky="ew")

        self.scrollable_frame = ttk.Frame(self.viewers_canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.viewers_canvas.configure(scrollregion=self.viewers_canvas.bbox("all"))
        )

        self.canvas_window = self.viewers_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw", tags="inner")
        self.viewers_canvas.configure(xscrollcommand=self.viewers_scroll_x.set)

        # Maintain canvas width on resize
        self.viewers_outer.bind(
            "<Configure>",
            lambda e: self.viewers_canvas.itemconfigure("inner", width=self.viewers_outer.winfo_width())
        )

        # Bottom pane: recommendations
        self.reco_outer = ttk.Frame(self.main_panes)
        self.main_panes.add(self.reco_outer, weight=1)

        reco_frame = ttk.LabelFrame(self.reco_outer, text="Recommended Matches", padding=8)
        reco_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("score", "raw", "gt")
        self.reco_table = ttk.Treeview(reco_frame, columns=cols, show="headings", height=8)
        for c, w in zip(cols, (80, 420, 420)):
            self.reco_table.heading(c, text=c.upper())
            self.reco_table.column(c, width=w, anchor=tk.W)
        self.reco_table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        reco_scroll = ttk.Scrollbar(reco_frame, orient="vertical", command=self.reco_table.yview)
        self.reco_table.configure(yscrollcommand=reco_scroll.set)
        reco_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        reco_btns = ttk.Frame(reco_frame)
        reco_btns.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(reco_btns, text="Approve & Save", command=self.approve_selected_reco).pack(side=tk.LEFT)
        ttk.Button(reco_btns, text="Reject", command=self.reject_selected_reco).pack(side=tk.LEFT, padx=5)

        self.reco_table.bind("<<TreeviewSelect>>", self.on_reco_selected)

        # Set initial sash position (70% viewers, 30% reco)
        self.root.update_idletasks()
        total_h = self.main_panes.winfo_height() or 900
        try:
            self.main_panes.sashpos(0, int(total_h * 0.70))
        except Exception:
            pass

        def _ensure_sash_on_first_resize(_evt=None):
            try:
                total_h2 = self.main_panes.winfo_height() or 900
                self.main_panes.sashpos(0, max(300, int(total_h2 * 0.70)))
            except Exception:
                pass
        self.root.after(50, _ensure_sash_on_first_resize)




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
            # NEW: auto-generate recommendations after loading studies
            # (use after to let UI draw first)
            self.root.after(50, self.find_recommendations)

    def close_all_viewers(self):
        """Close all open viewers"""
        for viewer in list(self.viewers.values()):
            viewer.close_viewer()
        self.viewers.clear()
        self.current_selections = {"raw": None, "ground_truth": None}
        # Clear recommendations table when switching patients
        self.populate_reco_table([])

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

    # ---------- patient navigation helpers ----------
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
    # -------------------------------------------------

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
        """Update selection tracking so only one RAW and one GT exist globally."""

        # 1) Evict previous holder for this role (safely clear only if they still show that role)
        if self.current_selections.get(selection_type):
            old_viewer_id = self.current_selections[selection_type]
            if old_viewer_id in self.viewers and old_viewer_id != viewer_id:
                self.viewers[old_viewer_id].clear_selection(only_if_value=selection_type)

        # 2) If THIS viewer was previously marked as the other role, drop that mapping
        other_type = "ground_truth" if selection_type == "raw" else "raw"
        if self.current_selections.get(other_type) == viewer_id:
            self.current_selections[other_type] = None

        # 3) Record the new holder
        self.current_selections[selection_type] = viewer_id

        # 4) Update UI status
        raw_status = "✓" if self.current_selections.get("raw") else "✗"
        gt_status = "✓" if self.current_selections.get("ground_truth") else "✗"
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

    # ===================== Similarity / Recommendation Engine =====================

    def _status_spin(self, text):
        """Lightweight UI refresh while doing heavy work (keeps Tk responsive)."""
        self.status_label.config(text=text)
        self.root.update_idletasks()

    @staticmethod
    def _yellow_stats_bgr(img_bgr):
        """
        Detect yellow pixels in HSV; ANY yellow -> potential GT.
        Returns (has_yellow: bool, yellow_count: int, mask_ratio: float)
        """
        if img_bgr is None or img_bgr.size == 0:
            return False, 0, 0.0
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        # yellow ~ [15..40] deg; fairly saturated/bright to avoid noise
        lower = np.array([15, 80, 80], dtype=np.uint8)
        upper = np.array([40, 255, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower, upper)
        cnt = int(np.count_nonzero(mask))
        return (cnt > 0), cnt, float(mask.mean()) / 255.0

    @staticmethod
    def _name_has_gt_hint(path_lower):
        """Filename-based hints for GT."""
        hints = ("gt", "ground_truth", "ground-truth", "mask", "annot", "label", "seg", "overlay", "contour")
        return any(h in path_lower for h in hints)

    @staticmethod
    def _prep_gray(img_bgr, max_side=900):
        """To speed up, resize longest side and convert to gray."""
        h, w = img_bgr.shape[:2]
        scale = min(1.0, float(max_side) / max(h, w))
        if scale < 1.0:
            img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        return gray

    @staticmethod
    def _orb():
        return cv2.ORB_create(nfeatures=1200, scaleFactor=1.2, nlevels=8, edgeThreshold=15, fastThreshold=5)

    def _score_pair_orb(self, desc1, kps1, desc2, kps2):
        """Return inlier count using BF+ratio test+RANSAC. 0 if weak."""
        if desc1 is None or desc2 is None or len(desc1) < 8 or len(desc2) < 8:
            return 0

        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        knn = bf.knnMatch(desc1, desc2, k=2)
        good = []
        for m_n in knn:
            if len(m_n) != 2:
                continue
            m, n = m_n
            if m.distance < 0.75 * n.distance:
                good.append(m)

        if len(good) < 8:
            return 0

        src = np.float32([kps1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kps2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if mask is None:
            return 0
        return int(mask.sum())

    def _collect_patient_pngs(self):
        """All PNGs under the current patient folder (path + folder + filename)."""
        paths = []
        for dirpath, _, filenames in os.walk(self.current_patient_folder):
            for f in filenames:
                if f.lower().endswith(".png"):
                    full = os.path.join(dirpath, f)
                    paths.append((full, dirpath, f))
        return paths

    def _build_index(self, all_paths):
        """
        Read once; cache:
          - grayscale for features
          - ORB kps/desc
          - yellow stats
          - area
          - filename GT hint
        """
        idx = {}
        if not _HAS_CV2:
            messagebox.showwarning(
                "OpenCV not available",
                "OpenCV (cv2) is required for recommendations.\n"
                "Install with: pip install opencv-python"
            )
            return idx

        orb = self._orb()
        for i, (full, _, _) in enumerate(all_paths, 1):
            self._status_spin(f"Indexing {i}/{len(all_paths)}: {os.path.basename(full)}")
            img = cv2.imread(full)
            if img is None:
                continue
            has_y, y_cnt, y_frac = self._yellow_stats_bgr(img)
            gray = self._prep_gray(img)
            kps, desc = orb.detectAndCompute(gray, None)
            h, w = gray.shape[:2]
            idx[full] = {
                "kps": kps,
                "desc": desc,
                "area": int(h * w),
                "has_yellow": has_y,
                "yellow_count": y_cnt,
                "yellow_frac": y_frac,
                "name_gt_hint": self._name_has_gt_hint(full.lower())
            }
        return idx

    def _assign_raw_gt(self, p1, p2, idx):
        """
        Decide which path is GT and which is RAW, robustly:
          1) Any yellow → that one is GT (if only one has yellow).
          2) If both (or neither) have yellow → the smaller area is GT (cropped).
          3) Tie-breakers: more yellow_count → GT; filename hints; stable alphabetical fallback.
        Returns (raw_path, gt_path).
        """
        a, b = idx[p1], idx[p2]
        y1, y2 = a["has_yellow"], b["has_yellow"]
        if y1 != y2:
            gt = p1 if y1 else p2
            raw = p2 if y1 else p1
            return raw, gt

        # both yellow or both no-yellow -> use area (cropped GT expected smaller)
        if a["area"] != b["area"]:
            gt = p1 if a["area"] < b["area"] else p2
            raw = p2 if a["area"] < b["area"] else p1
            return raw, gt

        # tie: use yellow_count (more ink likely GT)
        if a["yellow_count"] != b["yellow_count"]:
            gt = p1 if a["yellow_count"] > b["yellow_count"] else p2
            raw = p2 if a["yellow_count"] > b["yellow_count"] else p1
            return raw, gt

        # tie: filename hints
        if a["name_gt_hint"] != b["name_gt_hint"]:
            gt = p1 if a["name_gt_hint"] else p2
            raw = p2 if a["name_gt_hint"] else p1
            return raw, gt

        # final deterministic fallback
        raw, gt = (p1, p2) if p1 < p2 else (p2, p1)
        return raw, gt

    def _make_recommendations(self, idx):
        """
        Score ALL unordered pairs (no mirrored duplicates), assign raw/gt per pair,
        then greedy one-to-one by score.
        """
        if not idx:
            return []

        paths = list(idx.keys())
        n = len(paths)
        MIN_INLIERS = 15
        pairs = []
        total = n * (n - 1) // 2
        done = 0

        # Unordered combinations i < j to avoid mirrored duplicates
        for i in range(n):
            p1 = paths[i]
            d1 = idx[p1]["desc"]; k1 = idx[p1]["kps"]
            for j in range(i + 1, n):
                p2 = paths[j]
                d2 = idx[p2]["desc"]; k2 = idx[p2]["kps"]

                done += 1
                sc = self._score_pair_orb(d1, k1, d2, k2)
                if sc >= MIN_INLIERS:
                    raw, gt = self._assign_raw_gt(p1, p2, idx)
                    pairs.append({"score": sc, "raw": raw, "gt": gt})

                if done % 150 == 0:
                    self._status_spin(f"Scoring pairs {done}/{total}…")

        # Rank by score
        pairs.sort(key=lambda r: r["score"], reverse=True)

        # Greedy unique assignment
        used = set()
        shortlist = []
        for r in pairs:
            if r["raw"] in used or r["gt"] in used:
                continue
            used.add(r["raw"]); used.add(r["gt"])
            shortlist.append(r)
            if len(shortlist) >= 100:
                break

        return shortlist

    def _path_to_display(self, p):
        """Nice, short display with patient-relative path."""
        rel = os.path.relpath(p, self.current_patient_folder)
        return rel.replace("\\", "/")

    def populate_reco_table(self, recos):
        """Fill the Treeview with current recommendations."""
        self._updating_reco_table = True
        try:
            for r in self.reco_table.get_children():
                self.reco_table.delete(r)
            self._recommendations = recos  # keep for interactions
            for i, rec in enumerate(recos):
                self.reco_table.insert(
                    "", "end", iid=str(i),
                    values=(rec["score"], self._path_to_display(rec["raw"]), self._path_to_display(rec["gt"]))
                )
            self.status_label.config(text=f"{len(recos)} recommended raw↔GT pairs")
        finally:
            self._updating_reco_table = False

    def find_recommendations(self):
        """Compute and display recommendations for the current patient (all-vs-all)."""
        if not self.current_patient_folder or not os.path.exists(self.current_patient_folder):
            messagebox.showerror("Error", "Please select a patient first")
            return

        self.status_label.config(text="Collecting PNGs…")
        self.root.update_idletasks()

        all_paths = self._collect_patient_pngs()
        if not all_paths:
            messagebox.showwarning("No images", "No PNGs found under the selected patient.")
            self.populate_reco_table([])
            return

        idx = self._build_index(all_paths)
        recos = self._make_recommendations(idx)
        self.populate_reco_table(recos)

    # ===================== Applying / Approving suggestions =====================

    def _ensure_viewer_for_path(self, study_folder):
        """Return a viewer for the given folder; create it if not open."""
        for v in self.viewers.values():
            if os.path.abspath(v.study_folder) == os.path.abspath(study_folder):
                return v
        # Not open -> open now
        self.viewer_counter += 1
        viewer_id = self.viewer_counter
        viewer = ImageViewer(self.scrollable_frame, study_folder, viewer_id, self)
        self.viewers[viewer_id] = viewer
        return viewer

    def _load_pair_into_viewers(self, raw_full, gt_full, preselect=True):
        """Open the two studies if needed, jump to files, and (optionally) set radio selections."""
        raw_dir, raw_name = os.path.dirname(raw_full), os.path.basename(raw_full)
        gt_dir, gt_name = os.path.dirname(gt_full), os.path.basename(gt_full)

        raw_viewer = self._ensure_viewer_for_path(raw_dir)
        gt_viewer = self._ensure_viewer_for_path(gt_dir)

        ok_raw = raw_viewer.jump_to_file(raw_name)
        ok_gt = gt_viewer.jump_to_file(gt_name)

        if preselect:
            # Pre-select radio buttons (prediction). The user may change these later.
            raw_viewer.selection_type.set("raw")
            gt_viewer.selection_type.set("ground_truth")
            raw_viewer.on_selection_change()
            gt_viewer.on_selection_change()

        if not ok_raw or not ok_gt:
            messagebox.showwarning(
                "Missing file",
                "Could not find one of the files in its study viewer (refresh studies)."
            )


    def _selected_reco_idx(self):
        sel = self.reco_table.selection()
        if not sel:
            return None
        try:
            return int(sel[0])
        except Exception:
            return None

    def on_reco_selected(self, event=None):
        """Auto-load the selected recommendation when clicked."""
        if self._updating_reco_table:
            return  # ignore programmatic selection during refresh
        idx = self._selected_reco_idx()
        if idx is None or not (0 <= idx < len(self._recommendations)):
            return
        rec = self._recommendations[idx]
        # Ensure we're in the paired mode
        self.mode_var.set("has_gt")
        # Auto-load and preselect (user can change after this)
        self._load_pair_into_viewers(rec["raw"], rec["gt"], preselect=True)
        self.status_label.config(text=f"Loaded recommendation (score={rec['score']}). Pick organ and Save.")


    def approve_selected_reco(self):
        """Approve currently selected recommendation, but SAVE whatever radios are set NOW."""
        idx = self._selected_reco_idx()
        if idx is None:
            messagebox.showinfo("Select", "Please click a recommendation first.")
            return

        # Respect the user's current radio selections. Do NOT re-load the predicted pair here.
        if not self.organ_var.get():
            messagebox.showinfo("Organ required", "Pick an organ, then click Approve & Save again.")
            return

        # If user hasn't set both roles yet, help by loading the predicted pair ONCE, then ask to confirm.
        if not self.current_selections.get("raw") or not self.current_selections.get("ground_truth"):
            rec = self._recommendations[idx]
            self._load_pair_into_viewers(rec["raw"], rec["gt"], preselect=True)
            messagebox.showinfo(
                "Selections applied",
                "I've loaded the recommended pair. Verify Raw/GT (swap if needed) and click Approve & Save again."
            )
            return

        # Proceed with saving the CURRENTLY SELECTED viewers/images
        self.mode_var.set("has_gt")
        self.save_match()

        # Remove the approved item from the table (even if user swapped roles; it's handled)
        self.reject_selected_reco()


    def reject_selected_reco(self):
        idx = self._selected_reco_idx()
        if idx is None:
            return
        # Remove from internal list and UI
        if 0 <= idx < len(self._recommendations):
            del self._recommendations[idx]
        self.populate_reco_table(self._recommendations)

    def run(self):
        """Run the application"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MedicalImageApp()
    app.run()
