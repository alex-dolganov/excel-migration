import ast
import contextvars

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

SUPPORTED_IMPORT_LANGUAGES = ("ru", "en", "br")

_IMPORT_ERROR_TEXTS = {
    "missing_record_id": {
        "ru": MISSING_BITRIX_RECORD_ID_ERROR,
        "en": "Bitrix24 did not confirm record creation: no ID was returned.",
        "br": "O Bitrix24 não confirmou a criação do registro: nenhum ID foi retornado.",
    },
    "unreachable": {
        "ru": BITRIX_UNREACHABLE_ERROR,
        "en": "Could not reach Bitrix24. Check that the portal is available and retry the import.",
        "br": "Não foi possível conectar ao Bitrix24. Verifique a disponibilidade do portal e repita a importação.",
    },
    "operation_time_limit": {
        "ru": BITRIX_OPERATION_TIME_LIMIT_ERROR,
        "en": "Bitrix24 temporarily blocked the method due to the operation time limit. Wait 10 minutes and retry the import.",
        "br": "O Bitrix24 bloqueou temporariamente o método devido ao limite de tempo de execução. Aguarde 10 minutos e repita a importação.",
    },
    "daily_invitation_limit": {
        "ru": BITRIX_DAILY_INVITATION_LIMIT_ERROR,
        "en": "Bitrix24 has reached the daily e-mail invitation limit. User import stopped, try again later.",
        "br": "O Bitrix24 atingiu o limite diário de convites por e-mail. A importação de usuários foi interrompida, tente novamente mais tarde.",
    },
    "invitation_unknown": {
        "ru": BITRIX_USER_INVITATION_UNKNOWN_ERROR,
        "en": "Bitrix24 did not accept the user invitation. A frequent cause is the daily e-mail invitation limit. Check the invitation manually on the portal and try again later.",
        "br": "O Bitrix24 não aceitou o convite do usuário. Uma causa frequente é o limite diário de convites por e-mail. Verifique o convite manualmente no portal e tente novamente mais tarde.",
    },
    "timeout_seconds": {
        "ru": "Bitrix24 не ответил за {seconds} сек. Повторите импорт.",
        "en": "Bitrix24 did not respond within {seconds} sec. Retry the import.",
        "br": "O Bitrix24 não respondeu em {seconds} s. Repita a importação.",
    },
    "timeout": {
        "ru": "Bitrix24 не ответил вовремя. Повторите импорт.",
        "en": "Bitrix24 did not respond in time. Retry the import.",
        "br": "O Bitrix24 não respondeu a tempo. Repita a importação.",
    },
    "no_description": {
        "ru": "Без описания",
        "en": "No description",
        "br": "Sem descrição",
    },
}

_import_error_language = contextvars.ContextVar("import_error_language", default="ru")


def normalize_import_language(language) -> str:
    normalized = str(language or "").strip().lower().replace("_", "-")
    if normalized in {"br", "pt", "pt-br"}:
        return "br"
    if normalized == "en" or normalized.startswith("en-"):
        return "en"
    return "ru"


def set_import_error_language(language) -> None:
    _import_error_language.set(normalize_import_language(language))


def get_import_error_language() -> str:
    return _import_error_language.get()


def get_import_error_text(key: str, **params) -> str:
    texts = _IMPORT_ERROR_TEXTS.get(key) or {}
    template = texts.get(get_import_error_language()) or texts.get("ru") or ""
    return template.format(**params) if params else template

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
            return get_import_error_text("timeout_seconds", seconds=timeout_seconds)
        return get_import_error_text("timeout")

    if is_daily_invitation_limit_error(error):
        return get_import_error_text("daily_invitation_limit")

    message = _extract_error_message(error)
    normalized_message = message.lower()
    if "Read timed out" in message:
        return get_import_error_text("timeout")
    if "operation time limit" in normalized_message or "operation_time_limit" in normalized_message:
        return get_import_error_text("operation_time_limit")
    if any(marker in normalized_message for marker in (
        "failed to resolve",
        "nameresolutionerror",
        "no address associated with hostname",
        "temporary failure in name resolution",
        "name or service not known",
    )):
        return get_import_error_text("unreachable")

    return message or get_import_error_text("no_description")


def safe_format_import_error(error) -> str:
    try:
        return format_import_error(error)
    except Exception:
        try:
            message = _extract_error_message(error)
        except Exception:
            message = ""

        return str(message or "").strip() or get_import_error_text("no_description")
