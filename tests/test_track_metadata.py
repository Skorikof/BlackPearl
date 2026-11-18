from pathlib import Path

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import ID3

from blackpearl.core.track_metadata import (
    MAX_FOLDER_NAME_LENGTH,
    SOURCE_ID_TAG,
    VARIOUS_ARTISTS,
    TrackMetadata,
    library_location,
    read_source_id,
    resolve_target,
    write_id3_tags,
    write_tags,
)

OUT = Path("out")

ALBUM_TRACK = TrackMetadata(
    source_id="yandex:1",
    title="Numb",
    artists=["Linkin Park"],
    album_title="Meteora",
    album_artist="Linkin Park",
    year=2003,
    genre="rock",
    track_number=13,
    disc_number=1,
)


def make_mp3(path: Path) -> Path:
    # Содержимое не важно: ID3-теги записываются в начало файла.
    path.write_bytes(b"\xff\xfb\x90\x00" * 64)
    return path


def test_album_track_goes_to_artist_and_album_folders():
    directory, stem = library_location(ALBUM_TRACK, OUT)

    assert directory == OUT / "Linkin Park" / "Meteora (2003)"
    assert stem == "13 - Numb"


def test_multi_disc_track_number_includes_disc():
    metadata = TrackMetadata(
        **{**ALBUM_TRACK.__dict__, "disc_number": 2, "track_number": 3}
    )

    _, stem = library_location(metadata, OUT)

    assert stem == "2-03 - Numb"


def test_track_artist_differs_from_album_artist():
    metadata = TrackMetadata(
        source_id="yandex:2",
        title="Song",
        artists=["Guest", "Host"],
        album_title="Hits 2020",
        album_artist=VARIOUS_ARTISTS,
        year=2020,
        track_number=4,
    )

    directory, stem = library_location(metadata, OUT)

    assert directory == OUT / VARIOUS_ARTISTS / "Hits 2020 (2020)"
    assert stem == "04 - Guest, Host — Song"


def test_album_without_year_and_track_number():
    metadata = TrackMetadata(
        source_id="yandex:3",
        title="Song",
        artists=["Artist"],
        album_title="Album",
        album_artist="Artist",
    )

    directory, stem = library_location(metadata, OUT)

    assert directory == OUT / "Artist" / "Album"
    assert stem == "Song"


def test_missing_album_artist_falls_back_to_various():
    metadata = TrackMetadata(
        source_id="yandex:4", title="Song", album_title="Album"
    )

    directory, _ = library_location(metadata, OUT)

    assert directory == OUT / VARIOUS_ARTISTS / "Album"


@pytest.mark.parametrize("organize", [True, False])
def test_flat_layout_without_album_or_when_disabled(organize):
    metadata = (
        ALBUM_TRACK
        if not organize
        else TrackMetadata(source_id="yandex:5", title="Song", artists=["A"])
    )

    directory, stem = library_location(metadata, OUT, organize_by_album=organize)

    assert directory == OUT
    assert stem == ("Linkin Park — Numb" if not organize else "A — Song")


def test_folder_names_are_sanitized_and_shortened():
    metadata = TrackMetadata(
        source_id="yandex:6",
        title="T.N.T.",
        artists=["AC/DC"],
        album_title="x" * 200,
        album_artist="AC/DC",
        track_number=1,
    )

    directory, stem = library_location(metadata, OUT)

    assert directory.parent.name == "AC_DC"
    assert len(directory.name) == MAX_FOLDER_NAME_LENGTH
    assert stem == "01 - T.N.T"


def test_write_and_read_tags(tmp_path):
    path = make_mp3(tmp_path / "song.mp3")

    write_id3_tags(path, ALBUM_TRACK, cover=(b"\xff\xd8jpeg", "image/jpeg"))

    tags = ID3(path)
    assert tags["TIT2"].text == ["Numb"]
    assert tags["TPE1"].text == ["Linkin Park"]
    assert tags["TALB"].text == ["Meteora"]
    assert tags["TPE2"].text == ["Linkin Park"]
    assert str(tags["TDRC"].text[0]) == "2003"
    assert tags["TCON"].text == ["rock"]
    assert tags["TRCK"].text == ["13"]
    assert tags["TPOS"].text == ["1"]
    assert tags[f"TXXX:{SOURCE_ID_TAG}"].text == ["yandex:1"]
    assert tags.getall("APIC")[0].data == b"\xff\xd8jpeg"
    assert tags.version[:2] == (2, 3)
    assert read_source_id(path) == "yandex:1"


