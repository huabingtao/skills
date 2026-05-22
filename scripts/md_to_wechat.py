#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
【已弃用】此脚本已迁移为更通用的引擎，且参数已被重构。
为了保持向后兼容，此脚本会自动转发请求至新脚本，并默认使用弹壳特攻队内容包。

新用法:
  python scripts/compile.py --pack packs/danke <input_md_file>
"""
import sys
import os
import subprocess

def main():
    print("⚠ Deprecation Warning: scripts/md_to_wechat.py is deprecated.")
    print("⚠ Please use: python scripts/compile.py --pack packs/danke <input_file>\n")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    compile_py = os.path.join(script_dir, "compile.py")
    
    # We forward all arguments, but insert --pack packs/danke by default
    new_args = [sys.executable, compile_py, "--pack", os.path.join(script_dir, "../packs/danke")]
    
    # Keep other args except theme if it matches old style
    forward_args = sys.argv[1:]
    
    # Check if --theme is present
    theme_idx = -1
    for i, arg in enumerate(forward_args):
        if arg == '--theme':
            theme_idx = i
            break
            
    # Forward all args to compile.py
    new_args.extend(forward_args)
    
    try:
        sys.exit(subprocess.call(new_args))
    except Exception as e:
        print(f"❌ Error forwarding execution: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
