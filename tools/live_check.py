"""Elevated end-to-end check against real NTFS metadata and journal changes."""
import json
import os
import sys
import tempfile
from pathlib import Path
from threading import Event
from time import perf_counter

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))
ARTIFACTS = PROJECT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
sys.stdout = (ARTIFACTS / "live-check.log").open("w", encoding="utf-8", buffering=1)
sys.stderr = sys.stdout

from smallthings.catalog import Catalog
from smallthings.ntfs import Volume, Windows
from smallthings.search import Options, search


def main():
    print("Starting elevated NTFS check", flush=True)
    volumes = list(Windows().volumes())
    print("Volumes:", volumes, flush=True)
    fixture = Path(tempfile.mkdtemp(prefix="smallthings-live-"))
    first = fixture / "sample-original.txt"
    first.write_text("metadata test", encoding="utf-8")
    second = fixture / "sample-hardlink.txt"
    os.link(first, second)
    root, identity = next(item for item in volumes if item[0][:2].casefold() == fixture.drive.casefold())
    start = perf_counter()
    volume = Volume(root, identity)
    print("Geometry:", volume.sector_size, volume.cluster_size, volume.record_size, volume.mft_length, flush=True)
    source = volume.enumerate(lambda *progress: print(progress, flush=True), Event())
    print("Indexed", source.count, "in", perf_counter() - start, flush=True)
    catalog = Catalog((source,))
    result = search(catalog, str(fixture), Options(), Event())
    assert {row.entry.name for row in result.rows} == {fixture.name, first.name, second.name}
    file_rows = [row for row in result.rows if not row.metadata.folder]
    assert file_rows[0].metadata.identity == file_rows[1].metadata.identity
    assert all(row.metadata.size == 13 for row in file_rows)
    renamed = fixture.with_name(fixture.name + "-renamed")
    fixture.rename(renamed)
    source = volume.changes(source)
    result = search(Catalog((source,)), str(renamed), Options(), Event())
    assert len(result.rows) == 3
    (renamed / second.name).unlink()
    source = volume.changes(source)
    result = search(Catalog((source,)), str(renamed), Options(), Event())
    assert len(result.rows) == 2
    (renamed / first.name).write_text("changed", encoding="utf-8")
    source = volume.changes(source)
    result = search(Catalog((source,)), str(renamed / first.name), Options(), Event())
    assert result.total == 1 and result.rows[0].metadata.size == 7
    (renamed / first.name).unlink()
    renamed.rmdir()
    source = volume.changes(source)
    assert search(Catalog((source,)), str(renamed), Options(), Event()).total == 0
    volume.close()
    report = {"entries": source.count, "seconds": perf_counter() - start,
              "checks": ["MFT enumeration", "search", "hardlinks", "directory rename", "link removal", "size update", "deletion"]}
    (ARTIFACTS / "live-check.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("PASS", report, flush=True)


if __name__ == "__main__":
    main()
