# -*- coding: utf-8 -*-
"""
Core Markdown-to-WeChat HTML Compiler module.
Handles Markdown rendering, CSS theme inlining, image styling/preservation,
and metadata extraction.
"""

import os
import re
import yaml
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


def extract_frontmatter(md_content):
    """
    Splits optional YAML frontmatter from a Markdown document.
    """
    metadata = {}
    if md_content.startswith('---'):
        parts = re.split(r'^---', md_content, maxsplit=2, flags=re.MULTILINE)
        if len(parts) >= 3:
            try:
                metadata = yaml.safe_load(parts[1]) or {}
                md_content = parts[2]
            except Exception as e:
                print("⚠ Warning: Failed to parse frontmatter: " + str(e))
    return md_content, metadata


def preprocess_markdown(md_content, project_config=None, enable_highlight=None):
    """
    Applies Markdown-level normalization before HTML rendering.

    Numerical highlighting is intentionally opt-in. The interactive workflow
    performs highlighting in Stage 1 and Stage 3 compiles without applying it
    again, which prevents nested <strong>/<font> markup.
    """
    project_config = project_config or {}
    if enable_highlight is None:
        enable_highlight = bool(project_config.get("enable_highlight", False))

    md_content = re.sub(r'^[ \t]*[*+-]\s*$\n?', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^[ \t]*\d+\.\s*$\n?', '', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(^[ \t]*[*+-]\s+[^\n]+)\n[ \t]*[:：]\s*', r'\1：', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'(^[ \t]*\d+\.\s+[^\n]+)\n[ \t]*[:：]\s*', r'\1：', md_content, flags=re.MULTILINE)
    md_content = re.sub(r'^[ \t]*>\s*\[!(IMPORTANT|TIP|NOTE|WARNING|CAUTION)\][ \t]*\n?', '', md_content, flags=re.IGNORECASE | re.MULTILINE)

    md_content = re.sub(
        r'(^[ \t]*[*+-]\s+[^\n]*)(?:\n[ \t]*)*(?=\n[ \t]*\d+\.\s+)',
        r'\1\n\n<!-- -->',
        md_content,
        flags=re.MULTILINE
    )
    md_content = re.sub(
        r'(^[ \t]*\d+\.\s+[^\n]*)(?:\n[ \t]*)*(?=\n[ \t]*[*+-]\s+)',
        r'\1\n\n<!-- -->',
        md_content,
        flags=re.MULTILINE
    )
    md_content = re.sub(
        r'(^[ \t]*\d+\.\s+[^\n]*)(?:\n[ \t]*)*(?=\n[ \t]*1\.\s+)',
        r'\1\n\n<!-- -->',
        md_content,
        flags=re.MULTILINE
    )

    def _expand_shorthand(m):
        content = m.group(1)
        if '|' in content:
            name, params = content.split('|', 1)
            name, params = name.strip(), params.strip()
        else:
            name, params = content.strip(), 'type=icon'
        return '![' + name + '](img://' + name + '){' + params + '}'

    md_content = re.sub(r'\{\{([^}]+)\}\}', _expand_shorthand, md_content)
    md_content = re.sub(r'\[([^\]\n]+)\]\{([a-zA-Z0-9\sāáǎàēéěèīíǐìōóǒòūúǔùüǘǚǜ]+)\}', r'<ruby>\1<rt>\2</rt></ruby>', md_content)
    md_content = re.sub(r'(?<!\!)\[([^\]\n]+)\]\((img://[^\)\n]+)\)', r'![\1](\2)', md_content)

    highlight_rules_path = project_config.get("highlight_rules_path")
    if enable_highlight and highlight_rules_path:
        rules = load_highlight_rules(highlight_rules_path)
        md_content = apply_highlight_rules(md_content, rules)

    return md_content


