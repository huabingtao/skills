#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【已弃用】此脚本已迁移为更通用的引擎。
为了保持向后兼容，此脚本会自动转发请求至新脚本。

新用法:
  python scripts/publish.py -c <input_html_file>
"""
import sys
import os
import subprocess

def main():
    print("⚠ Deprecation Warning: scripts/wechat_publisher.py is deprecated.")
    print("⚠ Please use: python scripts/publish.py -c <input_html_file>\n")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    publish_py = os.path.join(script_dir, "publish.py")
    
    new_args = [sys.executable, publish_py]
    new_args.extend(sys.argv[1:])
    
    try:
        sys.exit(subprocess.call(new_args))
    except Exception as e:
        print(f"❌ Error forwarding execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
