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


def apply_image_node_styles(img, params, soup=None):
    """
    Applies style presets based on params. Handles caption wrapper generation if caption present.
    """
    inline_style = ""
    img_type = params.get('type')
    width_val = params.get('w') or params.get('width')
    height_val = params.get('h') or params.get('height')
    caption_text = params.get('caption')

    if img_type == 'card':
        inline_style = "display: block; margin: 20px auto; width: 90%; max-width: 100%; border-radius: 12px; box-shadow: 0 10px 20px rgba(0,0,0,0.1); border: 1px solid #eee;"
    elif img_type == 'center':
        w_str = width_val or 'auto'
        if w_str.isdigit():
            w_str += 'px'
        inline_style = "display: block; margin: 20px auto; width: " + str(w_str) + "; max-width: 100%;"
        if height_val:
            h_str = height_val
            if h_str.isdigit():
                h_str += 'px'
            inline_style += " height: " + str(h_str) + ";"
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
        if width_val:
            w_str = width_val + "px" if width_val.isdigit() else width_val
            inline_style += "width: " + str(w_str) + "; display: block; margin: 10px auto; max-width: 100%; "
        if height_val:
            h_str = height_val + "px" if height_val.isdigit() else height_val
            inline_style += "height: " + str(h_str) + "; "

    if 'pd' in params:
        inline_style += "padding: " + str(params['pd']) + "px; box-sizing: border-box; "

    if caption_text and soup:
        wrapper = soup.new_tag('section')
        wrapper['class'] = 'img-caption-wrapper'
        
        if img_type in ('grid2', 'grid3', 'grid4'):
            wrapper['style'] = inline_style + " vertical-align: top; text-align: center;"
            img['style'] = "display: block; width: 100%; height: auto; max-width: 100%; border-radius: inherit;"
        elif img_type in ('banner', 'card', 'center'):
            wrapper['style'] = inline_style + " text-align: center;"
            img['style'] = "display: block; width: 100%; height: auto; max-width: 100%; margin: 0 auto;"
        else:
            wrapper['style'] = (inline_style if inline_style else "display: block; margin: 10px auto; max-width: 100%;") + " text-align: center;"
            img['style'] = "display: block; width: 100%; height: auto; max-width: 100%; margin: 0 auto;"

        caption_node = soup.new_tag('section')
        caption_node['class'] = 'img-caption'
        caption_node['style'] = "display: block; width: 100%; margin-top: 6px; font-size: 12px; color: #888888; text-align: center; line-height: 1.4; word-break: break-all; box-sizing: border-box;"
        caption_node.string = caption_text

        img.replace_with(wrapper)
        wrapper.append(img)
        wrapper.append(caption_node)
    else:
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

    # 强制将无序列表（以 * 或 + 开头的项）的前缀统一规范化为减号 -
    md_content = re.sub(r'^([ \t]*)[*+](\s+)', r'\1-\2', md_content, flags=re.MULTILINE)

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
        content = m.group(1).strip()
        if content in ("往期推荐", "往期精彩推荐", "扫码获取更多精彩"):
            return m.group(0)
        params_str = m.group(2) if m.group(2) else ''
        if '|' in content:
            name, params = content.split('|', 1)
            name, params = name.strip(), params.strip()
        else:
            name, params = content, 'type=icon'
        if params_str:
            params = params_str.strip()
        return '![' + name + '](img://' + name + '){' + params + '}'

    md_content = re.sub(r'\{\{([^}]+)\}\}(?:\{([^}]+)\})?', _expand_shorthand, md_content)
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

    def get_abs_path(self, path):
        if not path:
            return ""
        if os.path.isabs(path) and os.path.exists(path):
            return os.path.abspath(path)
        if self.assets_dir:
            cand = os.path.abspath(os.path.join(self.assets_dir, "..", path))
            if os.path.exists(cand):
                return cand
        if self.input_dir:
            cand = os.path.abspath(os.path.join(self.input_dir, path))
            if os.path.exists(cand):
                return cand
    def relative_to_project(self, path):
        if not path:
            return path
        
        abs_path = None
        if os.path.isabs(path) and os.path.exists(path):
            abs_path = path
        elif self.assets_dir:
            cand = os.path.abspath(os.path.join(self.assets_dir, "..", path))
            if os.path.exists(cand):
                abs_path = cand
        if not abs_path and self.input_dir:
            cand = os.path.abspath(os.path.join(self.input_dir, path))
            if os.path.exists(cand):
                abs_path = cand
        
        if not abs_path:
            abs_path = os.path.abspath(path)

        if self.input_dir and os.path.exists(abs_path):
            try:
                rel = os.path.relpath(abs_path, os.path.abspath(self.input_dir)).replace('\\', '/')
                return rel
            except ValueError:
                pass

        project_root = os.path.dirname(self.assets_dir) if self.assets_dir else ""
        if not project_root:
            return abs_path
        try:
            rel = os.path.relpath(abs_path, project_root).replace('\\', '/')
            return rel
        except ValueError:
            return abs_path

    def get_absolute_path(self, path):
        if not path:
            return None
        if os.path.isabs(path) and os.path.exists(path):
            return path
        if self.assets_dir:
            cand = os.path.abspath(os.path.join(self.assets_dir, "..", path))
            if os.path.exists(cand):
                return cand
        if self.input_dir:
            cand = os.path.abspath(os.path.join(self.input_dir, path))
            if os.path.exists(cand):
                return cand
        return None

    def relative_to_input_or_project(self, path):
        abs_p = self.get_abs_path(path)
        if self.input_dir and abs_p and os.path.isabs(abs_p) and os.path.exists(abs_p):
            try:
                rel = os.path.relpath(abs_p, self.input_dir).replace('\\', '/')
                return rel
            except ValueError:
                pass
        return self.relative_to_project(path)

    def normalize_cover_src(self, src):
        return src.replace('img://', '').replace('[占位图:', '').replace('[占位图', '').replace(']', '').strip().lstrip(':').strip()

    def resolve_image_src(self, src, allow_placeholder=True, embed_base64=False):
        src = (src or '').strip()
        if not src or src.startswith(('http://', 'https://', 'data:')):
            return src

        src_clean = src.replace('img://', '')
        base_name = os.path.basename(src_clean)
        key_name = os.path.splitext(base_name)[0]

        mapped_path = self.image_mapping.get(src_clean) or self.image_mapping.get(base_name) or self.image_mapping.get(key_name)
        file_path = None
        if mapped_path and self.check_file_exists(mapped_path):
            return self.relative_to_input_or_project(mapped_path)

        if self.check_file_exists(src_clean):
            return self.relative_to_input_or_project(src_clean)

        fallback_match = self.assets_cache.get(key_name.lower()) or self.assets_cache.get(base_name.lower())
        if not fallback_match:
            # Try prefix-stripped variants as a fallback
            def strip_prefix(s):
                parts = s.split('-', 1)
                if len(parts) >= 2 and parts[0].isdigit():
                    return parts[1]
                return s
            stripped_key = strip_prefix(key_name)
            stripped_base = strip_prefix(base_name)
            fallback_match = self.assets_cache.get(stripped_key.lower()) or self.assets_cache.get(stripped_base.lower())

        if fallback_match:
            if self.verbose:
                print("ℹ Auto-resolved missing image '" + str(src) + "' via folder scanning to: " + str(fallback_match))
            return self.relative_to_input_or_project(fallback_match)

        if self.verbose:
            print("⚠ Warning: Image '" + str(src) + "' not found on disk or mapping. Leaving it blank.")
        return ""

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
    if not params_str:
        return params
    
    # 提取 key=value 或 key:value 组合（支持双引号、单引号或无引号值，支持中文字符与空格）
    pattern = r'([\w\-]+)\s*[:=]\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s;,}]+))'
    matches = re.findall(pattern, params_str)
    for match in matches:
        key = match[0].strip()
        val = match[1] if match[1] != '' else (match[2] if match[2] != '' else match[3])
        params[key] = val.strip()

    # 如果无 k-v，支持形如 {50%} 或 {300px} 的直接宽度写法
    if not params and params_str.strip():
        val = params_str.strip().strip('{}')
        if val.endswith('%') or val.endswith('px') or val.isdigit():
            params['w'] = val
            params['width'] = val

    # 别名无缝互映射: width <-> w, height <-> h
    if 'width' in params and 'w' not in params:
        params['w'] = params['width']
    if 'w' in params and 'width' not in params:
        params['width'] = params['w']
    if 'height' in params and 'h' not in params:
        params['h'] = params['height']
    if 'h' in params and 'height' not in params:
        params['height'] = params['h']

    return params


