from tkinter import ttk

from playwright.async_api import async_playwright


# ============================================================
# Constants
# ============================================================

CDP_URL = "http://127.0.0.1:9222"

MARTEX_PREFIX = (
    "https://sklep.martextruck.pl"
)

SEARCH_URL = (
    "https://sklep.martextruck.pl/"
    "clientcatalogue/searchform.aspx"
)


# ============================================================
# Browser connection
# ============================================================

async def connect():

    playwright = (
        await async_playwright().start()
    )

    browser = (
        await playwright.chromium.connect_over_cdp(
            CDP_URL
        )
    )

    if not browser.contexts:

        await playwright.stop()

        raise RuntimeError(
            "Не знайдено BrowserContext"
        )

    context = browser.contexts[0]

    return (
        playwright,
        browser,
        context
    )


# ============================================================
# Search page
# ============================================================

async def get_search_page(context):

    for page in context.pages:

        try:

            if page.url.startswith(
                MARTEX_PREFIX
            ):

                return page

        except Exception:
            pass

    page = await context.new_page()

    await page.goto(
        SEARCH_URL,
        wait_until="domcontentloaded"
    )

    return page


# ============================================================
# Search
# ============================================================

async def search(query):

    playwright, browser, context = (
        await connect()
    )

    try:

        page = await get_search_page(
            context
        )

        # ----------------------------------------------------
        # Активуємо вкладку
        # ----------------------------------------------------

        await page.bring_to_front()

        # ----------------------------------------------------
        # Поле пошуку
        # ----------------------------------------------------

        search_input = page.locator(
            "#ctl00_box_3_tbQuickSearch"
        )

        await search_input.fill(
            query
        )

        # ----------------------------------------------------
        # Кнопка пошуку
        # ----------------------------------------------------

        search_button = page.locator(
            "#ctl00_box_3_btnQuickSearch"
        )

        await search_button.click()

        return (
            f"Пошук Martex: "
            f"{query} — виконано"
        )

    finally:

        await playwright.stop()


# ============================================================
# Get product
# ============================================================

async def get_product():

    return (
        "Martex: Витягнути товар — "
        "ще не реалізовано"
    )


# ============================================================
# Martex UI
#
# Цей блок належить самому модулю Martex.
# playwright_app.py не знає, які саме кнопки тут є.
# ============================================================

def create_ui(
    parent,
    run_command
):

    frame = ttk.LabelFrame(
        parent,
        text="Martex",
        padding=8
    )

    # --------------------------------------------------------
    # Тимчасова назва товару для подальшого AI-розбору
    # --------------------------------------------------------

    title_frame = ttk.Frame(
        frame
    )

    title_frame.pack(
        fill="x",
        pady=(0, 5)
    )

    ttk.Label(
        title_frame,
        text="InputTitleMartex:"
    ).pack(
        anchor="w"
    )

    InputTitleMartex = ttk.Entry(
        title_frame
    )

    InputTitleMartex.pack(
        fill="x"
    )

    # --------------------------------------------------------
    # Кнопки
    # --------------------------------------------------------

    buttons = ttk.Frame(
        frame
    )

    buttons.pack(
        fill="x"
    )

    # --------------------------------------------------------
    # Пошук
    # --------------------------------------------------------

    search_button = ttk.Button(
        buttons,
        text="Пошук",
        command=lambda: run_command(
            "MARTEX",
            "SEARCH"
        )
    )

    search_button.grid(
        row=0,
        column=0,
        padx=3,
        pady=3,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витягнути товар
    # --------------------------------------------------------

    product_button = ttk.Button(
        buttons,
        text="Витягнути товар",
        command=lambda: run_command(
            "MARTEX",
            "GET_PRODUCT"
        )
    )

    product_button.grid(
        row=0,
        column=1,
        padx=3,
        pady=3,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Розтягуємо колонки рівномірно
    # --------------------------------------------------------

    buttons.columnconfigure(
        0,
        weight=1
    )

    buttons.columnconfigure(
        1,
        weight=1
    )

    return frame

# ============================================================
# Command dispatcher
# ============================================================

async def handle_command(command):

    action = command["command"]

    value = command["value"]

    if action == "SEARCH":

        return await search(
            value
        )

    if action == "GET_PRODUCT":

        return await get_product()

    return (
        f"Невідома команда Martex: "
        f"{action}"
    )
