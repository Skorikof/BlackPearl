import re
from pathlib import Path

DEFAULT_NAME = "Без названия"

# Ограничение длины имени без расширения. Лимит NTFS — 255 символов
# на компонент пути; оставляем запас под " (N)", расширение, ".part"
# и под длинный путь к папке назначения.
MAX_STEM_LENGTH = 150

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Имена устройств Windows: файл "CON.mp3" создать нельзя.
_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{i}" for i in range(1, 10)}
    | {f"LPT{i}" for i in range(1, 10)}
)


def sanitize_filename(name: str, max_length: int = MAX_STEM_LENGTH) -> str:
    """Превращает произвольную строку в допустимое имя файла (без расширения).

    Учитывает ограничения Windows: запрещённые символы, точки и пробелы
    в конце имени, зарезервированные имена устройств и длину.
    """
    name = _INVALID_CHARS.sub("_", name)
    name = name.strip().rstrip(". ")

    if len(name) > max_length:
        name = name[:max_length].rstrip(". ")

    if not name:
        return DEFAULT_NAME

    # Windows считает зарезервированным и "CON.something".
    if name.split(".", 1)[0].upper() in _RESERVED_NAMES:
        name = f"_{name}"

    return name


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """Возвращает путь к несуществующему файлу.

    Если "stem{suffix}" уже занят, добавляет номер: "stem (2){suffix}",
    "stem (3){suffix}" и т. д. — чтобы разные треки с одинаковым
    названием не перезаписывали друг друга.
    """
    path = directory / f"{stem}{suffix}"
    number = 2
    while path.exists():
        path = directory / f"{stem} ({number}){suffix}"
        number += 1
    return path