def process_soup_images(soup, resolver):
    """
    Applies custom image styles, cleans width/height attrs, and resolves sources.
    """
    for img in list(soup.find_all('img')):
        sibling = img.next_sibling
        if sibling and isinstance(sibling, str):
            stripped_sibling = sibling.lstrip()
            if stripped_sibling.startswith('{'):
                match = re.match(r'^\{(.*?)\}', stripped_sibling)
                if match:
                    apply_image_node_styles(img, parse_image_params(match.group(1)), soup=soup)
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
            img['src'] = resolver.resolve_image_src(src, embed_base64=True)

    # Clean up <br/> tags between consecutive inline-block/grid images or wrappers
    for br in list(soup.find_all('br')):
        prev_node = br.find_previous_sibling()
        next_node = br.find_next_sibling()
        if prev_node and next_node:
            prev_style = prev_node.get('style', '')
            next_style = next_node.get('style', '')
            if 'inline-block' in prev_style and 'inline-block' in next_style:
                br.extract()


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


def apply_nowrap_to_tag(tag, display_inline=True):
    """
    Applies white-space: nowrap !important and display: inline !important to tag without duplicating style rules.
    """
    existing_style = tag.get('style', '').strip()
    rules = []
    if existing_style:
        for rule in existing_style.split(';'):
            rule = rule.strip()
            if not rule:
                continue
            lower_rule = rule.lower()
            if lower_rule.startswith('display:') or lower_rule.startswith('white-space:'):
                continue
            rules.append(rule)
            
    if display_inline:
        rules.append('display: inline !important')
    rules.append('white-space: nowrap !important')
    tag['style'] = '; '.join(rules)


