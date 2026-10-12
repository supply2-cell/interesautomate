import asyncio
import json
import os
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
from pathlib import Path

from google import genai


# ============================================================
# НАЛАШТУВАННЯ
# ============================================================

APP_DIR = Path(__file__).resolve().parent

START_PROMPT_FILE = APP_DIR / "ai_start_prompt.txt"
PROCESS_PROMPT_FILE = APP_DIR / "ai_process_prompt.txt"

STATE_FILE = APP_DIR / "ai_process.json"

# Окрема папка з результатами AI.
# Видалення цієї папки не впливає на роботу модуля.
OUTPUT_DIR = APP_DIR / "ai_output"

MODEL_NAME = "gemini-2.5-flash"

# Після N успішних AI_PROCESS створюємо нову сесію.
# 0 або менше = автоматичний restart за кількістю вимкнений.
AI_RESTART_EVERY = 20

# Якщо між AI_PROCESS минуло більше цього часу,
# наступний AI_PROCESS створить нову сесію.
# 0 або менше = timeout вимкнений.
AI_SESSION_TIMEOUT_MINUTES = 30

# Скільки разів максимум автоматично повторювати
# поточний AI_PROCESS після аварійної помилки.
MAX_AUTO_RESTART_RETRIES = 1


# ============================================================
# ГЛОБАЛЬНИЙ СТАН
# ============================================================

InputTitleAI = None
InputOEMAI = None
SessionStatusAI = None

# Gemini client.
CLIENT = None

# Поточний останній Interaction ID.
CURRENT_INTERACTION_ID = None

# Усі ID interactions поточної сесії.
#
# Це важливо:
# якщо є
#   START -> ID1
#   PROCESS1 -> ID2
#   PROCESS2 -> ID3
#
# тут будуть:
#   ID1, ID2, ID3
#
# При ротації вся ця група переноситься в cleanup queue.
CURRENT_SESSION_INTERACTION_IDS = []

# Скільки успішних AI_PROCESS виконано в поточній сесії.
AI_PROCESS_COUNT = 0

# Час останньої успішної interaction.
LAST_ACTIVITY = None

# Джерело останніх переданих Name/OEM.
CURRENT_SOURCE = ""

# Захист від одночасних AI_START / AI_PROCESS.
AI_LOCK = threading.Lock()

# Прапорець завершення.
SHUTTING_DOWN = False


# ============================================================
# JSON SCHEMA
# ============================================================

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "NamePL": {
            "type": "string"
        },
        "OEM": {
            "type": "string"
        },
        "NameUa": {
            "type": "string"
        },
        "NameRu": {
            "type": "string"
        },
        "CommentUa": {
            "type": "string"
        },
        "CommentRu": {
            "type": "string"
        },
        "Size": {
            "type": "string"
        },
        "Vehicle": {
            "type": "string"
        },
        "Year": {
            "type": "string"
        },
        "Side": {
            "type": "string"
        },
        "Position": {
            "type": "string"
        },
        "Manufacturer": {
            "type": "string"
        },
        "PartType": {
            "type": "string"
        },
        "Confidence": {
            "type": "string"
        },
        "Source": {
            "type": "string"
        },
        "NeedsSearch": {
            "type": "boolean"
        }
    },
    "required": [
        "NamePL",
        "OEM",
        "NameUa",
        "NameRu",
        "CommentUa",
        "CommentRu",
        "Size",
        "Vehicle",
        "Year",
        "Side",
        "Position",
        "Manufacturer",
        "PartType",
        "Confidence",
        "Source",
        "NeedsSearch"
    ]
}


# ============================================================
# UI
# ============================================================

