# -*- coding: utf-8 -*-
import markdown
import re
import sys
import os
import yaml
import json

def convert_to_wechat_html(md_content):
    """
    Converts Markdown content to HTML with inline CSS styles optimized for WeChat Official Accounts.
    Extracts Frontmatter if present.
    """
    metadata = {}
    
    # Extract Frontmatter
    if md_content.startswith('---'):
        parts = re.split(r'^---', md_content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                md_content = parts[2]
            except Exception as e:
                print(f"⚠ Warning: Failed to parse frontmatter: {e}")

    # Enable common extensions
    # 'fenced_code' for ``` blocks, 'tables' for table support, 'toc' for table of contents
    # 'nl2br' makes single newlines into <br> tags
    extensions = ['fenced_code', 'tables', 'toc', 'nl2br']
    html = markdown.markdown(md_content, extensions=extensions)
    
    # (Rest of styles definition unchanged...)
    styles = {
        'h1': 'style="font-size: 1.6em; font-weight: bold; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-top: 30px; margin-bottom: 20px; color: #2c3e50;"',
        'h2': 'style="font-size: 1.4em; font-weight: bold; border-left: 6px solid #2c3e50; padding-left: 12px; margin-top: 25px; margin-bottom: 15px; color: #2c3e50; background-color: #f8f9fa; padding-top: 5px; padding-bottom: 5px;"',
        'h3': 'style="font-size: 1.2em; font-weight: bold; margin-top: 20px; margin-bottom: 10px; color: #34495e;"',
        'p': 'style="margin: 15px 0; line-height: 1.8; color: #333; font-size: 16px; text-align: justify; word-break: break-word;"',
        'code': 'style="font-family: Consolas, Monaco, \'Andale Mono\', \'Ubuntu Mono\', monospace; background-color: #f3f4f5; color: #e74c3c; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; margin: 0 2px;"',
        'pre': 'style="background-color: #282c34; color: #abb2bf; padding: 18px; border-radius: 10px; overflow-x: auto; margin: 22px 0; line-height: 1.5; font-size: 14px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);"',
        'pre_code': 'style="background: none; color: inherit; padding: 0; border-radius: 0; font-family: Consolas, Monaco, \'Andale Mono\', \'Ubuntu Mono\', monospace;"',
        'ul': 'style="padding-left: 25px; margin: 15px 0; list-style-type: disc;"',
        'ol': 'style="padding-left: 25px; margin: 15px 0; list-style-type: decimal;"',
        'li': 'style="margin-bottom: 10px; line-height: 1.7; color: #333;"',
        'table': 'style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px; border: 1px solid #dfe2e5; border-radius: 6px; overflow: hidden;"',
        'th': 'style="background-color: #f6f8fa; border: 1px solid #dfe2e5; padding: 10px 15px; font-weight: bold; text-align: center; color: #24292e;"',
        'td': 'style="border: 1px solid #dfe2e5; padding: 10px 15px; text-align: left; color: #24292e;"',
        'blockquote': 'style="border-left: 5px solid #dfe2e5; color: #6a737d; padding: 12px 20px; margin: 22px 0; background-color: #fafbfc; border-radius: 0 6px 6px 0;"',
        'hr': 'style="height: 2px; padding: 0; margin: 30px 0; background-color: #e1e4e8; border: 0;"',
        'strong': 'style="font-weight: bold; color: #000;"'
    }

    # Apply styles using regex
    # We use a pattern that matches the start tag and any existing attributes
    def add_style(match, style):
        tag_start = match.group(1)
        attributes = match.group(2)
        # If style already exists, we might need a more complex merge, but for now we append
        return f'<{tag_start} {style} {attributes}>'

    # Headers
    html = re.sub(r'<(h1)([^>]*)>', lambda m: add_style(m, styles['h1']), html)
    html = re.sub(r'<(h2)([^>]*)>', lambda m: add_style(m, styles['h2']), html)
    html = re.sub(r'<(h3)([^>]*)>', lambda m: add_style(m, styles['h3']), html)
    
    # Text and lists
    html = re.sub(r'<(p)([^>]*)>', lambda m: add_style(m, styles['p']), html)
    html = re.sub(r'<(ul)([^>]*)>', lambda m: add_style(m, styles['ul']), html)
    html = re.sub(r'<(ol)([^>]*)>', lambda m: add_style(m, styles['ol']), html)
    html = re.sub(r'<(li)([^>]*)>', lambda m: add_style(m, styles['li']), html)
    html = re.sub(r'<(blockquote)([^>]*)>', lambda m: add_style(m, styles['blockquote']), html)
    html = re.sub(r'<hr />', f'<hr {styles["hr"]}>', html)
    html = re.sub(r'<(strong)([^>]*)>', lambda m: add_style(m, styles['strong']), html)
    
    # Tables
    html = re.sub(r'<(table)([^>]*)>', lambda m: add_style(m, styles['table']), html)
    html = re.sub(r'<(th)([^>]*)>', lambda m: add_style(m, styles['th']), html)
    html = re.sub(r'<(td)([^>]*)>', lambda m: add_style(m, styles['td']), html)

    # Handle [!TIP] and [!WARNING] markers in blockquotes
    def replace_callouts(match):
        type_marker = match.group(1)
        content = match.group(2)
        
        if "TIP" in type_marker:
            bg_color = "#f6ffed"
            border_color = "#b7eb8f"
            text_color = "#389e0d"
            icon = "💡"
            label = "呱呱小贴士"
        else:
            bg_color = "#fffbe6"
            border_color = "#ffe58f"
            text_color = "#d48806"
            icon = "⚠️"
            label = "呱呱避坑指南"
            
        return f'<blockquote style="border-left: 8px solid {border_color}; background-color: {bg_color}; color: {text_color}; padding: 15px 20px; margin: 20px 0; border-radius: 6px;">' \
               f'<p style="margin: 0 0 8px 0; font-weight: bold; font-size: 17px;">{icon} {label}</p>' \
               f'<p style="margin: 0; line-height: 1.6; font-size: 15px;">{content.strip()}</p></blockquote>'

    # Pattern matches <blockquote>...[!TIP]...</blockquote>
    html = re.sub(r'<blockquote style="[^"]*">\s*<p[^>]*>\s*\[!(TIP|WARNING)\]\s*(.*?)</p>\s*</blockquote>', 
                  replace_callouts, html, flags=re.DOTALL)

    # Code Blocks (pre > code)
    # The markdown library usually generates <pre><code class="language-python">...</code></pre>
    html = re.sub(r'<(pre)([^>]*)>', lambda m: add_style(m, styles['pre']), html)
    
    # Special handling for <code> to distinguish between inline and block
    # 1. Apply styles to ALL code tags
    html = re.sub(r'<(code)([^>]*)>', lambda m: add_style(m, styles['code']), html)
    
    # 2. Re-apply styles to code tags that are children of pre (fix the ones we just broke)
    # We look for <pre ...><code ... style="..."> and replace the style
    html = re.sub(rf'(<pre[^>]*>)\s*<code([^>]*) {styles["code"]} ([^>]*)>', 
                  rf'\1<code\2 {styles["pre_code"]} \3>', html)

    # Convert <font color="..."> (from Survivor.io strategy rules) to <span style="color: ...">
    # This ensures better rendering consistency in modern WeChat views.
    html = re.sub(r'<font color="(.*?)">(.*?)</font>', r'<span style="color: \1; font-weight: bold;">\2</span>', html)

    # Custom Image Styling Support: ![alt](src){style_params}
    # We do this on the generated HTML to handle attributes correctly
    def apply_image_styles(match):
        img_tag = match.group(1)
        style_params = match.group(2)
        
        # Parse params
        params = {}
        for p in style_params.split(';'):
            if '=' in p:
                k, v = p.split('=', 1)
                params[k.strip()] = v.strip()
        
        inline_style = ""
        if params.get('type') == 'card':
            inline_style = "display: block; margin: 20px auto; width: 20%; text-align: center; max-width: 100px; border-radius: 12px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); border: 1px solid #eee;"
            if 'data-type="card"' not in img_tag:
                img_tag = img_tag.replace('<img', '<img data-type="card"')
        elif params.get('type') == 'icon' or params.get('icon') == 'card':
            inline_style = "width: 38px; height: 38px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px;"
            if 'data-type="icon"' not in img_tag:
                img_tag = img_tag.replace('<img', '<img data-type="icon"')
        else:
            # Custom w/h
            if 'w' in params:
                inline_style += f"width: {params['w']}; "
            if 'h' in params:
                inline_style += f"height: {params['h']}; "
        
        if inline_style:
            if 'style="' in img_tag:
                # Merge styles (simplistic)
                return img_tag.replace('style="', f'style="{inline_style} ')
            else:
                return img_tag.replace('<img', f'<img style="{inline_style}"')
        
        return img_tag

    # Match <img ... />{style_params}
    html = re.sub(r'(<img[^>]*?>)\{(.*?)\}', apply_image_styles, html)

    # 4. Handle [占位图:NAME type=...] Custom Placeholders
    def replace_placeholder(match):
        name = match.group(1).strip()
        img_type = match.group(2).strip()
        
        # Find path
        img_path = ""
        # Search common directories for icons
        search_dirs = [
            'assets/img/其它', 'assets/img/道具', 'assets/img/配件', 
            'assets/img/收藏品', 'assets/img/装备', 'assets/img/宝箱', 'assets/img/碎片'
        ]
        
        # Try exact name in common dirs (case-insensitive)
        name_lower = name.lower()
        for d in search_dirs:
            if not os.path.exists(d): continue
            for f in os.listdir(d):
                fname, ext = os.path.splitext(f)
                if fname.lower() == name_lower and ext.lower() in ['.png', '.jpg', '.webp', '.jpeg']:
                    img_path = os.path.join(d, f)
                    break
            if img_path: break
        
        # Fallback to recursive search (case-insensitive)
        if not img_path:
             for root, dirs, files in os.walk('assets/img'):
                 for f in files:
                     fname, ext = os.path.splitext(f)
                     if fname.lower() == name_lower and ext.lower() in ['.png', '.jpg', '.webp', '.jpeg']:
                         img_path = os.path.join(root, f)
                         break
                 if img_path: break
        
        if img_path:
            if img_type == 'card':
                # Card style: block, rounded corners
                inline_style = "display: block; margin: 20px auto; width: 20%; text-align: center; max-width: 100px; border-radius: 12px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); border: 1px solid #eee;"
                return f'<img data-type="card" style="{inline_style}" src="{img_path}" alt="{name}" />'
            else:
                # Default to icon style
                inline_style = "width: 38px; height: 38px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px;"
                return f'<img data-type="icon" style="{inline_style}" src="{img_path}" alt="{name}" />'
        
        return match.group(0)

    html = re.sub(r'!?\[占位图:(.*?)\s+type=(.*?)\]', replace_placeholder, html)

    # 5. Prevent Line Breaks for Icons (Unwrap standalone icons from <p> tags)
    # This removes the block-level margins that cause line breaks
    html = re.sub(r'<(p)[^>]*>\s*(<img [^>]*data-type="icon"[^>]*>)\s*</p>', r'\2', html)
    # Also handle multiple icons in one paragraph if they are the ONLY content
    html = re.sub(r'<(p)[^>]*>\s*((?:<img [^>]*data-type="icon"[^>]*>\s*)+)</p>', r'\2', html)

    # 6. Force Centering for Cards (Ensure parent <p> is centered)
    # Find <p> tags that ONLY contain a card image and change their alignment to center
    html = re.sub(r'<(p)[^>]*>\s*(<img [^>]*data-type="card"[^>]*>)\s*</p>', 
                  r'<p style="text-align: center; margin: 20px 0; display: block;">\2</p>', html)

    # 7. Default styling for standard images (auto-imported weapons/skills)
    # If an image doesn't have a style or data-type yet, treat it as a 38px icon
    default_icon_style = 'style="width: 38px; height: 38px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px;"'
    html = re.sub(r'<img(?![^>]*style=)([^>]*?)>', rf'<img \1 {default_icon_style} data-type="icon">', html)

    # 8. Auto-highlight Statistics (Percentages)
    # Automatically colors percentage values (e.g., 5%, +10%) in red.
    # The regex skips percentages inside HTML tag attributes (like width="100%").
    html = re.sub(r'(?<![0-9;])(\+?\d+(?:\.\d+)?%)(?![^<]*>)', 
                  r'<span style="color: #FF4D4F; font-weight: bold;">\1</span>', html)

    # 9. Add Global Background Container
    # Wraps everything in a light grey section for better readability and style
    bg_style = 'style="background-color: #F8F9FA; padding: 20px 15px; border-radius: 12px; margin: 10px; box-sizing: border-box;"'
    html = f'<section {bg_style}>{html}</section>'

    return html, metadata

def main():
    if len(sys.argv) < 2:
        print("Markdown to WeChat HTML Converter")
        print("Usage: python md_to_wechat.py <input_file> [output_file]")
        return

    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(input_path)[0] + "_wechat.html"
    meta_path = os.path.splitext(output_path)[0] + ".json"

    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        wechat_html, metadata = convert_to_wechat_html(content)
        
        # Save HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(wechat_html)
            
        # Save Metadata
        if metadata:
            # Handle date objects for JSON serialization
            def json_serial(obj):
                if isinstance(obj, (yaml.constructor.SafeConstructor,)): # Not likely but for safety
                     return str(obj)
                import datetime
                if isinstance(obj, (datetime.date, datetime.datetime)):
                    return obj.isoformat()
                raise TypeError ("Type %s not serializable" % type(obj))

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=json_serial)
        
        print(f"✅ Successfully converted '{input_path}' to '{output_path}'")
        if metadata:
            print(f"✅ Metadata saved to '{meta_path}'")
        print("Tip: You can now copy the content of the HTML file and paste it into the WeChat Official Account editor.")
    except Exception as e:
        print(f"❌ Error during conversion: {e}")

if __name__ == "__main__":
    main()
