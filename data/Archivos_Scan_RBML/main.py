import os
import re
import shutil

# List of source PDF files (add your full list here)

src_dir = "/Users/andrey/src/tessera/data/Archivos_Scan_RBML/yolo"

# Destination directory for the renamed files
destination_dir = "/Users/andrey/src/tessera/data/Archivos_Scan_RBML/pdf/"

def process_file(src_file):
    """Extracts the number from the file name and moves it to the destination directory with a new name."""
    basename = os.path.basename(src_file)
    # Ensure we're processing a PDF file
    if not basename.lower().endswith('.pdf'):
        print(f"Skipping non-PDF file: {src_file}")
        return

    # Remove the extension and match the pattern
    name_without_ext, ext = os.path.splitext(basename)
    # Use regex to match "Folder_" followed by one or more digits
    match = re.match(r'Folder_(\d+)', name_without_ext)
    if not match:
        print(f"Filename did not match expected pattern: {basename}")
        return

    number = match.group(1)
    # Construct new file name: "Folder <number>.pdf"
    new_filename = f"Folder {number}{ext}"
    destination_path = os.path.join(destination_dir, new_filename)
    src_file = os.path.join(src_dir, src_file)
    
    # Print the mapping (or move the file)
    print(f"Moving:\n  Source: {src_file}\n  Destination: {destination_path}\n")
    # Uncomment the next line to actually move the file:
    shutil.move(src_file, destination_path)

def main():
    # Ensure destination directory exists
    if not os.path.exists(destination_dir):
        os.makedirs(destination_dir)
    
    for file_path in os.listdir(src_dir):
        process_file(file_path)

if __name__ == "__main__":
    main()

