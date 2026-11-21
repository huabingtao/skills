#!/usr/bin/env python3
"""Extract Spine (.skel + .atlas + .png) assets by ResourceManager query from Survivor.io XAPK."""

import argparse
import io
import os
import struct
import zipfile
import UnityPy


def extract_textasset_bytes(raw_obj: bytes) -> bytes:
    nlen = struct.unpack_from("<I", raw_obj, 0)[0]
    off = (4 + nlen + 3) & ~3
    slen = struct.unpack_from("<I", raw_obj, off)[0]
    return raw_obj[off + 4 : off + 4 + slen]


def main():
    parser = argparse.ArgumentParser(description="Extract Spine assets from Danke XAPK")
    parser.add_argument(
        "--xapk",
        default="/home/guagua/workspace/project/danke/danke-resource/current_danke.xapk",
        help="Path to XAPK file",
    )
    parser.add_argument("--query", required=True, help="Substring to match in ResourceManager paths")
    parser.add_argument("--out-dir", required=True, help="Output base directory")
    args = parser.parse_args()

    q = args.query.lower()
    with zipfile.ZipFile(args.xapk) as z:
        with z.open("com.dxx.firenow.apk") as f:
            fire_bytes = f.read()
        with zipfile.ZipFile(io.BytesIO(fire_bytes)) as fire_zip:
            ggm = fire_zip.read("assets/bin/Data/globalgamemanagers")
            env = UnityPy.load(ggm)
            exts = env.file.externals
            matches = {}
            for obj in env.objects:
                if obj.type.name == "ResourceManager":
                    rm = obj.read()
                    for k, v in rm.m_Container:
                        if q in k.lower():
                            label = os.path.basename(k.rstrip("/"))
                            root_hash = os.path.basename(exts[v.m_FileID - 1].path)
                            matches[k] = (label, root_hash)

        if not matches:
            print(f"No ResourceManager matches for query={args.query!r}")
            return

        print(f"Found {len(matches)} matches:")
        for k, (label, h) in matches.items():
            print(f"  {k} -> {h}")

        with z.open("UnityDataAssetPack.apk") as f:
            data_bytes = f.read()

    cache_dir = "/tmp/danke_xapk_data_cache"
    os.makedirs(cache_dir, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(data_bytes)) as data_zip:
        all_names = set(data_zip.namelist())
        for res_path, (label, root_hash) in matches.items():
            out_dir = os.path.join(args.out_dir, label)
            os.makedirs(out_dir, exist_ok=True)
            visited, queue = set(), [root_hash]
            while queue:
                h = queue.pop(0)
                if h in visited or "/" in h or "unity" in h.lower():
                    continue
                visited.add(h)
                entry = f"assets/bin/Data/{h}"
                if entry not in all_names:
                    continue
                dst = os.path.join(cache_dir, h)
                if not os.path.exists(dst):
                    with open(dst, "wb") as out:
                        out.write(data_zip.read(entry))
                res_entry = f"assets/bin/Data/{h}.resource"
                if res_entry in all_names:
                    res_dst = os.path.join(cache_dir, f"{h}.resource")
                    if not os.path.exists(res_dst):
                        with open(res_dst, "wb") as out:
                            out.write(data_zip.read(res_entry))
                e = UnityPy.load(dst)
                for ext in e.file.externals:
                    ep = os.path.basename(ext.path)
                    if ep not in visited:
                        queue.append(ep)

            for h in visited:
                p = os.path.join(cache_dir, h)
                if not os.path.exists(p):
                    continue
                e = UnityPy.load(p)
                for obj in e.objects:
                    if obj.type.name == "Texture2D":
                        d = obj.read()
                        name = d.m_Name or h
                        if "font" in name.lower() or "default" in name.lower():
                            continue
                        d.image.save(os.path.join(out_dir, f"{name}.png"))
                    elif obj.type.name == "TextAsset":
                        d = obj.read()
                        name = d.m_Name or h
                        if name.endswith(".skel") or name.endswith(".atlas"):
                            raw = extract_textasset_bytes(obj.get_raw_data())
                            with open(os.path.join(out_dir, name), "wb") as tf:
                                tf.write(raw)
            print(f"Extracted {label} -> {out_dir}")


if __name__ == "__main__":
    main()
