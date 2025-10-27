import os
import shutil

# source and destination roots
src_root = r"CHANGETHIS"
dst_root = r"CHANGETHIS"

for root, dirs, files in os.walk(src_root, topdown=False):  # bottom-up so leaf dirs come first
    # Process only leaf directories (no subdirectories)
    if not dirs:
        pngs = [f for f in files if f.lower().endswith(".png")]
        if not pngs:
            continue

        rel_path = os.path.relpath(root, src_root)
        rel_parts = rel_path.split(os.sep)
        prefix = "_".join(rel_parts)

        # Copy first PNG (adjust if needed)
        src_file = os.path.join(root, pngs[0])

        # Destination parent directory (one level up under dst_root)
        parent_rel_path = os.path.relpath(os.path.dirname(root), src_root)
        dst_dir = os.path.join(dst_root, parent_rel_path)
        os.makedirs(dst_dir, exist_ok=True)

        dst_file = os.path.join(dst_dir, f"{prefix}.png")

        shutil.copy2(src_file, dst_file)
        print(f"Copied: {src_file} -> {dst_file}")
