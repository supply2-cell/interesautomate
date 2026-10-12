import asyncio
from pathlib import Path
from tkinter import ttk

from browser import connect


GOOGLE_URL_PREFIX = "https://www.google.com/"

LLM_PROCESS_PROMPT_FILE = Path(__file__).with_name(
    "llm_process_prompt.txt"
)

OUTPUT_DIR = Path(__file__).with_name("product_output")

_current_name = ""
_current_oem = ""

_name_entry = None
_oem_entry = None


# ============================================================
# Google page
# ============================================================

async def get_google_llm_page(context):
    pages = list(context.pages)

    for page in pages:

        try:

            if not page.url.startswith(
                "https://www.google.com/"
            ):
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

        except Exception:
            pass

    page = await context.new_page()

    await page.goto(
        "https://www.google.com/search",
        wait_until="domcontentloaded"
    )

    return page


# ============================================================
# Process prompt
# ============================================================

def load_process_prompt(
    name,
    oem
):
    if not LLM_PROCESS_PROMPT_FILE.exists():
        raise FileNotFoundError(
            f"Не знайдено файл: "
            f"{LLM_PROCESS_PROMPT_FILE}"
        )

    template = LLM_PROCESS_PROMPT_FILE.read_text(
        encoding="utf-8"
    )

    return template.format(
        name=name,
        oem=oem
    )


# ============================================================
# LLM PROCESS
# ============================================================

async def llm_process():

    if not _current_name:

        raise ValueError(
            "LLM_PROCESS: "
            "не задано NAME."
        )

    if not _current_oem:

        raise ValueError(
            "LLM_PROCESS: "
            "не задано OEM."
        )

    prompt = load_process_prompt(
        _current_name,
        _current_oem
    )

    playwright, browser, context = await connect()

    try:

        page = await get_google_llm_page(
            context
        )

        await page.bring_to_front()

        # ----------------------------------------------------
        # Варіант 1:
        # чиста Google сторінка
        # ----------------------------------------------------

        search_input = page.locator(
            'textarea[aria-label="Пошук"]'
        )

        if await search_input.count() > 0:

            await search_input.fill(
                prompt
            )

            await search_input.press(
                "Enter"
            )

            return (
                "Google AI: "
                "запит відправлено."
            )

        # ----------------------------------------------------
        # Варіант 2:
        # Google LLM вже використовувався
        # ----------------------------------------------------

        question_input = page.locator(
            'textarea[aria-label="Поставте запитання"]'
        )

        if await question_input.count() > 0:

            await question_input.fill(
                prompt
            )

            await question_input.press(
                "Enter"
            )

            return (
                "Google LLM: "
                "запит відправлено."
            )

        raise RuntimeError(
            "Не знайдено поле "
            "Google LLM."
        )

    finally:

        await playwright.stop()

# ============================================================
# LLM EXTRACT
# ============================================================

async def llm_extract():

    playwright, browser, context = await connect()

    try:

        page = await get_google_llm_page(
            context
        )

        await page.bring_to_front()

        # ----------------------------------------------------
        # 1. Знаходимо всі main-col
        # ----------------------------------------------------

        main_cols = page.locator(
            'div[data-sfc-inited][data-container-id="main-col"]'
        )

        main_col_count = await main_cols.count()

        if main_col_count == 0:

            return (
                "Google LLM: "
                "EXTRACT — "
                "не знайдено main-col."
            )

        # ----------------------------------------------------
        # 2. Шукаємо останній main-col,
        #    всередині якого є div[data-container-id]
        # ----------------------------------------------------

        last_main_col = None
        inner_count = 0

        for i in range(
            main_col_count
        ):

            main_col = main_cols.nth(i)

            containers = main_col.locator(
                'div[data-container-id]'
            )

            count = await containers.count()

            if count > 0:

                last_main_col = main_col
                inner_count = count

        if last_main_col is None:

            return (
                "Google LLM: "
                "EXTRACT — "
                "у main-col не знайдено "
                "внутрішніх data-container-id."
            )

        # ----------------------------------------------------
        # 3. Беремо останній контейнер
        # ----------------------------------------------------

        containers = last_main_col.locator(
            'div[data-container-id]'
        )

        last_response = containers.nth(
            inner_count - 1
        )

        await last_response.wait_for(
            state="visible",
            timeout=30000
        )

        # ----------------------------------------------------
        # 4. Беремо ПЕРШИЙ DIV всередині last_response
        #
        # Саме тут знаходиться наша відповідь LLM.
        #
        # Класи типу n6owBd awi2gc не використовуємо,
        # бо вони можуть змінюватися.
        # ----------------------------------------------------

        response_block = last_response.locator(
            ":scope > div"
        ).first

        if await response_block.count() == 0:

            return (
                "Google LLM: "
                "AI_EXTRACT — "
                "у last_response "
                "не знайдено блок відповіді."
            )

        await response_block.wait_for(
            state="visible",
            timeout=30000
        )

        # ----------------------------------------------------
        # 5. Витягуємо текст ТІЛЬКИ цього div
        #
        # Службовий текст, який знаходиться після цього div
        # всередині last_response, сюди вже не потрапить.
        # ----------------------------------------------------

        response_text = await response_block.inner_text()

        response_text = (
            response_text
            .strip()
        )

        if not response_text:

            return (
                "Google AI: "
                "AI_EXTRACT — "
                "блок відповіді порожній."
            )

        # ----------------------------------------------------
        # 6. Зберігаємо сирий результат
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
        # 7. Поля
        # ----------------------------------------------------

        fields = [
            "NameRu",
            "NameUa",
            "CommentRu",
            "CommentUa",
            "Size",
        ]

        # ----------------------------------------------------
        # 8. Розбираємо відповідь
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
        # 9. Записуємо поля
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
        # 10. Результат
        # ----------------------------------------------------

        return (
            "Google AI: "
            "AI_EXTRACT — відповідь витягнуто. "
            f"main-col: {main_col_count}, "
            f"контейнерів: {inner_count}. "
            "Поля записано."
        )

    finally:

        await playwright.stop()

