#!/usr/bin/env python3
"""Export editable FHD_Navigator v0.2.4 sources; rebuild without altering originals."""
from pathlib import Path
from zipfile import ZipFile
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

import dat_codec

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "install/FHD_Navigator_0.2.4_AUTOPILOT_OPEN_TEST.zip"
PREFIX = "Mods/FHD_MODS/FHD_Navigator/"
EXPECTED = "32e6896708c0ecff507570b79d5bfc3f52b9955654c8501acb3fa91c54b6fa60"
DAT = ("CFG/CacheData.dat", "CFG/Main.dat", "CFG/Rus/Lang.dat")
GI = ("Data/Image/AutopilotA.gi", "Data/Image/AutopilotD.gi",
      "Data/Image/AutopilotN.gi", "Data/Image/RouteFrame.gi")
TXT = ("SOURCE/CacheData.txt", "SOURCE/Lang.txt", "SOURCE/Main.txt")
MODINFO = "ModuleInfo.txt"
ENTRIES = set(PREFIX + n for n in (*DAT, *GI, *TXT, MODINFO))

def digest(data):
    return hashlib.sha256(data).hexdigest()

def kit(*args):
    subprocess.run([sys.executable, "-m", "srhd_modkit", *map(str, args)],
                   check=True, stdout=subprocess.DEVNULL)

def verify_archive():
    if digest(ARCHIVE.read_bytes()) != EXPECTED:
        raise RuntimeError("Original install ZIP checksum changed")
    with ZipFile(ARCHIVE) as z:
        assert z.testzip() is None, "Corrupt original ZIP"
        assert set(z.namelist()) == ENTRIES, "Unexpected paths in original ZIP"
        assert len(z.namelist()) == 11, "Unexpected game file count"

def export():
    verify_archive()
    if (ROOT / "SOURCE_HASHES.json").exists():
        print("Export already exists; refusing to overwrite editable sources")
        return
    edits = {}
    originals = {}
    with ZipFile(ARCHIVE) as z, tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        gi_files = []
        for path in sorted(ENTRIES):
            data = z.read(path)
            originals[path] = {"size": len(data), "sha256": digest(data)}
            rel = path[len(PREFIX):]
            if rel in DAT:
                fmt = "cachedata" if rel == "CFG/CacheData.dat" else "blockpar"
                decoded = dat_codec.decode(data, fmt)
                assert dat_codec.encode(decoded) == data, "Unreversible DAT: " + rel
                target_rel = "SOURCE/DAT_JSON/" + rel + ".json"
                data = (json.dumps(decoded, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
            elif rel in GI:
                target_rel = "SOURCE/ORIGINAL_GI/" + Path(rel).name
                gi = tmp / Path(rel).name
                gi.write_bytes(data)
                gi_files.append(gi)
            elif rel in TXT:
                target_rel = "SOURCE/ORIGINAL_TEXT/" + Path(rel).name
            elif rel == MODINFO:
                target_rel = "SOURCE/ModuleInfo.utf8.txt"
                data = data.decode("cp1251").encode("utf-8")
                assert data.decode("utf-8").encode("cp1251") == z.read(path)
            else:
                raise RuntimeError("Unexpected ZIP entry " + rel)
            target = ROOT / target_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            edits[target_rel] = digest(data)
        png_dir = ROOT / "SOURCE/PNG"
        png_dir.mkdir(parents=True, exist_ok=True)
        kit("convert", "gi-png", *gi_files, "--output", png_dir)
        for gi in GI:
            name = Path(gi).stem + ".png"
            target = png_dir / name
            assert target.is_file(), "Missing PNG " + name
            assert target.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"), "Invalid PNG " + name
            edits["SOURCE/PNG/" + name] = digest(target.read_bytes())
        assert len(edits) == 3+4+3+1+4, "Unexpected number of editable/source files"
    (ROOT / "ORIGINAL_FILE_SHA256.json").write_text(
        json.dumps(originals, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "SOURCE_HASHES.json").write_text(
        json.dumps(edits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Exported", len(edits), "editable/original files, including 4 PNG images")

def build(verify=False):
    verify_archive()
    hashes = json.loads((ROOT / "SOURCE_HASHES.json").read_text(encoding="utf-8"))
    updates = {}
    changed = set()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for rel, original in hashes.items():
            data = (ROOT / rel).read_bytes()
            if digest(data) == original:
                continue
            if rel.startswith("SOURCE/DAT_JSON/") and rel.endswith(".dat.json"):
                game = rel.removeprefix("SOURCE/DAT_JSON/").removesuffix(".json")
                assert game in DAT
                decoded = json.loads(data.decode("utf-8"))
                assert decoded["format"] == ("cachedata" if game=="CFG/CacheData.dat" else "blockpar")
                updates[PREFIX + game] = dat_codec.encode(decoded)
                changed.add("DAT:" + game)
            elif rel.startswith("SOURCE/ORIGINAL_GI/"):
                gi = "Data/Image/" + Path(rel).name
                assert gi in GI
                updates[PREFIX + gi] = data
                changed.add("GI:" + gi)
            elif rel.startswith("SOURCE/PNG/"):
                gi = "Data/Image/" + Path(rel).with_suffix(".gi").name
                assert gi in GI
                if "GI:" + gi in changed:
                    raise RuntimeError("Original GI and PNG both edited: " + gi)
                folder = tmp / Path(gi).stem
                folder.mkdir()
                kit("convert", "png-gi", ROOT / rel, "--mode", "2", "--output", folder)
                updates[PREFIX + gi] = (folder / Path(gi).name).read_bytes()
                changed.add("PNG:" + gi)
            elif rel.startswith("SOURCE/ORIGINAL_TEXT/"):
                game = "SOURCE/" + Path(rel).name
                assert game in TXT
                updates[PREFIX + game] = data
                changed.add("TEXT:" + game)
            elif rel == "SOURCE/ModuleInfo.utf8.txt":
                updates[PREFIX + MODINFO] = data.decode("utf-8").encode("cp1251")
                changed.add("ModuleInfo")
            else:
                raise RuntimeError("Unrecognized edit: " + rel)
        out = ROOT / "DIST/FHD_Navigator_0.2.4_AUTOPILOT_OPEN_TEST.zip"
        out.parent.mkdir(exist_ok=True)
        if not updates:
            shutil.copyfile(ARCHIVE, out)
        else:
            with ZipFile(ARCHIVE) as source, ZipFile(out, "w") as result:
                for info in source.infolist():
                    result.writestr(info, updates.get(info.filename, source.read(info.filename)))
        with ZipFile(ARCHIVE) as source, ZipFile(out) as result:
            assert source.namelist() == result.namelist()
            assert result.testzip() is None
            assert all(result.read(name) == source.read(name)
                       for name in source.namelist() if name not in updates)
        if verify and not updates:
            assert digest(out.read_bytes()) == EXPECTED, "Clean build SHA256 mismatch"
        print("Built", out, "changed game files:", len(updates), "SHA256", digest(out.read_bytes()))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.export:
        export()
    else:
        build(verify=args.verify)
