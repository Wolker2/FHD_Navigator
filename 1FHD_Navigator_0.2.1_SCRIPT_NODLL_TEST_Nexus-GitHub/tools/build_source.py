#!/usr/bin/env python3
"""Export Navigator source and build a safe ZIP from modified editable resources."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

import dat_codec

ROOT = Path(__file__).resolve().parents[1]
NAME = "FHD_Navigator_0.2.1_SCRIPT_NODLL_TEST.zip"
INSTALL = ROOT / "install" / NAME
EXPECTED = "9647e6adf92c1c0eb1366e0ba4311fd851c667f76eb323e4b75783f4fe1ed34f"
PREFIX = "Mods/FHD_MODS/FHD_Navigator/"
DAT = {
    "CFG/CacheData.dat": "SOURCE/CFG/CacheData.dat.json",
    "CFG/Main.dat": "SOURCE/CFG/Main.dat.json",
    "CFG/Rus/Lang.dat": "SOURCE/CFG/Rus/Lang.dat.json",
}
ITEM = "Data/Image/RouteFrame.gi"
PNG = "SOURCE/Data/Image/RouteFrame.png"
META = "ModuleInfo.txt"
META_SOURCE = "SOURCE/ModuleInfo.txt"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_zip() -> None:
    assert INSTALL.is_file(), str(INSTALL)
    assert sha(INSTALL.read_bytes()) == EXPECTED, "Install archive differs from the uploaded one"
    with ZipFile(INSTALL) as z:
        assert z.testzip() is None, "Corrupted ZIP"
        files = [i.filename for i in z.infolist() if not i.is_dir()]
        assert len(files) == 5, files
        assert set(files) == {PREFIX + s for s in (*DAT, ITEM, META)}, files


def modkit(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "srhd_modkit", *map(str, args)],
                   check=True, stdout=subprocess.DEVNULL)


def export_source() -> None:
    check_zip()
    if (ROOT / "SOURCE_HASHES.json").exists():
        print("Source already published: will not overwrite existing edits")
        return
    orig_hashes = {}
    sources = {}
    with ZipFile(INSTALL) as z, tempfile.TemporaryDirectory() as t:
        temp = Path(t)
        for name in z.namelist():
            if name.endswith("/"):
                continue
            raw = z.read(name)
            orig_hashes[name] = {"size": len(raw), "sha256": sha(raw)}
            rel = name.removeprefix(PREFIX)
            if rel in DAT:
                fmt = "cachedata" if rel == "CFG/CacheData.dat" else "blockpar"
                parsed = dat_codec.decode(raw, fmt)
                assert dat_codec.encode(parsed) == raw, "DAT not reversible: " + rel
                dst = ROOT / DAT[rel]
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                sources[DAT[rel]] = sha(dst.read_bytes())
            elif rel == META:
                dst = ROOT / META_SOURCE
                dst.parent.mkdir(parents=True, exist_ok=True)
                decoded = raw.decode("cp1251")
                dst.write_bytes(decoded.encode("utf-8"))
                assert dst.read_bytes().decode("utf-8").encode("cp1251") == raw, "ModuleInfo CP1251 roundtrip failed"
                sources[META_SOURCE] = sha(dst.read_bytes())
            elif rel == ITEM:
                gi = temp / "RouteFrame.gi"
                gi.write_bytes(raw)
                destdir = ROOT / "SOURCE" / "Data" / "Image"
                destdir.mkdir(parents=True, exist_ok=True)
                modkit("convert", "gi-png", str(gi), "--output", str(destdir))
                png = ROOT / PNG
                assert png.is_file() and png.stat().st_size > 0, "PNG conversion failed"
                sources[PNG] = sha(png.read_bytes())
    (ROOT / "ORIGINAL_FILE_SHA256.json").write_text(
        json.dumps(orig_hashes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "SOURCE_HASHES.json").write_text(
        json.dumps(sources, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported", len(sources), "editable source files")


def build(verify: bool = False) -> None:
    check_zip()
    source_hashes = json.loads((ROOT / "SOURCE_HASHES.json").read_text(encoding="utf-8"))
    overlay = {}
    with tempfile.TemporaryDirectory() as t:
        temp = Path(t)
        for rel, expected in source_hashes.items():
            path = ROOT / rel
            raw = path.read_bytes()
            if sha(raw) == expected:
                continue
            if rel in DAT.values():
                datpath = next(k for k, v in DAT.items() if v == rel)
                project = json.loads(raw.decode("utf-8"))
                fmt = "cachedata" if datpath == "CFG/CacheData.dat" else "blockpar"
                assert project["format"] == fmt, "Unexpected DAT format"
                overlay[PREFIX + datpath] = dat_codec.encode(project)
            elif rel == META_SOURCE:
                raw.decode("utf-8")
                overlay[PREFIX + META] = raw.decode("utf-8").encode("cp1251")
            elif rel == PNG:
                destdir = temp / "converted"
                destdir.mkdir()
                modkit("convert", "png-gi", str(path), "--mode", "2", "--output", str(destdir))
                overlay[PREFIX + ITEM] = (destdir / "RouteFrame.gi").read_bytes()
            else:
                raise RuntimeError("Unknown editable source: " + rel)
        dist = ROOT / "DIST"
        dist.mkdir(exist_ok=True)
        output = dist / NAME
        if not overlay:
            shutil.copyfile(INSTALL, output)
        else:
            with ZipFile(INSTALL) as original, ZipFile(output, "w") as result:
                assert set(overlay) <= set(original.namelist())
                for entry in original.infolist():
                    result.writestr(entry, overlay.get(entry.filename, original.read(entry.filename)))
        with ZipFile(INSTALL) as original, ZipFile(output) as result:
            assert original.namelist() == result.namelist()
            for name in original.namelist():
                if name not in overlay:
                    assert original.read(name) == result.read(name), "Unexpected change: " + name
        if verify and not overlay:
            assert sha(output.read_bytes()) == EXPECTED, "Clean rebuild is not byte-identical"
        print("Built", output, "modified game files:", len(overlay),
              "sha256:", sha(output.read_bytes()))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.export:
        export_source()
    else:
        build(args.verify)