class ImageResolver:
    """
    Resolves img://, mapped, relative, and fallback image references.
    """

    def __init__(self, project_config, input_dir=None, verbose=False):
        self.project_config = project_config or {}
        self.input_dir = input_dir
        self.verbose = verbose
        self.assets_dir = self.project_config.get("assets_dir")
        self.image_mapping_path = self.project_config.get("image_mapping_path")
        self.placeholder_dir = self.project_config.get("placeholder_dir") or (
            self.assets_dir and os.path.join(self.assets_dir, "img")
        )

        if self.placeholder_dir:
            ensure_placeholder_exists(self.placeholder_dir)

        self.assets_cache = scan_assets(self.assets_dir) if self.assets_dir else {}
        self.image_mapping = load_image_mapping(self.image_mapping_path) if self.image_mapping_path else {}

    def check_file_exists(self, path):
        if not path:
            return False
        if os.path.isabs(path) and os.path.exists(path):
            return True
        if self.assets_dir and os.path.exists(os.path.join(self.assets_dir, "..", path)):
            return True
        if self.input_dir and os.path.exists(os.path.join(self.input_dir, path)):
            return True
        return False

    def relative_to_project(self, path):
        project_root = os.path.dirname(self.assets_dir) if self.assets_dir else ""
        if not project_root:
            return path
        if os.path.isabs(path):
            try:
                rel = os.path.relpath(path, project_root).replace('\\', '/')
                if not rel.startswith('..'):
                    return rel
            except ValueError:
                pass
            return path
        if self.input_dir and os.path.exists(os.path.join(self.input_dir, path)):
            abs_path = os.path.abspath(os.path.join(self.input_dir, path))
            try:
                rel = os.path.relpath(abs_path, project_root).replace('\\', '/')
                if not rel.startswith('..'):
                    return rel
            except ValueError:
                pass
            return abs_path
        return path

    def normalize_cover_src(self, src):
        return src.replace('img://', '').replace('[占位图:', '').replace('[占位图', '').replace(']', '').strip().lstrip(':').strip()

    def resolve_image_src(self, src, allow_placeholder=True):
        src = (src or '').strip()
        if not src or src.startswith(('http://', 'https://')):
            return src

        src_clean = src.replace('img://', '')
        base_name = os.path.basename(src_clean)
        key_name = os.path.splitext(base_name)[0]

        mapped_path = self.image_mapping.get(src_clean) or self.image_mapping.get(base_name) or self.image_mapping.get(key_name)
        if mapped_path and self.check_file_exists(mapped_path):
            return self.relative_to_project(mapped_path)

        if self.check_file_exists(src_clean):
            return self.relative_to_project(src_clean)

        fallback_match = self.assets_cache.get(key_name.lower()) or self.assets_cache.get(base_name.lower())
        if fallback_match:
            if self.verbose:
                print("ℹ Auto-resolved missing image '" + str(src) + "' via folder scanning to: " + str(fallback_match))
            return self.relative_to_project(fallback_match)

        placeholder_path = "assets/img/占位图.png"
        if allow_placeholder and self.check_file_exists(placeholder_path):
            if self.verbose:
                print("⚠ Warning: Image '" + str(src) + "' not found on disk or mapping. Falling back to placeholder.")
            return placeholder_path

        if self.verbose:
            print("⚠ Warning: Image '" + str(src) + "' not found, and placeholder not found at '" + str(placeholder_path) + "'")
        return src

    def resolve_metadata_cover(self, metadata):
        cover = metadata.get('image')
        if not cover:
            return metadata
        resolved = self.resolve_image_src(self.normalize_cover_src(cover), allow_placeholder=True)
        if resolved:
            metadata['image'] = resolved
        return metadata


def resolve_image_src(src, resolver_context):
    """
    Public helper for callers/tests that need the shared resolver behavior.
    """
    if isinstance(resolver_context, ImageResolver):
        return resolver_context.resolve_image_src(src)
    return ImageResolver(resolver_context).resolve_image_src(src)


def parse_image_params(params_str):
    params = {}
    for p in params_str.split(';'):
        if '=' in p:
            k, v = p.split('=', 1)
            params[k.strip()] = v.strip()
    return params


def process_soup_images(soup, resolver):
    """
    Applies custom image styles, cleans width/height attrs, and resolves sources.
    """
    for img in soup.find_all('img'):
        sibling = img.next_sibling
        if sibling and isinstance(sibling, str):
            stripped_sibling = sibling.lstrip()
            if stripped_sibling.startswith('{'):
                match = re.match(r'^\{(.*?)\}', stripped_sibling)
                if match:
                    apply_image_node_styles(img, parse_image_params(match.group(1)))
                    rest = stripped_sibling[match.end():]
                    orig_space = sibling[:len(sibling) - len(stripped_sibling)]
                    sibling.replace_with(orig_space + rest)

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

        src = img.get('src', '').strip()
        if src and not src.startswith(('http://', 'https://')):
            img['src'] = resolver.resolve_image_src(src)


