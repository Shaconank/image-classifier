import os
import shutil
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

# Default root folder - changeable in the UI
ROOT_DATA_DIR = "Data-Remapped-Combined"

IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
LOG_FILE = 'organ_reclassifier_moves_log.json'


class OrganReclassifierApp(tk.Tk):
    def __init__(self, root_dir=None):
        super().__init__()
        self.title('Organ Reclassifier')
        self.geometry('1100x700')

        self.root_dir = root_dir or ROOT_DATA_DIR
        self.dataset_types = ['matched_images', 'pure_raw_images']
        self.current_dataset = tk.StringVar(value=self.dataset_types[0])
        self.current_organ = tk.StringVar()
        self.target_organ = tk.StringVar()
        self.view_gt = tk.BooleanVar(value=False)  # Only for matched_images

        # Internal state
        self.organs = []
        self.data_points = []  # list of folder names for current organ
        self.current_index = 0
        self.current_image_tk = None

        # Add raw data path constant
        self.RAW_DATA_DIR = r"C:\Users\shash\OneDrive\Documents\golej\Capstone\full_exported_data\full_exported_data"
        # Add OpenCV check
        self.has_cv2 = False
        try:
            import cv2
            import numpy as np
            self.has_cv2 = True
        except ImportError:
            pass

        # Build UI
        self._build_controls()
        self.scan_organs()
        # Defer initial load until after the window has been drawn so canvas sizes are valid.
        self.after(150, self.load_organ)

        # Bind keys
        self.bind('<Left>', lambda e: self.prev_item())
        self.bind('<Right>', lambda e: self.next_item())
        self.bind('<Key-m>', lambda e: self.move_current())

        # Ensure log file exists
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w') as f:
                json.dump([], f)

        # Add instance variable to track similar image window
        self.similar_window = None
        # Add variable to store current matches and index
        self.current_matches = []
        self.current_match_index = 0
    def set_as_pure_raw(self):
        """Move the current matched image (raw or ground truth view) into pure_raw_images and delete the pair."""
        ds = self.current_dataset.get()
        if ds != 'matched_images':
            messagebox.showwarning("Invalid Operation", "This action is only available for matched_images dataset.")
            return

        if not self.data_points:
            messagebox.showinfo("No item", "No data point selected.")
            return

        organ = self.current_organ.get()
        name = self.data_points[self.current_index]
        is_gt = self.view_gt.get()

        # Determine source folder
        src_dir = os.path.join(self.root_dir, ds, organ, 
                            'ground_truth_images' if is_gt else 'raw_images', name)
        other_dir = os.path.join(self.root_dir, ds, organ,
                                'raw_images' if is_gt else 'ground_truth_images', name)

        if not os.path.isdir(src_dir):
            messagebox.showerror("Error", f"Source folder not found: {src_dir}")
            return

        # Destination in pure_raw_images
        dest_dir = os.path.join(self.root_dir, 'pure_raw_images', organ, name)
        os.makedirs(dest_dir, exist_ok=True)

        # Collect files (png, json, dcm/_anon.dcm)
        src_png = src_json = src_dcm = None
        for file in os.listdir(src_dir):
            ext = os.path.splitext(file)[1].lower()
            path = os.path.join(src_dir, file)
            if ext == '.png':
                src_png = path
            elif ext == '.json':
                src_json = path
            elif ext == '.dcm' or file.lower().endswith('_anon.dcm'):
                src_dcm = path

        if not src_png:
            messagebox.showerror("Error", "No .png file found in source folder.")
            return

        # Confirm
        if not messagebox.askyesno("Confirm", f"Move '{name}' ({'GT' if is_gt else 'Raw'}) to pure_raw_images/{organ}?"):
            return

        try:
            # Copy files to new destination
            shutil.copy2(src_png, os.path.join(dest_dir, os.path.basename(src_png)))
            if src_json and os.path.exists(src_json):
                shutil.copy2(src_json, os.path.join(dest_dir, os.path.basename(src_json)))
            if src_dcm and os.path.exists(src_dcm):
                shutil.copy2(src_dcm, os.path.join(dest_dir, os.path.basename(src_dcm)))

            # Log the move
            self._log_move({
                "action": "set_as_pure_raw",
                "dataset": ds,
                "organ": organ,
                "name": name,
                "source_dir": src_dir,
                "destination_dir": dest_dir,
                "moved_files": [src_png, src_json, src_dcm],
            })

            # Delete both raw and ground truth folders
            deleted = []
            if os.path.isdir(src_dir):
                shutil.rmtree(src_dir)
                deleted.append(src_dir)
            if os.path.isdir(other_dir):
                shutil.rmtree(other_dir)
                deleted.append(other_dir)

            self._log_move({
                "action": "delete_matched_pair_after_set_as_pure_raw",
                "dataset": ds,
                "organ": organ,
                "name": name,
                "deleted_folders": deleted
            })

            # Refresh UI
            self.current_dataset.set('pure_raw_images')
            self.scan_organs()
            self.current_organ.set(organ)
            self.load_organ()
            self.load_organ()
            messagebox.showinfo("Success", f"'{name}' moved to pure_raw_images/{organ} and pair deleted.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to move image:\n{e}")

    def _build_controls(self):
        # Top frame for dataset and root dir
        top_frame = ttk.Frame(self)
        top_frame.pack(fill='x', padx=8, pady=6)

        ttk.Label(top_frame, text='Root folder:').pack(side='left')
        self.root_label = ttk.Label(top_frame, text=self.root_dir)
        self.root_label.pack(side='left', padx=(4, 12))
        ttk.Button(top_frame, text='Change...', command=self.change_root).pack(side='left')

        ttk.Label(top_frame, text='Dataset:').pack(side='left', padx=(20, 4))
        ds_cb = ttk.Combobox(top_frame, values=self.dataset_types, textvariable=self.current_dataset, state='readonly', width=18)
        ds_cb.pack(side='left')
        ds_cb.bind('<<ComboboxSelected>>', lambda e: self.scan_organs())

        # Left panel - image viewer
        main_pane = ttk.Panedwindow(self, orient='horizontal')
        main_pane.pack(fill='both', expand=True, padx=8, pady=6)

        left_frame = ttk.Frame(main_pane, width=700)
        right_frame = ttk.Frame(main_pane, width=350)
        main_pane.add(left_frame, weight=3)
        main_pane.add(right_frame, weight=1)

        # Viewer area
        viewer_top = ttk.Frame(left_frame)
        viewer_top.pack(fill='x')
        ttk.Label(viewer_top, text='Organ:').pack(side='left')
        self.organ_cb = ttk.Combobox(viewer_top, values=self.organs, textvariable=self.current_organ, state='readonly', width=30)
        self.organ_cb.pack(side='left', padx=6)
        self.organ_cb.bind('<<ComboboxSelected>>', lambda e: self.load_organ())

        # Toggle for raw/ground truth (only for matched_images)
        self.gt_toggle = ttk.Checkbutton(viewer_top, text='Show ground truth', variable=self.view_gt, command=self.show_current)
        self.gt_toggle.pack(side='left', padx=8)

        nav_frame = ttk.Frame(viewer_top)
        nav_frame.pack(side='right')
        ttk.Button(nav_frame, text='Prev', command=self.prev_item).pack(side='left')
        ttk.Button(nav_frame, text='Next', command=self.next_item).pack(side='left')

        self.canvas = tk.Canvas(left_frame, bg='black')
        self.canvas.pack(fill='both', expand=True)
        # Redraw preview on canvas resize so thumbnails are regenerated to the new size.
        self.canvas.bind('<Configure>', lambda e: self.after(50, self._on_canvas_configure))

        status_frame = ttk.Frame(left_frame)
        status_frame.pack(fill='x')
        self.status_label = ttk.Label(status_frame, text='No item loaded')
        self.status_label.pack(side='left')

        # Right pane - controls
        ttk.Label(right_frame, text='Target Organ:').pack(anchor='nw', pady=(6, 0))
        self.target_cb = ttk.Combobox(right_frame, values=self.organs, textvariable=self.target_organ, state='readonly', width=28)
        self.target_cb.pack(anchor='nw', padx=6, pady=4)

        ttk.Button(right_frame, text='Move here', command=self.move_current).pack(anchor='nw', padx=6, pady=(6, 4))

        # Switch raw/ground truth button
        ttk.Button(right_frame, text='Switch Raw/Ground Truth', command=self.switch_raw_gt).pack(anchor='nw', padx=6, pady=(0, 12))

        # Delete button (new)
        ttk.Button(right_frame, text='Delete Data Point', command=self.delete_current).pack(anchor='nw', padx=6, pady=(0, 12))

        # Add Find Similar button
        ttk.Button(right_frame, text='Find Similar Images', command=self.find_similar_images).pack(anchor='nw', padx=6, pady=(0, 12))
        # Set as Pure Raw button (new feature)
        ttk.Button(right_frame, text='Set as Pure Raw', command=self.set_as_pure_raw).pack(anchor='nw', padx=6, pady=(0, 12))

        # --- Enhanced interactive controls ---
        jump_frame = ttk.LabelFrame(right_frame, text="Jump to Data Point")
        jump_frame.pack(fill='x', padx=6, pady=6)

        # Index input (x/y)
        ttk.Label(jump_frame, text="Index (x/y):").grid(row=0, column=0, sticky='w', padx=2, pady=2)
        self.jump_entry = ttk.Entry(jump_frame, width=8)
        self.jump_entry.grid(row=0, column=1, sticky='w', padx=2)
        self.jump_entry.bind('<Return>', lambda e: self.jump_to_index())
        ttk.Button(jump_frame, text="Go", command=self.jump_to_index).grid(row=0, column=2, padx=2)

        # Patient ID input
        ttk.Label(jump_frame, text="Patient ID:").grid(row=1, column=0, sticky='w', padx=2, pady=2)
        self.jump_id_entry = ttk.Entry(jump_frame, width=16)
        self.jump_id_entry.grid(row=1, column=1, sticky='w', padx=2)
        self.jump_id_entry.bind('<Return>', lambda e: self.jump_to_id())
        ttk.Button(jump_frame, text="Go", command=self.jump_to_id).grid(row=1, column=2, padx=2)

        # Global Unique ID input
        ttk.Label(jump_frame, text="Global Unique ID:").grid(row=2, column=0, sticky='w', padx=2, pady=2)
        self.jump_guid_entry = ttk.Entry(jump_frame, width=24)
        self.jump_guid_entry.grid(row=2, column=1, sticky='w', padx=2)
        self.jump_guid_entry.bind('<Return>', lambda e: self.jump_to_guid())
        ttk.Button(jump_frame, text="Go", command=self.jump_to_guid).grid(row=2, column=2, padx=2)

        ttk.Separator(right_frame, orient='horizontal').pack(fill='x', pady=6)
        self.info_text = tk.Text(right_frame, width=40, height=20)
        self.info_text.pack(fill='both', expand=True, padx=6)
        self.info_text.configure(state='disabled')

    def change_root(self):
        new = filedialog.askdirectory(initialdir='.', title='Select Data-Remapped-Combiner root')
        if new:
            self.root_dir = new
            self.root_label.config(text=self.root_dir)
            self.scan_organs()

    def scan_organs(self):
        # Discover organ folders under the current dataset
        ds = self.current_dataset.get()
        ds_path = os.path.join(self.root_dir, ds)
        organs = []
        if os.path.isdir(ds_path):
            for name in sorted(os.listdir(ds_path)):
                p = os.path.join(ds_path, name)
                if os.path.isdir(p):
                    organs.append(name)
        else:
            messagebox.showwarning('Missing dataset', f'Dataset folder not found: {ds_path}')
        self.organs = organs
        self.organ_cb['values'] = organs
        self.target_cb['values'] = organs
        # Enable/disable ground truth toggle based on dataset
        ds = self.current_dataset.get()
        if ds == 'matched_images':
            self.gt_toggle.state(['!disabled'])
        else:
            self.gt_toggle.state(['disabled'])
            self.view_gt.set(False)
        if organs:
            self.current_organ.set(organs[0])
            self.target_organ.set(organs[0])
        else:
            self.current_organ.set('')
            self.target_organ.set('')
        self.load_organ()

    def load_organ(self):
        organ = self.current_organ.get()
        ds = self.current_dataset.get()
        if not organ:
            self.data_points = []
            self.current_index = 0
            self.render_canvas_empty('No organ selected')
            return
        if ds == 'matched_images':
            # Data points are in matched_images/<organ>/raw_images/<data_point_folder>
            folder = os.path.join(self.root_dir, ds, organ, 'raw_images')
        else:
            # raw_images dataset: data points are directly under organ
            folder = os.path.join(self.root_dir, ds, organ)
        if not os.path.isdir(folder):
            self.data_points = []
            self.current_index = 0
            self.render_canvas_empty('No items found')
            return
        items = [d for d in sorted(os.listdir(folder)) if os.path.isdir(os.path.join(folder, d))]
        self.data_points = items
        self.current_index = 0
        if items:
            self.show_current()
        else:
            self.render_canvas_empty('No items found')

    def show_current(self):
        if not self.data_points:
            self.render_canvas_empty('No items')
            return
        name = self.data_points[self.current_index]
        ds = self.current_dataset.get()
        organ = self.current_organ.get()
        # Determine which folder to preview
        if ds == 'matched_images':
            if self.view_gt.get():
                folder = os.path.join(self.root_dir, ds, organ, 'ground_truth_images', name)
            else:
                folder = os.path.join(self.root_dir, ds, organ, 'raw_images', name)
        else:
            folder = os.path.join(self.root_dir, ds, organ, name)

        # find an image file
        img_path = None
        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
                    img_path = os.path.join(folder, fn)
                    break
        # Build info string
        info = []
        info.append(f'Dataset: {ds}')
        info.append(f'Organ: {organ}')
        info.append(f'Item: {name} ({self.current_index+1}/{len(self.data_points)})')
        info.append(f'Path: {folder}')
        # Show patient id and global unique id if available
        patient_id, guid = self._extract_ids_from_name(name)
        info.append(f'Patient ID: {patient_id}')
        info.append(f'Global Unique ID: {guid}')
        # check ground truth counterpart for matched
        if ds == 'matched_images':
            gt_folder = os.path.join(self.root_dir, ds, organ, 'ground_truth_images', name)
            info.append(f'Ground truth exists: {os.path.isdir(gt_folder)}')
            info.append(f'Viewing: {"Ground Truth" if self.view_gt.get() else "Raw"}')
        else:
            info.append('Ground truth: N/A')

        self._set_info('\n'.join(info))

        if img_path and os.path.isfile(img_path):
            try:
                img = Image.open(img_path)
                # Ensure widget geometry is up-to-date before querying sizes
                self.canvas.update_idletasks()
                # resize to fit canvas while keeping aspect - clamp to sensible minimums
                canvas_w = max(100, self.canvas.winfo_width())
                canvas_h = max(100, self.canvas.winfo_height())
                thumb_w = max(10, canvas_w - 20)
                thumb_h = max(10, canvas_h - 20)
                img.thumbnail((thumb_w, thumb_h))
                self.current_image_tk = ImageTk.PhotoImage(img)
                self.canvas.delete('all')
                self.canvas.create_image(canvas_w // 2, canvas_h // 2, image=self.current_image_tk, anchor='center')
            except Exception as e:
                # If Pillow raises due to invalid scaling or other issues, show a clear message
                self.render_canvas_empty(f'Error loading image: {e}')
        else:
            self.render_canvas_empty('No preview image found in folder')

        self.status_label.config(text=f'{self.current_index+1}/{len(self.data_points)}')

    def render_canvas_empty(self, text):
        self.canvas.delete('all')
        self.canvas.create_text(20, 20, text=text, anchor='nw', fill='white')
        self.status_label.config(text=text)

    def _set_info(self, text):
        self.info_text.configure(state='normal')
        self.info_text.delete('1.0', 'end')
        self.info_text.insert('1.0', text)
        self.info_text.configure(state='disabled')

    def _extract_ids_from_name(self, name):
        """Extract patient id and global unique id from folder name. Adjust parsing as needed."""
        # Example: '119_000001_GUID123456'
        parts = name.split('_')
        patient_id = parts[0] if len(parts) > 0 else ''
        guid = parts[-1] if len(parts) > 1 else ''
        return patient_id, guid

    def prev_item(self):
        if not self.data_points:
            return
        self.current_index = max(0, self.current_index - 1)
        self.show_current()

    def next_item(self):
        if not self.data_points:
            return
        self.current_index = min(len(self.data_points)-1, self.current_index + 1)
        self.show_current()

    def jump_to_index(self):
        """Jump to the numeric (1-based) index entered in the jump_entry."""
        val = self.jump_entry.get().strip()
        if not val:
            return
        try:
            n = int(val)
        except ValueError:
            messagebox.showwarning('Invalid', 'Please enter a valid integer index')
            return
        if n < 1 or n > len(self.data_points):
            messagebox.showwarning('Out of range', f'Index must be between 1 and {len(self.data_points)}')
            return
        self.current_index = n - 1
        self.show_current()

    def jump_to_id(self):
        """Jump to an item by its patient id (first part of folder name)."""
        val = self.jump_id_entry.get().strip()
        if not val:
            return
        # Find by patient id (first part of folder name)
        for idx, name in enumerate(self.data_points):
            patient_id, _ = self._extract_ids_from_name(name)
            if patient_id == val:
                self.current_index = idx
                self.show_current()
                return
        messagebox.showinfo('Not found', f'Patient ID "{val}" not found in current organ')

    def jump_to_guid(self):
        """Jump to an item by its global unique id (last part of folder name)."""
        val = self.jump_guid_entry.get().strip()
        if not val:
            return
        # Find by guid (last part of folder name)
        for idx, name in enumerate(self.data_points):
            _, guid = self._extract_ids_from_name(name)
            if guid == val:
                self.current_index = idx
                self.show_current()
                return
        messagebox.showinfo('Not found', f'Global Unique ID "{val}" not found in current organ')

    def move_current(self):
        if not self.data_points:
            messagebox.showinfo('No item', 'No data point selected to move')
            return
        target = self.target_organ.get()
        if not target:
            messagebox.showwarning('No target', 'Please select a target organ')
            return
        ds = self.current_dataset.get()
        src_organ = self.current_organ.get()
        name = self.data_points[self.current_index]

        if ds == 'matched_images':
            src_folder = os.path.join(self.root_dir, ds, src_organ, 'raw_images', name)
            src_gt = os.path.join(self.root_dir, ds, src_organ, 'ground_truth_images', name)
            dest_folder = os.path.join(self.root_dir, ds, target, 'raw_images', name)
            dest_gt = os.path.join(self.root_dir, ds, target, 'ground_truth_images', name)
        else:
            src_folder = os.path.join(self.root_dir, ds, src_organ, name)
            dest_folder = os.path.join(self.root_dir, ds, target, name)

        # Confirm
        if messagebox.askyesno('Confirm move', f'Move "{name}" from {src_organ} to {target} in {ds}?'):
            try:
                os.makedirs(os.path.dirname(dest_folder), exist_ok=True)
                final_dest = self._safe_move(src_folder, dest_folder)
                moved_gt = None
                if ds == 'matched_images' and os.path.isdir(src_gt):
                    os.makedirs(os.path.dirname(dest_gt), exist_ok=True)
                    moved_gt = self._safe_move(src_gt, dest_gt)
                # log
                self._log_move({
                    'name': name,
                    'dataset': ds,
                    'from_organ': src_organ,
                    'to_organ': target,
                    'src_folder': src_folder,
                    'dest_folder': final_dest,
                    'src_gt': src_gt if ds=='matched_images' else None,
                    'dest_gt': moved_gt
                })
                # refresh list
                self.load_organ()
                messagebox.showinfo('Moved', f'{name} moved to {target}')
            except Exception as e:
                messagebox.showerror('Error', f'Error moving item: {e}')

    def _safe_move(self, src, dest):
        if not os.path.exists(src):
            raise FileNotFoundError(f'Source not found: {src}')
        if os.path.exists(dest):
            # find a new name to avoid overwrite
            base = dest
            i = 1
            while os.path.exists(f"{base}_dup{i}"):
                i += 1
            new_dest = f"{base}_dup{i}"
            shutil.move(src, new_dest)
            return new_dest
        else:
            shutil.move(src, dest)
            return dest

    def _log_move(self, rec):
        try:
            with open(LOG_FILE, 'r+') as f:
                arr = json.load(f)
                arr.append(rec)
                f.seek(0)
                json.dump(arr, f, indent=2)
        except Exception:
            with open(LOG_FILE, 'w') as f:
                json.dump([rec], f, indent=2)

    def switch_raw_gt(self):
        """Switch the raw_images and ground_truth_images folders for the current data point (matched_images only)."""
        if not self.data_points:
            messagebox.showinfo('No item', 'No data point selected to switch')
            return
        ds = self.current_dataset.get()
        if ds != 'matched_images':
            messagebox.showwarning('Not supported', 'Switching is only available for matched_images dataset')
            return
        organ = self.current_organ.get()
        name = self.data_points[self.current_index]
        raw_folder = os.path.join(self.root_dir, ds, organ, 'raw_images', name)
        gt_folder = os.path.join(self.root_dir, ds, organ, 'ground_truth_images', name)
        if not os.path.isdir(raw_folder) or not os.path.isdir(gt_folder):
            messagebox.showwarning('Missing folders', 'Both raw_images and ground_truth_images folders must exist to switch')
            return
        # Confirm
        if not messagebox.askyesno('Confirm switch', f'Switch raw and ground truth for "{name}" in {organ}?'):
            return
        try:
            # Use temporary folders to swap contents
            tmp_raw = raw_folder + '_tmp_switch'
            tmp_gt = gt_folder + '_tmp_switch'
            os.rename(raw_folder, tmp_raw)
            os.rename(gt_folder, tmp_gt)
            os.rename(tmp_raw, gt_folder)
            os.rename(tmp_gt, raw_folder)
            # Log the switch
            self._log_move({
                'name': name,
                'dataset': ds,
                'organ': organ,
                'action': 'switch_raw_gt',
                'raw_folder': raw_folder,
                'gt_folder': gt_folder
            })
            self.show_current()
            messagebox.showinfo('Switched', f'Raw and ground truth images switched for "{name}"')
        except Exception as e:
            messagebox.showerror('Error', f'Error switching folders: {e}')

    def delete_current(self):
        """Delete the current data point. For matched_images delete both raw and ground truth folders."""
        if not self.data_points:
            messagebox.showinfo('No item', 'No data point selected to delete')
            return
        ds = self.current_dataset.get()
        organ = self.current_organ.get()
        name = self.data_points[self.current_index]

        if ds == 'matched_images':
            raw_folder = os.path.join(self.root_dir, ds, organ, 'raw_images', name)
            gt_folder = os.path.join(self.root_dir, ds, organ, 'ground_truth_images', name)
            # ensure at least one exists
            if not (os.path.isdir(raw_folder) or os.path.isdir(gt_folder)):
                messagebox.showwarning('Not found', 'Neither raw nor ground truth folder exists for this item')
                return
            if not messagebox.askyesno('Confirm delete', f'Delete raw and ground truth for "{name}" in {organ}? This cannot be undone.'):
                return
            deleted = []
            errors = []
            try:
                if os.path.isdir(raw_folder):
                    shutil.rmtree(raw_folder)
                    deleted.append(raw_folder)
                if os.path.isdir(gt_folder):
                    shutil.rmtree(gt_folder)
                    deleted.append(gt_folder)
                # Log deletion
                self._log_move({
                    'name': name,
                    'dataset': ds,
                    'organ': organ,
                    'action': 'delete',
                    'deleted_paths': deleted
                })
                # Refresh listing and UI
                self.load_organ()
                messagebox.showinfo('Deleted', f'Deleted: {len(deleted)} folder(s) for "{name}"')
            except Exception as e:
                messagebox.showerror('Error', f'Error deleting folders: {e}')
        else:
            # other dataset: delete organ/<name>
            folder = os.path.join(self.root_dir, ds, organ, name)
            if not os.path.isdir(folder):
                messagebox.showwarning('Not found', f'Folder not found: {folder}')
                return
            if not messagebox.askyesno('Confirm delete', f'Delete "{name}" from {organ} in {ds}? This cannot be undone.'):
                return
            try:
                shutil.rmtree(folder)
                self._log_move({
                    'name': name,
                    'dataset': ds,
                    'organ': organ,
                    'action': 'delete',
                    'deleted_paths': [folder]
                })
                self.load_organ()
                messagebox.showinfo('Deleted', f'Deleted "{name}"')
            except Exception as e:
                messagebox.showerror('Error', f'Error deleting folder: {e}')

    def extract_patient_number(self, filename):
        """Extract patient number from filename, removing leading zeros."""
        parts = filename.split('_')
        if parts:
            return str(int(parts[0]))  # Remove leading zeros
        return None

    def find_similar_images(self):
        """Find similar images to the current image in the raw data folder."""
        if not self.has_cv2:
            messagebox.showwarning("OpenCV Required", "OpenCV is required for image similarity matching.\nInstall with: pip install opencv-python")
            return

        if not self.data_points or not hasattr(self, 'current_index'):
            messagebox.showinfo("No Image", "Please select an image first")
            return

        import cv2
        import numpy as np

        # Get current image
        name = self.data_points[self.current_index]
        ds = self.current_dataset.get()
        organ = self.current_organ.get()

        if ds == 'matched_images':
            folder = os.path.join(self.root_dir, ds, organ, 'raw_images' if not self.view_gt.get() else 'ground_truth_images', name)
        else:
            folder = os.path.join(self.root_dir, ds, organ, name)

        # Find first image in folder
        img_path = None
        for fn in os.listdir(folder):
            if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
                img_path = os.path.join(folder, fn)
                break

        if not img_path:
            messagebox.showerror("Error", "Could not load current image")
            return

        # Extract patient number from current image
        patient_num = self.extract_patient_number(name)
        if not patient_num:
            messagebox.showerror("Error", "Could not extract patient number from filename")
            return

        # Find patient folder in raw data
        patient_folder = os.path.join(self.RAW_DATA_DIR, patient_num)
        if not os.path.exists(patient_folder):
            messagebox.showerror("Error", f"Patient folder not found: {patient_folder}")
            return

        # Load and preprocess query image
        query_img = cv2.imread(img_path)
        if query_img is None:
            messagebox.showerror("Error", "Could not load query image")
            return

        # Create ORB detector
        orb = cv2.ORB_create(nfeatures=1200, scaleFactor=1.2, nlevels=8, edgeThreshold=15, fastThreshold=5)

        # Get query image keypoints and descriptors
        query_gray = cv2.cvtColor(query_img, cv2.COLOR_BGR2GRAY)
        query_kp, query_desc = orb.detectAndCompute(query_gray, None)

        if query_desc is None:
            messagebox.showwarning("Warning", "Could not extract features from query image")
            return

        # Find all PNG files in patient folder recursively
        matches = []
        for root, _, files in os.walk(patient_folder):
            for file in files:
                if file.lower().endswith('.png'):
                    target_path = os.path.join(root, file)
                    if target_path == img_path:  # Skip self
                        continue

                    # Load and process target image
                    target_img = cv2.imread(target_path)
                    if target_img is None:
                        continue

                    target_gray = cv2.cvtColor(target_img, cv2.COLOR_BGR2GRAY)
                    target_kp, target_desc = orb.detectAndCompute(target_gray, None)

                    if target_desc is None:
                        continue

                    # Match descriptors
                    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
                    knn_matches = bf.knnMatch(query_desc, target_desc, k=2)

                    # Apply ratio test
                    good = []
                    for m, n in knn_matches:
                        if m.distance < 0.75 * n.distance:
                            good.append(m)

                    if len(good) >= 8:  # Minimum matches threshold
                        # Get matched keypoints for homography
                        src_pts = np.float32([query_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                        dst_pts = np.float32([target_kp[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

                        # Find homography matrix and get inliers mask
                        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

                        if mask is not None:
                            inlier_count = int(mask.sum())
                            if inlier_count >= 15:  # Minimum inliers threshold
                                matches.append({
                                    'path': target_path,
                                    'score': inlier_count,
                                    'filename': file
                                })

        # Sort matches by score
        matches.sort(key=lambda x: x['score'], reverse=True)

        # Store matches and show first result
        self.current_matches = matches
        self.current_match_index = 1 if len(matches) > 1 else 0  # Start with second highest score if available
        if len(matches) > 1:
            self.show_similar_image()
        else:
            messagebox.showinfo("No Matches", "No similar images found")
    def pair_to_matched_images(self, role):
        """
        Create a matched_images entry from a pure_raw_images image and a similar image.
        role: 'ground_truth' or 'raw' - defines what the CURRENT pure_raw image becomes.
        """
        if not self.current_matches:
            messagebox.showwarning("No Match", "No similar image selected.")
            return

        match = self.current_matches[self.current_match_index]
        source_path = match['path']
        if not os.path.exists(source_path):
            messagebox.showerror("Error", f"File not found: {source_path}")
            return

        ds = self.current_dataset.get()
        if ds != 'pure_raw_images':
            messagebox.showwarning("Invalid Operation", "This action is only available for pure_raw_images.")
            return

        organ = self.current_organ.get()
        name = self.data_points[self.current_index]

        # Current (pure raw) image folder and image path
        current_folder = os.path.join(self.root_dir, ds, organ, name)
        current_img = None
        for fn in os.listdir(current_folder):
            if os.path.splitext(fn)[1].lower() in IMAGE_EXTS:
                current_img = os.path.join(current_folder, fn)
                break
        if not current_img:
            messagebox.showerror("Error", "No image found in current folder.")
            return

        # Prepare destination in matched_images
        matched_root = os.path.join(self.root_dir, 'matched_images', organ)
        raw_dir = os.path.join(matched_root, 'raw_images', name)
        gt_dir = os.path.join(matched_root, 'ground_truth_images', name)

        # Confirm before creating
        if not messagebox.askyesno("Confirm", f"Create matched pair for '{name}'?\n\nRole: {role}\nSource: {source_path}"):
            return

        os.makedirs(raw_dir, exist_ok=True)
        os.makedirs(gt_dir, exist_ok=True)

        # Decide roles
        if role == 'ground_truth':
            gt_img = current_img
            raw_img = source_path
        else:  # role == 'raw'
            raw_img = current_img
            gt_img = source_path

        # Determine destination filenames
        raw_name = os.path.splitext(os.path.basename(raw_img))[0]
        gt_name = os.path.splitext(os.path.basename(gt_img))[0]

        dest_raw = os.path.join(raw_dir, f"{raw_name}.png")
        dest_gt = os.path.join(gt_dir, f"{gt_name}.png")

        try:
            shutil.copy2(raw_img, dest_raw)
            shutil.copy2(gt_img, dest_gt)

            # Optionally copy json/dcm if exist
            for ext in ['.json', '.dcm', '_anon.dcm']:
                raw_src_extra = os.path.splitext(raw_img)[0] + ext
                gt_src_extra = os.path.splitext(gt_img)[0] + ext
                if os.path.exists(raw_src_extra):
                    shutil.copy2(raw_src_extra, os.path.join(raw_dir, os.path.basename(raw_src_extra)))
                if os.path.exists(gt_src_extra):
                    shutil.copy2(gt_src_extra, os.path.join(gt_dir, os.path.basename(gt_src_extra)))

            # Log and delete original pure raw directory
            self._log_move({
                "action": f"promote_to_matched_{role}",
                "organ": organ,
                "name": name,
                "from_dataset": ds,
                "to_dataset": "matched_images",
                "raw_image": dest_raw,
                "ground_truth_image": dest_gt,
                "source_match_path": source_path
            })

            shutil.rmtree(current_folder)

            self.load_organ()
            messagebox.showinfo("Success", f"Created matched pair for '{name}' and removed pure raw folder.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create matched pair:\n{e}")

        

    def replace_corresponding_files(self, target_type):
        """
        Replace corresponding files (PNG, JSON, DCM) in the target folder
        with the selected similar image's versions.
        target_type: 'ground_truth' or 'raw'
        """
        if not self.current_matches:
            messagebox.showwarning("No Match", "No similar image selected.")
            return

        match = self.current_matches[self.current_match_index]
        source_path = match['path']
        if not os.path.exists(source_path):
            messagebox.showerror("Error", f"File not found: {source_path}")
            return

        ds = self.current_dataset.get()
        organ = self.current_organ.get()
        name = self.data_points[self.current_index]

        if ds != 'matched_images':
            messagebox.showwarning("Invalid Operation", "This action is only available for matched_images.")
            return

        raw_dir = os.path.join(self.root_dir, ds, organ, 'raw_images', name)
        gt_dir = os.path.join(self.root_dir, ds, organ, 'ground_truth_images', name)

        if not os.path.isdir(raw_dir) or not os.path.isdir(gt_dir):
            messagebox.showerror("Missing Folders", "Both raw and ground_truth directories must exist.")
            return

        if target_type == 'ground_truth':
            target_dir = gt_dir
            source_label = "ground truth"
            reference_dir = raw_dir
        else:
            target_dir = raw_dir
            source_label = "raw"
            reference_dir = gt_dir

        # Find base name from reference .png file
        base_name = None
        for file in os.listdir(reference_dir):
            if file.lower().endswith('.png'):
                base_name = os.path.splitext(file)[0]
                break
        if not base_name:
            messagebox.showerror("Error", "No reference .png found to determine filenames.")
            return

        # Destination files
        target_png = os.path.join(target_dir, f"{base_name}.png")
        target_json = os.path.join(target_dir, f"{base_name}.json")
        target_dcm = os.path.join(target_dir, f"{base_name}.dcm")  # <<-- no "_anon" here

        # Source files
        source_dir = os.path.dirname(source_path)
        source_base = os.path.splitext(os.path.basename(source_path))[0]
        source_png = source_path
        source_json = os.path.join(source_dir, f"{source_base}.json")

        # Try both with and without "_anon" for the source DICOM
        source_dcm = os.path.join(source_dir, f"{source_base}_anon.dcm")
        if not os.path.exists(source_dcm):
            alt_dcm = os.path.join(source_dir, f"{source_base}.dcm")
            if os.path.exists(alt_dcm):
                source_dcm = alt_dcm

        # --- Confirmation Popup ---
        confirm_win = tk.Toplevel(self)
        confirm_win.title("Confirm Replacement")
        confirm_win.geometry("600x400")

        ttk.Label(confirm_win, text=f"⚠️ You are about to replace {source_label} files").pack(pady=(10, 5))
        ttk.Separator(confirm_win, orient='horizontal').pack(fill='x', padx=10, pady=5)

        text = tk.Text(confirm_win, wrap='word', width=70, height=16)
        text.pack(padx=10, pady=10, fill='both', expand=True)

        def add_section(title, paths):
            text.insert('end', f"{title}:\n", 'header')
            for p in paths:
                text.insert('end', f"  {p}\n")
            text.insert('end', "\n")

        add_section("Current Files Being Replaced", [target_png, target_json, target_dcm])
        add_section("Source Files (Replacing)", [source_png, source_json, source_dcm])
        add_section("New Destination Filenames", [
            os.path.basename(target_png),
            os.path.basename(target_json),
            os.path.basename(target_dcm)
        ])

        text.tag_configure('header', font=('TkDefaultFont', 10, 'bold'))
        text.configure(state='disabled')

        btn_frame = ttk.Frame(confirm_win)
        btn_frame.pack(pady=10)

        def do_replace():
            try:
                shutil.copy2(source_png, target_png)
                if os.path.exists(source_json):
                    shutil.copy2(source_json, target_json)
                if os.path.exists(source_dcm):
                    shutil.copy2(source_dcm, target_dcm)

                self._log_move({
                    "action": f"replace_{source_label}",
                    "dataset": ds,
                    "organ": organ,
                    "name": name,
                    "source_files": [source_png, source_json, source_dcm],
                    "replaced_files": [target_png, target_json, target_dcm]
                })

                confirm_win.destroy()
                self.similar_window.destroy()
                messagebox.showinfo("Success", f"Replaced {source_label} files successfully.")
                self.show_current()

            except Exception as e:
                messagebox.showerror("Error", f"Failed to replace files:\n{e}")

        ttk.Button(btn_frame, text="✅ Confirm Replace", command=do_replace).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="❌ Cancel", command=confirm_win.destroy).pack(side=tk.LEFT, padx=10)


    def show_similar_image(self):
        """Show the similar image in a popup window with navigation and replacement options."""
        if not self.current_matches:
            return

        # Close existing window if open
        if self.similar_window and self.similar_window.winfo_exists():
            self.similar_window.destroy()

        self.similar_window = tk.Toplevel(self)
        self.similar_window.title("Similar Images")
        self.similar_window.geometry("800x600")

        match = self.current_matches[self.current_match_index]

        # --- Action buttons depending on dataset state ---
        ds = self.current_dataset.get()
        is_gt = self.view_gt.get()

        action_frame = ttk.Frame(self.similar_window)
        action_frame.pack(side=tk.TOP, fill=tk.X, pady=6)

        if ds == 'matched_images':
            if not is_gt:
                ttk.Button(
                    action_frame, text="✅ Set as Ground Truth",
                    command=lambda: self.replace_corresponding_files('ground_truth')
                ).pack(side=tk.LEFT, padx=8)
            else:
                ttk.Button(
                    action_frame, text="✅ Set as Raw",
                    command=lambda: self.replace_corresponding_files('raw')
                ).pack(side=tk.LEFT, padx=8)
        elif ds == 'pure_raw_images':
            ttk.Button(
                action_frame, text="🌱 Set as Ground Truth (Create Match)",
                command=lambda: self.pair_to_matched_images('ground_truth')
            ).pack(side=tk.LEFT, padx=8)
            ttk.Button(
                action_frame, text="🌿 Set as Raw (Create Match)",
                command=lambda: self.pair_to_matched_images('raw')
            ).pack(side=tk.LEFT, padx=8)


        # --- Navigation + Info ---
        nav_frame = ttk.Frame(self.similar_window)
        nav_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        prev_btn = ttk.Button(nav_frame, text="Previous",
                            command=self.prev_similar_image,
                            state='disabled' if self.current_match_index == 0 else 'normal')
        prev_btn.pack(side=tk.LEFT, padx=5)

        next_btn = ttk.Button(nav_frame, text="Next",
                            command=self.next_similar_image,
                            state='disabled' if self.current_match_index >= len(self.current_matches) - 1 else 'normal')
        next_btn.pack(side=tk.LEFT, padx=5)

        count_label = ttk.Label(nav_frame,
                                text=f"Image {self.current_match_index + 1} of {len(self.current_matches)}")
        count_label.pack(side=tk.LEFT, padx=20)

        ttk.Button(nav_frame, text="Close", command=self.similar_window.destroy).pack(side=tk.RIGHT, padx=5)

        ttk.Label(self.similar_window, text=f"Similarity Score: {match['score']}").pack(side=tk.BOTTOM, pady=5)
        ttk.Label(self.similar_window, text=f"Path: {match['path']}").pack(side=tk.BOTTOM, pady=5)

        canvas = tk.Canvas(self.similar_window, bg='black')
        canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        try:
            img = Image.open(match['path'])
            canvas_w = 780
            canvas_h = 520
            img_w, img_h = img.size
            scale = min(canvas_w/img_w, canvas_h/img_h)
            new_w = int(img_w * scale)
            new_h = int(img_h * scale)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            canvas.image = photo
            x = (canvas_w - new_w) // 2
            y = (canvas_h - new_h) // 2
            canvas.create_image(x, y, image=photo, anchor='nw')
        except Exception as e:
            canvas.create_text(400, 300, text=f"Error loading image: {str(e)}", fill='white', anchor='center')

        self.similar_window.bind('<Left>', lambda e: self.prev_similar_image())
        self.similar_window.bind('<Right>', lambda e: self.next_similar_image())
        self.similar_window.bind('<Escape>', lambda e: self.similar_window.destroy())


    def prev_similar_image(self):
        """Show previous similar image."""
        if self.current_match_index > 0:
            self.current_match_index -= 1
            self.show_similar_image()

    def next_similar_image(self):
        """Show next similar image."""
        if self.current_match_index < len(self.current_matches) - 1:
            self.current_match_index += 1
            self.show_similar_image()

    def _on_canvas_configure(self):
        """Handler called after canvas resizing to refresh the current preview without changing index."""
        # if we're currently showing an item, redraw it to fit the new size
        if self.data_points:
            # avoid heavy work if no change
            try:
                self.show_current()
            except Exception:
                # swallow exceptions here to keep UI responsive; show_current has its own error handling
                pass


if __name__ == '__main__':
    app = OrganReclassifierApp()
    app.mainloop()
