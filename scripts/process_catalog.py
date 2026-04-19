import os
import re
import cloudinary
import cloudinary.uploader
from pathlib import Path
from collections import defaultdict

# Cloudinary configuration (user provided API key)
cloudinary.config(
    cloud_name="da3hc6qxp",  # TODO: User needs to fill this
    api_key="943549291431879",
    api_secret="JZ7OEMiuGlTXBdv3Q6sk_4qMcfE"  # TODO: User needs to fill this
)

# Paths
CATALOG_MD_PATH = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\Catalog.md")
CATALOG_ASSET_PATH = Path(r"c:\Users\maxvr\OneDrive\Desktop\CatalogAsset")
OUTPUT_MD_PATH = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\ProcessedCatalog.md")


def parse_catalog_md():
    """Parse the raw Catalog.md into structured data."""
    with open(CATALOG_MD_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cases = []
    current_case = None
    current_stickers = []

    # Regex patterns
    case_pattern = re.compile(r"\[\d{2}\.\d{2}\.\d{4} \d{1,2}:\d{2}\] Sasha: (.+) Case / \d+ items")
    sticker_pattern = re.compile(r"\[\d{2}\.\d{2}\.\d{4} \d{1,2}:\d{2}\] Sasha: (.+)")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Skip lines that are just notes like "1 ITEM WITHOUT LOTTIE"
        if "WITHOUT" in line.upper() or "Link does not exist" in line:
            i += 1
            continue

        # Check if it's a case line
        case_match = case_pattern.search(line)
        if case_match:
            if current_case is not None:
                current_case["stickers"] = current_stickers
                cases.append(current_case)

            current_case = {
                "name": case_match.group(1),
                "stickers": []
            }
            current_stickers = []
            i += 1
            continue

        # It's a sticker line - let's collect 3 or 4 lines per sticker
        sticker_lines = []
        for j in range(4):
            if i + j < len(lines):
                l = lines[i + j].strip()
                if l and not ("WITHOUT" in l.upper() or "Link does not exist" in l):
                    sticker_match = sticker_pattern.search(l)
                    if sticker_match:
                        sticker_lines.append(sticker_match.group(1))

        # Process sticker lines
        if len(sticker_lines) >= 3:
            # Case 1: 4 lines (collection, name, max_pool, address)
            if len(sticker_lines) == 4 and "items" in sticker_lines[2]:
                collection = sticker_lines[0]
                name = sticker_lines[1]
                max_pool_match = re.search(r"(\d+) items", sticker_lines[2])
                max_pool = int(max_pool_match.group(1)) if max_pool_match else 0
                address = sticker_lines[3]
            # Case 2: 3 lines (collection=name, max_pool, address)
            elif len(sticker_lines) == 3 and "items" in sticker_lines[1]:
                collection = sticker_lines[0]
                name = sticker_lines[0]
                max_pool_match = re.search(r"(\d+) items", sticker_lines[1])
                max_pool = int(max_pool_match.group(1)) if max_pool_match else 0
                address = sticker_lines[2]
            else:
                i += 1
                continue

            current_stickers.append({
                "collection": collection,
                "name": name,
                "max_pool": max_pool,
                "address": address,
                "assets": []
            })
            i += len(sticker_lines)
        else:
            i += 1

    # Add last case
    if current_case is not None:
        current_case["stickers"] = current_stickers
        cases.append(current_case)

    return cases


def normalize_case_name(name):
    """Normalize case name by removing extra words like FULL, (items), etc."""
    name = name.lower().strip()
    # Remove extra suffixes
    name = re.sub(r"\s*\(.*?\)", "", name)  # remove (36 items) etc
    name = re.sub(r"\s*full", "", name)  # remove FULL
    name = re.sub(r"\s*case", "", name)  # remove Case suffix
    name = re.sub(r"\s*pack", "", name)  # remove Pack suffix
    name = re.sub(r"\s*ss", "", name)  # remove SS (for DOGS SS)
    name = re.sub(r"\s*\d+", "", name)  # remove numbers
    name = re.sub(r"\s+", " ", name).strip()  # collapse spaces
    # Map similar names
    if "doges" in name:
        name = "dogs"
    return name

def scan_assets():
    """Scan CatalogAsset directory and map assets to sticker names/collections, grouped by case."""
    asset_map = defaultdict(lambda: defaultdict(list))  # normalized_case_name -> asset_name -> [files]

    for case_dir in CATALOG_ASSET_PATH.iterdir():
        if not case_dir.is_dir():
            continue
        
        # Extract and normalize case name from directory
        case_name = normalize_case_name(case_dir.stem)
        
        # Go into nested case directory (since it's "Case Name/Case Name/")
        nested_dirs = [d for d in case_dir.iterdir() if d.is_dir()]
        if nested_dirs:
            asset_dir = nested_dirs[0]
        else:
            asset_dir = case_dir

        for file in asset_dir.iterdir():
            if file.is_file():
                # Normalize name: remove numbers, underscores, extensions
                base_name = file.stem.lower().replace("_", " ").replace("-", " ")
                # Remove trailing numbers
                base_name = re.sub(r"\s*\d+$", "", base_name).strip()
                asset_map[case_name][base_name].append(file)

    return asset_map


def upload_to_cloudinary(file_path, case_name="", sticker_name=""):
    """Upload file to Cloudinary and return URL. Skip if already exists with same name."""
    try:
        ext = file_path.suffix.lower()
        resource_type = "auto"
        if ext in [".json"]:
            resource_type = "raw"
        elif ext in [".webm", ".mp4"]:
            resource_type = "video"
        
        # Create meaningful public ID
        public_id_parts = []
        if case_name:
            public_id_parts.append(re.sub(r'[^\w\s-]', '', case_name).lower().replace(' ', '_'))
        if sticker_name:
            public_id_parts.append(re.sub(r'[^\w\s-]', '', sticker_name).lower().replace(' ', '_'))
        public_id_parts.append(file_path.stem.lower().replace(' ', '_'))
        public_id = "_".join(public_id_parts)
        full_public_id = f"catalog_assets/{public_id}"
        
        # First check if file already exists
        try:
            existing = cloudinary.api.resource(full_public_id, resource_type=resource_type)
            print(f"    Skipping upload, asset already exists: {full_public_id}")
            return existing["secure_url"]
        except Exception as e:
            # If doesn't exist, upload new one
            pass
        
        # Upload new file
        result = cloudinary.uploader.upload(
            str(file_path),
            resource_type=resource_type,
            folder="catalog_assets",
            public_id=public_id,
            overwrite=True
        )
        return result["secure_url"]
    except Exception as e:
        print(f"Failed to upload {file_path}: {e}")
        return None


def match_and_upload_assets(cases, asset_map):
    """Match stickers to assets, upload them to Cloudinary, and attach URLs."""
    for case in cases:
        normalized_case_name = normalize_case_name(case["name"])
        
        # Find matching case directory in asset_map
        case_asset_map = None
        for asset_case_name, assets in asset_map.items():
            if normalized_case_name == asset_case_name or normalized_case_name in asset_case_name or asset_case_name in normalized_case_name:
                case_asset_map = assets
                break
        
        if not case_asset_map:
            print(f"Warning: No assets found for case: {case['name']}")
            continue
        
        for sticker in case["stickers"]:
            matched_files = []
            sticker_name_lower = sticker["name"].lower()
            collection_name_lower = sticker["collection"].lower()
            print(f"\n  Matching sticker: {sticker['collection']} / {sticker['name']}")
            print(f"  Available assets in this case: {list(case_asset_map.keys())}")
            
            # Try all matching strategies ONLY WITHIN THIS CASE'S ASSETS
            for key, files in case_asset_map.items():
                key_lower = key.lower()
                # Strategy 1: exact name match
                if sticker_name_lower == key_lower:
                    matched_files.extend(files)
                    print(f"    ✅ Exact match with asset: {key}")
                    continue
                # Strategy 2: name is substring of key
                if sticker_name_lower in key_lower:
                    matched_files.extend(files)
                    print(f"    ✅ Name in asset: {key}")
                    continue
                # Strategy 3: key is substring of name
                if key_lower in sticker_name_lower:
                    matched_files.extend(files)
                    print(f"    ✅ Asset in name: {key}")
                    continue
                # Strategy 4: collection + name match
                full_name = f"{collection_name_lower} {sticker_name_lower}"
                if key_lower in full_name or full_name in key_lower:
                    matched_files.extend(files)
                    print(f"    ✅ Full name match: {key}")
                    continue
            
            # Remove duplicates
            matched_files = list(set(matched_files))
            if not matched_files:
                print(f"    ❌ No assets found for this sticker!")
            
            # Upload matched files
            for file_path in matched_files:
                print(f"Uploading {case['name']} / {file_path.name}...")
                url = upload_to_cloudinary(file_path, case['name'], sticker['name'])
                if url:
                    sticker["assets"].append({
                        "path": str(file_path),
                        "url": url,
                        "type": file_path.suffix.lower()
                    })
    
    return cases


def generate_processed_md(cases):
    """Generate the processed markdown file."""
    lines = []
    
    for case in cases:
        lines.append(f"## {case['name']} Case")
        lines.append("")
        
        for sticker in case["stickers"]:
            lines.append(f"### {sticker['collection']} - {sticker['name']}")
            lines.append(f"- Collection Address: {sticker['address']}")
            lines.append(f"- Max Pool: {sticker['max_pool']}")
            
            if sticker["assets"]:
                lines.append("- Assets:")
                for asset in sticker["assets"]:
                    lines.append(f"  - [{asset['type']}]({asset['url']})")
            
            lines.append("")
    
    with open(OUTPUT_MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print(f"Processed catalog saved to {OUTPUT_MD_PATH}")


def main():
    print("Parsing Catalog.md...")
    cases = parse_catalog_md()
    print(f"Found {len(cases)} cases")
    
    print("Scanning assets...")
    asset_map = scan_assets()
    print(f"Found {len(asset_map)} asset groups (by case)")
    
    print("Matching and uploading assets to Cloudinary...")
    cases = match_and_upload_assets(cases, asset_map)
    
    print("Generating processed catalog...")
    generate_processed_md(cases)
    
    print("Done!")


if __name__ == "__main__":
    main()
