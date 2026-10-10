"""Fetch all official Libya test tiles from pinned BRIGHT ZIPs using HTTP ranges.

Run with ``uv run python scripts/prepare_bright.py``. Large files are ignored
research artifacts; this downloader never falls back to full archive downloads.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import struct
import time
from datetime import datetime, timezone
import zipfile
import zlib

import httpx
import numpy as np
import rasterio

DATA_REVISION = "46f202d9520cb0844a6ca4679d016d0d27a6d58c"
CODE_REVISION = "59269142f3a3550320513e362692732f46486985"
BASE_URL = f"https://huggingface.co/datasets/Kullervo/BRIGHT/resolve/{DATA_REVISION}"
SPLIT_URL = (
    f"https://raw.githubusercontent.com/ChenHongruixuan/BRIGHT/{CODE_REVISION}/"
    "bda_benchmark/dataset/splitname/standard_ML/test_set.txt"
)
ARCHIVES = {
    "pre-event.zip": (9_901_512_150, "pre-event", "pre_disaster"),
    "post-event.zip": (3_291_986_721, "post-event", "post_disaster"),
    "target.zip": (47_638_868, "target", "building_damage"),
}
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_INDEX_READ = 2 * 1024 * 1024
MAX_TRANSFER_BYTES = 512 * 1024 * 1024


class RangeArchive(io.RawIOBase):
    """Seekable ZIP index reader with strictly bounded HTTP range responses."""

    def __init__(self, client: httpx.Client, url: str, expected_size: int):
        self.client = client
        self.url = url
        self.size = expected_size
        self.pos = 0
        self.transferred = 0
        self.request_count = 0
        self.fetch(0, 1)

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = 0) -> int:
        target = offset if whence == 0 else self.pos + offset if whence == 1 else self.size + offset
        if whence not in (0, 1, 2) or target < 0 or target > self.size:
            raise ValueError("ZIP seek outside pinned archive bounds")
        self.pos = target
        return target

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = self.size - self.pos
        size = min(size, self.size - self.pos)
        if size > MAX_INDEX_READ:
            raise ValueError("ZIP index read exceeds bounded index budget")
        value = self.fetch(self.pos, size) if size else b""
        self.pos += len(value)
        return value

    def fetch(self, start: int, size: int) -> bytes:
        if size <= 0 or size > MAX_MEMBER_BYTES + 65536 or start < 0 or start + size > self.size:
            raise ValueError("HTTP member range outside allowed bounds")
        if self.transferred + size > MAX_TRANSFER_BYTES or self.request_count >= 1000:
            raise ValueError("Research transfer budget exhausted")
        last_error: Exception | None = None
        for attempt in range(3):
            self.request_count += 1
            try:
                # A range-specific query avoids intermediaries reusing a different
                # byte-range response for the same URL. The pinned asset is unchanged.
                with self.client.stream(
                    "GET", self.url, params={"rangeprobe": f"{start}-{start + size - 1}"},
                    headers={"Range": f"bytes={start}-{start + size - 1}", "Accept-Encoding": "identity"},
                ) as response:
                    if response.status_code in (429, 502, 503, 504):
                        response.raise_for_status()
                    if response.status_code != 206:
                        raise ValueError("Server did not honor bounded range request")
                    expected = f"bytes {start}-{start + size - 1}/{self.size}"
                    if response.headers.get("content-range") != expected:
                        raise ValueError("Content-Range differs from pinned archive request")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        if len(body) + len(chunk) > size:
                            raise ValueError("Range response exceeded requested byte limit")
                        body.extend(chunk)
                    if len(body) != size:
                        raise ValueError("Truncated HTTP range response")
                self.transferred += len(body)
                return bytes(body)
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(attempt + 1)
        # Do not print response URLs: redirects can contain transient signatures.
        raise RuntimeError("Bounded archive request failed after three attempts") from last_error


def validate_member(info: zipfile.ZipInfo) -> None:
    path = PurePosixPath(info.filename)
    if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
        raise ValueError("Unsafe ZIP member path")
    if len(path.parts) != 2 or path.parts[0] not in {"pre-event", "post-event", "target"}:
        raise ValueError("Unexpected ZIP member directory")
    if info.is_dir() or info.file_size <= 0 or info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("Uncompressed member exceeds sample budget")
    if info.compress_size <= 0 or info.compress_size > MAX_MEMBER_BYTES:
        raise ValueError("Compressed member exceeds sample budget")
    if info.flag_bits & 1 or info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
        raise ValueError("Encrypted or unsupported ZIP member")


def decode_member(header: bytes, compressed: bytes, info: zipfile.ZipInfo) -> bytes:
    """Validate local header, bounded decompression, size and CRC before writing."""
    validate_member(info)
    if len(header) < 30 or header[:4] != b"PK\x03\x04":
        raise ValueError("Invalid ZIP local header")
    fields = struct.unpack("<IHHHHHIIIHH", header[:30])
    name_length, extra_length = fields[-2:]
    if len(header) != 30 + name_length + extra_length:
        raise ValueError("Truncated ZIP member header")
    encoding = "utf-8" if fields[2] & 0x800 else "cp437"
    name = header[30:30 + name_length].decode(encoding)
    if name != info.filename or fields[3] != info.compress_type or fields[2] & 1:
        raise ValueError("ZIP central and local headers disagree")
    if len(compressed) != info.compress_size:
        raise ValueError("Truncated compressed ZIP member")
    if info.compress_type == zipfile.ZIP_DEFLATED:
        decoder = zlib.decompressobj(-15)
        raw = decoder.decompress(compressed, info.file_size + 1)
        if len(raw) > info.file_size or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise ValueError("ZIP decompression exceeds declared member bounds")
    else:
        raw = compressed
    if len(raw) != info.file_size or zlib.crc32(raw) != info.CRC:
        raise ValueError("ZIP member size or CRC mismatch")
    return raw


def fetch_member(archive: RangeArchive, info: zipfile.ZipInfo) -> bytes:
    validate_member(info)
    prefix = archive.fetch(info.header_offset, 30)
    fields = struct.unpack("<IHHHHHIIIHH", prefix)
    header_length = 30 + fields[-2] + fields[-1]
    if header_length > 65536:
        raise ValueError("ZIP member header exceeds bounded header size")
    body = archive.fetch(info.header_offset + 30, header_length - 30 + info.compress_size)
    header = prefix + body[:header_length - 30]
    return decode_member(header, body[header_length - 30:], info)


def official_ids(text: str) -> list[str]:
    result = [line.strip() for line in text.splitlines() if line.startswith("libya-flood_")]
    if len(result) != 26 or len(set(result)) != 26 or any(
        re.fullmatch(r"libya-flood_\d{8}", uid) is None for uid in result
    ):
        raise ValueError("Pinned split does not contain the expected 26 unique Libya test tiles")
    return result


def prepare(output: Path) -> Path:
    manifest: list[dict] = []
    grids: dict[str, tuple] = {}
    output.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    path = output.parent / "bright-sample-manifest.json"
    previous = {record["member"]: record for record in json.loads(path.read_text())} if path.exists() else {}
    with httpx.Client(follow_redirects=True, max_redirects=5, timeout=40) as client:
        split = client.get(SPLIT_URL)
        split.raise_for_status()
        if len(split.content) > MAX_INDEX_READ:
            raise ValueError("Split metadata exceeds budget")
        ids = official_ids(split.text)  # fixed selection before reading labels
        (output / "test-ids.txt").write_text("\n".join(ids) + "\n")
        for archive_name, (size, folder, suffix) in ARCHIVES.items():
            url = f"{BASE_URL}/{archive_name}"
            archive = RangeArchive(client, url, size)
            with zipfile.ZipFile(archive) as index:
                for uid in ids:
                    name = f"{folder}/{uid}_{suffix}.tif"
                    info = index.getinfo(name)
                    validate_member(info)
                    target = output / name
                    cached = False
                    if target.exists() and target.stat().st_size == info.file_size:
                        raw = target.read_bytes()
                        cached = zlib.crc32(raw) == info.CRC
                        known_sha = previous.get(name, {}).get("sha256")
                        if known_sha is not None:
                            cached = cached and hashlib.sha256(raw).hexdigest() == known_sha
                    if not cached:
                        raw = fetch_member(archive, info)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        temporary = target.with_suffix(".tif.part")
                        temporary.write_bytes(raw)
                        temporary.replace(target)
                    with rasterio.open(target) as raster:
                        record = {
                            "id": uid, "archive": archive_name, "member": name,
                            "url": url, "path": str(target), "bytes": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest(), "crc32": info.CRC,
                            "crs": str(raster.crs), "transform": list(raster.transform),
                            "shape": list(raster.shape), "bands": raster.count,
                            "dtype": list(raster.dtypes),
                            "retrieved_at": previous.get(name, {}).get("retrieved_at") if cached else retrieved_at,
                            "verified_at": retrieved_at,
                            "cache_verified": cached,
                        }
                        if raster.shape != (1024, 1024) or str(raster.crs) != "EPSG:32634":
                            raise ValueError("Unexpected research raster shape or CRS")
                        if raster.count != (3 if folder == "pre-event" else 1):
                            raise ValueError("Unexpected research raster band count")
                        grid = tuple(raster.transform)
                        if uid in grids and not np.allclose(grid, grids[uid], rtol=0, atol=1e-6):
                            raise ValueError("Pre/post/reference raster grids disagree")
                        grids[uid] = grid
                        if folder == "target":
                            values, counts = np.unique(raster.read(1), return_counts=True)
                            if not set(values).issubset({0, 1, 2, 3}):
                                raise ValueError("Unexpected BRIGHT damage class")
                            record["classes"] = {str(v): int(n) for v, n in zip(values, counts)}
                        manifest.append(record)
                    print(f"{uid} {folder}: {'verified cache' if cached else 'downloaded'}", flush=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    (output / "retrieval.json").write_text(json.dumps({
        "dataset_revision": DATA_REVISION, "code_revision": CODE_REVISION,
        "split_url": SPLIT_URL, "split_sha256": hashlib.sha256(split.content).hexdigest(),
        "retrieved_at": retrieved_at, "selection": "all 26 official Libya test identifiers",
        "license": "Maxar optical and associated labels CC-BY-NC-4.0; SAR CC-BY-4.0",
        "acquisition_times": "Not recovered per input; event date is not acquisition time",
    }, indent=2) + "\n")
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/research/bright-sample"))
    arguments = parser.parse_args()
    print(prepare(arguments.output))
