"""Security/integrity checks for selective research archive downloads."""

import io
import importlib.util
from pathlib import Path
import zipfile

import pytest

spec = importlib.util.spec_from_file_location(
    "prepare_bright", Path(__file__).resolve().parents[1] / "scripts" / "prepare_bright.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
RangeArchive = module.RangeArchive
decode_member = module.decode_member
official_ids = module.official_ids
validate_member = module.validate_member


def example_member():
    memory = io.BytesIO()
    with zipfile.ZipFile(memory, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("target/libya-flood_00000001_building_damage.tif", b"valid raster bytes")
    encoded = memory.getvalue()
    with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
        info = archive.infolist()[0]
    offset = info.header_offset + 30 + len(info.filename.encode())
    return encoded[:offset], encoded[offset:offset + info.compress_size], info


def test_real_zip_member_round_trip_and_corruption_rejected():
    header, compressed, info = example_member()
    assert decode_member(header, compressed, info) == b"valid raster bytes"
    info.CRC ^= 1
    with pytest.raises(ValueError, match="CRC"):
        decode_member(header, compressed, info)


@pytest.mark.parametrize("path", ["../target/a.tif", "/target/a.tif", "target/../a.tif", "target\\a.tif"])
def test_unsafe_archive_paths_rejected(path):
    info = zipfile.ZipInfo(path)
    info.file_size = info.compress_size = 1
    with pytest.raises(ValueError, match="Unsafe"):
        validate_member(info)


def test_decompression_budget_rejects_declared_size_mismatch():
    header, compressed, info = example_member()
    info.file_size = 2
    with pytest.raises(ValueError, match="bounds"):
        decode_member(header, compressed, info)


def test_selection_uses_complete_pinned_event_split():
    ids = [f"libya-flood_{n:08d}" for n in range(26)]
    assert official_ids("unrelated_00000000\n" + "\n".join(ids)) == ids
    with pytest.raises(ValueError, match="26 unique"):
        official_ids("\n".join(ids[:-1]))


def test_server_ignoring_ranges_never_downloads_full_archive():
    import httpx

    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"full archive"))
    with httpx.Client(transport=transport) as client:
        with pytest.raises(ValueError, match="honor bounded"):
            RangeArchive(client, "https://example.com/archive.zip", 1_000_000_000)
