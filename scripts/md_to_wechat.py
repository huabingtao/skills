# -*- coding: utf-8 -*-
import markdown
import re
import sys
import os
import yaml
import json
import argparse
from bs4 import BeautifulSoup

def load_image_mapping(mapping_path):
    """
    Parses image_mapping.md to build a dictionary of {keyword: image_path}
    """
    mapping = {}
    if not os.path.exists(mapping_path):
        return mapping
        
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

def parse_css(css_content):
    """
    Parses a CSS string into a list of (selector, declarations) tuples.
    Preserves declaration order for cascading rules.
    """
    # Remove CSS comments
    css_content = re.sub(r'/\*.*?\*/', '', css_content, flags=re.DOTALL)
    
    rules = []
    pattern = re.compile(r'([^{]+)\{([^}]+)\}')
    for match in pattern.finditer(css_content):
        selectors_raw = match.group(1).strip()
        declarations = match.group(2).strip()
        
        # Normalize spaces
        declarations = re.sub(r'\s+', ' ', declarations).strip()
        if not declarations.endswith(';'):
            declarations += ';'
            
        for selector in selectors_raw.split(','):
            selector = selector.strip()
            if selector:
                rules.append((selector, declarations))
    return rules

def apply_css_theme(soup, theme_path):
    """
    Applies the CSS rules defined in theme_path to elements in the soup.
    """
    if not os.path.exists(theme_path):
        print(f"⚠ Warning: Theme CSS file not found at: {theme_path}")
        return
        
    try:
        with open(theme_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
            
        css_rules = parse_css(css_content)
        
        for selector, new_style in css_rules:
            try:
                elements = soup.select(selector)
                for elem in elements:
                    existing_style = elem.get('style', '').strip()
                    if existing_style:
                        if not existing_style.endswith(';'):
                            existing_style += ';'
                        elem['style'] = f"{existing_style} {new_style}"
                    else:
                        elem['style'] = new_style
            except Exception as e:
                # Silently skip advanced/unsupported selectors in soup
                pass
    except Exception as e:
        print(f"⚠ Warning: Error applying CSS theme: {e}")

def apply_image_node_styles(img, params):
    """
    Applies style presets based on params (similar to previous layout system).
    """
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
    elif img_type in ('avatar', 'acatar'):
        inline_style = "width: 30px; height: 30px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); box-sizing: border-box; object-fit: cover;"
    elif img_type == 'icon' or params.get('icon') == 'card':
        inline_style = "width: 24px; height: 24px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px; object-fit: cover;"
    else:
        if 'w' in params:
            inline_style += f"width: {params['w']}; "
        if 'h' in params:
            inline_style += f"height: {params['h']}; "
            
    if 'pd' in params:
        inline_style += f"padding: {params['pd']}px; box-sizing: border-box; "

    if inline_style:
        existing_style = img.get('style', '').strip()
        if existing_style:
            if not existing_style.endswith(';'):
                existing_style += ';'
            img['style'] = f"{existing_style} {inline_style}"
        else:
            img['style'] = inline_style

def convert_to_wechat_html(md_content, theme_name='default'):
    """
    Converts Markdown content to HTML with inline CSS styles optimized for WeChat.
    """
    # 1. Preprocess Ruby Annotations: [文字]{注音} -> <ruby>文字<rt>注音</rt></ruby>
    md_content = re.sub(r'\[([^\]\n]+)\]\{([^\}\n]+)\}', r'<ruby>\1<rt>\2</rt></ruby>', md_content)



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

    # Resolve metadata cover image if it exists in frontmatter
    cover = metadata.get('image')
    if cover:
        cover_clean = cover.replace('img://', '').replace('[占位图:', '').replace('[占位图', '').replace(']', '').strip()
        cover_clean = cover_clean.lstrip(':').strip()
        base_name = os.path.basename(cover_clean)
        key_name = os.path.splitext(base_name)[0]
        real_path = image_mapping.get(cover_clean) or image_mapping.get(base_name) or image_mapping.get(key_name)
        if real_path:
            metadata['image'] = real_path

    # Render Markdown to raw HTML
    extensions = ['fenced_code', 'tables', 'nl2br', 'toc']
    html = markdown.markdown(md_content, extensions=extensions)

    # Convert <font color="..."> (from strategy rules) to <span style="color: ...">
    html = re.sub(r'<font\s+[^>]*?color=["\'](.*?)["\']\s*>(.*?)</font>', 
                  r'<span style="color: \1; font-weight: bold;">\2</span>', 
                  html, flags=re.IGNORECASE)

    # Parse with BeautifulSoup for structural modifications
    soup = BeautifulSoup(html, 'html.parser')

    # Apply CSS Theme stylesheets
    theme_path = os.path.abspath(os.path.join(script_dir, f'../references/themes/{theme_name}.css'))
    apply_css_theme(soup, theme_path)

    # Parse Custom Image Styles: image sibling `{type=...}` tags
    for img in soup.find_all('img'):
        sibling = img.next_sibling
        if sibling and isinstance(sibling, str):
            stripped_sibling = sibling.lstrip()
            if stripped_sibling.startswith('{'):
                match = re.match(r'^\{(.*?)\}', stripped_sibling)
                if match:
                    style_params = match.group(1)
                    params = {}
                    for p in style_params.split(';'):
                        if '=' in p:
                            k, v = p.split('=', 1)
                            params[k.strip()] = v.strip()
                            
                    apply_image_node_styles(img, params)
                    
                    # Remove curly braces styling text from the text node
                    # Keep any remaining trailing characters
                    rest = stripped_sibling[match.end():]
                    # Restore original leading space if any
                    orig_space = sibling[:len(sibling)-len(stripped_sibling)]
                    sibling.replace_with(orig_space + rest)

    # Clean Image width/height attributes (convert them to inline styles)
    for img in soup.find_all('img'):
        width = img.get('width')
        height = img.get('height')
        
        style_additions = []
        if width:
            img.attrs.pop('width', None)
            width_str = f"{width}px" if width.isdigit() else width
            style_additions.append(f"width: {width_str};")
            
        if height:
            img.attrs.pop('height', None)
            height_str = f"{height}px" if height.isdigit() else height
            style_additions.append(f"height: {height_str};")
            
        if style_additions:
            style_additions.append("object-fit: cover;")
            new_styles = " ".join(style_additions)
            existing_style = img.get('style', '').strip()
            if existing_style:
                if not existing_style.endswith(';'):
                    existing_style += ';'
                img['style'] = f"{existing_style} {new_styles}"
            else:
                img['style'] = new_styles

    # Resolve all image paths intelligently (supporting img://, bare name, or partial paths)
    for img in soup.find_all('img'):
        src = img.get('src', '').strip()
        if not src:
            continue
        if src.startswith(('http://', 'https://')):
            continue
            
        src_clean = src.replace('img://', '')
        base_name = os.path.basename(src_clean)
        key_name = os.path.splitext(base_name)[0]
        
        real_path = image_mapping.get(src_clean) or image_mapping.get(base_name) or image_mapping.get(key_name)
        if real_path:
            img['src'] = real_path
        else:
            if not src.startswith('assets/'):
                print(f"⚠ Warning: Image path not found in mapping dictionary for: {src}")

    # Convert External Hyperlinks to Footnotes
    external_links = []
    for a in soup.find_all('a'):
        href = a.get('href', '').strip()
        text = a.get_text().strip()
        
        if not href or href.startswith('#') or 'mp.weixin.qq.com' in href:
            continue
            
        # Deduplicate links to match the same index
        existing_hrefs = [x['href'] for x in external_links]
        if href in existing_hrefs:
            index = existing_hrefs.index(href) + 1
        else:
            external_links.append({'href': href, 'title': text or href})
            index = len(external_links)
            
        sup = soup.new_tag('sup')
        sup.string = f"[{index}]"
        a.append(sup)

    if external_links:
        # We append a divider
        hr = soup.new_tag('hr')
        soup.append(hr)
        
        h4 = soup.new_tag('h4')
        h4.string = "引用链接"
        soup.append(h4)
        
        for idx, link_info in enumerate(external_links, 1):
            p = soup.new_tag('p')
            p['style'] = "font-size: 14px; color: #888; line-height: 1.6; margin: 5px 0;"
            
            code = soup.new_tag('code')
            code['style'] = "font-size: 90%; opacity: 0.6; background-color: #f3f4f5; padding: 2px 4px; border-radius: 4px;"
            code.string = f"[{idx}]"
            
            p.append(code)
            p.append(f" {link_info['title']}: ")
            
            i_tag = soup.new_tag('i')
            i_tag['style'] = "word-break: break-all; color: #576b95;"
            i_tag.string = link_info['href']
            
            p.append(i_tag)
            soup.append(p)

    final_html = str(soup)

    # Wrap in a modern WeChat-optimized responsive container
    container_style = 'font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, \'Helvetica Neue\', Arial, \'PingFang SC\', \'Hiragino Sans GB\', \'Microsoft YaHei\', sans-serif; padding: 15px; max-width: 100%; box-sizing: border-box; font-size: 16px; color: #333; line-height: 1.8; word-wrap: break-word; text-align: justify;'
    wrapped_html = f'<div style="{container_style}">\n{final_html}\n</div>'

    return wrapped_html, metadata

def main():
    parser = argparse.ArgumentParser(description="Markdown to WeChat HTML Converter")
    parser.add_argument("input_file", help="Path to the input Markdown file")
    parser.add_argument("output_file", nargs="?", help="Path to the output HTML file (optional)")
    parser.add_argument("--theme", default="default", help="Theme stylesheet name to use (default: default)")

    args = parser.parse_args()

    input_path = args.input_file
    output_path = args.output_file if args.output_file else os.path.splitext(input_path)[0] + "_wechat.html"
    meta_path = os.path.splitext(output_path)[0] + ".json"

    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        wechat_html, metadata = convert_to_wechat_html(content, theme_name=args.theme)
        
        # Save HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(wechat_html)
            
        # Save Metadata
        if metadata:
            def json_serial(obj):
                import datetime
                if isinstance(obj, (datetime.date, datetime.datetime)):
                    return obj.isoformat()
                raise TypeError ("Type %s not serializable" % type(obj))

            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2, default=json_serial)
        
        print(f"✅ Successfully converted '{input_path}' to '{output_path}' using theme '{args.theme}'")
        if metadata:
            print(f"✅ Metadata saved to '{meta_path}'")
    except Exception as e:
        print(f"❌ Error during conversion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
