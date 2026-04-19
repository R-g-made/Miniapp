import os
import re
import cloudinary
import cloudinary.uploader
from pathlib import Path

# Cloudinary configuration
cloudinary.config(
    cloud_name="da3hc6qxp",
    api_key="943549291431879",
    api_secret="JZ7OEMiuGlTXBdv3Q6sk_4qMcfE"
)

# Paths
CATALOG_ASSET_PATH = Path(r"C:\Users\maxvr\Documents\trae_projects\MiniApp\catalog_asset")
OUTPUT_URLS_FILE = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\catalog_urls.md")


def upload_file_to_cloudinary(file_path, public_id_prefix=""):
    """Upload a single file to Cloudinary and return URL."""
    try:
        ext = file_path.suffix.lower()
        resource_type = "auto"
        if ext in [".json"]:
            resource_type = "raw"
        elif ext in [".webm", ".mp4"]:
            resource_type = "video"
        
        # Create public ID from filename
        public_id = public_id_prefix + re.sub(r'[^\w\s-]', '', file_path.stem).lower().replace(' ', '_')
        full_public_id = f"catalog_all/{public_id}"
        
        # Check if already exists
        try:
            existing = cloudinary.api.resource(full_public_id, resource_type=resource_type)
            print(f"Skipping existing: {file_path.name}")
            return existing["secure_url"]
        except:
            pass
        
        # Upload
        print(f"Uploading: {file_path.name}")
        result = cloudinary.uploader.upload(
            str(file_path),
            resource_type=resource_type,
            folder="catalog_all",
            public_id=public_id,
            overwrite=True
        )
        return result["secure_url"]
    except Exception as e:
        print(f"Failed to upload {file_path.name}: {e}")
        return None


def main():
    print("Starting upload of all assets...")
    all_urls = []
    
    # Walk through all directories
    for case_dir in CATALOG_ASSET_PATH.iterdir():
        if not case_dir.is_dir():
            continue
        
        print(f"\nProcessing case directory: {case_dir.stem}")
        
        # Handle nested directory structure
        nested_dirs = [d for d in case_dir.iterdir() if d.is_dir()]
        if nested_dirs:
            asset_dir = nested_dirs[0]
        else:
            asset_dir = case_dir
        
        prefix = f"{case_dir.stem.lower().replace(' ', '_').replace('(', '').replace(')', '')}_"
        
        for file in asset_dir.iterdir():
            if file.is_file():
                url = upload_file_to_cloudinary(file, prefix)
                if url:
                    all_urls.append((file.name, url))
    
    # Write output file
    print(f"\nWriting URLs to {OUTPUT_URLS_FILE}...")
    lines = ["# All Catalog Assets URLs", ""]
    for filename, url in all_urls:
        lines.append(f"- [{filename}]({url})")
    
    with open(OUTPUT_URLS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Done! Uploaded {len(all_urls)} files!")


if __name__ == "__main__":
    main()
