import json
import os
from pathlib import Path
from typing import Dict, Any

def migrate_json_files(data_dir: str = "data") -> None:
    """
    Migrate all JSON files to ensure video fields are lists.
    
    Args:
        data_dir: Root directory containing JSON files (default: "data")
    """
    # Get all JSON files recursively
    json_files = Path(data_dir).rglob("*.json")
    
    modified_count = 0
    error_count = 0
    skipped_count = 0
    
    print(f"Starting migration of JSON files in {data_dir}...")
    
    for json_path in json_files:
        try:
            # Read the current JSON file
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            # Check if we need to modify this file
            if "video" in data:
                if isinstance(data["video"], str):
                    # Convert string to list
                    data["video"] = [data["video"]]
                    
                    # Write back the modified data
                    with open(json_path, 'w') as f:
                        json.dump(data, f, indent=4)
                    
                    print(f"✓ Modified: {json_path}")
                    modified_count += 1
                else:
                    print(f"- Skipped: {json_path} (video already in correct format)")
                    skipped_count += 1
            else:
                print(f"- Skipped: {json_path} (no video field)")
                skipped_count += 1
                
        except Exception as e:
            print(f"✗ Error processing {json_path}: {str(e)}")
            error_count += 1
    
    # Print summary
    print("\nMigration Complete!")
    print(f"Modified: {modified_count} files")
    print(f"Skipped: {skipped_count} files")
    print(f"Errors: {error_count} files")

if __name__ == "__main__":
    # You can run this directly with: python migrate_json.py
    migrate_json_files()
