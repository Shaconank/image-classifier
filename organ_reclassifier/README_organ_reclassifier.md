# Organ Reclassifier

## What this does

A small Tkinter application to browse data-point folders in your
`Data-Remapped-Combiner` folder and move (reclassify) them between organ
folders.

## How it expects your folder layout

Root: `Data-Remapped-Combiner`

- `matched_images`/<organ>/{raw_images,ground_truth_images}/<data_point_folder>
- `raw_images`/<organ>/<data_point_folder>

## Quick start

1. Create a conda/venv and install the requirements:

```powershell
pip install -r requirements.txt
```

2. Run the app from the `konk-new` folder:

```powershell
python organ_reclassifier.py
```

## Usage notes

- Use the left/right arrow keys or the Prev/Next buttons to navigate items.
- Select a target organ on the right and click "Move here" (or press `m`) to move the
  entire data-point folder.
- For `matched_images`, if a matching folder exists under `ground_truth_images`,
  it will also be moved alongside the `raw_images` folder.
- Moves are logged to `organ_reclassifier_moves_log.json` in the same folder.

## Safety

- If the destination already contains a folder with the same name, the moved folder
  will be renamed by appending `_dupN` to avoid accidental overwrite.

## Next steps / Improvements

- Add undo for a move.
- Show thumbnails for all frames inside a data-point folder.
- Add search/filtering by patient id prefix.
