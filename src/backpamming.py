import os
import json
import shutil
from pathlib import Path
from PIL import Image
import imagehash
from collections import defaultdict
import logging
import sys

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('remapping.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class UltrasoundRemapper:
    def __init__(self, json_path, data_matched_path, data_raw_path, output_path):
        self.json_path = Path(json_path)
        self.data_matched_path = Path(data_matched_path)
        self.data_raw_path = Path(data_raw_path)
        self.output_path = Path(output_path)
        
        # Index: hash -> (original_path, triplet_info)
        self.hash_index = {}
        # Track which files from JSON were used
        self.used_files = set()
        # Track unmatched files
        self.unmatched_files = []
        
    def load_json_mapping(self):
        """Load the JSON file with original file mappings"""
        logging.info(f"Loading JSON mapping from {self.json_path}")
        with open(self.json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def build_hash_index(self, json_data):
        """Build a hash index of all original images"""
        logging.info("Building hash index of original images...")
        
        total_folders = len(json_data)
        processed_folders = 0
        
        for folder_path, png_files in json_data.items():
            processed_folders += 1
            
            # Normalize the path - handle mixed separators
            # First replace all separators with forward slash, then convert to OS-specific
            normalized = folder_path.replace('\\', '/').replace('//', '/')
            folder_path = Path(normalized)
            
            # Log the path for debugging
            logging.info(f"\n[{processed_folders}/{total_folders}] Processing folder:")
            logging.info(f"  Original path: {folder_path}")
            logging.info(f"  Exists: {folder_path.exists()}")
            logging.info(f"  Files to process: {len(png_files)}")
            
            if not folder_path.exists():
                logging.warning(f"  ⚠ Folder doesn't exist, skipping...")
                continue
            
            successfully_indexed = 0
            for png_file in png_files:
                png_path = folder_path / png_file
                
                # Log each file being checked
                logging.debug(f"  Checking: {png_file}")
                
                if not png_path.exists():
                    logging.warning(f"  ✗ File not found: {png_file}")
                    logging.warning(f"     Full path: {png_path}")
                    continue
                
                # Extract base name (without extension)
                base_name = png_file.replace('.png', '')
                
                # Define the triplet - DICOM has _anon suffix
                json_path = folder_path / f"{base_name}.json"
                dicom_path = folder_path / f"{base_name}_anon.dcm"
                
                # Handle alternative DICOM naming (without _anon)
                if not dicom_path.exists():
                    alt_dicom_path = folder_path / f"{base_name}.dcm"
                    if alt_dicom_path.exists():
                        dicom_path = alt_dicom_path
                        logging.debug(f"  Using alternative DICOM name (without _anon): {base_name}.dcm")
                
                triplet = {
                    'png': png_path,
                    'json': json_path,
                    'dicom': dicom_path
                }
                
                # Verify all files exist
                missing_files = [k for k, v in triplet.items() if not v.exists()]
                if missing_files:
                    logging.warning(f"  ✗ Missing files for {base_name}: {missing_files}")
                    continue
                
                # Calculate hash
                try:
                    img = Image.open(triplet['png'])
                    img_hash = imagehash.phash(img)
                    
                    # Store in index
                    hash_key = str(img_hash)
                    if hash_key in self.hash_index:
                        logging.warning(f"  ⚠ Hash collision for {png_file} with {self.hash_index[hash_key]['base_name']}")
                    
                    self.hash_index[hash_key] = {
                        'base_name': base_name,
                        'triplet': triplet,
                        'original_path': str(png_path)
                    }
                    
                    successfully_indexed += 1
                    logging.debug(f"  ✓ Indexed: {png_file} (hash: {hash_key})")
                    
                except Exception as e:
                    logging.error(f"  ✗ Error processing {png_path}: {e}")
            
            logging.info(f"  Successfully indexed: {successfully_indexed}/{len(png_files)} files")
        
        logging.info(f"Built index with {len(self.hash_index)} images")
    
    def find_matching_original(self, filtered_image_path):
        """Find the original image matching the filtered image - exact match only"""
        try:
            logging.info(f"\n{'='*60}")
            logging.info(f"MATCHING: {filtered_image_path}")
            logging.info(f"{'='*60}")
            
            img = Image.open(filtered_image_path)
            img_hash = str(imagehash.phash(img))
            
            logging.info(f"Calculated hash: {img_hash}")
            
            # Only accept exact hash matches
            if img_hash in self.hash_index:
                match = self.hash_index[img_hash]
                logging.info(f"✓ HASH MATCH FOUND: {match['base_name']}")
                logging.info(f"  Original path: {match['original_path']}")
                return match
            
            logging.info(f"✗ No exact hash match found")
            logging.info(f"Trying pixel-by-pixel comparison with {len(self.hash_index)} candidates...")
            
            # If no hash match, try exact pixel comparison as fallback
            filtered_pixels = list(img.getdata())
            
            candidates_checked = 0
            for stored_hash, data in self.hash_index.items():
                candidates_checked += 1
                if candidates_checked <= 5 or candidates_checked % 100 == 0:
                    logging.debug(f"Checking candidate {candidates_checked}/{len(self.hash_index)}: {data['base_name']}")
                
                try:
                    original_img = Image.open(data['triplet']['png'])
                    original_pixels = list(original_img.getdata())
                    
                    # Check if dimensions and pixels match exactly
                    if img.size == original_img.size and filtered_pixels == original_pixels:
                        logging.info(f"✓ PIXEL MATCH FOUND: {data['base_name']}")
                        logging.info(f"  Original path: {data['original_path']}")
                        return data
                except Exception as e:
                    logging.debug(f"Error comparing with {data['base_name']}: {e}")
                    continue
            
            logging.warning(f"✗ NO MATCH FOUND after checking {candidates_checked} candidates")
            return None
            
        except Exception as e:
            logging.error(f"Error matching {filtered_image_path}: {e}")
            return None
    
    def process_filtered_images(self, source_root, output_root):
        """Process all filtered images in a directory structure"""
        for root, dirs, files in os.walk(source_root):
            for file in files:
                if not file.lower().endswith('.png'):
                    continue
                
                filtered_image_path = Path(root) / file
                
                # Find matching original
                match = self.find_matching_original(filtered_image_path)
                
                if match is None:
                    self.unmatched_files.append(str(filtered_image_path))
                    logging.warning(f"No match found for: {filtered_image_path}")
                    continue
                
                # Mark as used
                self.used_files.add(match['original_path'])
                
                # Calculate relative path structure
                rel_path = filtered_image_path.relative_to(source_root)
                
                # Create output directory: replace image filename with folder
                output_dir = output_root / rel_path.parent / match['base_name']
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy all three files
                for file_type, source_path in match['triplet'].items():
                    dest_path = output_dir / source_path.name
                    try:
                        shutil.copy2(source_path, dest_path)
                        logging.debug(f"Copied {source_path.name} to {output_dir}")
                    except Exception as e:
                        logging.error(f"Error copying {source_path}: {e}")
                
                logging.info(f"Remapped: {file} -> {match['base_name']}")
    
    def run(self):
        """Main execution method"""
        logging.info("Starting ultrasound image remapping...")
        
        # Load JSON and build index
        json_data = self.load_json_mapping()
        self.build_hash_index(json_data)
        
        # Process matched_images
        matched_images_source = self.data_matched_path / 'matched_images'
        matched_images_output = self.output_path / 'matched_images'
        
        if matched_images_source.exists():
            logging.info("Processing matched_images...")
            self.process_filtered_images(matched_images_source, matched_images_output)
        
        # Process pure_raw_images
        pure_raw_source = self.data_matched_path / 'pure_raw_images'
        pure_raw_output = self.output_path / 'pure_raw_images'
        
        if pure_raw_source.exists():
            logging.info("Processing pure_raw_images...")
            self.process_filtered_images(pure_raw_source, pure_raw_output)
        
        # Report unused files
        all_original_files = set(data['original_path'] for data in self.hash_index.values())
        unused_files = all_original_files - self.used_files
        
        logging.info(f"\n{'='*60}")
        logging.info(f"SUMMARY")
        logging.info(f"{'='*60}")
        logging.info(f"Total original images indexed: {len(self.hash_index)}")
        logging.info(f"Images successfully matched: {len(self.used_files)}")
        logging.info(f"Unmatched filtered images: {len(self.unmatched_files)}")
        logging.info(f"Unused original images: {len(unused_files)}")
        
        # Write detailed logs
        if self.unmatched_files:
            with open('unmatched_files.txt', 'w') as f:
                f.write('\n'.join(self.unmatched_files))
            logging.info(f"Unmatched files written to unmatched_files.txt")
        
        if unused_files:
            with open('unused_original_files.txt', 'w') as f:
                f.write('\n'.join(sorted(unused_files)))
            logging.info(f"Unused original files written to unused_original_files.txt")
        
        logging.info("Remapping complete!")


if __name__ == "__main__":
    # Configure paths
    JSON_PATH = r"CHANGETHIS"
    DATA_MATCHED_PATH = r"CHANGETHIS"
    DATA_RAW_PATH = r"CHANGETHIS"
    OUTPUT_PATH = r"CHANGETHIS"
    
    # Create remapper and run
    remapper = UltrasoundRemapper(JSON_PATH, DATA_MATCHED_PATH, DATA_RAW_PATH, OUTPUT_PATH)
    remapper.run()
