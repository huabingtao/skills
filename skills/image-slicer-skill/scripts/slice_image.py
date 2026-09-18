#!/usr/bin/env python3
import os
import sys
import re
import argparse
from PIL import Image, ImageFilter

def find_components(img_path, min_size=50, threshold_alpha=10, threshold_color=250, bg='auto', dilation=None):
    """
    Scans the image and runs a BFS Connected Component Analysis to identify bounding boxes
    of non-transparent, non-white foreground icons.
    """
    img = Image.open(img_path)
    w, h = img.size
    img_rgba = img.convert("RGBA")
    pixels = img_rgba.load()

    # Step 1: Detect background if auto
    detected_bg = bg
    if bg == 'auto':
        # sample the 4 corners
        corners = [pixels[0, 0], pixels[w-1, 0], pixels[0, h-1], pixels[w-1, h-1]]
        # Count transparent corners
        transparent_corners = sum(1 for c in corners if c[3] < threshold_alpha)
        if transparent_corners >= 2:
            detected_bg = 'transparent'
        else:
            avg_a = sum(c[3] for c in corners) / 4.0
            if avg_a < threshold_alpha:
                detected_bg = 'transparent'
            else:
                avg_r = sum(c[0] for c in corners) / 4.0
                avg_g = sum(c[1] for c in corners) / 4.0
                avg_b = sum(c[2] for c in corners) / 4.0
                if avg_r > threshold_color and avg_g > threshold_color and avg_b > threshold_color:
                    detected_bg = 'white'
                elif avg_r < 40 and avg_g < 40 and avg_b < 40:
                    detected_bg = 'black'
                else:
                    detected_bg = 'transparent'
    
    print(f"Detected background mode: {detected_bg}")
    
    # Auto-set dilation if None
    if dilation is None:
        if detected_bg == 'transparent':
            dilation = 1
        else:
            dilation = 5
    print(f"Using dilation size: {dilation}")

    # Step 2: Create a binary mask of foreground pixels as a PIL Image
    mask_img = Image.new("L", (w, h), 0)
    mask_pixels = mask_img.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            is_foreground = False
            
            if detected_bg == 'transparent':
                if a > threshold_alpha:
                    is_foreground = True
            elif detected_bg == 'white':
                if not (r > threshold_color and g > threshold_color and b > threshold_color):
                    is_foreground = True
            elif detected_bg == 'black':
                # not solid black (to avoid noise, threshold is set to 20)
                if not (r < 20 and g < 20 and b < 20):
                    is_foreground = True
                    
            if is_foreground:
                mask_pixels[x, y] = 255

    # Dilate mask to group nearby components together (jump across gaps)
    if dilation > 1:
        dilated_img = mask_img.filter(ImageFilter.MaxFilter(size=dilation))
        dilated_pixels = dilated_img.load()
    else:
        dilated_pixels = mask_pixels

    # Step 3: Connected Component Labeling using BFS
    visited = [[False] * h for _ in range(w)]
    components = []

    for x in range(w):
        for y in range(h):
            if mask_pixels[x, y] == 255 and not visited[x][y]:
                # Start a new component BFS
                queue = [(x, y)]
                visited[x][y] = True
                
                min_x, max_x = None, None
                min_y, max_y = None, None
                
                while queue:
                    cx, cy = queue.pop(0)
                    
                    # Update bounding box bounds only for original foreground pixels (keeps bbox tight)
                    if mask_pixels[cx, cy] == 255:
                        if min_x is None or cx < min_x: min_x = cx
                        if max_x is None or cx > max_x: max_x = cx
                        if min_y is None or cy < min_y: min_y = cy
                        if max_y is None or cy > max_y: max_y = cy
                    
                    # Check 8-neighbors in dilated mask
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h:
                                if dilated_pixels[nx, ny] == 255 and not visited[nx][ny]:
                                    visited[nx][ny] = True
                                    queue.append((nx, ny))
                
                if min_x is not None:
                    comp_w = max_x - min_x + 1
                    comp_h = max_y - min_y + 1
                    
                    # Filter out small noise elements
                    if comp_w >= min_size and comp_h >= min_size:
                        components.append((min_x, min_y, max_x, max_y))
    
    img.close()
    return components, detected_bg

