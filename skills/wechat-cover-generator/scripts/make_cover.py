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
    parser.add_argument("--font-size", type=int, help="Custom font size in pixels (default: 56 for horizontal, 52 for vertical)")
    parser.add_argument("--style", choices=["horizontal", "vertical", "square"], default="horizontal", 
                        help="Aspect ratio style of the cover (horizontal [900x384], vertical [640x853], or square [500x500])")
    parser.add_argument("--both", action="store_true", default=True,
                        help="Generate both horizontal (cover.png) and vertical (cover_vertical.png) covers simultaneously (default: True)")
    parser.add_argument("--single", action="store_true", help="Only generate single specified style output")
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
    representing the most visually interesting content.
    """
    w, h = img.size
    crop_h = min(crop_h, h)
    if crop_h >= h:
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
        
    max_top = h - crop_h
    best_top = max_top // 2
    max_var = -1
    step = max(1, max_top // 20)
    
    for top in range(0, max_top + 1, step):
        window_var = sum(row_vars[top : top + crop_h]) / crop_h
        if window_var > max_var:
            max_var = window_var
            best_top = top
            
    return best_top, best_top + crop_h

def render_cover(img, style, text, font_path, color_hex, crop_y_str, output_path, custom_font_size=None):
    w, h = img.size
    
    # Resolve style properties
    if style == 'horizontal':
        canvas_w, canvas_h = 900, 384
        default_font_size = 56
    elif style == 'vertical':
        canvas_w, canvas_h = 640, 853  # 3:4 aspect ratio
        default_font_size = 50
    elif style == 'square':
        canvas_w, canvas_h = 500, 500  # 1:1 aspect ratio
        default_font_size = 46
    else:
        canvas_w, canvas_h = 900, 384
        default_font_size = 56
        
    aspect_ratio = canvas_w / canvas_h
    default_crop_h = min(int(w / aspect_ratio), h)
    
    # Determine crop coordinates
    if crop_y_str:
        try:
            crop_start, crop_end = map(int, crop_y_str.split('-'))
        except Exception:
            crop_start, crop_end = find_best_crop_y(img, default_crop_h)
    else:
        crop_start, crop_end = find_best_crop_y(img, default_crop_h)
        
    # Crop the raw region
    raw_cropped = img.crop((0, crop_start, w, crop_end))
    
    # Scale to cover target canvas size without stretching
    rc_w, rc_h = raw_cropped.size
    scale = max(canvas_w / rc_w, canvas_h / rc_h)
    scaled_w = int(rc_w * scale)
    scaled_h = int(rc_h * scale)
    scaled_img = raw_cropped.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
    
    # Center crop to target canvas size
    left_c = (scaled_w - canvas_w) // 2
    top_c = (scaled_h - canvas_h) // 2
    cover = scaled_img.crop((left_c, top_c, left_c + canvas_w, top_c + canvas_h))
    
    # Text line resolution: prioritize \n, fallback to space
    raw_text = text.replace('\\n', '\n')
    if '\n' in raw_text:
        text_lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    else:
        parts = [p.strip() for p in raw_text.split(' ') if p.strip()]
        text_lines = parts if parts else [raw_text.strip()]
        
    max_text_w = canvas_w - (80 if style == 'horizontal' else 50)
    
    # Auto-scale font size so each line fits within max_text_w without wrapping
    cur_font_size = custom_font_size if custom_font_size else default_font_size
    temp_draw = ImageDraw.Draw(Image.new('L', (1, 1)))
    
    while cur_font_size > 24:
        if font_path:
            font = ImageFont.truetype(font_path, cur_font_size)
        else:
            font = ImageFont.load_default()
            break
            
        all_fit = True
        for line in text_lines:
            bbox = temp_draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            if line_w > max_text_w:
                all_fit = False
                break
        if all_fit or (custom_font_size is not None):
            break
        cur_font_size -= 2
        
    if font_path:
        font = ImageFont.truetype(font_path, cur_font_size)
    else:
        font = ImageFont.load_default()
        
    text_content = '\n'.join(text_lines)
    line_spacing = int(cur_font_size * 0.25)
    
    bbox = temp_draw.multiline_textbbox((0, 0), text_content, font=font, align='center', spacing=line_spacing)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    text_x = (canvas_w - text_w) // 2
    text_y = (canvas_h - text_h) // 2 - 10
    
    # Soft Dark Shadow / Glow
    stroke_w = max(4, int(cur_font_size * 0.16))
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
        stroke_width=stroke_w
    )
    shadow_blurred = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
    cover = Image.alpha_composite(cover.convert('RGBA'), shadow_blurred)
    
    # Draw text
    final_draw = ImageDraw.Draw(cover)
    text_color = hex_to_rgb(color_hex) + (255,)
    final_draw.multiline_text(
        (text_x, text_y),
        text_content,
        font=font,
        fill=text_color,
        align='center',
        spacing=line_spacing,
        stroke_fill=(0, 0, 0, 255),
        stroke_width=max(2, int(stroke_w * 0.5))
    )
    
    # Ensure parent directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cover.save(output_path, 'PNG')
    print(f"✅ Cover [{style}] (font size {cur_font_size}px) successfully generated and saved to: {output_path}")

def main():
    args = parse_args()
    
    input_path = os.path.abspath(args.image)
    if not os.path.exists(input_path):
        print(f"❌ Error: Image not found: {input_path}")
        sys.exit(1)
        
    img = Image.open(input_path)
    
    # Resolve Font
    font_path = args.font
    if not font_path or not os.path.exists(font_path):
        options = [
            '/mnt/c/Windows/Fonts/msyhbd.ttc',
            '/mnt/c/Windows/Fonts/msyh.ttc',
            '/mnt/c/Windows/Fonts/simhei.ttf',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Supplemental/Songti.ttc'
        ]
        font_path = None
        for path in options:
            if os.path.exists(path):
                font_path = path
                break

    input_dir = os.path.dirname(input_path)
    out_dir = os.path.dirname(os.path.abspath(args.output)) if args.output else input_dir
    dist_dir = out_dir if os.path.basename(out_dir) == "dist" else os.path.join(out_dir, "dist")
    os.makedirs(dist_dir, exist_ok=True)
    
    if args.single:
        out_path = os.path.abspath(args.output) if args.output else os.path.join(out_dir, f"cover_{args.style}.png")
        render_cover(img, args.style, args.text, font_path, args.color, args.crop_y, out_path, args.font_size)
        if out_dir != dist_dir:
            dist_out_path = os.path.join(dist_dir, f"cover_{args.style}.png")
            render_cover(img, args.style, args.text, font_path, args.color, args.crop_y, dist_out_path, args.font_size)
    else:
        # Default dual-generation mode: both horizontal cover.png and vertical cover_vertical.png
        h_path = os.path.abspath(args.output) if (args.output and args.style == 'horizontal') else os.path.join(out_dir, "cover.png")
        v_path = os.path.join(out_dir, "cover_vertical.png")
        
        render_cover(img, 'horizontal', args.text, font_path, args.color, args.crop_y, h_path, args.font_size)
        render_cover(img, 'vertical', args.text, font_path, args.color, args.crop_y, v_path, args.font_size)

        if out_dir != dist_dir:
            dist_h_path = os.path.join(dist_dir, "cover.png")
            dist_v_path = os.path.join(dist_dir, "cover_vertical.png")
            render_cover(img, 'horizontal', args.text, font_path, args.color, args.crop_y, dist_h_path, args.font_size)
            render_cover(img, 'vertical', args.text, font_path, args.color, args.crop_y, dist_v_path, args.font_size)

if __name__ == "__main__":
    main()
