class MissingTokenError(Exception):
    """Исключение, возникающее при отсутствии обязательных токенов."""


class ApiResponseError(Exception):
    """Исключение при некорректном ответе от API."""


class EmptyAPIResponse(Exception):
    """Исключение при отсутствии необходимых ключей."""
