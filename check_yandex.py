from yandex_music import Client

from blackpearl.core.config import settings


def main() -> None:
    if not settings.yandex_music_token:
        raise RuntimeError(
            "Не задан YANDEX_MUSIC_TOKEN в файле .env"
        )

    client = Client(settings.yandex_music_token).init()

    print("Авторизация успешна")
    print(f"Аккаунт: {client.me.account.login}")


if __name__ == "__main__":
    main()
