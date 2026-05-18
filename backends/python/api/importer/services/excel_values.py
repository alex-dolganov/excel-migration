import re
from datetime import datetime, timedelta
from xml.etree import ElementTree


XLSX_MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
EXCEL_SERIAL_VALUE_RE = re.compile(r"^-?\d+(?:[.,]\d+)?$")
EXCEL_SERIAL_EPOCH = datetime(1899, 12, 30)
EXCEL_SERIAL_MIN = 10000
EXCEL_SERIAL_MAX = 2958465
_EXCEL_FORMAT_QUOTED_TEXT_RE = re.compile(r'"[^"]*"')
_EXCEL_FORMAT_ESCAPED_CHAR_RE = re.compile(r"\\.")
_EXCEL_FORMAT_BRACKET_RE = re.compile(r"\[(?!h+\]|m+\]|s+\])[^]]*\]", re.IGNORECASE)

_BUILTIN_XLSX_NUMBER_FORMAT_CODES = {
    14: "m/d/yy",
    15: "d-mmm-yy",
    16: "d-mmm",
    17: "mmm-yy",
    18: "h:mm AM/PM",
    19: "h:mm:ss AM/PM",
    20: "h:mm",
    21: "h:mm:ss",
    22: "m/d/yy h:mm",
    45: "mm:ss",
    46: "[h]:mm:ss",
    47: "mmss.0",
}


def parse_excel_serial_datetime_value(value) -> datetime:
    normalized_value = str(value or "").strip()
    if not normalized_value or not EXCEL_SERIAL_VALUE_RE.match(normalized_value):
        raise ValueError("Invalid Excel serial date value")

    serial_value = float(normalized_value.replace(",", "."))
    if serial_value < EXCEL_SERIAL_MIN or serial_value > EXCEL_SERIAL_MAX:
        raise ValueError("Invalid Excel serial date value")

    return EXCEL_SERIAL_EPOCH + timedelta(days=serial_value)


def parse_iso_datetime_value(value) -> datetime:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        raise ValueError("Invalid ISO date value")

    if normalized_value.endswith("Z"):
        normalized_value = f"{normalized_value[:-1]}+00:00"

    parsed_value = datetime.fromisoformat(normalized_value)
    if parsed_value.tzinfo is not None:
        return parsed_value.replace(tzinfo=None)
    return parsed_value


def _normalize_excel_number_format_code(format_code: str) -> str:
    cleaned = _EXCEL_FORMAT_QUOTED_TEXT_RE.sub("", str(format_code or ""))
    cleaned = _EXCEL_FORMAT_ESCAPED_CHAR_RE.sub("", cleaned)
    cleaned = _EXCEL_FORMAT_BRACKET_RE.sub("", cleaned)
    return cleaned.lower()


def is_excel_date_or_time_format(format_code: str) -> bool:
    normalized_format = _normalize_excel_number_format_code(format_code)
    has_date = "y" in normalized_format or "d" in normalized_format
    has_time = "h" in normalized_format or "s" in normalized_format or "am/pm" in normalized_format
    return has_date or has_time


def parse_xlsx_date_style_formats(styles_xml: bytes | None) -> dict[int, str]:
    if not styles_xml:
        return {}

    try:
        root = ElementTree.fromstring(styles_xml)
    except ElementTree.ParseError as error:
        raise ValueError("Unable to read workbook preview") from error

    custom_formats = {}
    for num_format in root.findall("main:numFmts/main:numFmt", XLSX_MAIN_NS):
        try:
            num_format_id = int(num_format.attrib.get("numFmtId"))
        except (TypeError, ValueError):
            continue
        format_code = str(num_format.attrib.get("formatCode") or "")
        if format_code:
            custom_formats[num_format_id] = format_code

    style_formats = {}
    for style_index, cell_xf in enumerate(root.findall("main:cellXfs/main:xf", XLSX_MAIN_NS)):
        try:
            num_format_id = int(cell_xf.attrib.get("numFmtId"))
        except (TypeError, ValueError):
            continue

        format_code = custom_formats.get(num_format_id) or _BUILTIN_XLSX_NUMBER_FORMAT_CODES.get(num_format_id, "")
        if format_code and is_excel_date_or_time_format(format_code):
            style_formats[style_index] = format_code

    return style_formats


def format_excel_datetime_for_preview(value: datetime, format_code: str = "") -> str:
    normalized_format = _normalize_excel_number_format_code(format_code)
    has_date = "y" in normalized_format or "d" in normalized_format
    has_time = "h" in normalized_format or "s" in normalized_format or "am/pm" in normalized_format
    has_seconds = "s" in normalized_format

    if has_date and has_time:
        return value.strftime("%d.%m.%Y %H:%M:%S" if has_seconds else "%d.%m.%Y %H:%M")
    if has_date:
        return value.strftime("%d.%m.%Y")
    return value.strftime("%H:%M:%S" if has_seconds else "%H:%M")


def normalize_xlsx_cell_value(value: str, *, cell_type: str = "", style_format: str = "") -> str:
    normalized_type = str(cell_type or "").strip().lower()
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""

    if normalized_type == "d":
        try:
            parsed_value = parse_iso_datetime_value(normalized_value)
        except ValueError:
            return normalized_value
        preview_format = style_format or ("yyyy-mm-dd hh:mm" if parsed_value.time() != datetime.min.time() else "yyyy-mm-dd")
        return format_excel_datetime_for_preview(parsed_value, preview_format)

    if style_format:
        try:
            parsed_value = parse_excel_serial_datetime_value(normalized_value)
        except ValueError:
            return normalized_value
        return format_excel_datetime_for_preview(parsed_value, style_format)

    return normalized_value
