from blackpearl.providers.yandex_music_provider import YandexMusicProvider


def main():
    provider = YandexMusicProvider()

    url = input("Вставь ссылку на альбом или плейлист: ").strip()

    if not provider.can_handle(url):
        print("Ссылка не распознана")
        return

    print("\nПолучаю список треков...")

    tracks = provider.get_collection_tracks(url)

    print(f"\nНайдено треков: {len(tracks)}\n")

    for number, track in enumerate(tracks, start=1):
        duration = ""

        if track.duration_seconds is not None:
            minutes, seconds = divmod(int(track.duration_seconds), 60)
            duration = f"{minutes}:{seconds:02d}"

        print(
            f"{number:03}. "
            f"{track.artists} — {track.title} "
            f"[{duration}]"
        )


if __name__ == "__main__":
    main()