def append_external_link_footnotes(soup):
    """
    Converts non-WeChat external links to WeChat-safe footnote references.
    """
    external_links = []
    for a in soup.find_all('a'):
        href = a.get('href', '').strip()
        text = a.get_text().strip()
        if not href or href.startswith('#') or 'mp.weixin.qq.com' in href:
            continue

        existing_hrefs = [x['href'] for x in external_links]
        if href in existing_hrefs:
            index = existing_hrefs.index(href) + 1
        else:
            external_links.append({'href': href, 'title': text or href})
            index = len(external_links)

        sup = soup.new_tag('sup')
        sup.string = "[" + str(index) + "]"
        a.append(sup)

    if not external_links:
        return

    soup.append(soup.new_tag('hr'))
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


def cleanup_list_text_nodes(soup):
    for list_tag in soup.find_all(['ul', 'ol']):
        for child in list(list_tag.children):
            if not child.name and isinstance(child, str) and not child.strip():
                child.extract()


def _move_colon_into_strong(soup, target):
    for strong in target.find_all('strong'):
        siblings_to_move = []
        curr = strong.next_sibling
        colon_part = None
        remaining_text = None

        while curr:
            if getattr(curr, 'name', None) in ('strong', 'br', 'p', 'div', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'td', 'tr', 'table'):
                break
            if not getattr(curr, 'name', None) and isinstance(curr, str):
                curr_text = str(curr)
                match = re.match(r'^(\s*[:：]\s*)', curr_text)
                if match:
                    colon_part = match.group(1)
                    remaining_text = curr_text[len(colon_part):]
                break
            siblings_to_move.append(curr)
            curr = curr.next_sibling

        if colon_part is None:
            continue

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
        strong['style'] = (existing_style + (" " if existing_style.endswith(';') else "; ") + nowrap_rule) if existing_style else nowrap_rule
        return True
    return False


def _wrap_prefix_to_colon(soup, target, prepend_nbsp=False):
    text = target.get_text()
    colon_match = re.search(r'[:：]', text)
    if not colon_match:
        return False

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
        if current_len <= colon_match.start() < current_len + child_len:
            found = True
            rel_idx = colon_match.start() - current_len
            if not hasattr(child, 'name') or child.name is None:
                left_text = child[:rel_idx + 1]
                right_text = child[rel_idx + 1:]
                spaces = ""
                while right_text and right_text[0] in (' ', '\t'):
                    spaces += right_text[0]
                    right_text = right_text[1:]
                nodes_to_wrap.append(soup.new_string(left_text + spaces))
                if right_text:
                    remaining_nodes.append(soup.new_string(right_text))
            else:
                nodes_to_wrap.append(child)
        else:
            nodes_to_wrap.append(child)
            current_len += child_len

    if not nodes_to_wrap:
        return False

    target.clear()
    if prepend_nbsp:
        target.append(soup.new_string('\u00a0'))
    span_tag = soup.new_tag('span')
    span_tag['style'] = 'white-space: nowrap !important;'
    for node in nodes_to_wrap:
        span_tag.append(node)
    target.append(span_tag)
    for node in remaining_nodes:
        target.append(node)
    return True


def apply_list_nowrap(soup):
    for li in soup.find_all('li'):
        text = li.get_text().strip()
        if text and text[0].isdigit() and ('：' in text or ': ' in text):
            if any(img.get('alt') in ('红星', '黄星') for img in li.find_all('img')) or '星' in text:
                existing_style = li.get('style', '').strip()
                nowrap_rule = "white-space: nowrap !important;"
                li['style'] = (existing_style + (" " if existing_style.endswith(';') else "; ") + nowrap_rule) if existing_style else nowrap_rule
                continue

        target = li.find('p') or li
        if _move_colon_into_strong(soup, target):
            continue
        _wrap_prefix_to_colon(soup, target)


def apply_table_nowrap(soup):
    for td in soup.find_all('td'):
        if 'white-space: nowrap' in td.get('style', ''):
            continue
        text = td.get_text()
        colon_match = re.search(r'[:：]', text)
        if not colon_match or colon_match.start() > 40:
            continue
        if _move_colon_into_strong(soup, td):
            continue
        _wrap_prefix_to_colon(soup, td, prepend_nbsp=True)


