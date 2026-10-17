"""Validate recommended short image names against the unchanged local mapping."""

import json
from collections import defaultdict
from pathlib import Path


def read_short_mapping(path):
    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"short 映射存在重复名称：{key}")
            result[key] = value
        return result

    data = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    if not isinstance(data, dict):
        raise ValueError("short 映射必须是 short → 现有完整名称的 JSON 对象")
    return data


def inspect_short_mapping(short_mapping, local_mapping, pack_root, require_coverage=False):
    root = Path(pack_root)
    groups = defaultdict(list)
    for name, relative in local_mapping.items():
        groups[str((root / relative).resolve())].append(name)

    errors, entries, seen_assets, seen_names = [], [], {}, {}
    legacy_names = defaultdict(set)
    for asset, names in groups.items():
        for name in names:
            legacy_names[name.strip().casefold()].add(asset)

    for short, full in short_mapping.items():
        if not isinstance(short, str) or not short or short != short.strip() or any(c in short for c in '{}|\r\n'):
            errors.append(f"非法 short 名称：{short!r}")
            continue
        if not isinstance(full, str) or full not in local_mapping:
            errors.append(f"{short} 的目标不是现有完整名称：{full!r}")
            continue
        asset = str((root / local_mapping[full]).resolve())
        if not Path(asset).is_file():
            errors.append(f"{short} 指向失效素材：{local_mapping[full]}")
            continue
        if short.casefold() in seen_names:
            errors.append(f"short 名称大小写冲突：{short} / {seen_names[short.casefold()]}")
        seen_names[short.casefold()] = short
        if legacy_names.get(short.casefold(), set()) - {asset}:
            errors.append(f"{short} 与指向其他素材的旧名称冲突")
        if asset in seen_assets:
            errors.append(f"同一素材有多个推荐 short：{seen_assets[asset]} / {short}")
        seen_assets[asset] = short
        entries.append({"short": short, "full_name": full,
                        "path": local_mapping[full], "absolute_path": asset})

    missing = [{"path": local_mapping[names[0]], "names": sorted(names)}
               for asset, names in sorted(groups.items()) if not Path(asset).is_file()]
    unmapped = [{"path": local_mapping[names[0]], "names": sorted(names)}
                for asset, names in sorted(groups.items())
                if Path(asset).is_file() and asset not in seen_assets]
    if require_coverage and unmapped:
        errors.append(f"{len(unmapped)} 个可用素材尚无推荐 short")
    return {"legacy_name_count": len(local_mapping), "asset_count": len(groups),
            "short_count": len(short_mapping), "available_asset_count": len(groups) - len(missing),
            "errors": errors, "missing_legacy_assets": missing,
            "unmapped_assets": unmapped, "entries": entries, "passed": not errors}


def load_short_mapping(path, local_mapping, pack_root):
    mapping = read_short_mapping(path)
    report = inspect_short_mapping(mapping, local_mapping, pack_root)
    if report["errors"]:
        raise ValueError("short 图片映射校验失败：" + "；".join(report["errors"]))
    return mapping