def fix_strong_colon_wrapping(soup, target):
    """
    Finds strong tags in target and pulls any trailing colons (and intervening inline elements)
    inside the strong tag, and marks the strong tag with nowrap to prevent break.
    """
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
            # Mark the strong tag with nowrap inline style to protect it from line break
            apply_nowrap_to_tag(strong, display_inline=True)


def cleanup_list_text_nodes(soup):
    for list_tag in soup.find_all(['ul', 'ol']):
        for child in list(list_tag.children):
            if not child.name and isinstance(child, str) and not child.strip():
                child.extract()


def is_emoji_char(char):
    if not char:
        return False
    cp = ord(char)
    if (0x1F300 <= cp <= 0x1FAFF) or (0x2600 <= cp <= 0x27BF) or (0x1F600 <= cp <= 0x1F64F) or (0x1F680 <= cp <= 0x1F6FF):
        return True
    if char in ('👉', '📢', '🏆', '🍻', '🏰', '🔹', '📌', '▪️', '▫️', '⭐', '🌟', '💥', '🔥', '🚀', '📜', '📈'):
        return True
    return False


def convert_lists_to_emoji_paragraphs(soup):
    """
    Converts <ul> / <ol> lists into clean Emoji Paragraphs (<p>) to completely bypass
    WeChat mobile client auto-injecting native list bullet points (•) or empty <li> items.
    """
    for list_tag in list(soup.find_all(['ul', 'ol'])):
        paragraphs = []
        for li in list_tag.find_all('li'):
            text = li.get_text(strip=True)
            if not text and not li.find_all('img'):
                continue
            
            p = soup.new_tag('p')
            p['style'] = 'margin: 15px 0; line-height: 1.8; color: #333333; font-size: 16px; text-align: justify; word-break: break-word;'
            
            has_emoji = False
            if text and is_emoji_char(text[0]):
                has_emoji = True
            
            if not has_emoji:
                emoji_str = "🔹 "
                p.append(soup.new_string(emoji_str))
                
            for child in list(li.contents):
                p.append(child)
            paragraphs.append(p)
            
        if paragraphs:
            for p in reversed(paragraphs):
                list_tag.insert_after(p)
            list_tag.decompose()


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

        apply_nowrap_to_tag(strong, display_inline=True)
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
            w = params.get('w') or params.get('width')
            if w:
                width_val = w + 'px' if w.isdigit() else w
            h = params.get('h') or params.get('height')
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
        w = params.get('w') or params.get('width')
        if w:
            width_val = w + 'px' if w.isdigit() else w
        h = params.get('h') or params.get('height')
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


