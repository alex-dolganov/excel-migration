import ast

from b24pysdk.error import BitrixRequestTimeout


MISSING_BITRIX_RECORD_ID_ERROR = "Bitrix24 не подтвердил создание записи: ID не получен."


def _format_timeout_seconds(value) -> str:
    try:
        normalized_value = float(value)
    except (TypeError, ValueError):
        return ""

    if normalized_value <= 0:
        return ""

    if normalized_value.is_integer():
        return str(int(normalized_value))

    return str(normalized_value).rstrip("0").rstrip(".")


def _extract_error_message(error) -> str:
    if isinstance(error, dict):
        for key in ("error_description", "description", "message", "error"):
            value = str(error.get(key) or "").strip()
            if value:
                return value
        return ""

    message = str(error or "").strip()
    if not (message.startswith("{") and message.endswith("}")):
        return message

    try:
        parsed_error = ast.literal_eval(message)
    except (SyntaxError, ValueError):
        return message

    if isinstance(parsed_error, dict):
        extracted_message = _extract_error_message(parsed_error)
        if extracted_message:
            return extracted_message

    return message


def format_import_error(error) -> str:
    if isinstance(error, BitrixRequestTimeout):
        timeout_seconds = _format_timeout_seconds(getattr(error, "timeout", None))
        if timeout_seconds:
            return f"Bitrix24 не ответил за {timeout_seconds} сек. Повторите импорт."
        return "Bitrix24 не ответил вовремя. Повторите импорт."

    message = _extract_error_message(error)
    if "Read timed out" in message:
        return "Bitrix24 не ответил вовремя. Повторите импорт."

    return message or "Без описания"