# ============================================================
# Data
# ============================================================

def set_data(value):

    global _current_name
    global _current_oem

    if not isinstance(
        value,
        dict
    ):

        raise ValueError(
            "Google AI AI_SET_DATA: "
            "value має бути об'єктом."
        )

    name = value.get(
        "name",
        ""
    )

    oem = value.get(
        "oem",
        ""
    )

    _current_name = str(
        name
        if name is not None
        else ""
    ).strip()

    _current_oem = str(
        oem
        if oem is not None
        else ""
    ).strip()

    update_ui_fields()


def update_ui_fields():

    if _name_entry is not None:

        _name_entry.delete(
            0,
            "end"
        )

        _name_entry.insert(
            0,
            _current_name
        )

    if _oem_entry is not None:

        _oem_entry.delete(
            0,
            "end"
        )

        _oem_entry.insert(
            0,
            _current_oem
        )


def on_name_changed(
    event=None
):

    global _current_name

    if _name_entry is not None:

        _current_name = (
            _name_entry.get()
        )


def on_oem_changed(
    event=None
):

    global _current_oem

    if _oem_entry is not None:

        _current_oem = (
            _oem_entry.get()
        )


# ============================================================
# UI
# ============================================================

def create_ui(
    parent,
    run_command
):

    frame = ttk.LabelFrame(
        parent,
        text="Google AI",
        padding=8
    )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    name_frame = ttk.Frame(
        frame
    )

    name_frame.pack(
        fill="x",
        pady=(0, 5)
    )

    ttk.Label(
        name_frame,
        text="Name:"
    ).pack(
        anchor="w"
    )

    name_entry = ttk.Entry(
        name_frame
    )

    name_entry.pack(
        fill="x"
    )

    name_entry.bind(
        "<KeyRelease>",
        on_name_changed
    )

    # --------------------------------------------------------
    # OEM
    # --------------------------------------------------------

    oem_frame = ttk.Frame(
        frame
    )

    oem_frame.pack(
        fill="x",
        pady=(0, 8)
    )

    ttk.Label(
        oem_frame,
        text="OEM:"
    ).pack(
        anchor="w"
    )

    oem_entry = ttk.Entry(
        oem_frame
    )

    oem_entry.pack(
        fill="x"
    )

    oem_entry.bind(
        "<KeyRelease>",
        on_oem_changed
    )

    global _name_entry
    global _oem_entry

    _name_entry = name_entry
    _oem_entry = oem_entry

    # --------------------------------------------------------
    # BUTTONS
    # --------------------------------------------------------

    buttons = ttk.Frame(
        frame
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

    process_button = ttk.Button(
        buttons,
        text="LLM PROCESS",
        command=lambda: run_command(
            "GOOGLE_LLM",
            "LLM_PROCESS"
        )
    )

    process_button.grid(
        row=0,
        column=0,
        padx=3,
        pady=3,
        sticky="ew"
    )

    extract_button = ttk.Button(
        buttons,
        text="LLM_EXTRACT",
        command=lambda: run_command(
            "GOOGLE_LLM",
            "LLM_EXTRACT"
        )
    )

    extract_button.grid(
        row=0,
        column=1,
        padx=3,
        pady=3,
        sticky="ew"
    )

    return frame


# ============================================================
# Command handler
# ============================================================

async def handle_command(
    command,
    value
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

    if action == "LLM_PROCESS":

        return await llm_process()

    if action == "LLM_EXTRACT":

        return await llm_extract()

    return (
        f"Невідома команда "
        f"Google LLM: {action}"
    )