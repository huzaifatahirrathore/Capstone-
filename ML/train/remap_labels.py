"""
Remap all YOLO label files to a single 'tree' class (0).
- Removes annotations for non-tree classes.
- Remaps all tree-related class IDs → 0.
"""
import os
from pathlib import Path

DATASET_DIR = "dataset"

# Non-tree class IDs to DROP
NON_TREE_IDS = {2, 4, 5, 6, 9, 11, 12, 13, 15, 17, 18}

# Everything else (0,1,3,7,8,10,14,16,19,20,21,22,23,24,25,26,27,28,29) → 0

def remap_file(label_path: Path):
    lines = label_path.read_text().strip().splitlines()
    new_lines = []
    for line in lines:
        parts = line.split()
        if len(parts) < 5:
            continue
        cls_id = int(parts[0])
        if cls_id in NON_TREE_IDS:
            continue
        # Remap to class 0
        new_lines.append(f"0 {' '.join(parts[1:])}")
    label_path.write_text("\n".join(new_lines) + ("\n" if new_lines else ""))
    return len(lines), len(new_lines)

def main():
    total_before = 0
    total_after = 0
    files_processed = 0

    for split in ("train", "val", "test"):
        label_dir = Path(DATASET_DIR) / "labels" / split
        if not label_dir.exists():
            continue
        for label_file in sorted(label_dir.glob("*.txt")):
            before, after = remap_file(label_file)
            total_before += before
            total_after += after
            files_processed += 1

    removed = total_before - total_after
    print(f"✅ Remapped {files_processed} label files")
    print(f"   Annotations before: {total_before}")
    print(f"   Annotations after:  {total_after}")
    print(f"   Removed (non-tree): {removed}")

if __name__ == "__main__":
    main()
