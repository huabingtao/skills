#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用微信草稿箱发布器 CLI

用法:
  python scripts/publish.py -c output_wechat.html
  python scripts/publish.py -c output_wechat.html --new
  python scripts/publish.py --test-config
"""
import argparse
import os
import sys

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from engine.publisher import main as publisher_main


def main():
    """
    Thin wrapper that delegates to engine.publisher.main().
    This ensures the engine/ module is properly importable.
    """
    # We need to re-invoke the publisher's argparse from here.
    # Since engine/publisher.py has its own main() with full argparse,
    # we just call it directly.
    publisher_main()


if __name__ == "__main__":
    main()
