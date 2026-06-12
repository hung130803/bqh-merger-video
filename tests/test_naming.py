"""Unit + property tests cho app.engine.naming."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from app.engine import naming


# ----------------------------------------------------------------- unit tests
def test_format_stt_basic():
    assert naming.format_stt(1) == "001"
    assert naming.format_stt(2) == "002"
    assert naming.format_stt(999) == "999"


def test_format_stt_over_999():
    assert naming.format_stt(1000) == "1000"
    assert naming.format_stt(12345) == "12345"


def test_merged_name_format():
    assert naming.merged_name("001", "001", "a") == "merged_001__001__a.mp4"


def test_used_name_format():
    assert naming.used_name("001", "F1", "clip") == "001_F1_clip.mp4"
    assert naming.used_name("007", "F2", "b") == "007_F2_b.mp4"


def test_resolve_collision_no_conflict(tmp_path: Path):
    target = tmp_path / "x.mp4"
    assert naming.resolve_collision(target) == target


def test_resolve_collision_with_conflict(tmp_path: Path):
    target = tmp_path / "x.mp4"
    target.write_bytes(b"a")
    result = naming.resolve_collision(target)
    assert result == tmp_path / "x_1.mp4"

    (tmp_path / "x_1.mp4").write_bytes(b"a")
    result2 = naming.resolve_collision(target)
    assert result2 == tmp_path / "x_2.mp4"


# ------------------------------------------------------------- property tests
# Feature: batch-video-merger, Property 4: STT là duy nhất và tăng đơn điệu
@given(st.integers(min_value=1, max_value=100))
def test_property_stt_unique_monotonic(count: int):
    stts = [naming.format_stt(i) for i in range(1, count + 1)]
    # duy nhất từng đôi
    assert len(set(stts)) == len(stts)
    # bắt đầu từ "001"
    assert stts[0] == "001"
    # tăng đều 1, không mất thông tin số
    for i, s in enumerate(stts, start=1):
        assert int(s) == i


# Feature: batch-video-merger, Property 5: Cùng một cặp dùng chung một STT
@given(
    st.integers(min_value=1, max_value=5000),
    st.text(
        alphabet=st.characters(blacklist_characters="/\\\x00"),
        min_size=1,
        max_size=12,
    ),
    st.text(
        alphabet=st.characters(blacklist_characters="/\\\x00"),
        min_size=1,
        max_size=12,
    ),
)
def test_property_same_pair_same_stt(index: int, name1: str, name2: str):
    stt = naming.format_stt(index)
    merged = naming.merged_name(stt, name1, name2)
    used1 = naming.used_name(stt, "F1", name1)
    used2 = naming.used_name(stt, "F2", name2)
    assert merged.startswith(f"merged_{stt}__")
    assert used1.startswith(f"{stt}_F1_")
    assert used2.startswith(f"{stt}_F2_")


# Feature: batch-video-merger, Property 6: Giải quyết trùng tên luôn cho tên duy nhất
@given(st.integers(min_value=0, max_value=20))
def test_property_resolve_collision_unique(num_existing: int):
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        tmp_path = Path(d)
        target = tmp_path / "video.mp4"
        # tạo trước target và một số biến thể _n
        if num_existing >= 1:
            target.write_bytes(b"x")
        for n in range(1, num_existing):
            (tmp_path / f"video_{n}.mp4").write_bytes(b"x")

        result = naming.resolve_collision(target)
        assert not result.exists()
        if num_existing >= 1:
            assert result.stem.startswith("video_")
            suffix_num = int(result.stem.split("_")[-1])
            assert suffix_num >= 1
        else:
            assert result == target