def test_minimal_tags_skip_empty_fields(tmp_path):
    path = make_mp3(tmp_path / "song.mp3")

    write_id3_tags(path, TrackMetadata(source_id="yandex:9", title="Solo"))

    tags = ID3(path)
    assert tags["TIT2"].text == ["Solo"]
    for frame in ("TPE1", "TALB", "TPE2", "TDRC", "TCON", "TRCK", "TPOS", "APIC"):
        assert not tags.getall(frame)


def test_read_source_id_without_tags(tmp_path):
    assert read_source_id(make_mp3(tmp_path / "plain.mp3")) is None


def test_read_source_id_of_missing_file(tmp_path):
    assert read_source_id(tmp_path / "missing.mp3") is None


def test_resolve_target_free_name(tmp_path):
    assert resolve_target(tmp_path, "Song", ".mp3", "yandex:1") == (
        tmp_path / "Song.mp3",
        False,
    )


def test_resolve_target_finds_same_track(tmp_path):
    path = make_mp3(tmp_path / "Song.mp3")
    write_id3_tags(path, TrackMetadata(source_id="yandex:1", title="Song"))

    assert resolve_target(tmp_path, "Song", ".mp3", "yandex:1") == (path, True)


def test_resolve_target_skips_other_track_with_same_name(tmp_path):
    other = make_mp3(tmp_path / "Song.mp3")
    write_id3_tags(other, TrackMetadata(source_id="yandex:2", title="Song"))

    assert resolve_target(tmp_path, "Song", ".mp3", "yandex:1") == (
        tmp_path / "Song (2).mp3",
        False,
    )


def test_resolve_target_finds_same_track_under_numbered_name(tmp_path):
    other = make_mp3(tmp_path / "Song.mp3")
    write_id3_tags(other, TrackMetadata(source_id="yandex:2", title="Song"))
    same = make_mp3(tmp_path / "Song (2).mp3")
    write_id3_tags(same, TrackMetadata(source_id="yandex:1", title="Song"))

    assert resolve_target(tmp_path, "Song", ".mp3", "yandex:1") == (same, True)


def make_flac(path: Path) -> Path:
    """Минимальный корректный FLAC: сигнатура и блок STREAMINFO."""
    stream_params = ((44100 << 44) | (1 << 41) | (15 << 36)).to_bytes(8, "big")
    streaminfo = (4096).to_bytes(2, "big") * 2 + bytes(6) + stream_params + bytes(16)
    path.write_bytes(b"fLaC" + bytes([0x80, 0, 0, len(streaminfo)]) + streaminfo)
    return path


def test_write_and_read_flac_tags(tmp_path):
    path = make_flac(tmp_path / "song.flac")

    write_tags(
        path, ALBUM_TRACK, "flac", cover=(b"\xff\xd8jpeg", "image/jpeg")
    )

    audio = FLAC(path)
    assert audio["TITLE"] == ["Numb"]
    assert audio["ARTIST"] == ["Linkin Park"]
    assert audio["ALBUM"] == ["Meteora"]
    assert audio["ALBUMARTIST"] == ["Linkin Park"]
    assert audio["DATE"] == ["2003"]
    assert audio["GENRE"] == ["rock"]
    assert audio["TRACKNUMBER"] == ["13"]
    assert audio["DISCNUMBER"] == ["1"]
    assert audio.pictures[0].data == b"\xff\xd8jpeg"
    assert audio.pictures[0].type == 3
    assert read_source_id(path) == "yandex:1"


def test_flac_tags_written_to_part_file_by_explicit_format(tmp_path):
    # Во время загрузки файл называется *.flac.part — формат задаётся явно.
    part = make_flac(tmp_path / "song.flac.part")

    write_tags(part, TrackMetadata(source_id="yandex:7", title="T"), "flac")
    final = part.replace(tmp_path / "song.flac")

    assert read_source_id(final) == "yandex:7"


def test_write_tags_mp3_dispatch(tmp_path):
    path = make_mp3(tmp_path / "song.mp3.part")

    write_tags(path, TrackMetadata(source_id="yandex:8", title="T"), "mp3")

    assert ID3(path)["TIT2"].text == ["T"]


def test_read_source_id_of_broken_flac(tmp_path):
    path = tmp_path / "broken.flac"
    path.write_bytes(b"not a flac")

    assert read_source_id(path) is None


def test_resolve_target_finds_flac_by_id(tmp_path):
    path = make_flac(tmp_path / "Song.flac")
    write_tags(path, TrackMetadata(source_id="yandex:1", title="Song"), "flac")

    assert resolve_target(tmp_path, "Song", ".flac", "yandex:1") == (path, True)
