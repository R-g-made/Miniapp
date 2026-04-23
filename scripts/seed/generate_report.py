import json
import re

def parse_multi_json(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split the content by }{ and add the braces back to make them valid individual JSON objects
    # Or better, find all { ... } blocks
    # Since the file might have nested braces, a simple regex might fail.
    # Let's use a more robust way: find top-level objects.
    
    objects = []
    decoder = json.JSONDecoder()
    pos = 0
    while pos < len(content):
        # Skip whitespace/newlines
        match = re.search(r'\S', content[pos:])
        if not match:
            break
        pos += match.start()
        
        try:
            obj, next_pos = decoder.raw_decode(content[pos:])
            objects.append(obj)
            pos += next_pos
        except json.JSONDecodeError:
            # If we hit an error, try to skip one character and continue (might be extra chars between objects)
            pos += 1
            
    return objects

def main():
    json_path = r'c:\Users\maxvr\Documents\trae_projects\MiniApp\scripts\seed\SS_id.json'
    output_path = r'c:\Users\maxvr\Documents\trae_projects\MiniApp\scripts\seed\collections_report.md'
    
    data_objects = parse_multi_json(json_path)
    
    report_lines = [
        "# Collections and Characters Mapping\n",
        "| Character Name | Collection Name | Character ID | Collection ID |",
        "| :--- | :--- | :--- | :--- |"
    ]
    
    found_collection_ids = set()
    
    for obj in data_objects:
        coll = obj.get('collection', {})
        coll_id = coll.get('id')
        coll_title = coll.get('title', 'N/A')
        
        if coll_id is not None:
            found_collection_ids.add(coll_id)
            
        characters = obj.get('characters', [])
        for char in characters:
            char_name = char.get('name', 'N/A')
            char_id = char.get('id', 'N/A')
            report_lines.append(f"| {char_name} | {coll_title} | {char_id} | {coll_id} |")
            
    # Check for missing collection IDs up to 45
    missing_ids = []
    for i in range(1, 46):
        if i not in found_collection_ids:
            missing_ids.append(str(i))
            
    report_lines.append("\n## Missing Collection IDs (up to 45)")
    if missing_ids:
        report_lines.append(f"The following collection IDs are missing: {', '.join(missing_ids)}")
    else:
        report_lines.append("All collection IDs from 1 to 45 are present.")
        
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
        
    print(f"Report generated successfully at: {output_path}")

if __name__ == "__main__":
    main()
