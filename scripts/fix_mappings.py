import os
import json

def fix_image_mappings():
    skill_root = "/Users/hbt/my-project/skills/danke-strategy-skill"
    pack_dir = os.path.join(skill_root, "packs/danke")
    mapping_path = os.path.join(pack_dir, "image_mapping.json")
    assets_dir = os.path.join(pack_dir, "assets/img")

    if not os.path.exists(mapping_path):
        print("image_mapping.json not found")
        return

    # Load existing mappings
    with open(mapping_path, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    # Scan all actual image files on disk
    disk_files = {}
    for r, d, fs in os.walk(assets_dir):
        for f in fs:
            if f.endswith(('.png', '.jpg', '.jpeg')):
                full_path = os.path.join(r, f)
                rel_path = os.path.relpath(full_path, pack_dir)
                basename = os.path.basename(f)
                disk_files[basename] = rel_path
                # Also index without extension
                name_only = os.path.splitext(basename)[0]
                disk_files[name_only] = rel_path

    # Attempt to fix each mapping
    fixed_count = 0
    for key, path in list(mapping.items()):
        full_mapped_path = os.path.join(pack_dir, path)
        if not os.path.exists(full_mapped_path):
            # Try to resolve by filename
            basename = os.path.basename(path)
            name_only = os.path.splitext(basename)[0]
            if basename in disk_files:
                mapping[key] = disk_files[basename]
                print(f"Fixed mapping for '{key}': {path} -> {disk_files[basename]}")
                fixed_count += 1
            elif name_only in disk_files:
                mapping[key] = disk_files[name_only]
                print(f"Fixed mapping for '{key}': {path} -> {disk_files[name_only]}")
                fixed_count += 1
            else:
                # Try search by key name
                if key in disk_files:
                    mapping[key] = disk_files[key]
                    print(f"Fixed mapping by key '{key}': {path} -> {disk_files[key]}")
                    fixed_count += 1
                else:
                    print(f"Could not find replacement for '{key}': {path}")

    if fixed_count > 0:
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        print(f"Successfully fixed {fixed_count} mappings in image_mapping.json")
    else:
        print("No mappings needed fixing.")

if __name__ == "__main__":
    fix_image_mappings()
