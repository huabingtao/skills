#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WeChat Article Cover Generator
Generates a WeChat-friendly cover image (horizontal 2.35:1, vertical 3:4, or square 1:1) from a vertical screenshot.
"""
import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def parse_args():
    parser = argparse.ArgumentParser(description="Generate standard WeChat cover from vertical screenshot.")
    parser.add_argument("-i", "--image", required=True, help="Path to the input vertical screenshot image")
    parser.add_argument("-t", "--text", required=True, help="Text to draw on the cover (use \\n for multiline)")
    parser.add_argument("-o", "--output", help="Path to output cover image (default: cover.png in the same directory)")
    parser.add_argument("--color", default="#FFD700", help="Hex color code for the text (default: #FFD700 for Gold)")
    parser.add_argument("--font", help="Path to a custom TTF/TTC font file")
    parser.add_argument("--style", choices=["horizontal", "vertical", "square"], default="horizontal", 
                        help="Aspect ratio style of the cover (horizontal [900x384], vertical [640x853], or square [500x500])")
    parser.add_argument("--crop-y", help="Y crop range format: 'start-end' (e.g. 420-920). If omitted, automatically detects based on row variance.")
    return parser.parse_args()

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([c*2 for c in hex_str])
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def find_best_crop_y(img, crop_h=500):
    """
    Finds the window with the highest variance of pixels,
    representing the most visually interesting content (rewards/chests/pets).
    """
    w, h = img.size
    crop_h = min(crop_h, h)
    if crop_h == h:
        return 0, h
    img_l = img.convert('L')
    pixels = list(img_l.getdata())
    
    # Calculate row variance
    row_vars = []
    for r in range(h):
        row_pixels = pixels[r*w : (r+1)*w]
        if not row_pixels:
            row_vars.append(0)
            continue
        mean = sum(row_pixels) / len(row_pixels)
        var = sum((x - mean)**2 for x in row_pixels) / len(row_pixels)
        row_vars.append(var)
        
    max_top = max(0, h - crop_h)
    if max_top == 0:
        return 0, h
        
    # Search within comfortable range if image is tall enough, otherwise across all possible tops
    if max_top >= 300:
        search_start = min(300, max_top)
        search_end = max(search_start, max_top - 300 if max_top >= 600 else max_top)
    else:
        search_start = 0
        search_end = max_top

    best_top = search_start
    max_var = -1
    
    step = max(1, (search_end - search_start) // 50) if search_end > search_start else 1
    for top in range(search_start, search_end + 1, step):
        top_clamped = min(top, max_top)
        window_var = sum(row_vars[top_clamped : top_clamped + crop_h]) / crop_h
        if window_var > max_var:
            max_var = window_var
            best_top = top_clamped
            
    best_top = max(0, min(best_top, h - crop_h))
    return best_top, best_top + crop_h

def main():
    args = parse_args()
    
    input_path = os.path.abspath(args.image)
    if not os.path.exists(input_path):
        print(f"❌ Error: Image not found: {input_path}")
        sys.exit(1)
        
    # Open base image
    img = Image.open(input_path)
    w, h = img.size
    
    # Resolve style properties
    if args.style == 'horizontal':
        canvas_w, canvas_h = 900, 384
        default_crop_h = min(500, h)
    elif args.style == 'vertical':
        canvas_w, canvas_h = 640, 853  # 3:4 aspect ratio
        default_crop_h = min(1560, h)
    elif args.style == 'square':
        canvas_w, canvas_h = 500, 500  # 1:1 aspect ratio
        default_crop_h = min(1170, h)
        
    # Resolve output path
    output_path = args.output
    if not output_path:
        output_path = os.path.join(os.path.dirname(input_path), "cover.png")
    output_path = os.path.abspath(output_path)
    
    # Determine crop coordinates
    if args.crop_y:
        try:
            crop_start, crop_end = map(int, args.crop_y.split('-'))
        except Exception:
            print(f"⚠ Warning: Invalid crop-y format: {args.crop_y}. Using auto-detection.")
            crop_start, crop_end = find_best_crop_y(img, default_crop_h)
    else:
        crop_start, crop_end = find_best_crop_y(img, default_crop_h)
        print(f"ℹ Auto-detected crop range: {crop_start}-{crop_end}")
        
    # Clamp crop coordinates strictly within [0, h]
    crop_start = max(0, min(crop_start, h - 1))
    crop_end = max(crop_start + 1, min(crop_end, h))
    
    # Crop the raw region
    raw_cropped = img.crop((0, crop_start, w, crop_end))
    
    # Scale to cover target canvas size without stretching (aspect ratio cover)
    rc_w, rc_h = raw_cropped.size
    scale = max(canvas_w / rc_w, canvas_h / rc_h)
    scaled_w = int(rc_w * scale)
    scaled_h = int(rc_h * scale)
    scaled_img = raw_cropped.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    
    # Center crop to target canvas size
    left_c = (scaled_w - canvas_w) // 2
    top_c = (scaled_h - canvas_h) // 2
    cover = scaled_img.crop((left_c, top_c, left_c + canvas_w, top_c + canvas_h))
    
    # Resolve Font
    font_path = args.font
    if not font_path or not os.path.exists(font_path):
        options = [
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Supplemental/Songti.ttc'
        ]
        font_path = None
        for path in options:
            if os.path.exists(path):
                font_path = path
                break
        if not font_path:
            print("⚠ Warning: No system Chinese fonts found. Text might render as fallback blocks.")
            
    # Draw Text
    draw = ImageDraw.Draw(cover)
    font_size = 72 if args.style != 'square' else 60 # Adjust font size slightly for square
    
    # Prepare text
    text_content = args.text.replace('\\n', '\n')
    line_spacing = 15
    
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # Calculate max width for text wrapping (maintaining appropriate margins)
    if args.style == 'horizontal':
        max_text_w = canvas_w - 200
    elif args.style == 'vertical':
        max_text_w = canvas_w - 120
    else:
        max_text_w = canvas_w - 100

    # Auto wrap text if lines exceed max width
    temp_draw = ImageDraw.Draw(Image.new('L', (1, 1)))
    def wrap_text(text, font, max_w, draw_obj):
        lines = []
        for paragraph in text.split('\n'):
            current_line = ""
            for char in paragraph:
                test_line = current_line + char
                bbox = draw_obj.textbbox((0, 0), test_line, font=font)
                w = bbox[2] - bbox[0]
                if w > max_w and current_line:
                    lines.append(current_line)
                    current_line = char
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line)
        return '\n'.join(lines)

    text_content = wrap_text(text_content, font, max_text_w, temp_draw)
        
    # Calculate sizes
    bbox = temp_draw.multiline_textbbox((0, 0), text_content, font=font, align='center', spacing=line_spacing)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Center text coordinates
    text_x = (canvas_w - text_w) // 2
    text_y = (canvas_h - text_h) // 2 - 10
    
    # 4. Draw Professional Soft Dark Shadow/Glow
    shadow_layer = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.multiline_text(
        (text_x, text_y),
        text_content,
        font=font,
        fill=(0, 0, 0, 240),
        align='center',
        spacing=line_spacing,
        stroke_fill=(0, 0, 0, 240),
        stroke_width=12
    )
    shadow_blurred = shadow_layer.filter(ImageFilter.GaussianBlur(radius=12))
    cover = Image.alpha_composite(cover.convert('RGBA'), shadow_blurred)
    
    # 5. Draw final colored text
    final_draw = ImageDraw.Draw(cover)
    text_color = hex_to_rgb(args.color) + (255,)
    final_draw.multiline_text(
        (text_x, text_y),
        text_content,
        font=font,
        fill=text_color,
        align='center',
        spacing=line_spacing,
        stroke_fill=(0, 0, 0, 255),
        stroke_width=6
    )
    
    # Save cover
    cover.save(output_path, 'PNG')
    print(f"✅ Cover successfully generated and saved to: {output_path}")

if __name__ == "__main__":
    main()
