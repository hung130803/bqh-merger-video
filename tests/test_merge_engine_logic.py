"""Unit + property tests cho logic thuần của merge_engine.

Bao gồm: scan_folder, compute_keep_window, pair_videos.
"""

from __future__ import annotations

import random
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from app.engine.merge_engine import compute_keep_window, pair_videos, scan_folder
from app.engine.models import MergeOrder


# ----------------------------------------------------------------- unit tests
def test_scan_folder_filters_and_case_insensitive(tmp_path: Path):
    (tmp_path / "a.MP4").write_bytes(b"x")
    (tmp_path / "b.mov").write_bytes(b"x")
    (tmp_path / "c.txt").write_bytes(b"x")
    (tmp_path / "d.MKV").write_bytes(b"x")
    names = {p.name for p in scan_folder(tmp_path)}
    assert names == {"a.MP4", "b.mov", "d.MKV"}


def test_scan_folder_no_recursion(tmp_path: Path):
    (tmp_path / "top.mp4").write_bytes(b"x")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.mp4").write_bytes(b"x")
    names = {p.name for p in scan_folder(tmp_path)}
    assert names == {"top.mp4"}


def test_scan_folder_missing_dir(tmp_path: Path):
    assert scan_folder(tmp_path / "nope") == []


def test_compute_keep_window():
    assert compute_keep_window(10, 1, 1) == 8
    assert compute_keep_window(2, 1, 1) is None  # = 0 -> None
    assert compute_keep_window(1.5, 1, 1) is None  # < 0 -> None
    assert compute_keep_window(5, 0, 0) == 5


def test_pair_videos_min_count_and_leftovers():
    f1 = [Path(f"{i}.mp4") for i in "abc"]
    f2 = [Path(f"{i}.mp4") for i in "xy"]
    pairs, leftovers = pair_videos(f1, f2, MergeOrder.SORTED)
    assert len(pairs) == 2
    assert len(leftovers) == 1


def test_pair_videos_sorted_order():
    f1 = [Path("b.mp4"), Path("a.mp4")]
    f2 = [Path("2.mp4"), Path("1.mp4")]
    pairs, _ = pair_videos(f1, f2, MergeOrder.SORTED)
    assert pairs[0][0].name == "a.mp4"
    assert pairs[0][1].name == "1.mp4"
    assert pairs[1][0].name == "b.mp4"
    assert pairs[1][1].name == "2.mp4"


# ------------------------------------------------------------- property tests
def _paths(names: list[str], parent: str = "f") -> list[Path]:
    return [Path(parent) / f"{n}.mp4" for n in names]


_name_lists = st.lists(
    st.text(alphabet="abcdefghij", min_size=1, max_size=4), max_size=15
).map(lambda xs: [f"{i}_{x}" for i, x in enumerate(xs)])  # đảm bảo tên duy nhất


# Feature: batch-video-merger, Property 1: Mỗi video nguồn được dùng nhiều nhất một lần
@given(_name_lists, _name_lists, st.sampled_from(list(MergeOrder)))
def test_property_each_source_used_at_most_once(names1, names2, order):
    f1 = _paths(names1, "f1")
    f2 = _paths(names2, "f2")
    pairs, leftovers = pair_videos(f1, f2, order, random.Random(123))

    used1 = [p[0] for p in pairs]
    used2 = [p[1] for p in pairs]

    # không file nào dùng quá một lần trong các cặp
    assert len(used1) == len(set(used1))
    assert len(used2) == len(set(used2))

    # phân hoạch: file trong cặp + leftover = nguồn, không trùng
    all_paired = set(used1) | set(used2)
    all_left = set(leftovers)
    assert all_paired.isdisjoint(all_left)
    assert all_paired | all_left == set(f1) | set(f2)


# Feature: batch-video-merger, Property 2: Số cặp bằng min của hai số lượng
@given(_name_lists, _name_lists, st.sampled_from(list(MergeOrder)))
def test_property_pair_count_is_min(names1, names2, order):
    f1 = _paths(names1, "f1")
    f2 = _paths(names2, "f2")
    pairs, leftovers = pair_videos(f1, f2, order, random.Random(7))
    assert len(pairs) == min(len(f1), len(f2))
    assert len(leftovers) == abs(len(f1) - len(f2))


# Feature: batch-video-merger, Property 3: Ghép cặp theo vị trí một-đối-một
@given(_name_lists, _name_lists)
def test_property_positional_pairing_sorted(names1, names2):
    f1 = _paths(names1, "f1")
    f2 = _paths(names2, "f2")
    pairs, _ = pair_videos(f1, f2, MergeOrder.SORTED, random.Random(1))

    s1 = sorted(f1, key=lambda p: p.name.lower())
    s2 = sorted(f2, key=lambda p: p.name.lower())
    for i, (a, b) in enumerate(pairs):
        assert a == s1[i]
        assert b == s2[i]


# Feature: batch-video-merger, Property 7: Cửa sổ cắt đúng và bỏ qua khi không dương
@given(
    st.floats(min_value=0, max_value=10000, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, max_value=5000, allow_nan=False, allow_infinity=False),
    st.floats(min_value=0, max_value=5000, allow_nan=False, allow_infinity=False),
)
def test_property_keep_window(duration, head, tail):
    result = compute_keep_window(duration, head, tail)
    expected = duration - head - tail
    if expected <= 0:
        assert result is None
    else:
        assert result == expected


# Feature: batch-video-merger, Property 8: Quét file lọc đúng định dạng, không phân biệt hoa thường, không đệ quy
@given(
    st.lists(
        st.tuples(
            st.text(alphabet="abcdef", min_size=1, max_size=5),
            st.sampled_from(
                [".mp4", ".MOV", ".Mkv", ".avi", ".WEBM", ".txt", ".jpg", ".mp3"]
            ),
        ),
        max_size=12,
    ),
)
def test_property_scan_folder(entries):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp_path = Path(d)
        sub = tmp_path / "sub"
        sub.mkdir()

        expected = set()
        seen = set()
        for i, (stem, ext) in enumerate(entries):
            fname = f"{i}_{stem}{ext}"
            if fname in seen:
                continue
            seen.add(fname)
            (tmp_path / fname).write_bytes(b"x")
            # file trong thư mục con không bao giờ được trả về
            (sub / f"nested_{fname}").write_bytes(b"x")
            if ext.lower() in {".mp4", ".mov", ".mkv", ".avi", ".webm"}:
                expected.add(fname)

        result = {p.name for p in scan_folder(tmp_path)}
        assert result == expected
