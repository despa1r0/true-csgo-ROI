"""Shared building blocks for marketplace adapters (CSFloat, WhiteMarket, ...)."""


class MarketplaceRequestError(Exception):
    """Безопасное для отображения пользователю описание сбоя адаптера маркетплейса."""
