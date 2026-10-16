from pathlib import Path
import tkinter as tk
from tkinter import ttk
from playwright_app_general import compact_button, bind_universal_clipboard

import pyperclip
import browser


GOOGLE_URL_PREFIX = "https://gemini.google.com"
GOOGLE_SEARCH_URL = "https://gemini.google.com/app"

LLM_PREPARE_PROMPT_FILE = Path(__file__).with_name(
    "llm_prepare_prompt.txt"
)

LLM_PROCESS_PROMPT_FILE = Path(__file__).with_name(
    "llm_process_prompt.txt"
)

OUTPUT_DIR = Path(__file__).with_name(
    "product_output"
)

# Файли, які пишуть MARTEX / OPOLTRANS «Витягнути товар».
# Кнопка «Забрати товар» читає їх у поля Name / OEM.
PRODUCT_NAME_FILE = OUTPUT_DIR / "name_desc_to_process.txt"
PRODUCT_OEM_FILE = OUTPUT_DIR / "oem_main.txt"

# Кеш значень полів.
#
# Команди виконуються в робочих потоках, тому вони
# читають ці змінні, а не Tk-віджети напряму.
# Кеш оновлюється з полів при БУДЬ-якій зміні
# (введення, вставка мишкою, програмний запис).
_current_name = ""
_current_oem = ""

_name_var = None
_oem_var = None
_root = None


# ============================================================
# Google page
# ============================================================

def is_google_page(url):
    return str(url or "").startswith(
        GOOGLE_URL_PREFIX
    )


async def get_google_llm_page(context):

    pages = list(context.pages)

    for page in reversed(pages):

        try:

            if not is_google_page(page.url):
                continue

            search_input = page.locator(
                'textarea[aria-label="Пошук"]'
            )

            if await search_input.count() > 0:
                return page

            question_input = page.locator(
                'textarea[aria-label="Поставте запитання"]'
            )

            if await question_input.count() > 0:
                return page

            # Навіть якщо Google зараз має інший стан,
            # але це вже відкрита Google-сторінка —
            # можемо використати її.
            return page

        except Exception:
            pass

    page = await context.new_page()

    await page.goto(
        GOOGLE_SEARCH_URL,
        wait_until="domcontentloaded"
    )

    return page


# ============================================================
# Browser preparation
# ============================================================

async def prepare_browser():

    playwright, browser_instance, context = await browser.connect()

    try:

        page = await get_google_llm_page(
            context
        )

        await browser.activate_page(
            page
        )

        return (
            "Google AI: "
            "сторінка підготовлена."
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Prompt files
# ============================================================

def load_prepare_prompt():

    if not LLM_PREPARE_PROMPT_FILE.exists():

        raise FileNotFoundError(
            f"Не знайдено файл: "
            f"{LLM_PREPARE_PROMPT_FILE}"
        )

    return LLM_PREPARE_PROMPT_FILE.read_text(
        encoding="utf-8"
    )


def load_process_prompt(name, oem):

    if not LLM_PROCESS_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Не знайдено файл: {LLM_PROCESS_PROMPT_FILE}"
        )

    template = LLM_PROCESS_PROMPT_FILE.read_text(
        encoding="utf-8"
    )

    return template.format(
        name=str(name or ""),
        oem=str(oem or "")
    )


# ============================================================
# Clipboard
# ============================================================

def copy_to_clipboard(text):

    pyperclip.copy(
        str(text)
    )


# ============================================================
# LLM PREPARE
# ============================================================

