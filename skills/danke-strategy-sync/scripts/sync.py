#!/usr/bin/env python3
"""检查或创建原创 danke 技能链接；不复制源码、不删除既有目录。"""
import argparse
import os
from pathlib import Path
import subprocess
import sys


def sync_links(source_root, target_root, apply=False):
    source_root = Path(source_root).expanduser().resolve()
    target_root = Path(target_root).expanduser().absolute()
    sources = sorted(p for p in source_root.glob("danke-*") if (p / "SKILL.md").is_file())
    if not sources:
        raise ValueError(f"源目录没有 danke 技能: {source_root}")
    if source_root == target_root.resolve():
        raise ValueError("源目录与目标目录相同，无需链接")
    actions = []
    conflicts = []
    for source in sources:
        target = target_root / source.name
        if target.is_symlink() and target.resolve() == source.resolve():
            actions.append(("ok", source, target))
        elif target.exists() or target.is_symlink():
            conflicts.append(str(target))
        else:
            actions.append(("missing", source, target))
    # 全部预检后才创建链接，避免发现冲突时前面的项目已被修改。
    if conflicts:
        raise FileExistsError("目标已有目录或不同链接，保留原状: " + ", ".join(conflicts))
    for state, source, target in actions:
        if state == "missing" and apply:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=True)
            state = "linked"
        print(f"{state}: {target} -> {source}")
    return not any(state == "missing" for state, _, _ in actions) or apply


def main():
    source = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=source, help="包含各技能目录的 skills/ 路径")
    parser.add_argument("--target-root", type=Path, default=source.parent.parent / ".agents/skills")
    parser.add_argument("--apply", action="store_true", help="创建缺失链接；默认只检查")
    parser.add_argument("--test", action="store_true", help="对唯一源码中的排版技能运行离线测试")
    args = parser.parse_args()
    complete = sync_links(args.source_root, args.target_root, args.apply)
    if args.test:
        strategy = args.source_root.resolve() / "danke-strategy-skill"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(strategy) + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "test", "-p", "test_*.py"],
                       cwd=strategy, env=env, check=True)
    if not complete:
        print("存在缺失链接；使用 --apply 创建。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
