import shutil


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
