import os
import zipfile
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
# Try this alternative import
try:
    from supabase import create_client, Client
except ImportError:
    from supabase.client import create_client, Client
import sys
# Load environment variables from .env file
load_dotenv()

# Supabase Configuration from .env
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = "Pdfs_"

# Initialize Supabase client
def init_supabase():
    """Initialize Supabase client"""
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        sys.exit(1)
    
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# # Initialize SQLite database
# def init_database():
#     """Initialize SQLite database with files table"""
#     print("📁 Initializing database...")
#     conn = sqlite3.connect('supabase_files.db')
#     cursor = conn.cursor()
    
#     cursor.execute('''
#         CREATE TABLE IF NOT EXISTS files (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             filename TEXT NOT NULL,
#             file_path TEXT NOT NULL,
#             file_size INTEGER,
#             download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#             bucket_name TEXT NOT NULL
#         )
#     ''')
    
#     conn.commit()
#     conn.close()
#     print("✅ Database initialized\n")

# List all files in Supabase bucket recursively
def list_all_files(bucket_name, path=""):
    """Recursively list all files in a bucket"""
    all_files = []
    
    try:
        # List files in current path
        response = supabase.storage.from_(bucket_name).list(path)
        
        for item in response:
            item_name = item.get('name')
            item_id = item.get('id')
            
            # Skip .emptyFolderPlaceholder files
            if item_name == '.emptyFolderPlaceholder':
                continue
            
            # Check if it's a folder
            if item.get('id') is None or ('metadata' in item and item['metadata'] is None):
                # It's a folder, recursively list its contents
                folder_path = f"{path}/{item_name}" if path else item_name
                all_files.extend(list_all_files(bucket_name, folder_path))
            else:
                # It's a file
                file_path = f"{path}/{item_name}" if path else item_name
                all_files.append({
                    'name': item_name,
                    'path': file_path,
                    'size': item.get('metadata', {}).get('size', 0)
                })
        
        return all_files
    except Exception as e:
        print(f"❌ Error listing files: {str(e)}")
        return []

# Download file from Supabase Storage
def download_file_from_storage(bucket_name, file_path):
    """Download a single file from Supabase Storage"""
    try:
        response = supabase.storage.from_(bucket_name).download(file_path)
        return response
    except Exception as e:
        print(f"⚠️  Failed to download {file_path}: {str(e)}")
        return None

# Create ZIP file with all files from bucket
def create_zip_from_bucket(bucket_name, output_filename):
    """Download all files and create a ZIP file"""
    try:
        print(f"📦 Listing files from bucket '{bucket_name}'...")
        files = list_all_files(bucket_name)
        
        if not files:
            print(f"❌ No files found in bucket '{bucket_name}'")
            return None, 0
        
        print(f"✅ Found {len(files)} files\n")
        
        # Create ZIP file
        print(f"📥 Downloading and creating ZIP archive...")
        with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for idx, file_info in enumerate(files, 1):
                file_path = file_info['path']
                print(f"  [{idx}/{len(files)}] Downloading: {file_path}")
                
                # Download file
                file_data = download_file_from_storage(bucket_name, file_path)
                
                if file_data:
                    # Add to ZIP with original path structure
                    zip_file.writestr(file_path, file_data)
        
        print(f"\n✅ ZIP file created: {output_filename}\n")
        return files, len(files)
    
    except Exception as e:
        print(f"❌ Error creating ZIP: {str(e)}")
        return None, 0

# Save file metadata to SQLite
def save_to_database(bucket_name, files):
    """Save file metadata to SQLite database"""
    try:
        print("💾 Saving metadata to database...")
        conn = sqlite3.connect('supabase_files.db')
        cursor = conn.cursor()
        
        for file_info in files:
            cursor.execute('''
                INSERT INTO files (filename, file_path, file_size, bucket_name)
                VALUES (?, ?, ?, ?)
            ''', (
                file_info['name'],
                file_info['path'],
                file_info.get('size', 0),
                bucket_name
            ))
        
        conn.commit()
        conn.close()
        print(f"✅ Saved {len(files)} file records to database\n")
        return True
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
        return False

# Get database statistics
def get_db_stats():
    """Get statistics from SQLite database"""
    try:
        conn = sqlite3.connect('supabase_files.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM files')
        total_files = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(file_size) FROM files')
        total_size = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return total_files, total_size
    except:
        return 0, 0

# Main function
def main():
    print("\n" + "="*60)
    print("   SUPABASE STORAGE DOWNLOADER")
    print("="*60 + "\n")
    
    # Initialize database
    init_database()
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{BUCKET_NAME}_{timestamp}.zip"
    
    # Download and create ZIP
    files, file_count = create_zip_from_bucket(BUCKET_NAME, output_filename)
    
    if files:
        # Save to database
        save_to_database(BUCKET_NAME, files)
        [(1)]
        # Get final statistics
        total_files, total_size = get_db_stats()
        
        # Print summary
        print("="*60)
        print("   DOWNLOAD COMPLETE")
        print("="*60)
        print(f"📦 ZIP File: {output_filename}")
        print(f"📊 Files Downloaded: {file_count}")
        print(f"💾 Database Records: {total_files}")
        print(f"📏 Total Size in DB: {total_size / (1024*1024):.2f} MB")
        print("="*60 + "\n")
        
        print("✅ Process completed successfully!")
    else:
        print("❌ Download failed!")
        sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        sys.exit(1)
