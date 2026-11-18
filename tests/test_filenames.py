import pytest

from blackpearl.core.filenames import (
    DEFAULT_NAME,
    MAX_STEM_LENGTH,
    sanitize_filename,
    unique_path,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Artist — Song", "Artist — Song"),
        ('AC/DC: "Back in Black"?', "AC_DC_ _Back in Black__"),
        ("tab\tand\nnewline", "tab_and_newline"),
        ("Ending dot.", "Ending dot"),
        ("Dots and spaces . . ", "Dots and spaces"),
        ("  padded  ", "padded"),
        ("CON", "_CON"),
        ("con", "_con"),
        ("Nul.remix", "_Nul.remix"),
        ("COM1", "_COM1"),
        ("LPT9", "_LPT9"),
        ("CONTROL", "CONTROL"),
        ("COM10", "COM10"),
        ("", DEFAULT_NAME),
        ("...", DEFAULT_NAME),
        ("   ", DEFAULT_NAME),
    ],
)
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_truncates_long_names():
    result = sanitize_filename("x" * 500)

    assert len(result) == MAX_STEM_LENGTH


def test_sanitize_filename_strips_dot_left_after_truncation():
    result = sanitize_filename("a" * 9 + ". tail", max_length=11)

    assert result == "a" * 9


def test_unique_path_returns_free_name(tmp_path):
    assert unique_path(tmp_path, "Song", ".mp3") == tmp_path / "Song.mp3"


def test_unique_path_adds_number_for_existing_files(tmp_path):
    (tmp_path / "Song.mp3").touch()
    (tmp_path / "Song (2).mp3").touch()

    assert unique_path(tmp_path, "Song", ".mp3") == tmp_path / "Song (3).mp3"


def test_unique_path_ignores_other_extensions(tmp_path):
    (tmp_path / "Song.txt").touch()

    assert unique_path(tmp_path, "Song", ".mp3") == tmp_path / "Song.mp3"
