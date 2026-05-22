import ast

from b24pysdk.error import BitrixRequestTimeout


MISSING_BITRIX_RECORD_ID_ERROR = "Bitrix24 не подтвердил создание записи: ID не получен."
BITRIX_UNREACHABLE_ERROR = "Не удалось связаться с Bitrix24. Проверьте доступность портала и повторите импорт."
BITRIX_OPERATION_TIME_LIMIT_ERROR = "Bitrix24 временно заблокировал метод из-за лимита времени выполнения. Подождите 10 минут и повторите импорт."
BITRIX_DAILY_INVITATION_LIMIT_ERROR = (
    "Bitrix24 исчерпал дневной лимит приглашений по e-mail. "
    "Импорт пользователей остановлен, повторите попытку позже."
)
BITRIX_USER_INVITATION_UNKNOWN_ERROR = (
    "Bitrix24 не принял приглашение пользователя. "
    "Частая причина — дневной лимит приглашений по e-mail. "
    "Проверьте приглашение вручную на портале и повторите попытку позже."
)

_BITRIX_DAILY_INVITATION_LIMIT_MARKERS = (
    "дневной лимит количества приглашений",
    "превышен дневной лимит количества приглашений",
    "лимит количества приглашений по e-mail",
    "daily invitation limit",
    "invitation limit exceeded",
)


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
    json_response = getattr(error, "json_response", None)
    if isinstance(json_response, dict):
        extracted_message = _extract_error_message(json_response)
        if extracted_message:
            return extracted_message

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


def _iter_error_messages(error):
    pending = [error]
    seen = set()

    while pending:
        current = pending.pop()
        if current is None:
            continue

        if isinstance(current, dict):
            for value in current.values():
                if isinstance(value, (dict, list, tuple, set)):
                    pending.append(value)

            for key in ("error_description", "description", "message", "error"):
                value = str(current.get(key) or "").strip()
                if value and value not in seen:
                    seen.add(value)
                    yield value
            continue

        if isinstance(current, (list, tuple, set)):
            pending.extend(current)
            continue

        json_response = getattr(current, "json_response", None)
        if isinstance(json_response, dict):
            pending.append(json_response)

        message = str(current or "").strip()
        if not message:
            continue

        if message.startswith("{") and message.endswith("}"):
            try:
                parsed_message = ast.literal_eval(message)
            except (SyntaxError, ValueError):
                parsed_message = None
            if isinstance(parsed_message, dict):
                pending.append(parsed_message)

        if message not in seen:
            seen.add(message)
            yield message


def iter_error_messages(error):
    return tuple(_iter_error_messages(error))


def is_daily_invitation_limit_error(error) -> bool:
    for message in iter_error_messages(error):
        normalized_message = message.lower()
        if any(marker in normalized_message for marker in _BITRIX_DAILY_INVITATION_LIMIT_MARKERS):
            return True
        if "invitation" in normalized_message and any(
            marker in normalized_message for marker in ("limit", "quota", "exceed", "email")
        ):
            return True
    return False


def format_import_error(error) -> str:
    if isinstance(error, BitrixRequestTimeout):
        timeout_seconds = _format_timeout_seconds(getattr(error, "timeout", None))
        if timeout_seconds:
            return f"Bitrix24 не ответил за {timeout_seconds} сек. Повторите импорт."
        return "Bitrix24 не ответил вовремя. Повторите импорт."

    if is_daily_invitation_limit_error(error):
        return BITRIX_DAILY_INVITATION_LIMIT_ERROR

    message = _extract_error_message(error)
    normalized_message = message.lower()
    if "Read timed out" in message:
        return "Bitrix24 не ответил вовремя. Повторите импорт."
    if "operation time limit" in normalized_message or "operation_time_limit" in normalized_message:
        return BITRIX_OPERATION_TIME_LIMIT_ERROR
    if any(marker in normalized_message for marker in (
        "failed to resolve",
        "nameresolutionerror",
        "no address associated with hostname",
        "temporary failure in name resolution",
        "name or service not known",
    )):
        return BITRIX_UNREACHABLE_ERROR

    return message or "Без описания"


def safe_format_import_error(error) -> str:
    try:
        return format_import_error(error)
    except Exception:
        try:
            message = _extract_error_message(error)
        except Exception:
            message = ""

        return str(message or "").strip() or "Без описания"
