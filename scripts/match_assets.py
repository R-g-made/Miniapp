import re
from pathlib import Path

# Paths
CATALOG_PATH = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\Catalog.md")
CATALOG_URLS_PATH = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\catalog_urls.md")
OUTPUT_PATH = Path(r"c:\Users\maxvr\Documents\trae_projects\MiniApp\FinalCatalog.md")


def normalize_name(s):
    """Normalize name for matching: lowercase, remove punctuation, spaces, etc."""
    s = s.lower()
    s = re.sub(r'[^\w]', '', s)
    return s


def match_case_name(case_name):
    """Map catalog case names to folder names."""
    case_map = {
        "DOGES (Goodies) Case": "Dogs Goodies Pack",
        "Slon Case": "Slon Case (1 no Lottie Webp)",
        "Pengu Case (Goodies & Sticker Store)": "Pengu Pack",
        "Blum Case": "Blum Case FULL",
        "DOGS (Sticker Store) Case": "DOGS SS (36 items) FULL",
        "Monkey Case": "Monkey Case (4 no Lottie Webp)",
        "NOT Case": "NOT Case (1 no Lottie only TGS)"
    }
    return case_map.get(case_name, case_name)


def parse_urls_file():
    """Parse catalog_urls.md and return a dict mapping normalized filename to url."""
    url_map = {}
    with open(CATALOG_URLS_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("- ["):
                match = re.match(r"-\s*\[(.*?)\]\((.*?)\)", line)
                if match:
                    filename = match.group(1)
                    url = match.group(2)
                    # Extract case folder from URL
                    case_from_url = ""
                    if "catalog_all/" in url:
                        parts = url.split("catalog_all/")[1].split("/")[0]
                        case_from_url = parts.split("_")[0]
                    norm_name = normalize_name(filename)
                    url_map[norm_name] = {
                        "filename": filename,
                        "url": url,
                        "case_prefix": case_from_url
                    }
    return url_map


def parse_catalog():
    """Parse Catalog.md correctly."""
    cases = []
    lines = []
    
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            line = re.sub(r'^\[\d{2}\.\d{2}\.\d{4}.*?\]\s*Sasha:\s*', '', line)
            if line:
                lines.append(line)
    
    current_case = None
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if "Case /" in line:
            if current_case:
                cases.append(current_case)
            
            case_name = line.split(" / ")[0].strip()
            current_case = {
                "name": case_name,
                "folder_name": match_case_name(case_name),
                "stickers": []
            }
            i += 1
            continue
        
        if current_case and i + 3 < len(lines):
            collection = lines[i]
            name = lines[i+1]
            max_pool_line = lines[i+2]
            address = lines[i+3]
            
            if not ("Case /" in collection or "items" in collection):
                max_pool = 0
                try:
                    if max_pool_line.endswith(" items"):
                        max_pool = int(max_pool_line.split(" ")[0])
                    else:
                        max_pool = int(max_pool_line)
                except:
                    pass
                
                current_case["stickers"].append({
                    "collection": collection,
                    "name": name,
                    "collection_address": address if address.startswith("EQ") else "",
                    "max_pool": max_pool,
                    "assets": []
                })
                i += 4
                continue
        
        i += 1
    
    if current_case:
        cases.append(current_case)
    
    return cases


def match_sticker_assets(sticker, url_map, case_folder_name):
    """Match sticker assets with strict filtering."""
    matched_assets = []
    sticker_name_norm = normalize_name(sticker["name"])
    collection_name_norm = normalize_name(sticker["collection"])
    case_name_norm = normalize_name(case_folder_name)
    
    # Common patterns
    patterns = []
    # Remove "OG", "Pack", etc.
    clean_sticker = sticker_name_norm.replace("og", "").replace("pack", "")
    clean_collection = collection_name_norm.replace("og", "").replace("pack", "")
    
    # Try different name combinations
    patterns.append(f"{clean_sticker}")
    patterns.append(f"{clean_collection}{clean_sticker}")
    patterns.append(f"{case_name_norm}{clean_sticker}")
    patterns.append(f"{case_name_norm}{clean_collection}{clean_sticker}")
    
    # Also check with numbers
    num_match = re.search(r'\d+', sticker["name"])
    if num_match:
        num = num_match.group(0)
        patterns.append(f"{clean_sticker}{num}")
        patterns.append(f"{clean_collection}{clean_sticker}{num}")
    
    for norm_name, data in url_map.items():
        filename = data["filename"]
        filename_norm = normalize_name(filename)
        
        # Check exact or very close match
        matched = False
        for pattern in patterns:
            if pattern and (pattern in filename_norm or filename_norm in pattern):
                matched = True
                break
        
        # Also check if filename contains key parts from sticker name
        if not matched:
            key_parts = []
            # Extract key words
            for part in sticker["name"].split():
                if len(part) > 2:
                    key_parts.append(normalize_name(part))
            for part in sticker["collection"].split():
                if len(part) > 2:
                    key_parts.append(normalize_name(part))
            
            match_count = 0
            for part in key_parts:
                if part in filename_norm:
                    match_count += 1
            
            if match_count >= 1:
                matched = True
        
        if matched:
            matched_assets.append((data["filename"], data["url"]))
    
    # Remove duplicates
    seen = set()
    unique_assets = []
    for filename, url in matched_assets:
        if url not in seen:
            seen.add(url)
            unique_assets.append((filename, url))
    
    # Limit to reasonable number (max 4 assets per sticker)
    return unique_assets[:4]


def main():
    print("Parsing catalog...")
    url_map = parse_urls_file()
    cases = parse_catalog()
    
    print(f"Loaded {len(url_map)} URLs")
    print(f"Loaded {len(cases)} cases with {sum(len(c['stickers']) for c in cases)} stickers")
    
    print("\nMatching assets...")
    total_matched = 0
    
    for case in cases:
        print(f"\nCase: {case['name']}")
        for sticker in case["stickers"]:
            assets = match_sticker_assets(sticker, url_map, case["folder_name"])
            if assets:
                sticker["assets"] = assets
                total_matched += 1
                print(f"  ✅ {sticker['collection']} - {sticker['name']}: {len(assets)} assets")
            else:
                print(f"  ❌ {sticker['collection']} - {sticker['name']}: no assets")
    
    print(f"\nTotal matched: {total_matched} stickers")
    
    # Generate output
    print(f"\nWriting final catalog to {OUTPUT_PATH}...")
    lines = []
    
    for case in cases:
        lines.append(f"## {case['name']}")
        lines.append("")
        
        for sticker in case["stickers"]:
            lines.append(f"### {sticker['collection']} - {sticker['name']}")
            lines.append(f"- Collection Address: {sticker['collection_address']}")
            lines.append(f"- Max Pool: {sticker['max_pool']}")
            
            if sticker["assets"]:
                lines.append("- Assets:")
                for filename, url in sticker["assets"]:
                    lines.append(f"  - [{filename}]({url})")
            
            lines.append("")
    
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    print("Done! Final catalog written!")


if __name__ == "__main__":
    main()
