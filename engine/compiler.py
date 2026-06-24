# -*- coding: utf-8 -*-
"""
Core Markdown-to-WeChat HTML Compiler module.
Handles Markdown rendering, CSS theme inlining, image styling/preservation,
and metadata extraction.
"""

import os
import re
import yaml
import json
import markdown
from bs4 import BeautifulSoup

from .utils import scan_assets, ensure_placeholder_exists, load_image_mapping
from .highlight import load_highlight_rules, apply_highlight_rules


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
    if not theme_path or not os.path.exists(theme_path):
        print("⚠ Warning: Theme CSS file not found or not specified: " + str(theme_path))
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
                        elem['style'] = existing_style + " " + new_style
                    else:
                        elem['style'] = new_style
            except Exception:
                # Silently skip advanced/unsupported selectors in soup
                pass
    except Exception as e:
        print("⚠ Warning: Error applying CSS theme: " + str(e))


def apply_image_node_styles(img, params):
    """
    Applies style presets based on params.
    """
    inline_style = ""
    img_type = params.get('type')
    if img_type == 'card':
        inline_style = "display: block; margin: 20px auto; width: 90%; max-width: 100%; border-radius: 12px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); border: 1px solid #eee;"
    elif img_type == 'center':
        width_val = params.get('w', 'auto')
        if width_val.isdigit():
            width_val += 'px'
        inline_style = "display: block; margin: 20px auto; width: " + str(width_val) + "; max-width: 100%;"
        if 'h' in params:
            h_val = params['h']
            if h_val.isdigit():
                h_val += 'px'
            inline_style += " height: " + str(h_val) + ";"
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
        inline_style = "width: 30px; height: 30px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px; background: transparent; box-sizing: border-box; object-fit: cover;"
    elif img_type == 'icon' or params.get('icon') == 'card':
        inline_style = "width: 24px; height: 24px; vertical-align: middle; display: inline-block; margin: -2px 4px 0 4px; object-fit: cover;"
    else:
        if 'w' in params:
            inline_style += "width: " + str(params['w']) + "; "
        if 'h' in params:
            inline_style += "height: " + str(params['h']) + "; "
            
    if 'pd' in params:
        inline_style += "padding: " + str(params['pd']) + "px; box-sizing: border-box; "

    if inline_style:
        existing_style = img.get('style', '').strip()
        if existing_style:
            if not existing_style.endswith(';'):
                existing_style += ';'
            img['style'] = existing_style + " " + inline_style
        else:
            img['style'] = inline_style