def create_ui(parent, run_command):
    global InputTitleAI
    global InputOEMAI
    global SessionStatusAI

    frame = ttk.LabelFrame(parent, text="AI Process", padding=8)

    ttk.Label(frame, text="Назва:").pack(anchor="w")

    InputTitleAI = ttk.Entry(frame)
    InputTitleAI.pack(fill="x", pady=(0, 5))

    ttk.Label(frame, text="OEM:").pack(anchor="w")

    InputOEMAI = ttk.Entry(frame)
    InputOEMAI.pack(fill="x", pady=(0, 8))

    buttons = ttk.Frame(frame)
    buttons.pack(fill="x")

    btn_start = ttk.Button(
        buttons,
        text="AI_START",
        command=lambda: run_command(
            "AI_PROCESS",
            "AI_START"
        )
    )

    btn_start.grid(
        row=0,
        column=0,
        padx=(0, 3),
        pady=3,
        sticky="ew"
    )

    btn_process = ttk.Button(
        buttons,
        text="AI_PROCESS",
        command=lambda: run_command(
            "AI_PROCESS",
            "AI_PROCESS"
        )
    )

    btn_process.grid(
        row=0,
        column=1,
        padx=(3, 0),
        pady=3,
        sticky="ew"
    )

    buttons.columnconfigure(0, weight=1)
    buttons.columnconfigure(1, weight=1)

    SessionStatusAI = ttk.Label(
        frame,
        text="AI session: немає"
    )

    SessionStatusAI.pack(
        anchor="w",
        pady=(8, 0)
    )

    return frame


def _set_session_status(text):
    """
    Оновлює UI безпечним способом.
    Якщо UI ще не створений — просто нічого не робимо.
    """

    if SessionStatusAI is None:
        return

    try:
        SessionStatusAI.after(
            0,
            lambda: SessionStatusAI.config(text=text)
        )
    except Exception:
        pass


# ============================================================
# DATA INPUT
# ============================================================

def set_data(name, oem, source=""):
    """
    AI_SET_DATA.

    Тільки записує Name/OEM у поля.
    Gemini НЕ викликається.
    """

    global CURRENT_SOURCE

    name = str(name or "")
    oem = str(oem or "")
    source = str(source or "").strip().upper()

    if InputTitleAI is not None:
        InputTitleAI.delete(0, tk.END)
        InputTitleAI.insert(0, name)

    if InputOEMAI is not None:
        InputOEMAI.delete(0, tk.END)
        InputOEMAI.insert(0, oem)

    if source:
        CURRENT_SOURCE = source

    return "AI: Name/OEM отримано"


def get_data():
    name = ""
    oem = ""

    if InputTitleAI is not None:
        name = InputTitleAI.get().strip()

    if InputOEMAI is not None:
        oem = InputOEMAI.get().strip()

    return name, oem


# ============================================================
# PROMPTS
# ============================================================

def load_start_prompt():
    if not START_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Не знайдено файл стартового prompt: "
            f"{START_PROMPT_FILE}"
        )

    return START_PROMPT_FILE.read_text(
        encoding="utf-8"
    )


def load_process_prompt(source, name, oem):
    if not PROCESS_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Не знайдено файл process prompt: "
            f"{PROCESS_PROMPT_FILE}"
        )

    template = PROCESS_PROMPT_FILE.read_text(
        encoding="utf-8"
    )

    return template.format(
        source=source,
        name=name,
        oem=oem
    )


# ============================================================
# STATE FILE
# ============================================================

def empty_state():
    return {
        "current_interaction_id": None,
        "current_session_interaction_ids": [],
        "cleanup_interaction_ids": [],
        "ai_process_count": 0,
        "last_activity": None,
        "source": ""
    }