def build_recommendations_section(soup, project_config, input_dir, metadata):
    """
    Builds the beautiful '往期精彩推荐' (Past Recommendations) section tag.
    """
    recs = []

    # 1. Check if explicit recommendations exist in metadata
    explicit_recs = metadata.get('recommendations')
    if explicit_recs:
        for item in explicit_recs:
            if isinstance(item, dict):
                recs.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", "#")
                })
            elif isinstance(item, str):
                recs.append({
                    "title": item,
                    "url": "#"
                })

    # 2. If no explicit recommendations, automatically scan siblings
    if not recs and input_dir:
        content_root = None
        curr_dir = os.path.abspath(input_dir)
        for _ in range(5):
            if os.path.basename(curr_dir) == 'my-articles-md':
                content_root = curr_dir
                break
            if os.path.basename(curr_dir) == 'danke':
                t_path = os.path.join(curr_dir, 'my-articles-md')
                if os.path.exists(t_path):
                    content_root = t_path
                    break
            # check sibling/child directories
            t_path = os.path.join(curr_dir, 'content', 'danke', 'my-articles-md')
            if os.path.exists(t_path):
                content_root = t_path
                break
            parent = os.path.dirname(curr_dir)
            if parent == curr_dir:
                break
            curr_dir = parent

        if not content_root:
            content_root = os.path.dirname(os.path.abspath(input_dir))

        all_articles = []
        if os.path.exists(content_root):
            for root, dirs, files in os.walk(content_root):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('venv', 'node_modules', 'scripts')]
                for file in files:
                    if file.endswith('.md') and not file.endswith(('_wechat.html', '_preview.html')):
                        full_path = os.path.join(root, file)
                        try:
                            with open(full_path, 'r', encoding='utf-8') as f:
                                file_content = f.read()
                            _, file_meta = extract_frontmatter(file_content)
                            if file_meta and file_meta.get('title'):
                                title = file_meta.get('title')
                                if title == metadata.get('title'):
                                    continue
                                all_articles.append({
                                    "title": title,
                                    "path": full_path,
                                    "date": file_meta.get('date', '')
                                })
                        except Exception:
                            pass

        # Sort: sibling files in the same directory/subcategory first
        sibling_recs = []
        other_recs = []
        for art in all_articles:
            art_dir = os.path.dirname(art["path"])
            if os.path.dirname(art_dir) == os.path.dirname(os.path.abspath(input_dir)) or art_dir == os.path.abspath(input_dir):
                sibling_recs.append(art)
            else:
                other_recs.append(art)

        # Sort by date (descending)
        sibling_recs.sort(key=lambda x: str(x.get('date') or ''), reverse=True)
        other_recs.sort(key=lambda x: str(x.get('date') or ''), reverse=True)

        selected = sibling_recs[:3]
        if len(selected) < 3:
            selected += other_recs[:3 - len(selected)]

        # Extract image if available
        for art in selected[:3]:
            art_meta = {}
            try:
                with open(art["path"], 'r', encoding='utf-8') as f:
                    _, art_meta = extract_frontmatter(f.read())
            except Exception:
                pass
            recs.append({
                "title": art["title"],
                "url": "#",
                "image": art_meta.get("image") or art_meta.get("cover") or art_meta.get("bg_image")
            })

    if not recs:
        return None

    # Default premium low-saturation dark gradients
    default_gradients = [
        "linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #334155 100%)",  # Slate Dark
        "linear-gradient(135deg, #18181b 0%, #27272a 50%, #3f3f46 100%)",  # Zinc Dark
        "linear-gradient(135deg, #064e3b 0%, #047857 50%, #059669 100%)",  # Emerald Dark
        "linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #4338ca 100%)",  # Indigo Dark
        "linear-gradient(135deg, #450a0a 0%, #7f1d1d 50%, #991b1b 100%)",  # Rose Dark
        "linear-gradient(135deg, #132a13 0%, #31572c 50%, #4f772d 100%)"   # Olive Dark
    ]

    rec_div = soup.new_tag('section')
    rec_div['style'] = (
        "margin: 30px auto 20px auto; "
        "max-width: 100%; "
        "box-sizing: border-box; "
        "display: block;"
    )

    # Section Title / Header
    title_div = soup.new_tag('section')
    title_div['style'] = (
        "font-weight: bold; "
        "color: #1e293b; "
        "font-size: 16px; "
        "margin-bottom: 16px; "
        "letter-spacing: 0.5px; "
        "text-align: center; "
        "display: block;"
    )

    t1 = soup.new_tag('span')
    t1.string = "下方查看"
    title_div.append(t1)

    t2 = soup.new_tag('span')
    t2['style'] = "color: #2563eb; margin: 0 2px;"
    t2.string = "往期精彩推荐"
    title_div.append(t2)

    t3 = soup.new_tag('span')
    t3['style'] = "color: #2563eb;"
    t3.string = "🔻"
    title_div.append(t3)

    rec_div.append(title_div)

    # Render Method 2 HTML/CSS Cards (Pure Color/Gradient Flex-end Layout without Arrow Icon)
    for idx, item in enumerate(recs):
        a_tag = soup.new_tag('a')
        a_tag['href'] = item.get('url', '#') or '#'
        a_tag['target'] = "_blank"
        a_tag['style'] = "text-decoration: none; display: block; margin-bottom: 12px; -webkit-tap-highlight-color: transparent;"

        gradient = default_gradients[idx % len(default_gradients)]

        card_sec = soup.new_tag('section')
        card_sec['style'] = (
            "position: relative; "
            "width: 100%; "
            "height: 95px; "
            "border-radius: 12px; "
            "overflow: hidden; "
            "box-sizing: border-box; "
            "display: flex; "
            "flex-direction: column; "
            "justify-content: flex-end; "
            "align-items: flex-start; "
            "padding: 14px 16px; "
            "margin-bottom: 14px; "
            f"background: {gradient};"
        )

        title_sec = soup.new_tag('section')
        title_sec['style'] = (
            "width: 100%; "
            "color: #ffffff; "
            "font-size: 15px; "
            "font-weight: bold; "
            "line-height: 1.4; "
            "letter-spacing: 0.3px; "
            "text-align: left; "
            "overflow: hidden; "
            "text-overflow: ellipsis; "
            "white-space: nowrap; "
            "display: block;"
        )
        title_sec.string = item.get('title', '')
        card_sec.append(title_sec)

        a_tag.append(card_sec)
        rec_div.append(a_tag)

    return rec_div



