#!/usr/bin/env python3
"""
Supabase storage downloader:
- Lists all files from a Supabase Storage bucket
- Downloads files into DOWNLOAD_DIR preserving folder structure
- Creates a ZIP from the downloaded files
- Extracts the ZIP into DOWNLOAD_DIR/pdfs and replaces any existing 'pdfs' folder
- Records metadata into an SQLite DB (supabase_files.db)

Requirements:
  pip install python-dotenv supabase
Set .env with:
  SUPABASE_URL=https://your-project.supabase.co
  SUPABASE_KEY=your_supabase_key
  DOWNLOAD_DIR=D:/MTech_DS/MLOps/Downloads   # optional, defaults to ./downloads
"""
import os
import sys
import zipfile
import sqlite3
import shutil
import time
from datetime import datetime
from dotenv import load_dotenv

# Try alternative import for supabase client packaging differences
try:
    from supabase import create_client
except ImportError:
    from supabase.client import create_client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DEFAULT_BUCKET_NAME = "Pdfs_"
DEFAULT_DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")
DB_PATH = "supabase_files.db"

# Initialize Supabase client
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        sys.exit(1)
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Initialize SQLite database
def init_database(db_path=DB_PATH):
    print("📁 Initializing database...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bucket_name TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    print("✅ Database initialized\n")

# List all files in a bucket recursively
def list_all_files(bucket_name, path=""):
    """
    Recursively list all files in bucket_name under 'path'.
    Returns a list of dicts: {'name': ..., 'path': ..., 'size': ...}
    """
    all_files = []
    try:
        response = supabase.storage.from_(bucket_name).list(path)
        # response is usually a list of dict-like items
        for item in response:
            # robustly get name and metadata
            item_name = item.get('name') if isinstance(item, dict) else getattr(item, 'name', None)
            metadata = item.get('metadata') if isinstance(item, dict) else getattr(item, 'metadata', None)

            # skip placeholder
            if item_name == '.emptyFolderPlaceholder':
                continue

            # If metadata is None -> treat as folder and recurse
            if metadata is None and item_name:
                folder_path = f"{path}/{item_name}" if path else item_name
                all_files.extend(list_all_files(bucket_name, folder_path))
            else:
                file_path = f"{path}/{item_name}" if path else item_name
                size = 0
                if isinstance(metadata, dict):
                    try:
                        size = int(metadata.get('size', 0))
                    except Exception:
                        size = 0
                all_files.append({'name': item_name, 'path': file_path, 'size': size})
        return all_files
    except Exception as e:
        print(f"❌ Error listing files: {e}")
        return []

# Download and save a single file to disk (handles bytes or file-like responses)
def download_and_save_file(bucket_name, file_path, download_dir):
    try:
        resp = supabase.storage.from_(bucket_name).download(file_path)
        if resp is None:
            print(f"⚠  No data for {file_path}")
            return None

        local_path = os.path.join(download_dir, file_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        # Some clients return a file-like object; some return bytes
        if hasattr(resp, "read"):
            with open(local_path, "wb") as f:
                while True:
                    chunk = resp.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        else:
            # assume bytes-like
            with open(local_path, "wb") as f:
                f.write(resp)

        return local_path
    except Exception as e:
        print(f"⚠  Failed to download {file_path}: {e}")
        return None

# Create a ZIP from the local downloaded files (preserves original bucket path names)
def create_zip_from_local_files(files, download_dir, output_filename):
    try:
        with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                local_path = os.path.join(download_dir, f['path'].replace("/", os.sep))
                if os.path.exists(local_path):
                    zf.write(local_path, arcname=f['path'])
        return True
    except Exception as e:
        print(f"❌ Error creating ZIP: {e}")
        return False

# Extract the zip into a folder named target_folder_name under extract_parent_dir.
# Replacement is atomic on same filesystem: extract to tmp, delete old final, rename tmp -> final
def extract_zip_to_folder(zip_path, extract_parent_dir, target_folder_name="pdfs", remove_zip=True):
    try:
        os.makedirs(extract_parent_dir, exist_ok=True)
        tmp_dir = os.path.join(extract_parent_dir, f"{target_folder_name}tmp{int(time.time())}")
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
        os.makedirs(tmp_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(tmp_dir)

        final_dir = os.path.join(extract_parent_dir, target_folder_name)

        # Remove existing final folder if present
        if os.path.exists(final_dir):
            try:
                shutil.rmtree(final_dir)
            except Exception as e:
                print(f"⚠ Could not remove existing folder {final_dir}: {e}")
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return None

        # Rename tmp -> final
        try:
            os.rename(tmp_dir, final_dir)
        except Exception as e:
            print(f"❌ Failed to move temp folder into place: {e}")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return None

        # Optionally remove zip
        if remove_zip:
            try:
                os.remove(zip_path)
            except Exception as e:
                print(f"⚠ Could not remove zip file {zip_path}: {e}")

        return final_dir
    except Exception as e:
        print(f"❌ Failed to extract zip {zip_path}: {e}")
        return None

# Save metadata to sqlite db
def save_to_database(bucket_name, files, db_path=DB_PATH):
    try:
        print("💾 Saving metadata to database...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for file_info in files:
            cursor.execute('''
                INSERT INTO files (filename, file_path, file_size, bucket_name)
                VALUES (?, ?, ?, ?)
            ''', (file_info['name'], file_info['path'], file_info.get('size', 0), bucket_name))
        conn.commit()
        conn.close()
        print(f"✅ Saved {len(files)} file records to database\n")
        return True
    except Exception as e:
        print(f"❌ Database error: {e}")
        return False

# Get DB stats
def get_db_stats(db_path=DB_PATH):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM files')
        total_files = cursor.fetchone()[0]
        cursor.execute('SELECT SUM(file_size) FROM files')
        total_size = cursor.fetchone()[0] or 0
        conn.close()
        return total_files, total_size
    except:
        return 0, 0

# Main function - can be called from other scripts
def main(bucket_name=DEFAULT_BUCKET_NAME, download_dir=DEFAULT_DOWNLOAD_DIR):
    print("\n" + "="*60)
    print("   SUPABASE STORAGE DOWNLOADER")
    print("="*60 + "\n")

    # Ensure download directory exists
    os.makedirs(download_dir, exist_ok=True)

    # Initialize DB
    init_database()

    # List files
    print(f"📦 Listing files from bucket '{bucket_name}'...")
    files = list_all_files(bucket_name)
    if not files:
        print(f"❌ No files found in bucket '{bucket_name}'")
        return

    print(f"✅ Found {len(files)} files\n")

    # Download each file to disk
    downloaded = []
    for idx, f in enumerate(files, 1):
        print(f"  [{idx}/{len(files)}] Downloading: {f['path']}")
        local = download_and_save_file(bucket_name, f['path'], download_dir)
        if local:
            downloaded.append(f)

    if not downloaded:
        print("❌ No files were downloaded.")
        return

    # Create zip filename inside download_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_bucket = bucket_name.rstrip("_")
    output_filename = os.path.join(download_dir, f"{safe_bucket}_{timestamp}.zip")

    print("\n📥 Creating ZIP archive...")
    ok = create_zip_from_local_files(downloaded, download_dir, output_filename)
    if not ok:
        print("\n❌ Failed to create ZIP.\n")
        return

    print(f"\n✅ ZIP file created: {output_filename}\n")

    # Extract into folder named 'pdfs' and replace existing one
    extracted_folder = extract_zip_to_folder(output_filename, download_dir, target_folder_name="pdfs", remove_zip=True)
    if extracted_folder:
        print(f"📂 Extracted ZIP into folder (replaced previous): {extracted_folder}")
    else:
        print("⚠ Extraction failed - the ZIP will remain at: " + output_filename)

    # Save metadata into DB
    #save_to_database(bucket_name, downloaded)

    # Print stats
    total_files, total_size = get_db_stats()
    print("="*60)
    print("   DOWNLOAD COMPLETE")
    print("="*60)
    print(f"📦 ZIP File (was): {output_filename}")
    print(f"📊 Files Downloaded: {len(downloaded)}")
    print(f"💾 Database Records: {total_files}")
    print(f"📏 Total Size in DB: {total_size / (1024*1024):.2f} MB")
    print("="*60 + "\n")
    print("✅ Process completed successfully!")

# # Run as script
# if _name_ == "_main_":
#     try:
#         # default run uses values from .env; override here if you like
#         main()
#     except KeyboardInterrupt:
#         print("\n\n⚠  Process interrupted by user")
#         sys.exit(1)
#     except Exception as e:
#         print(f"\n❌ Unexpected error: {e}")
#         sys.exit(1)