def load_state():
    """
    Безпечне читання ai_process.json.

    Якщо файл:
    - не існує;
    - пошкоджений;
    - порожній;
    - вручну видалений;

    повертаємо чистий стан.

    Тобто ai_process.json НЕ є критично необхідним
    для роботи програми.
    """

    if not STATE_FILE.exists():
        return empty_state()

    try:
        text = STATE_FILE.read_text(
            encoding="utf-8"
        ).strip()

        if not text:
            return empty_state()

        data = json.loads(text)

        if not isinstance(data, dict):
            return empty_state()

        state = empty_state()

        state["current_interaction_id"] = data.get(
            "current_interaction_id"
        )

        state["current_session_interaction_ids"] = (
            data.get(
                "current_session_interaction_ids",
                []
            )
            if isinstance(
                data.get(
                    "current_session_interaction_ids",
                    []
                ),
                list
            )
            else []
        )

        state["cleanup_interaction_ids"] = (
            data.get(
                "cleanup_interaction_ids",
                []
            )
            if isinstance(
                data.get(
                    "cleanup_interaction_ids",
                    []
                ),
                list
            )
            else []
        )

        state["ai_process_count"] = int(
            data.get(
                "ai_process_count",
                0
            ) or 0
        )

        state["last_activity"] = data.get(
            "last_activity"
        )

        state["source"] = str(
            data.get(
                "source",
                ""
            ) or ""
        )

        return state

    except Exception:
        # Пошкоджений state не повинен ламати AI.
        return empty_state()


