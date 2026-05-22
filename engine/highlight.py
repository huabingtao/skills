# -*- coding: utf-8 -*-
"""
Highlight rules engine for semantic color-coding of Markdown content.

This module replaces the hardcoded HSL color patterns that were previously
embedded directly in the convert_to_wechat_html function. Highlight rules
are now loaded from an external JSON file, making them configurable
per-project without code changes.

Expected JSON format for highlight_rules.json:
{
    "colors": {
        "green": "#52C41A",
        "blue": "#1890FF",
        "red": "#FF4D4F"
    },
    "green": [
        {"pattern": "(?<!\\d)(3|5|10)(?=\\s*(?:!\\[黄红星\\]))", "description": "Star counts"}
    ],
    "blue": [
        {"pattern": "(?<=减伤效果)(\\+20%)", "description": "Survival/reductions"}
    ],
    "red": [
        {"pattern": "(?<=伤害)(\\+(?:5|10|50|13)%)", "description": "Damage boosts"}
    ]
}
"""

import json
import re
import os


def load_highlight_rules(rules_path):
    """
    Loads highlight rules from a JSON file.

    Args:
        rules_path: Absolute path to a highlight_rules.json file.

    Returns:
        A dict with keys "colors" (color name -> hex), and color-name keys
        (e.g. "green", "blue", "red") each containing a list of rule dicts
        with "pattern" and optional "description" fields.
        Returns an empty dict if the file doesn't exist or fails to parse.
    """
    if not rules_path or not os.path.exists(rules_path):
        return {}

    try:
        with open(rules_path, 'r', encoding='utf-8') as f:
            rules = json.load(f)
        return rules
    except Exception as e:
        print(f"⚠ Warning: Failed to load highlight rules from {rules_path}: {e}")
        return {}


def apply_highlight_rules(md_content, rules):
    """
    Applies semantic color-coding highlight rules to Markdown content.

    Iterates through each color group in the rules dict and wraps regex
    matches with <span style="color: {hex}; font-weight: bold;">.

    Args:
        md_content: The raw Markdown string to process.
        rules: A dict loaded by load_highlight_rules(). Must contain a
               "colors" key mapping color names to hex values, and
               additional keys for each color name containing lists of
               {"pattern": "..."} dicts.

    Returns:
        The Markdown string with highlight spans applied.
        If rules is empty or None, returns md_content unchanged.
    """
    if not rules:
        return md_content

    colors = rules.get('colors', {})
    if not colors:
        return md_content

    for color_name, hex_value in colors.items():
        patterns = rules.get(color_name, [])
        for rule in patterns:
            pattern = rule.get('pattern')
            if not pattern:
                continue
            try:
                md_content = re.sub(
                    pattern,
                    rf'<span style="color: {hex_value}; font-weight: bold;">\1</span>',
                    md_content
                )
            except re.error as e:
                desc = rule.get('description', pattern)
                print(f"⚠ Warning: Invalid highlight regex for '{desc}': {e}")

    return md_content
