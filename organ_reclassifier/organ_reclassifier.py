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
