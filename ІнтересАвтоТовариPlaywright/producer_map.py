import csv
import io
from pathlib import Path


# ============================================================
# Словники підстановок виробників
#
# Простий CSV, 2 колонки:
#
#     виробник на сайті ; скорочення для артикля
#
# Приклад:
#
#     DT SPARE PARTS;DT
#     DAF OE;DAF
#
# Роздільник: ";" або "," (визначається автоматично).
# Регістр і зайві пробіли в ключі не мають значення.
# Рядки, що починаються з "#", ігноруються.
#
# Файл читається при КОЖНОМУ виклику,
# тож правки в CSV діють одразу, без перезапуску.
#
# Якщо виробника немає у словнику —
# повертається виробник як є.
# ============================================================

APP_DIR = Path(__file__).resolve().parent

MARTEX_PRODUCERS_FILE = APP_DIR / "producers_martex.csv"
OPOLTRANS_PRODUCERS_FILE = APP_DIR / "producers_opoltrans.csv"


def _normalize_key(value):

    return " ".join(
        str(value or "").split()
    ).casefold()


def _read_text(path):
    """
    Excel зберігає CSV або в UTF-8 (з BOM),
    або в cp1251 — пробуємо обидва.
    """

    raw = path.read_bytes()

    for encoding in ("utf-8-sig", "cp1251"):

        try:
            return raw.decode(encoding)

        except UnicodeDecodeError:
            continue

    return raw.decode("utf-8", errors="replace")


def load_map(path):

    path = Path(path)

    if not path.exists():
        return {}

    text = _read_text(path)

    mapping = {}

    for line in text.splitlines():

        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        delimiter = ";" if ";" in stripped else ","

        row = next(
            csv.reader(
                io.StringIO(stripped),
                delimiter=delimiter
            ),
            []
        )

        if len(row) < 2:
            continue

        key = _normalize_key(row[0])
        value = str(row[1]).strip()

        if key:
            mapping[key] = value

    return mapping


def map_producer(producer, path):
    """
    Повертає скорочення виробника для артикля.

    Немає в словнику -> виробник як є.
    Порожній виробник -> "".
    """

    producer = " ".join(
        str(producer or "").split()
    )

    if not producer:
        return ""

    mapping = load_map(path)

    return mapping.get(
        _normalize_key(producer),
        producer
    )


def build_article(base, producer, path):
    """
    base + підстановка(виробник).

    Якщо виробника немає — тільки base.
    """

    base = str(base or "").strip()

    suffix = map_producer(producer, path)

    return f"{base}{suffix}"
