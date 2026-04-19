import os
import re
from pathlib import Path
from collections import defaultdict

# Paths
CATALOG_MD_PATH = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\Catalog.md")
CATALOG_ASSET_PATH = Path(r"c:\Users\maxvr\OneDrive\Desktop\CatalogAsset")


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


def scan_assets():
    """Scan CatalogAsset directory and map assets to sticker names/collections."""
    asset_map = defaultdict(list)

    for case_dir in CATALOG_ASSET_PATH.iterdir():
        if not case_dir.is_dir():
            continue
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
                asset_map[base_name].append(file)

    return asset_map


def main():
    print("Parsing Catalog.md...")
    cases = parse_catalog_md()
    print(f"Found {len(cases)} cases")
    
    for case in cases:
        print(f"\nCase: {case['name']} - {len(case['stickers'])} stickers")
        for sticker in case['stickers']:
            print(f"  - {sticker['collection']} / {sticker['name']}")
    
    print("\nScanning assets...")
    asset_map = scan_assets()
    print(f"Found {len(asset_map)} asset groups")
    print("\nAsset group keys:")
    for key in sorted(asset_map.keys()):
        print(f"  - {key}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()