async def llm_prepare():

    prompt = load_prepare_prompt()

    if not prompt.strip():

        raise ValueError(
            "LLM_PREPARE: "
            "файл llm_prepare_prompt.txt порожній."
        )

    copy_to_clipboard(
        prompt
    )

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_google_llm_page(
            context
        )

        await browser.activate_page(
            page
        )

        return (
            "Google AI: "
            "PREPARE — prompt скопійовано "
            "в буфер обміну. "
            "Вставте його в Google та натисніть Enter."
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# LLM PROCESS
# ============================================================
async def llm_process():

    prompt = load_process_prompt(
        _current_name,
        _current_oem
    )

    if not prompt.strip():

        raise ValueError(
            "LLM_PROCESS: "
            "сформований prompt порожній."
        )

    copy_to_clipboard(
        prompt
    )

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_google_llm_page(
            context
        )

        await browser.activate_page(
            page
        )

        return (
            "Google AI: "
            "PROCESS — prompt скопійовано "
            "в буфер обміну. "
            "Вставте його в Google та натисніть Enter."
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# LLM EXTRACT
# ============================================================

# ============================================================
# LLM EXTRACT
# ============================================================

async def llm_extract():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_google_llm_page(
            context
        )

        await browser.activate_page(
            page
        )

        # ----------------------------------------------------
        # 1. Знаходимо infinite-scroller
        # ----------------------------------------------------

        scroller = page.locator(
            "infinite-scroller"
        )

        scroller_count = await scroller.count()

        if scroller_count == 0:

            return (
                "Google LLM: "
                "EXTRACT — "
                "не знайдено infinite-scroller."
            )

        scroller = scroller.last

        # ----------------------------------------------------
        # 2. Беремо ОСТАННІЙ conversation-container
        # ----------------------------------------------------

        conversations = scroller.locator(
            "div.conversation-container"
        )

        conversation_count = await conversations.count()

        if conversation_count == 0:

            return (
                "Google LLM: "
                "EXTRACT — "
                "не знайдено conversation-container."
            )

        conversation = conversations.last

        await conversation.wait_for(
            state="visible",
            timeout=30000
        )

        # ----------------------------------------------------
        # 3. Беремо ОСТАННІЙ model-response
        # ----------------------------------------------------

        responses = conversation.locator(
            "model-response"
        )

        response_count = await responses.count()

        if response_count == 0:

            return (
                "Google LLM: "
                "EXTRACT — "
                "не знайдено model-response."
            )

        response = responses.last

        # ----------------------------------------------------
        # 4. Знаходимо message-content
        # ----------------------------------------------------

        message_content = response.locator(
            "message-content"
        )

        message_count = await message_content.count()

        if message_count == 0:

            return (
                "Google LLM: "
                "EXTRACT — "
                "не знайдено message-content."
            )

        message_content = message_content.last

        await message_content.wait_for(
            state="visible",
            timeout=30000
        )

        # ----------------------------------------------------
        # 5. Беремо paragraph <p>
        #
        # Саме тут знаходиться структурована відповідь:
        #
        # NameRu: ...
        # NameUa: ...
        # CommentRu: ...
        # CommentUa: ...
        # Size: ...
        #
        # source-sites / carousel сюди не беремо.
        # ----------------------------------------------------

        paragraphs = message_content.locator(
            "p"
        )

        paragraph_count = await paragraphs.count()

        if paragraph_count == 0:

            return (
                "Google LLM: "
                "EXTRACT — "
                "у message-content "
                "не знайдено p."
            )

        response_block = None

        # Шукаємо paragraph, який містить
        # очікувані поля.
        for i in range(paragraph_count):

            paragraph = paragraphs.nth(i)

            try:

                text = (
                    await paragraph.inner_text()
                ).strip()

            except Exception:

                continue

            if (
                "NameRu:" in text
                and "NameUa:" in text
                and "CommentRu:" in text
                and "CommentUa:" in text
                and "Size:" in text
            ):

                response_block = paragraph
                break

        if response_block is None:

            return (
                "Google LLM: "
                "EXTRACT — "
                "не знайдено paragraph "
                "з очікуваними полями."
            )

        # ----------------------------------------------------
        # 6. Витягуємо ТІЛЬКИ текст paragraph
        #
        # source-sites / carousel не потрапить сюди.
        # ----------------------------------------------------

        response_text = await response_block.evaluate(
            """
            element => {
                const clone = element.cloneNode(true);

                const sources = clone.querySelectorAll(
                    'sources-carousel-inline'
                );

                sources.forEach(
                    source => source.remove()
                );

                return clone.innerText.trim();
            }
            """
        )

        if not response_text:

            return (
                "Google AI: "
                "AI_EXTRACT — "
                "paragraph порожній."
            )

        # ----------------------------------------------------
        # 7. Зберігаємо сирий результат
        # ----------------------------------------------------

        OUTPUT_DIR.mkdir(
            exist_ok=True
        )

        raw_file = (
            OUTPUT_DIR
            / "google_ai_last_response.txt"
        )

        raw_file.write_text(
            response_text,
            encoding="utf-8"
        )

        # ----------------------------------------------------
        # 8. Поля
        # ----------------------------------------------------

        fields = [
            "NameRu",
            "NameUa",
            "CommentRu",
            "CommentUa",
            "Size",
        ]

        # ----------------------------------------------------
        # 9. Розбираємо відповідь
        # ----------------------------------------------------

        lines = response_text.splitlines()

        extracted = {
            field: ""
            for field in fields
        }

        current_field = None

        for line in lines:

            line = line.strip()

            if not line:
                continue

            matched_field = None

            for field in fields:

                prefix = field + ":"

                if line.startswith(
                    prefix
                ):

                    matched_field = field

                    value = line[
                        len(prefix):
                    ].strip()

                    extracted[field] = value

                    current_field = field

                    break

            if matched_field is not None:

                continue

            if (
                current_field
                and line
            ):

                if extracted[
                    current_field
                ]:

                    extracted[
                        current_field
                    ] += " " + line

                else:

                    extracted[
                        current_field
                    ] = line

        # ----------------------------------------------------
        # 10. Записуємо поля
        #
        # Якщо Size порожній:
        #
        # Size.txt = ""
        #
        # тобто порожній файл.
        # ----------------------------------------------------

        for field in fields:

            output_file = (
                OUTPUT_DIR
                / f"{field}.txt"
            )

            output_file.write_text(
                extracted[field].strip(),
                encoding="utf-8"
            )

        # ----------------------------------------------------
        # 11. Результат
        # ----------------------------------------------------

        return (
            "Google AI: "
            "AI_EXTRACT — відповідь витягнуто. "
            "Дані взято з останнього "
            "conversation-container / model-response. "
            "Поля записано."
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Data
# ============================================================

def _run_in_ui(function):
    """
    Виконує function у головному Tk-потоці.
    """

    if _root is None:

        function()
        return

    _root.after(0, function)


def _apply_fields(name, oem):
    """
    Записує значення в кеш та (асинхронно) в поля UI.
    """

    global _current_name
    global _current_oem

    _current_name = str(name or "").strip()
    _current_oem = str(oem or "").strip()

    def update():

        if _name_var is not None:
            _name_var.set(_current_name)

        if _oem_var is not None:
            _oem_var.set(_current_oem)

    _run_in_ui(update)


def set_data(value):

    if not isinstance(
        value,
        dict
    ):

        raise ValueError(
            "Google AI AI_SET_DATA: "
            "value має бути об'єктом."
        )

    _apply_fields(
        value.get("name") or "",
        value.get("oem") or ""
    )


def _read_output_file(path):

    if not path.exists():

        return ""

    return path.read_text(
        encoding="utf-8-sig"
    ).strip()


def load_product():
    """
    «Забрати товар»:

        name_desc_to_process.txt -> Name
        oem_main.txt             -> OEM
    """

    name = _read_output_file(
        PRODUCT_NAME_FILE
    )

    oem = _read_output_file(
        PRODUCT_OEM_FILE
    )

    if not name and not oem:

        return (
            "Google LLM: файли товару порожні — "
            "спочатку «Витягнути товар» у Martex / Opoltrans."
        )

    _apply_fields(name, oem)

    return (
        "Google LLM: товар забрано — "
        f"Name={name}, OEM={oem}"
    )


def clean():
    """
    Очищення UI при новому пошуку з Excel.

    Викликається playwright_app у головному потоці.
    """

    _apply_fields("", "")


def _on_name_var_changed(*_args):

    global _current_name

    if _name_var is not None:
        _current_name = _name_var.get()


def _on_oem_var_changed(*_args):

    global _current_oem

    if _oem_var is not None:
        _current_oem = _oem_var.get()


# ============================================================
# google UI
# ============================================================

def _labeled_entry(parent, label, variable):

    entry_frame = ttk.Frame(
        parent,
        style="Compact.TFrame"
    )

    entry_frame.pack(
        fill="x",
        pady=(0, 1)
    )

    ttk.Label(
        entry_frame,
        text=label,
        style="Compact.TLabel"
    ).pack(
        anchor="w"
    )

    entry = ttk.Entry(
        entry_frame,
        textvariable=variable,
        style="Compact.TEntry"
    )

    entry.pack(
        fill="x"
    )

    bind_universal_clipboard(
        entry
    )

    return entry


def create_ui(
    parent,
    run_command
):

    global _name_var
    global _oem_var
    global _root

    _root = parent.winfo_toplevel()

    frame = ttk.LabelFrame(
        parent,
        text="Google AI",
        padding=1,
        style="Compact.TLabelframe"
    )

    _name_var = tk.StringVar(
        master=frame,
        value=_current_name
    )

    _oem_var = tk.StringVar(
        master=frame,
        value=_current_oem
    )

    _name_var.trace_add(
        "write",
        _on_name_var_changed
    )

    _oem_var.trace_add(
        "write",
        _on_oem_var_changed
    )

    _labeled_entry(frame, "Name:", _name_var)
    _labeled_entry(frame, "OEM:", _oem_var)

    # --------------------------------------------------------
    # BUTTONS
    # --------------------------------------------------------

    buttons = ttk.Frame(
        frame,
        style="Compact.TFrame"
    )

    buttons.pack(
        fill="x"
    )

    buttons.columnconfigure(
        0,
        weight=1
    )

    buttons.columnconfigure(
        1,
        weight=1
    )

    layout = [
        ("Забрати товар", "LLM_LOAD_PRODUCT", 0, 0, 2),
        ("LLM PREPARE", "LLM_PREPARE", 1, 0, 1),
        ("LLM PROCESS", "LLM_PROCESS", 1, 1, 1),
        ("LLM EXTRACT", "LLM_EXTRACT", 2, 0, 2),
    ]

    for text, command, row, column, span in layout:

        compact_button(
            buttons,
            text=text,
            command=lambda c=command: run_command(
                "GOOGLE_LLM",
                c
            )
        ).grid(
            row=row,
            column=column,
            columnspan=span,
            padx=1,
            pady=1,
            sticky="ew"
        )

    return frame


# ============================================================
# Command handler
# ============================================================

async def handle_command(
    command,
    value=None
):

    action = str(
        command or ""
    ).strip().upper()

    if action == "LLM_SET_DATA":

        set_data(
            value
        )

        return (
            "Google LLM: "
            "отримано "
            f"Name={_current_name}, "
            f"OEM={_current_oem}"
        )

    if action == "LLM_LOAD_PRODUCT":

        return load_product()

    if action == "LLM_PREPARE":

        return await llm_prepare()

    if action == "LLM_PROCESS":

        return await llm_process()

    if action == "LLM_EXTRACT":

        return await llm_extract()

    return (
        f"Невідома команда "
        f"Google LLM: {action}"
    )