def replace_recommendations_placeholder(soup, project_config, input_dir, metadata):
    """
    Finds placeholder texts like {{往期推荐}} or {{往期精彩推荐}} and removes them cleanly.
    """
    for text_node in list(soup.find_all(string=True)):
        if "{{往期推荐}}" in text_node or "{{往期精彩推荐}}" in text_node:
            parent = text_node.parent
            text_node.extract()
            if parent and not parent.get_text().strip() and parent.name in ('p', 'div', 'section'):
                parent.extract()


def build_qrcode_section(soup, project_config, input_dir, metadata):
    """
    Builds a beautiful centered QR code section tag.
    """
    import urllib.parse
    
    qrcode_image = metadata.get('qrcode_image')
    qrcode_url = metadata.get('qrcode_url')
    
    if qrcode_image:
        if qrcode_image.startswith('img://'):
            from .compiler import ImageResolver
            resolver = ImageResolver(project_config, input_dir=input_dir)
            qr_src = resolver.resolve_image_src(qrcode_image)
        else:
            qr_src = qrcode_image
    elif qrcode_url:
        # Generate custom QR code using online API
        encoded_url = urllib.parse.quote(qrcode_url, safe='')
        api_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={encoded_url}"
        
        # Download locally to avoid WeChat remote download issues
        try:
            import urllib.request
            import tempfile
            out_dir = input_dir or tempfile.gettempdir()
            temp_path = os.path.join(out_dir, "_qrcode_temp.png")
            req = urllib.request.Request(
                api_url, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                with open(temp_path, 'wb') as f:
                    f.write(response.read())
            qr_src = temp_path if not input_dir else "_qrcode_temp.png"
        except Exception as e:
            print(f"Warning: Failed to generate and download QR code: {e}")
            qr_src = api_url
    else:
        # Default fallback: Use the static QR code of the Official Account
        from .compiler import ImageResolver
        resolver = ImageResolver(project_config, input_dir=input_dir)
        qr_src = resolver.resolve_image_src("img://二维码")

    # Get author name for display (default to 弹壳呱呱)
    author_name = metadata.get('author') or project_config.get('author') or "弹壳呱呱"
    
    # 2. Build the HTML block using <section> tags for WeChat Official Account compatibility
    qr_div = soup.new_tag('section')
    qr_div['style'] = (
        "margin: 30px auto 20px auto; "
        "max-width: 360px; "
        "padding: 24px 20px; "
        "background-color: #f8fafc; "
        "border: 1px dashed #e2e8f0; "
        "border-radius: 12px; "
        "text-align: center; "
        "box-sizing: border-box; "
        "display: block;"
    )

    # Title
    title_div = soup.new_tag('section')
    title_div['style'] = (
        "font-weight: bold; "
        "color: #1e293b; "
        "font-size: 16px; "
        "margin-bottom: 4px; "
        "letter-spacing: 0.5px; "
        "text-align: center; "
        "display: block;"
    )
    title_div.string = "扫码获取更多精彩"
    qr_div.append(title_div)

    # Subtitle
    subtitle_div = soup.new_tag('section')
    subtitle_div['style'] = (
        "font-size: 13px; "
        "color: #64748b; "
        "margin-bottom: 20px; "
        "text-align: center; "
        "display: block;"
    )
    subtitle_div.string = "最新活动 · 特工 · 配件 · 宠物攻略"
    qr_div.append(subtitle_div)

    # QR Code Wrap
    wrap_div = soup.new_tag('section')
    wrap_div['style'] = (
        "display: block; "
        "width: 198px; "
        "margin: 0 auto 16px auto; "
        "padding: 8px; "
        "background: #ffffff; "
        "border: 1px solid #e2e8f0; "
        "border-radius: 8px; "
        "box-shadow: 0 4px 12px rgba(0,0,0,0.05); "
        "box-sizing: border-box; "
        "text-align: center;"
    )
    
    img_tag = soup.new_tag('img')
    img_tag['src'] = qr_src
    img_tag['style'] = "width: 180px; height: 180px; display: block; margin: 0 auto; object-fit: contain;"
    img_tag['alt'] = "二维码"
    wrap_div.append(img_tag)
    qr_div.append(wrap_div)

    # Footer
    footer_div = soup.new_tag('section')
    footer_div['style'] = (
        "font-size: 12px; "
        "color: #94a3b8; "
        "letter-spacing: 1px; "
        "text-align: center; "
        "display: block;"
    )
    footer_div.string = f"长按识别二维码关注「{author_name}」"
    qr_div.append(footer_div)

    return qr_div


def replace_qrcode_placeholder(soup, project_config, input_dir, metadata):
    """
    Finds placeholder {{扫码获取更多精彩}} and replaces it in-place with the QR code section.
    """
    target_node = None
    placeholder_text = None
    for text_node in soup.find_all(string=True):
        if "{{扫码获取更多精彩}}" in text_node:
            target_node = text_node
            placeholder_text = "{{扫码获取更多精彩}}"
            break

    if not target_node:
        return

    qr_div = build_qrcode_section(soup, project_config, input_dir, metadata)
    if not qr_div:
        # Cleanup placeholder
        parent = target_node.parent
        target_node.extract()
        if parent and not parent.get_text().strip() and parent.name in ('p', 'div'):
            parent.extract()
        return

    parent = target_node.parent
    if parent and parent.name in ('p', 'div') and len(parent.get_text().strip()) == len(placeholder_text):
        parent.replace_with(qr_div)
    else:
        target_node.replace_with(qr_div)


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
    convert_lists_to_emoji_paragraphs(soup)

    # Prevent line breaks around colons in regular paragraphs
    for p in soup.find_all('p'):
        fix_strong_colon_wrapping(soup, p)

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
        fix_strong_colon_wrapping(soup, td)
        
        # Check if already handled via strong tags
        if td.find('strong'):
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

    # Replace recommendations placeholder in-place with the section if present
    replace_recommendations_placeholder(soup, project_config, input_dir, metadata)

    # Replace QR code placeholder in-place with the section if present
    replace_qrcode_placeholder(soup, project_config, input_dir, metadata)

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
