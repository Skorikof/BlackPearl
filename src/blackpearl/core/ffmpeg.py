import shutil
import subprocess
from pathlib import Path


class FfmpegNotFoundError(RuntimeError):
    """ffmpeg не найден ни в PATH, ни в пакете imageio-ffmpeg."""

    def __init__(self) -> None:
        super().__init__(
            "Не найден ffmpeg. Установите его и добавьте в PATH "
            "или установите пакет imageio-ffmpeg"
        )


def find_ffmpeg() -> str | None:
    """Возвращает путь к ffmpeg или None, если он не найден."""
    path = shutil.which("ffmpeg")
    if path is not None:
        return path

    try:
        import imageio_ffmpeg
    except ImportError:
        return None

    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except RuntimeError:
        return None


def require_ffmpeg() -> str:
    """Возвращает путь к ffmpeg или бросает FfmpegNotFoundError."""
    path = find_ffmpeg()
    if path is None:
        raise FfmpegNotFoundError()
    return path


def remux_audio(source: Path, destination: Path, container: str) -> None:
    """Перекладывает аудиодорожку в другой контейнер без перекодирования.

    Например, FLAC из MP4 в обычный .flac: звук копируется как есть,
    качество не меняется. container — имя формата ffmpeg ("flac").
    """
    command = [
        require_ffmpeg(),
        "-nostdin",
        "-loglevel", "error",
        "-y",
        "-i", str(source),
        "-map", "0:a:0",
        "-c:a", "copy",
        "-f", container,
        str(destination),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        # GUI-приложение не должно мигать консольным окном на Windows.
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode != 0:
        details = result.stderr.strip() or f"код {result.returncode}"
        raise RuntimeError(f"Не удалось переупаковать аудио: {details}")
