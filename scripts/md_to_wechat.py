# -*- coding: utf-8 -*-
import markdown
import re
import sys
import os
import yaml
import json

def load_image_mapping(mapping_path):
    """
    Parses image_mapping.md to build a dictionary of {keyword: image_path}
    """
    mapping = {}
    if not os.path.exists(mapping_path):
        return mapping
        
    # Regular expression to extract the key name and image path from the Markdown table row.
    # Matches: | **【双绝枪】** | `![双绝枪](assets/img/装备/ss武器-双绝枪-原始形态.png)` | ...
    line_pattern = re.compile(r'^\s*\|\s*(?:\*\*)?【?([^】\*]+)】?(?:\*\*)?\s*\|\s*`?!\s*\[[^\]]*\]\(([^)]+)\)`?\s*\|')
    
    try:
        with open(mapping_path, 'r', encoding='utf-8') as f:
            for line in f:
                match = line_pattern.match(line)
                if match:
                    key = match.group(1).strip()
                    path = match.group(2).strip()
                    mapping[key] = path
    except Exception as e:
        print(f"⚠ Warning: Failed to parse image mapping dictionary: {e}")
        
    return mapping

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

    # Load image mapping dictionary
    script_dir = os.path.dirname(os.path.abspath(__file__))
    mapping_file = os.path.abspath(os.path.join(script_dir, '../references/image_mapping.md'))
    image_mapping = load_image_mapping(mapping_file)

    # Enable common extensions
    # 'fenced_code' for ``` blocks, 'tables' for table support, 'nl2br' for newline handling
    extensions = ['fenced_code', 'tables', 'nl2br', 'toc']
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
        'strong': 'style="font-weight: bold;"'
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
        img_type = params.get('type')
        if img_type == 'card':
            inline_style = "display: block; margin: 20px auto; width: 90%; max-width: 100%; border-radius: 12px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); border: 1px solid #eee;"
        elif img_type == 'banner':
            inline_style = "display: block; margin: 20px auto; width: 100%; max-width: 100%; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08);"
        elif img_type == 'grid2':
            inline_style = "width: 48%; display: inline-block; margin: 10px 1%; vertical-align: middle; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.06); border: 1px solid #eee; box-sizing: border-box;"
        elif img_type == 'grid3':
            inline_style = "width: 31.3%; display: inline-block; margin: 10px 1%; vertical-align: middle; border-radius: 6px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border: 1px solid #eee; box-sizing: border-box;"
        elif img_type == 'grid4':
            inline_style = "width: 23%; display: inline-block; margin: 10px 1%; vertical-align: middle; border-radius: 6px; box-shadow: 0 4px 8px rgba(0,0,0,0.05); border: 1px solid #eee; box-sizing: border-box;"
        elif img_type == 'float-left':
            inline_style = "float: left; width: 80px; height: 80px; margin: 5px 15px 5px 0; border-radius: 10px; border: 1px solid #eee; box-shadow: 0 2px 6px rgba(0,0,0,0.08); object-fit: cover;"
        elif img_type == 'float-right':
            inline_style = "float: right; width: 80px; height: 80px; margin: 5px 0 5px 15px; border-radius: 10px; border: 1px solid #eee; box-shadow: 0 2px 6px rgba(0,0,0,0.08); object-fit: cover;"
        elif img_type == 'avatar':
            inline_style = "width: 30px; height: 30px; border-radius: 50%; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px; border: 1.5px solid #2c3e50; box-shadow: 0 2px 4px rgba(0,0,0,0.1); box-sizing: border-box; object-fit: cover;"
        elif img_type == 'icon' or params.get('icon') == 'card':
            inline_style = "width: 24px; height: 24px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px; object-fit: cover;"
        else:
            # Custom w/h
            if 'w' in params:
                inline_style += f"width: {params['w']}; "
            if 'h' in params:
                inline_style += f"height: {params['h']}; "
        
        # Add padding support (pd=2 -> padding: 2px;)
        if 'pd' in params:
            inline_style += f"padding: {params['pd']}px; box-sizing: border-box; "
        
        if inline_style:
            if 'style="' in img_tag:
                # Merge styles (simplistic)
                return img_tag.replace('style="', f'style="{inline_style} ')
            else:
                return img_tag.replace('<img', f'<img style="{inline_style}"')
        
        return img_tag

    # Match <img ... />{style_params}
    # Note: markdown library might wrap the style in a separate paragraph if there's a newline,
    # but if it's on the same line it will be <img ... />{...}
    html = re.sub(r'(<img[^>]*?>)\{(.*?)\}', apply_image_styles, html)

    # Resolve all image paths intelligently (supporting img://, bare name, or partial paths)
    def resolve_image_path(match):
        original_src = match.group(1).strip()
        
        # Ignore external http/https URLs
        if original_src.startswith('http://') or original_src.startswith('https://'):
            return match.group(0)
            
        # Clean the src path (e.g. strip img:// prefix if present)
        src_clean = original_src.replace('img://', '')
        
        # Extract the base key (e.g., "assets/img/装备/ss武器-双绝枪.png" -> "ss武器-双绝枪")
        base_name = os.path.basename(src_clean)
        key_name = os.path.splitext(base_name)[0]
        
        # Try finding a path in image_mapping
        real_path = image_mapping.get(src_clean) or image_mapping.get(base_name) or image_mapping.get(key_name)
        
        if real_path:
            return f'src="{real_path}"'
        else:
            # If not in mapping, keep as is but print warning only if it's not already a valid assets path
            if not original_src.startswith('assets/'):
                print(f"⚠ Warning: Image path not found in mapping dictionary for: {original_src}")
            return match.group(0)

    html = re.sub(r'src=["\']([^"\']+)["\']', resolve_image_path, html)

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
