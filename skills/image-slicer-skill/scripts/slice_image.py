#!/usr/bin/env python3
import os
import sys
import re
import argparse
from PIL import Image

def find_components(img_path, min_size=50, threshold_alpha=10, threshold_color=250):
    """
    Scans the image and runs a BFS Connected Component Analysis to identify bounding boxes
    of non-transparent, non-white foreground icons.
    """
    img = Image.open(img_path)
    w, h = img.size
    img_rgba = img.convert("RGBA")
    pixels = img_rgba.load()

    # Step 1: Create a binary mask of foreground pixels
    mask = [[False] * h for _ in range(w)]
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            # Foreground: not transparent and not white background
            if a > threshold_alpha and not (r > threshold_color and g > threshold_color and b > threshold_color):
                mask[x][y] = True

    # Step 2: Connected Component Labeling using BFS
    visited = [[False] * h for _ in range(w)]
    components = []

    for x in range(w):
        for y in range(h):
            if mask[x][y] and not visited[x][y]:
                # Start a new component BFS
                queue = [(x, y)]
                visited[x][y] = True
                
                min_x, max_x = x, x
                min_y, max_y = y, y
                
                while queue:
                    cx, cy = queue.pop(0)
                    
                    # Update bounding box bounds
                    min_x = min(min_x, cx)
                    max_x = max(max_x, cx)
                    min_y = min(min_y, cy)
                    max_y = max(max_y, cy)
                    
                    # Check 8-neighbors
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                if mask[nx][ny] and not visited[nx][ny]:
                                    visited[nx][ny] = True
                                    queue.append((nx, ny))
                
                comp_w = max_x - min_x + 1
                comp_h = max_y - min_y + 1
                
                # Filter out small noise elements
                if comp_w >= min_size and comp_h >= min_size:
                    components.append((min_x, min_y, max_x, max_y))
    
    img.close()
    return components

def main():
    parser = argparse.ArgumentParser(description="CCA Spritesheet Slicing Tool - automatically crops icons from a spritesheet.")
    parser.add_argument("--image", required=True, help="Path to the input spritesheet image (PNG).")
    parser.add_argument("--output", required=True, help="Directory to save the sliced PNG outputs.")
    parser.add_argument("--prefix", default="sprite", help="Prefix for the sliced output filenames.")
    parser.add_argument("--min-size", type=int, default=50, help="Minimum width/height for cropped components.")
    parser.add_argument("--alpha", type=int, default=10, help="Alpha threshold for transparency (0-255).")
    parser.add_argument("--color", type=int, default=250, help="Color threshold to exclude white background (0-255).")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        print(f"Error: Input image {args.image} does not exist.")
        sys.exit(1)
        
    os.makedirs(args.output, exist_ok=True)
    
    print(f"Analyzing {args.image} using Connected Component Analysis...")
    bboxes = find_components(args.image, args.min_size, args.alpha, args.color)
    
    # Sort bounding boxes top-to-bottom, then left-to-right to preserve row-by-row layout order
    # We group items into rows by checking if their Y centers are within min_size height of each other
    bboxes.sort(key=lambda b: (b[1], b[0]))
    
    # Refined row-wise sorting
    sorted_bboxes = []
    if bboxes:
        rows = []
        current_row = [bboxes[0]]
        for b in bboxes[1:]:
            # If Y coordinate is close to previous item in the row, group it
            if abs(b[1] - current_row[-1][1]) < (args.min_size / 2):
                current_row.append(b)
            else:
                current_row.sort(key=lambda x: x[0]) # sort columns left-to-right
                rows.append(current_row)
                current_row = [b]
        current_row.sort(key=lambda x: x[0])
        rows.append(current_row)
        
        # Flatten rows back
        row_num = 1
        for row_idx, r in enumerate(rows):
            col_num = 1
            for b in r:
                sorted_bboxes.append((b, row_num, col_num))
                col_num += 1
            row_num += 1

    print(f"Found {len(sorted_bboxes)} matching components. Starting crop...")
    
    img = Image.open(args.image)
    count = 0
    for bbox, r, c in sorted_bboxes:
        cropped = img.crop(bbox)
        # Save as transparent png
        out_name = f"{args.prefix}_row{r}_col{c}.png"
        out_path = os.path.join(args.output, out_name)
        cropped.save(out_path)
        count += 1
        w_val = bbox[2] - bbox[0] + 1
        h_val = bbox[3] - bbox[1] + 1
        print(f"Cropped: {out_name} ({w_val}x{h_val}) at Box={bbox}")
        
    img.close()
    print(f"\nSuccessfully sliced {count} icons to: {args.output}")

if __name__ == "__main__":
    main()