def translate_params_to_pandoc(params_str):
    params = parse_image_params(params_str)
    img_type = params.get('type')
    width_val = None
    height_val = None

    if img_type in ('icon', 'center') or params.get('icon') == 'card':
        if img_type == 'icon' or params.get('icon') == 'card':
            width_val, height_val = '24px', '24px'
        else:
            w = params.get('w')
            if w:
                width_val = w + 'px' if w.isdigit() else w
            h = params.get('h')
            if h:
                height_val = h + 'px' if h.isdigit() else h
    elif img_type in ('avatar', 'acatar'):
        # Keep the legacy "acatar" typo as a compatibility alias for avatar.
        width_val, height_val = '30px', '30px'
    elif img_type in ('float-left', 'float-right'):
        width_val, height_val = '80px', '80px'
    elif img_type == 'card':
        width_val = '90%'
    elif img_type == 'banner':
        width_val = '100%'
    elif img_type == 'grid2':
        width_val = '48%'
    elif img_type == 'grid3':
        width_val = '31.3%'
    elif img_type == 'grid4':
        width_val = '23%'
    else:
        w = params.get('w')
        if w:
            width_val = w + 'px' if w.isdigit() else w
        h = params.get('h')
        if h:
            height_val = h + 'px' if h.isdigit() else h

    out_parts = []
    if width_val:
        out_parts.append(f'width={width_val}')
    if height_val:
        out_parts.append(f'height={height_val}')
    return ' '.join(out_parts)


def wrap_wechat_html(final_html, project_config):
    font_family = project_config.get("container_font", "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif")
    container_style = "font-family: " + str(font_family) + "; padding: 15px; max-width: 100%; box-sizing: border-box; font-size: 16px; color: #333; line-height: 1.8; word-wrap: break-word; text-align: justify;"
    return '<meta name="referrer" content="no-referrer">\n<div style="' + container_style + '">\n' + final_html + '\n</div>'


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
    theme_path = project_config.get("theme_path")
    resolver = ImageResolver(project_config, input_dir=input_dir, verbose=True)
    md_content, metadata = extract_frontmatter(md_content)
    md_content = preprocess_markdown(md_content, project_config)
    metadata = resolver.resolve_metadata_cover(metadata)

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

    process_soup_images(soup, resolver)
    append_external_link_footnotes(soup)
    cleanup_list_text_nodes(soup)

    # Process list items: star list item nowrap and colon wrapping prevention in a single pass
    for li in soup.find_all('li'):
        # 1. Apply nowrap inline style to star list items to prevent mobile wrapping
        text = li.get_text().strip()
        is_star_list_item = False
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
                is_star_list_item = True

        # 2. Prevent line breaks around the first colon in list items
        if is_star_list_item:
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
    resolver = ImageResolver(project_config, input_dir=input_dir, verbose=False)
    md_content, metadata = extract_frontmatter(md_content)
    md_content = preprocess_markdown(md_content, project_config)

    # 5. Resolve all image paths in markdown syntax: ![alt](src)
    def _replace_markdown_img(m):
        alt = m.group(1)
        src = m.group(2)
        resolved_src = resolver.resolve_image_src(src)
        return '![' + alt + '](' + resolved_src + ')'
    md_content = re.sub(r'!\[([^\]\n]*)\]\(([^)\n]+)\)', _replace_markdown_img, md_content)

    # 5.5 Translate styling params (like `{type=icon}`) to Pandoc attributes
    def _translate_image_attrs(match):
        alt = match.group(1)
        src = match.group(2)
        attrs = match.group(3)
        translated = translate_params_to_pandoc(attrs)
        if translated:
            return f'![{alt}]({src}){{{translated}}}'
        return f'![{alt}]({src})'
    md_content = re.sub(r'!\[([^\]\n]*)\]\(([^)\n]+)\)\{(.*?)\}', _translate_image_attrs, md_content)

    # 6. Resolve all image paths in HTML img tags if any: <img src="src" ...>
    def _replace_html_img(m):
        before = m.group(1)
        src = m.group(2)
        after = m.group(3)
        resolved_src = resolver.resolve_image_src(src)
        return '<img ' + before + 'src="' + resolved_src + '"' + after + '>'
    md_content = re.sub(r'<img\s+([^>]*?)src=["\'](img://[^"\']+|[^"\']+)["\']([^>]*?)>', _replace_html_img, md_content)

    # 7. Resolve Cover Image in Metadata
    metadata = resolver.resolve_metadata_cover(metadata)

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
