from blackpearl.providers.base import MediaProvider


class ProviderRegistry:
    """Реестр доступных источников медиа."""

    def __init__(self) -> None:
        self._providers: list[MediaProvider] = []

    def register(self, provider: MediaProvider) -> None:
        """Регистрирует источник."""
        self._providers.append(provider)

    def get_provider(self, url: str) -> MediaProvider | None:
        """Возвращает источник, способный обработать URL."""

        for provider in self._providers:
            if provider.can_handle(url):
                return provider

        return None