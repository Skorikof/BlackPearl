from blackpearl.providers.base import MediaKind, MediaProvider


class ProviderRegistry:
    """Реестр доступных источников медиа."""

    def __init__(self) -> None:
        self._providers: list[MediaProvider] = []

    def register(self, provider: MediaProvider) -> None:
        """Регистрирует источник."""
        self._providers.append(provider)

    def get_provider(
        self,
        url: str,
        kind: MediaKind | None = None,
    ) -> MediaProvider | None:
        """Возвращает источник, способный обработать URL.

        Если задан kind, учитываются только источники,
        поддерживающие этот режим скачивания.
        """
        for provider in self._providers:
            if kind is not None and not provider.supports(kind):
                continue
            if provider.can_handle(url):
                return provider

        return None