def save_state():
    """
    Атомарне збереження state.

    Спочатку пишемо .tmp,
    потім замінюємо основний файл.

    Якщо ai_process.json видалити вручну —
    модуль просто почне з чистого стану.
    """

    state = {
        "current_interaction_id": CURRENT_INTERACTION_ID,
        "current_session_interaction_ids": list(
            CURRENT_SESSION_INTERACTION_IDS
        ),
        "cleanup_interaction_ids": list(
            cleanup_ids
        ),
        "ai_process_count": AI_PROCESS_COUNT,
        "last_activity": (
            LAST_ACTIVITY.isoformat()
            if LAST_ACTIVITY is not None
            else None
        ),
        "source": CURRENT_SOURCE
    }

    temp_file = STATE_FILE.with_suffix(
        ".json.tmp"
    )

    try:
        temp_file.write_text(
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

        os.replace(
            str(temp_file),
            str(STATE_FILE)
        )

    except Exception:
        try:
            if temp_file.exists():
                temp_file.unlink()
        except Exception:
            pass


# ============================================================
# CLEANUP QUEUE
# ============================================================

cleanup_ids = set()


def add_cleanup_ids(ids):
    """
    Додає IDs у queue на видалення.
    """

    for interaction_id in ids:
        interaction_id = str(
            interaction_id or ""
        ).strip()

        if interaction_id:
            cleanup_ids.add(
                interaction_id
            )

    save_state()


async def cleanup_interactions(ids):
    """
    Асинхронно видаляє старі interactions.

    Gemini SDK має async resource API,
    тому використовуємо client.aio.interactions.delete().
    """

    if not ids:
        return

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        return

    cleanup_client = None

    try:
        cleanup_client = genai.Client(
            api_key=api_key
        ).aio

        for interaction_id in list(ids):

            try:
                await cleanup_client.interactions.delete(
                    id=interaction_id
                )

                cleanup_ids.discard(
                    interaction_id
                )

            except Exception as error:
                # Не видаляємо ID з queue,
                # якщо сервер не дозволив видалення.
                print(
                    f"AI cleanup error "
                    f"{interaction_id}: "
                    f"{error}"
                )

        save_state()

    except Exception as error:
        print(
            f"AI cleanup initialization error: "
            f"{error}"
        )

    finally:
        if cleanup_client is not None:
            try:
                await cleanup_client.aclose()
            except Exception:
                pass


def start_cleanup_background(ids):
    """
    Запускає cleanup в окремому daemon thread.

    AI_PROCESS не чекає завершення cleanup.
    """

    ids = list(
        set(
            str(x).strip()
            for x in ids
            if str(x).strip()
        )
    )

    if not ids:
        return

    add_cleanup_ids(ids)

    def worker():
        try:
            asyncio.run(
                cleanup_interactions(ids)
            )
        except Exception as error:
            print(
                f"AI cleanup worker error: "
                f"{error}"
            )

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()


def cleanup_saved_state_on_start():
    """
    Якщо Python впав під час минулої роботи,
    ai_process.json може містити старі IDs.

    При наступному запуску вони ставляться
    на асинхронне очищення.

    Важливо:
    цей метод НЕ видаляє state-файл.
    """

    global CURRENT_INTERACTION_ID
    global CURRENT_SESSION_INTERACTION_IDS
    global AI_PROCESS_COUNT
    global LAST_ACTIVITY
    global CURRENT_SOURCE
    global cleanup_ids

    state = load_state()

    old_ids = set()

    current_id = state.get(
        "current_interaction_id"
    )

    if current_id:
        old_ids.add(
            str(current_id)
        )

    for interaction_id in state.get(
        "current_session_interaction_ids",
        []
    ):
        if interaction_id:
            old_ids.add(
                str(interaction_id)
            )

    for interaction_id in state.get(
        "cleanup_interaction_ids",
        []
    ):
        if interaction_id:
            old_ids.add(
                str(interaction_id)
            )

    # Поточний Python process НЕ відновлює
    # стару сесію.
    #
    # Це свідомо:
    # після запуску програми починаємо нову AI session.
    CURRENT_INTERACTION_ID = None
    CURRENT_SESSION_INTERACTION_IDS = []
    AI_PROCESS_COUNT = 0
    LAST_ACTIVITY = None
    CURRENT_SOURCE = ""

    cleanup_ids.clear()

    if old_ids:
        start_cleanup_background(
            old_ids
        )
    else:
        save_state()


# ============================================================
# GEMINI CLIENT
# ============================================================

def get_client():
    global CLIENT

    if CLIENT is not None:
        return CLIENT

    api_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if not api_key:
        raise RuntimeError(
            "Не знайдено змінну середовища "
            "GEMINI_API_KEY."
        )

    CLIENT = genai.Client(
        api_key=api_key
    )

    return CLIENT


# ============================================================
# TIME
# ============================================================

def parse_last_activity(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            value
        )
    except Exception:
        return None


def session_is_expired():
    if CURRENT_INTERACTION_ID is None:
        return True

    if AI_SESSION_TIMEOUT_MINUTES <= 0:
        return False

    if LAST_ACTIVITY is None:
        return False

    elapsed = datetime.now() - LAST_ACTIVITY

    return elapsed >= timedelta(
        minutes=AI_SESSION_TIMEOUT_MINUTES
    )


def restart_required_by_count():
    if AI_RESTART_EVERY <= 0:
        return False

    return AI_PROCESS_COUNT >= AI_RESTART_EVERY


# ============================================================
# SESSION MANAGEMENT
# ============================================================

async def start_ai_session():
    """
    Створює нову server-side Gemini interaction
    і відправляє ai_start_prompt.txt як перший turn.
    """

    global CURRENT_INTERACTION_ID
    global CURRENT_SESSION_INTERACTION_IDS
    global AI_PROCESS_COUNT
    global LAST_ACTIVITY

    prompt = load_start_prompt()

    client = get_client()

    interaction = await client.aio.interactions.create(
        model=MODEL_NAME,
        input=prompt,
        store=True
    )

    interaction_id = str(
        interaction.id
    ).strip()

    if not interaction_id:
        raise RuntimeError(
            "Gemini не повернув Interaction ID."
        )

    # Якщо існувала стара session,
    # її IDs передаємо на cleanup.
    old_ids = list(
        CURRENT_SESSION_INTERACTION_IDS
    )

    CURRENT_INTERACTION_ID = (
        interaction_id
    )

    CURRENT_SESSION_INTERACTION_IDS = [
        interaction_id
    ]

    AI_PROCESS_COUNT = 0

    LAST_ACTIVITY = datetime.now()

    save_state()

    _set_session_status(
        f"AI session: 0 / "
        f"{AI_RESTART_EVERY}"
    )

    if old_ids:
        start_cleanup_background(
            old_ids
        )

    return (
        "AI_START: нову сесію створено."
    )


async def rotate_ai_session():
    """
    Нова session замість старої.

    Старі interactions не видаляємо синхронно.
    Вони відправляються в background cleanup.
    """

    global CURRENT_INTERACTION_ID
    global CURRENT_SESSION_INTERACTION_IDS
    global AI_PROCESS_COUNT
    global LAST_ACTIVITY

    old_ids = list(
        CURRENT_SESSION_INTERACTION_IDS
    )

    CURRENT_INTERACTION_ID = None
    CURRENT_SESSION_INTERACTION_IDS = []
    AI_PROCESS_COUNT = 0
    LAST_ACTIVITY = None

    save_state()

    if old_ids:
        start_cleanup_background(
            old_ids
        )

    return await start_ai_session()


# ============================================================
# RESULT FILES
# ============================================================

RESULT_FIELDS = [
    "NamePL",
    "OEM",
    "NameUa",
    "NameRu",
    "CommentUa",
    "CommentRu",
    "Size",
    "Vehicle",
    "Year",
    "Side",
    "Position",
    "Manufacturer",
    "PartType",
    "Confidence",
    "Source",
    "NeedsSearch"
]


def normalize_result(result):
    """
    Гарантує, що всі поля присутні
    і мають очікуваний тип.
    """

    normalized = {}

    for field in RESULT_FIELDS:

        value = result.get(
            field,
            ""
        )

        if field == "NeedsSearch":
            if isinstance(
                value,
                bool
            ):
                normalized[field] = value
            else:
                normalized[field] = (
                    str(value)
                    .strip()
                    .lower()
                    == "true"
                )

        else:
            if value is None:
                value = ""

            normalized[field] = str(
                value
            )

    return normalized


def write_result_files(result):
    """
    Записує кожне поле в окремий TXT:

        ai_output/
            NamePL.txt
            OEM.txt
            NameUa.txt
            NameRu.txt
            CommentUa.txt
            CommentRu.txt
            ...

    Файли перезаписуються для кожної нової деталі.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    for field in RESULT_FIELDS:

        value = result.get(
            field,
            ""
        )

        if field == "NeedsSearch":
            text = (
                "true"
                if value
                else "false"
            )
        else:
            text = str(
                value or ""
            )

        target_file = (
            OUTPUT_DIR /
            f"{field}.txt"
        )

        temp_file = (
            OUTPUT_DIR /
            f"{field}.txt.tmp"
        )

        try:
            temp_file.write_text(
                text,
                encoding="utf-8"
            )

            os.replace(
                str(temp_file),
                str(target_file)
            )

        except Exception:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception:
                pass

            raise


# ============================================================
# STATUS OUTPUT
# ============================================================

def format_result_for_status(result):
    """
    Перетворює JSON result у читабельний статус.

    Без:
        {}
        ""
        JSON syntax
        True/False JSON representation

    Наприклад:

    NamePL: Zamek atrapy...
    OEM: 1997220
    NameUa: Замок капота
    ...
    NeedsSearch: ні
    """

    lines = []

    display_names = {
        "NamePL": "NamePL",
        "OEM": "OEM",
        "NameUa": "NameUa",
        "NameRu": "NameRu",
        "CommentUa": "CommentUa",
        "CommentRu": "CommentRu",
        "Size": "Size",
        "Vehicle": "Vehicle",
        "Year": "Year",
        "Side": "Side",
        "Position": "Position",
        "Manufacturer": "Manufacturer",
        "PartType": "PartType",
        "Confidence": "Confidence",
        "Source": "Source",
        "NeedsSearch": "NeedsSearch"
    }

    for field in RESULT_FIELDS:

        value = result.get(
            field,
            ""
        )

        if field == "NeedsSearch":
            value_text = (
                "так"
                if value
                else "ні"
            )
        else:
            value_text = str(
                value or ""
            )

        lines.append(
            f"{display_names[field]}: "
            f"{value_text}"
        )

    return "\n".join(
        lines
    )


# ============================================================
# AI PROCESS
# ============================================================

async def process_ai(
    source,
    name,
    oem,
    retry_after_restart=True
):
    """
    Основний AI_PROCESS.

    Логіка:

    1. Якщо session немає → START.
    2. Якщо session протухла → START.
    3. Якщо досягнуто AI_RESTART_EVERY → START.
    4. Надсилаємо process prompt.
    5. Отримуємо structured JSON.
    6. Записуємо поля у файли.
    7. Оновлюємо state.
    8. При аварії один раз робимо restart
       і повторюємо поточний PROCESS.
    """

    global CURRENT_INTERACTION_ID
    global CURRENT_SESSION_INTERACTION_IDS
    global AI_PROCESS_COUNT
    global LAST_ACTIVITY

    source = str(
        source or ""
    ).strip().upper()

    name = str(
        name or ""
    ).strip()

    oem = str(
        oem or ""
    ).strip()

    if not name:
        raise RuntimeError(
            "AI_PROCESS: поле Name порожнє."
        )

    if not oem:
        raise RuntimeError(
            "AI_PROCESS: поле OEM порожнє."
        )

    # --------------------------------------------------------
    # SESSION CHECK
    # --------------------------------------------------------

    if (
        CURRENT_INTERACTION_ID is None
        or session_is_expired()
        or restart_required_by_count()
    ):
        await start_ai_session()

    # --------------------------------------------------------
    # PROCESS PROMPT
    # --------------------------------------------------------

    process_prompt = load_process_prompt(
        source,
        name,
        oem
    )

    client = get_client()

    try:

        interaction = await client.aio.interactions.create(
            model=MODEL_NAME,
            input=process_prompt,
            previous_interaction_id=(
                CURRENT_INTERACTION_ID
            ),
            store=True,
            tools=[
                {
                    "type": "google_search"
                }
            ],
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": RESULT_SCHEMA
            }
        )

        interaction_id = str(
            interaction.id
        ).strip()

        if not interaction_id:
            raise RuntimeError(
                "Gemini не повернув Interaction ID "
                "для AI_PROCESS."
            )

        output_text = str(
            getattr(
                interaction,
                "output_text",
                ""
            ) or ""
        ).strip()

        if not output_text:
            raise RuntimeError(
                "Gemini не повернув output_text."
            )

        try:
            result = json.loads(
                output_text
            )
        except json.JSONDecodeError as error:
            raise RuntimeError(
                "Gemini повернув некоректний JSON: "
                f"{error}"
            )

        if not isinstance(
            result,
            dict
        ):
            raise RuntimeError(
                "Gemini JSON має бути object."
            )

        result = normalize_result(
            result
        )

        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        CURRENT_INTERACTION_ID = (
            interaction_id
        )

        CURRENT_SESSION_INTERACTION_IDS.append(
            interaction_id
        )

        AI_PROCESS_COUNT += 1

        LAST_ACTIVITY = datetime.now()

        # Спочатку результат у файли.
        write_result_files(
            result
        )

        # Потім state.
        save_state()

        _set_session_status(
            f"AI session: "
            f"{AI_PROCESS_COUNT} / "
            f"{AI_RESTART_EVERY}"
        )

        return result

    except Exception as error:

        # ----------------------------------------------------
        # АВАРІЙНИЙ RESTART
        # ----------------------------------------------------

        if not retry_after_restart:
            raise

        old_ids = list(
            CURRENT_SESSION_INTERACTION_IDS
        )

        CURRENT_INTERACTION_ID = None
        CURRENT_SESSION_INTERACTION_IDS = []
        AI_PROCESS_COUNT = 0
        LAST_ACTIVITY = None

        save_state()

        if old_ids:
            start_cleanup_background(
                old_ids
            )

        try:
            await start_ai_session()

        except Exception as restart_error:
            raise RuntimeError(
                "AI_PROCESS аварійно завершився, "
                "а автоматичний AI_START також "
                "не вдався.\n"
                f"Початкова помилка: {error}\n"
                f"Помилка restart: {restart_error}"
            ) from restart_error

        # Повторюємо поточний товар лише один раз.
        return await process_ai(
            source=source,
            name=name,
            oem=oem,
            retry_after_restart=False
        )


# ============================================================
# COMMAND HANDLER
# ============================================================

def handle_command(
    command,
    value
):
    """
    Основний handler модуля.

    Універсальний контракт:

        handle_command(command, value)

    Команди:

        AI_SET_DATA
        AI_START
        AI_PROCESS
    """

    action = str(
        command or ""
    ).strip().upper()

    # --------------------------------------------------------
    # AI_SET_DATA
    #
    # value очікується у вигляді:
    #
    # {
    #     "name": "...",
    #     "oem": "..."
    # }
    # --------------------------------------------------------

    if action == "AI_SET_DATA":

        if not isinstance(
            value,
            dict
        ):

            return (
                "AI_SET_DATA ERROR: "
                "value має бути JSON object."
            )

        return set_data(
            name=value.get(
                "name",
                ""
            ),
            oem=value.get(
                "oem",
                ""
            ),
            source=value.get(
                "source",
                ""
            )
        )

    # --------------------------------------------------------
    # AI_START
    # --------------------------------------------------------

    if action == "AI_START":

        with AI_LOCK:

            try:

                return asyncio.run(
                    start_ai_session()
                )

            except Exception as error:

                return (
                    "AI_START ERROR: "
                    f"{error}"
                )

    # --------------------------------------------------------
    # AI_PROCESS
    # --------------------------------------------------------

    if action == "AI_PROCESS":

        name, oem = get_data()

        if not name:

            return (
                "AI_PROCESS: "
                "поле Name порожнє"
            )

        if not oem:

            return (
                "AI_PROCESS: "
                "поле OEM порожнє"
            )

        # ----------------------------------------------------
        # Source
        #
        # Якщо source переданий у value,
        # використовуємо його.
        #
        # Інакше беремо CURRENT_SOURCE.
        # ----------------------------------------------------

        source = ""

        if isinstance(
            value,
            dict
        ):

            source = str(
                value.get(
                    "source",
                    ""
                )
            ).strip().upper()

        if not source:

            source = CURRENT_SOURCE

        with AI_LOCK:

            try:

                result = asyncio.run(
                    process_ai(
                        source=source,
                        name=name,
                        oem=oem
                    )
                )

                return (
                    "AI_PROCESS: готово\n\n"
                    + format_result_for_status(
                        result
                    )
                )

            except Exception as error:

                return (
                    "AI_PROCESS ERROR:\n"
                    f"{error}"
                )

    # --------------------------------------------------------
    # Unknown command
    # --------------------------------------------------------

    return (
        f"AI: невідома команда — "
        f"{action}"
    )


# ============================================================
# SHUTDOWN / CLEANUP
# ============================================================

def cleanup_on_shutdown():
    """
    Викликається при нормальному закритті програми.

    Не блокує GUI.

    Поточна сесія + queue відправляються
    на background cleanup.
    """

    global SHUTTING_DOWN

    if SHUTTING_DOWN:
        return

    SHUTTING_DOWN = True

    ids = set(
        CURRENT_SESSION_INTERACTION_IDS
    )

    ids.update(
        cleanup_ids
    )

    if CURRENT_INTERACTION_ID:
        ids.add(
            CURRENT_INTERACTION_ID
        )

    if ids:
        start_cleanup_background(
            ids
        )


def initialize():
    """
    Викликати один раз після завантаження модуля.

    Чистить залишені IDs після аварійного
    завершення попереднього запуску.
    """

    cleanup_saved_state_on_start()