def make_background_transparent(cropped_img, bg_type, threshold_color=250):
    """
    Floods the background from the borders of the cropped image and makes it transparent.
    This prevents internal black/white parts of the icon from becoming transparent.
    """
    if bg_type == 'transparent':
        return cropped_img  # already transparent

    w, h = cropped_img.size
    img_rgba = cropped_img.convert("RGBA")
    pixels = img_rgba.load()

    # Step 1: Identify background pixels using BFS from all border pixels
    visited = [[False] * h for _ in range(w)]
    queue = []

    def is_bg_pixel(r, g, b, a):
        if bg_type == 'white':
            return r > threshold_color and g > threshold_color and b > threshold_color
        elif bg_type == 'black':
            return r < 40 and g < 40 and b < 40
        return False

    # Add all border pixels matching the background color to the queue
    for x in range(w):
        for y in [0, h - 1]:
            r, g, b, a = pixels[x, y]
            if is_bg_pixel(r, g, b, a) and not visited[x][y]:
                visited[x][y] = True
                queue.append((x, y))
    for y in range(h):
        for x in [0, w - 1]:
            r, g, b, a = pixels[x, y]
            if is_bg_pixel(r, g, b, a) and not visited[x][y]:
                visited[x][y] = True
                queue.append((x, y))

    # BFS traversal
    while queue:
        cx, cy = queue.pop(0)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h:
                if not visited[nx][ny]:
                    r, g, b, a = pixels[nx, ny]
                    if is_bg_pixel(r, g, b, a):
                        visited[nx][ny] = True
                        queue.append((nx, ny))

    # Step 2: Set alpha of all visited background pixels to 0
    for y in range(h):
        for x in range(w):
            if visited[x][y]:
                r, g, b, a = pixels[x, y]
                pixels[x, y] = (r, g, b, 0)

    return img_rgba

def main():
    parser = argparse.ArgumentParser(description="CCA Spritesheet Slicing Tool - automatically crops icons from a spritesheet.")
    parser.add_argument("--image", required=True, help="Path to the input spritesheet image (PNG/JPG).")
    parser.add_argument("--output", required=True, help="Directory to save the sliced PNG outputs.")
    parser.add_argument("--prefix", default="sprite", help="Prefix for the sliced output filenames.")
    parser.add_argument("--min-size", type=int, default=50, help="Minimum width/height for cropped components.")
    parser.add_argument("--alpha", type=int, default=10, help="Alpha threshold for transparency (0-255).")
    parser.add_argument("--color", type=int, default=250, help="Color threshold to exclude white background (0-255).")
    parser.add_argument("--bg", default="auto", choices=["auto", "transparent", "white", "black"], help="Background color type to filter out.")
    parser.add_argument("--dilation", type=int, default=None, help="Dilation filter size (must be an odd integer) to group nearby parts (default: None, auto-set based on background).")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        print(f"Error: Input image {args.image} does not exist.")
        sys.exit(1)
        
    os.makedirs(args.output, exist_ok=True)
    
    print(f"Analyzing {args.image} using Connected Component Analysis...")
    bboxes, detected_bg = find_components(args.image, args.min_size, args.alpha, args.color, args.bg, args.dilation)
    
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
        # Make background transparent if needed
        cropped_transparent = make_background_transparent(cropped, detected_bg, args.color)
        
        # Save as transparent png
        out_name = f"{args.prefix}_row{r}_col{c}.png"
        out_path = os.path.join(args.output, out_name)
        cropped_transparent.save(out_path)
        count += 1
        w_val = bbox[2] - bbox[0] + 1
        h_val = bbox[3] - bbox[1] + 1
        print(f"Cropped: {out_name} ({w_val}x{h_val}) at Box={bbox}")
        
    img.close()
    print(f"\nSuccessfully sliced {count} icons to: {args.output}")

if __name__ == "__main__":
    main()