def convert_to_wechat_html(md_content, project_config, input_dir=None):
    """
    Converts Markdown content to HTML with inline CSS styles optimized for WeChat.
    
    Args:
        md_content: Raw Markdown string.
        project_config: Dict of absolute paths for configuration.
        input_dir: Directory where the source markdown file is located.
        
    Returns:
        A tuple of (wrapped_html, metadata).
    """
    assets_dir = project_config.get("assets_dir")
    image_mapping_path = project_config.get("image_mapping_path")
    highlight_rules_path = project_config.get("highlight_rules_path")
    theme_path = project_config.get("theme_path")
    placeholder_dir = project_config.get("placeholder_dir") or (assets_dir and os.path.join(assets_dir, "img"))
    
    if placeholder_dir:
        ensure_placeholder_exists(placeholder_dir)

    assets_cache = scan_assets(assets_dir) if assets_dir else {}

    def check_file_exists(p, input_dir=None):
        if not p:
            return False
        if os.path.isabs(p) and os.path.exists(p):
            return True
        if assets_dir and os.path.exists(os.path.join(assets_dir, "..", p)):
            return True
        if input_dir and os.path.exists(os.path.join(input_dir, p)):
            return True
        return False

    def get_relative_to_project(p, input_dir=None):
        # Relativize against the root containing assets_dir
        project_root = os.path.dirname(assets_dir) if assets_dir else ""
        if not project_root:
            return p
        if os.path.isabs(p):
            try:
                rel = os.path.relpath(p, project_root).replace('\\', '/')
                if not rel.startswith('..'):
                    return rel
            except ValueError:
                pass
            return p
        if input_dir and os.path.exists(os.path.join(input_dir, p)):
            abs_p = os.path.abspath(os.path.join(input_dir, p))
            try:
                rel = os.path.relpath(abs_p, project_root).replace('\\', '/')
                if not rel.startswith('..'):
                    return rel
            except ValueError:
                pass
            return abs_p
        return p

    metadata = {}
    # Extract Frontmatter
    if md_content.startswith('---'):
        parts = re.split(r'^---', md_content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                md_content = parts[2]
            except Exception as e:
                print("⚠ Warning: Failed to parse frontmatter: " + str(e))

    # 0. Preprocess Lists to prevent Python-Markdown from merging distinct list types or blocks
    # Clean up empty list items (e.g. "* " or "1. " with nothing after them) to prevent rendering empty elements
    md_content = re.sub(r'^[ \t]*[*+-]\s*$\n?', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^[ \t]*\d+\.\s*$\n?', '', md_content, flags=re.MULTILINE)

    # Merge colon-wrapped break lines inside list items (e.g. * Item \n : description) to prevent unexpected line breaks
    md_content = re.sub(r'(^[ \t]*[*+-]\s+[^\n]+)\n[ \t]*[:：]\s*', r'\1：', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(^[ \t]*\d+\.\s+[^\n]+)\n[ \t]*[:：]\s*', r'\1：', md_content, flags=re.MULTILINE)

    # Remove GitHub style admonitions (e.g. [!IMPORTANT], [!TIP]) in blockquotes
    md_content = re.sub(r'^[ \t]*>\s*\[!(IMPORTANT|TIP|NOTE|WARNING|CAUTION)\][ \t]*\n?', '', md_content, flags=re.IGNORECASE | re.MULTILINE)

    # Cut off: Unordered -> Ordered list
    md_content = re.sub(
        r'(^[ \t]*[*+-]\s+[^\n]*)(?:\n[ \t]*)*(?=\n[ \t]*\d+\.\s+)',
        r'\1\n\n<!-- -->',
        md_content,
        flags=re.MULTILINE
    )
    # Cut off: Ordered -> Unordered list
    md_content = re.sub(
        r'(^[ \t]*\d+\.\s+[^\n]*)(?:\n[ \t]*)*(?=\n[ \t]*[*+-]\s+)',
        r'\1\n\n<!-- -->',
        md_content,
        flags=re.MULTILINE
    )
    # Cut off: Ordered -> Another new Ordered list starting with 1.
    md_content = re.sub(
        r'(^[ \t]*\d+\.\s+[^\n]*)(?:\n[ \t]*)*(?=\n[ \t]*1\.\s+)',
        r'\1\n\n<!-- -->',
        md_content,
        flags=re.MULTILINE
    )

    # 0.5 Preprocess image shorthand: {{名称}} or {{名称|type=card}} etc.
    # - {{名称}} -> ![名称](img://名称){type=icon}
    # - {{名称|type=card}} -> ![名称](img://名称){type=card}
    # Must run before Ruby annotation preprocessing (which uses single {})
    def _expand_shorthand(m):
        content = m.group(1)
        if '|' in content:
            name, params = content.split('|', 1)
            name, params = name.strip(), params.strip()
        else:
            name, params = content.strip(), 'type=icon'
        return '![' + name + '](img://' + name + '){' + params + '}'
    md_content = re.sub(r'\{\{([^}]+)\}\}', _expand_shorthand, md_content)

    # 1. Preprocess Ruby Annotations: [文字]{注音} -> <ruby>文字<rt>注音</rt></ruby>
    md_content = re.sub(r'\[([^\]\n]+)\]\{([^\}\n]+)\}', r'<ruby>\1<rt>\2</rt></ruby>', md_content)

    # 1.5 Preprocess link-style image references [name](img://path) to ![name](img://path)
    md_content = re.sub(r'(?<!\!)\[([^\]\n]+)\]\((img://[^\)\n]+)\)', r'![\1](\2)', md_content)

    # 2. Dynamic numerical highlights loaded from highlight rules
    if highlight_rules_path:
        rules = load_highlight_rules(highlight_rules_path)
        md_content = apply_highlight_rules(md_content, rules)

    # Load image mapping dictionary
    image_mapping = load_image_mapping(image_mapping_path) if image_mapping_path else {}

    # Resolve metadata cover image if it exists in frontmatter
    cover = metadata.get('image')
    if cover:
        cover_clean = cover.replace('img://', '').replace('[占位图:', '').replace('[占位图', '').replace(']', '').strip()
        cover_clean = cover_clean.lstrip(':').strip()
        base_name = os.path.basename(cover_clean)
        key_name = os.path.splitext(base_name)[0]
        
        resolved = None
        mapped_path = image_mapping.get(cover_clean) or image_mapping.get(base_name) or image_mapping.get(key_name)
        if mapped_path and check_file_exists(mapped_path, input_dir):
            resolved = get_relative_to_project(mapped_path, input_dir)
        elif check_file_exists(cover_clean, input_dir):
            resolved = get_relative_to_project(cover_clean, input_dir)
        else:
            fallback_match = assets_cache.get(key_name.lower()) or assets_cache.get(base_name.lower())
            if fallback_match:
                resolved = get_relative_to_project(fallback_match, input_dir)
            else:
                placeholder_path = "assets/img/占位图.png"
                if check_file_exists(placeholder_path):
                    resolved = placeholder_path
        
        if resolved:
            metadata['image'] = resolved

    # Render Markdown to raw HTML
    extensions = ['fenced_code', 'tables', 'nl2br', 'toc']
    html = markdown.markdown(md_content, extensions=extensions)

    # Convert <font color="..."> (from strategy rules) to <strong><font color="...">
    html = re.sub(r'<font\s+[^>]*?color=["\'](.*?)["\']\s*>(.*?)</font>', 
                  r'<strong><font color="\1">\2</font></strong>', 
                  html, flags=re.IGNORECASE)
    # Flatten duplicate strong tags
    html = re.sub(r'<strong>\s*<strong>(.*?)</strong>\s*</strong>', r'<strong>\1</strong>', html)

    # Parse with BeautifulSoup for structural modifications
    soup = BeautifulSoup(html, 'html.parser')

    # Remove nested strong tags (flattening) to prevent WeChat editor copy-paste line breaks
    for strong in list(soup.find_all('strong')):
        if strong.find_parent('strong'):
            strong.unwrap()

    # Apply CSS Theme stylesheets
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
            width_str = width + "px" if width.isdigit() else width
            style_additions.append("width: " + width_str + ";")
            
        if height:
            img.attrs.pop('height', None)
            height_str = height + "px" if height.isdigit() else height
            style_additions.append("height: " + height_str + ";")
            
        if style_additions:
            style_additions.append("object-fit: cover;")
            new_styles = " ".join(style_additions)
            existing_style = img.get('style', '').strip()
            if existing_style:
                if not existing_style.endswith(';'):
                    existing_style += ';'
                img['style'] = existing_style + " " + new_styles
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
        
        resolved = None
        mapped_path = image_mapping.get(src_clean) or image_mapping.get(base_name) or image_mapping.get(key_name)
        if mapped_path and check_file_exists(mapped_path, input_dir):
            resolved = get_relative_to_project(mapped_path, input_dir)
        elif check_file_exists(src_clean, input_dir):
            resolved = get_relative_to_project(src_clean, input_dir)
        else:
            fallback_match = assets_cache.get(key_name.lower()) or assets_cache.get(base_name.lower())
            if fallback_match:
                print("ℹ Auto-resolved missing image '" + str(src) + "' via folder scanning to: " + str(fallback_match))
                resolved = get_relative_to_project(fallback_match, input_dir)
            else:
                placeholder_path = "assets/img/占位图.png"
                if check_file_exists(placeholder_path):
                    print("⚠ Warning: Image '" + str(src) + "' not found on disk or mapping. Falling back to placeholder.")
                    resolved = placeholder_path
                else:
                    print("⚠ Warning: Image '" + str(src) + "' not found, and placeholder not found at '" + str(placeholder_path) + "'")
        
        if resolved:
            img['src'] = resolved

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
        sup.string = "[" + str(index) + "]"
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
            code.string = "[" + str(idx) + "]"
            
            p.append(code)
            p.append(" " + str(link_info['title']) + ": ")
            
            i_tag = soup.new_tag('i')
            i_tag['style'] = "word-break: break-all; color: #576b95;"
            i_tag.string = link_info['href']
            
            p.append(i_tag)
            soup.append(p)

    # Clean up empty text nodes inside <ul> and <ol> to prevent WeChat editor from generating extra list items
    for list_tag in soup.find_all(['ul', 'ol']):
        for child in list(list_tag.children):
            if not child.name and isinstance(child, str) and not child.strip():
                child.extract()

    # Apply nowrap inline style to star list items to prevent mobile wrapping
    for li in soup.find_all('li'):
        text = li.get_text().strip()
        if text and text[0].isdigit() and ('：' in text or ': ' in text):
            if any(img.get('alt') in ('红星', '黄星') for img in li.find_all('img')) or '星' in text:
                existing_style = li.get('style', '').strip()
                nowrap_rule = "white-space: nowrap !important;"
                if existing_style:
                    if not existing_style.endswith(';'):
                        existing_style += ';'
                    li['style'] = existing_style + " " + nowrap_rule
                else:
                    li['style'] = nowrap_rule

    # Prevent line breaks around the first colon in list items (e.g. "专属效果：...")
    for li in soup.find_all('li'):
        # Skip star list items which are already fully nowrap
        li_style = li.get('style', '')
        if 'white-space: nowrap' in li_style:
            continue
            
        target = li
        p_tag = li.find('p')
        if p_tag:
            target = p_tag
            
        bold_colon_fixed = False
        for strong in target.find_all('strong'):
            siblings_to_move = []
            curr = strong.next_sibling
            colon_found = False
            colon_part = None
            remaining_text = None
            
            while curr:
                if getattr(curr, 'name', None) in ('strong', 'br', 'p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'td', 'tr', 'table'):
                    break
                elif not getattr(curr, 'name', None) and isinstance(curr, str):
                    curr_text = str(curr)
                    m = re.match(r'^(\s*[:：]\s*)', curr_text)
                    if m:
                        colon_part = m.group(1)
                        remaining_text = curr_text[len(colon_part):]
                        colon_found = True
                        break
                    else:
                        break
                else:
                    siblings_to_move.append(curr)
                curr = curr.next_sibling
                
            if colon_found:
                for sib in siblings_to_move:
                    strong.append(sib)
                strong.append(soup.new_string(colon_part))
                if curr:
                    if remaining_text:
                        curr.replace_with(soup.new_string(remaining_text))
                    else:
                        curr.extract()
                
                existing_style = strong.get('style', '').strip()
                nowrap_rule = "white-space: nowrap !important;"
                if existing_style:
                    if not existing_style.endswith(';'):
                        existing_style += ';'
                    strong['style'] = existing_style + " " + nowrap_rule
                else:
                    strong['style'] = nowrap_rule
                bold_colon_fixed = True
        
        if bold_colon_fixed:
            continue
            
        text = target.get_text()
        colon_match = re.search(r'[:：]', text)
        if not colon_match:
            continue
            
        colon_idx = colon_match.start()
        
        children = list(target.contents)
        nodes_to_wrap = []
        remaining_nodes = []
        current_len = 0
        found = False
        
        for child in children:
            if found:
                remaining_nodes.append(child)
                continue
                
            child_text = child.get_text() if hasattr(child, 'get_text') else str(child)
            child_len = len(child_text)
            
            if current_len <= colon_idx < current_len + child_len:
                found = True
                rel_idx = colon_idx - current_len
                
                # Check if it's a text node (NavigableString/str or has no name)
                if not hasattr(child, 'name') or child.name is None:
                    left_text = child[:rel_idx + 1]
                    right_text = child[rel_idx + 1:]
                    
                    # Consume any trailing spaces to include them in nowrap
                    spaces = ""
                    while right_text and right_text[0] in (' ', '\t'):
                        spaces += right_text[0]
                        right_text = right_text[1:]
                        
                    left_node = soup.new_string(left_text + spaces)
                    nodes_to_wrap.append(left_node)
                    if right_text:
                        right_node = soup.new_string(right_text)
                        remaining_nodes.append(right_node)
                else:
                    nodes_to_wrap.append(child)
            else:
                nodes_to_wrap.append(child)
                current_len += child_len
                
        if nodes_to_wrap:
            target.clear()
            span_tag = soup.new_tag('span')
            span_tag['style'] = 'white-space: nowrap !important;'
            for node in nodes_to_wrap:
                span_tag.append(node)
            target.append(span_tag)
            for node in remaining_nodes:
                target.append(node)

    # Prevent line breaks around the first colon in table cells (e.g. "盾伤: ...")
    for td in soup.find_all('td'):
        td_style = td.get('style', '')
        if 'white-space: nowrap' in td_style:
            continue
            
        text = td.get_text()
        colon_match = re.search(r'[:：]', text)
        if not colon_match:
            continue
            
        colon_idx = colon_match.start()
        if colon_idx > 40:
            continue
            
        # First, try optimization: if td contains strong tags, pull subsequent inline elements and colons inside
        bold_colon_fixed = False
        for strong in td.find_all('strong'):
            siblings_to_move = []
            curr = strong.next_sibling
            colon_found = False
            colon_part = None
            remaining_text = None
            
            while curr:
                if getattr(curr, 'name', None) in ('strong', 'br', 'p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'td', 'tr', 'table'):
                    break
                elif not getattr(curr, 'name', None) and isinstance(curr, str):
                    curr_text = str(curr)
                    m = re.match(r'^(\s*[:：]\s*)', curr_text)
                    if m:
                        colon_part = m.group(1)
                        remaining_text = curr_text[len(colon_part):]
                        colon_found = True
                        break
                    else:
                        break
                else:
                    siblings_to_move.append(curr)
                curr = curr.next_sibling
                
            if colon_found:
                for sib in siblings_to_move:
                    strong.append(sib)
                strong.append(soup.new_string(colon_part))
                if curr:
                    if remaining_text:
                        curr.replace_with(soup.new_string(remaining_text))
                    else:
                        curr.extract()
                
                existing_style = strong.get('style', '').strip()
                nowrap_rule = "white-space: nowrap !important;"
                if existing_style:
                    if not existing_style.endswith(';'):
                        existing_style += ';'
                    strong['style'] = existing_style + " " + nowrap_rule
                else:
                    strong['style'] = nowrap_rule
                bold_colon_fixed = True
                
        if bold_colon_fixed:
            continue
            
        children = list(td.contents)
        nodes_to_wrap = []
        remaining_nodes = []
        current_len = 0
        found = False
        
        for child in children:
            if found:
                remaining_nodes.append(child)
                continue
                
            child_text = child.get_text() if hasattr(child, 'get_text') else str(child)
            child_len = len(child_text)
            
            if current_len <= colon_idx < current_len + child_len:
                found = True
                rel_idx = colon_idx - current_len
                
                # Check if it's a text node (NavigableString/str or has no name)
                if not hasattr(child, 'name') or child.name is None:
                    left_text = child[:rel_idx + 1]
                    right_text = child[rel_idx + 1:]
                    
                    # Consume any trailing spaces to include them in nowrap
                    spaces = ""
                    while right_text and right_text[0] in (' ', '\t'):
                        spaces += right_text[0]
                        right_text = right_text[1:]
                        
                    left_node = soup.new_string(left_text + spaces)
                    nodes_to_wrap.append(left_node)
                    if right_text:
                        right_node = soup.new_string(right_text)
                        remaining_nodes.append(right_node)
                else:
                    nodes_to_wrap.append(child)
            else:
                nodes_to_wrap.append(child)
                current_len += child_len
                
        if nodes_to_wrap:
            td.clear()
            
            # Prepend a non-breaking space (\u00a0) directly to the td cell (before the span)
            # to make sure the cell content starts with a text node rather than an element.
            zw_space = soup.new_string('\u00a0')
            td.append(zw_space)
            
            span_tag = soup.new_tag('span')
            span_tag['style'] = 'white-space: nowrap !important;'
            for node in nodes_to_wrap:
                span_tag.append(node)
            td.append(span_tag)
            for node in remaining_nodes:
                td.append(node)

    final_html = str(soup)

    # Wrap in a modern WeChat-optimized responsive container
    font_family = project_config.get("container_font", "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif")
    container_style = "font-family: " + str(font_family) + "; padding: 15px; max-width: 100%; box-sizing: border-box; font-size: 16px; color: #333; line-height: 1.8; word-wrap: break-word; text-align: justify;"
    wrapped_html = '<meta name="referrer" content="no-referrer">\n<div style="' + container_style + '">\n' + final_html + '\n</div>'

    return wrapped_html, metadata


def convert_to_optimized_markdown(md_content, project_config, input_dir=None):
    """
    Converts Markdown content to an optimized Markdown version, resolving all shorthand,
    image mappings, cover image, and highlight rules, while keeping the Markdown syntax.
    """
    assets_dir = project_config.get("assets_dir")
    image_mapping_path = project_config.get("image_mapping_path")
    highlight_rules_path = project_config.get("highlight_rules_path")
    placeholder_dir = project_config.get("placeholder_dir") or (assets_dir and os.path.join(assets_dir, "img"))
    
    if placeholder_dir:
        ensure_placeholder_exists(placeholder_dir)

    assets_cache = scan_assets(assets_dir) if assets_dir else {}
    image_mapping = load_image_mapping(image_mapping_path) if image_mapping_path else {}

    def check_file_exists(p, input_dir=None):
        if not p:
            return False
        if os.path.isabs(p) and os.path.exists(p):
            return True
        if assets_dir and os.path.exists(os.path.join(assets_dir, "..", p)):
            return True
        if input_dir and os.path.exists(os.path.join(input_dir, p)):
            return True
        return False

    def get_relative_to_project(p, input_dir=None):
        project_root = os.path.dirname(assets_dir) if assets_dir else ""
        if not project_root:
            return p
        if os.path.isabs(p):
            try:
                rel = os.path.relpath(p, project_root).replace('\\', '/')
                if not rel.startswith('..'):
                    return rel
            except ValueError:
                pass
            return p
        if input_dir and os.path.exists(os.path.join(input_dir, p)):
            abs_p = os.path.abspath(os.path.join(input_dir, p))
            try:
                rel = os.path.relpath(abs_p, project_root).replace('\\', '/')
                if not rel.startswith('..'):
                    return rel
            except ValueError:
                pass
            return abs_p
        return p

    def resolve_img_src(src):
        src = src.strip()
        if not src:
            return src
        if src.startswith(('http://', 'https://')):
            return src
            
        src_clean = src.replace('img://', '')
        base_name = os.path.basename(src_clean)
        key_name = os.path.splitext(base_name)[0]
        
        resolved = None
        mapped_path = image_mapping.get(src_clean) or image_mapping.get(base_name) or image_mapping.get(key_name)
        if mapped_path and check_file_exists(mapped_path, input_dir):
            resolved = get_relative_to_project(mapped_path, input_dir)
        elif check_file_exists(src_clean, input_dir):
            resolved = get_relative_to_project(src_clean, input_dir)
        else:
            fallback_match = assets_cache.get(key_name.lower()) or assets_cache.get(base_name.lower())
            if fallback_match:
                resolved = get_relative_to_project(fallback_match, input_dir)
            else:
                placeholder_path = "assets/img/占位图.png"
                if check_file_exists(placeholder_path):
                    resolved = placeholder_path
        return resolved or src

    metadata = {}
    # Extract Frontmatter
    if md_content.startswith('---'):
        parts = re.split(r'^---', md_content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                md_content = parts[2]
            except Exception as e:
                print("⚠ Warning: Failed to parse frontmatter: " + str(e))

    # Preprocess list items
    md_content = re.sub(r'^[ \t]*[*+-]\s*$\n?', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^[ \t]*\d+\.\s*$\n?', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(^[ \t]*[*+-]\s+[^\n]+)\n[ \t]*[:：]\s*', r'\1：', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(^[ \t]*\d+\.\s+[^\n]+)\n[ \t]*[:：]\s*', r'\1：', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^[ \t]*>\s*\[!(IMPORTANT|TIP|NOTE|WARNING|CAUTION)\][ \t]*\n?', '', md_content, flags=re.IGNORECASE | re.MULTILINE)

    # 1. Expand shorthands {{名称}} -> ![名称](img://名称){type=icon}
    def _expand_shorthand(m):
        content = m.group(1)
        if '|' in content:
            name, params = content.split('|', 1)
            name, params = name.strip(), params.strip()
        else:
            name, params = content.strip(), 'type=icon'
        return '![' + name + '](img://' + name + '){' + params + '}'
    md_content = re.sub(r'\{\{([^}]+)\}\}', _expand_shorthand, md_content)

    # 2. Ruby Annotations [文字]{注音} -> <ruby>文字<rt>注音</rt></ruby>
    md_content = re.sub(r'\[([^\]\n]+)\]\{([^\}\n]+)\}', r'<ruby>\1<rt>\2</rt></ruby>', md_content)

    # 3. Link-style image references [name](img://path) to ![name](img://path)
    md_content = re.sub(r'(?<!\!)\[([^\]\n]+)\]\((img://[^\)\n]+)\)', r'![\1](\2)', md_content)

    # 4. Apply highlight rules
    if highlight_rules_path:
        rules = load_highlight_rules(highlight_rules_path)
        md_content = apply_highlight_rules(md_content, rules)

    # 5. Resolve all image paths in markdown syntax: ![alt](src)
    def _replace_markdown_img(m):
        alt = m.group(1)
        src = m.group(2)
        resolved_src = resolve_img_src(src)
        return '![' + alt + '](' + resolved_src + ')'
    md_content = re.sub(r'!\[([^\]\n]*)\]\(([^)\n]+)\)', _replace_markdown_img, md_content)

    # 6. Resolve all image paths in HTML img tags if any: <img src="src" ...>
    def _replace_html_img(m):
        before = m.group(1)
        src = m.group(2)
        after = m.group(3)
        resolved_src = resolve_img_src(src)
        return '<img ' + before + 'src="' + resolved_src + '"' + after + '>'
    md_content = re.sub(r'<img\s+([^>]*?)src=["\'](img://[^"\']+|[^"\']+)["\']([^>]*?)>', _replace_html_img, md_content)

    # 7. Resolve Cover Image in Metadata
    cover = metadata.get('image')
    if cover:
        resolved_cover = resolve_img_src(cover)
        if resolved_cover:
            metadata['image'] = resolved_cover

    # Reconstruct the optimized Markdown file
    output_parts = []
    if metadata:
        output_parts.append('---')
        try:
            yaml_str = yaml.safe_dump(metadata, allow_unicode=True, default_flow_style=False, sort_keys=False)
            output_parts.append(yaml_str.strip())
        except Exception:
            yaml_str = yaml.dump(metadata, allow_unicode=True, default_flow_style=False)
            output_parts.append(yaml_str.strip())
        output_parts.append('---\n')
    
    output_parts.append(md_content.lstrip('\n'))
    return '\n'.join(output_parts)

