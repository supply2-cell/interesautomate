from playwright.async_api import async_playwright


CDP_URL = "http://127.0.0.1:9222"

MARTEX_PREFIX = (
    "https://sklep.martextruck.pl"
)

SEARCH_URL = (
    "https://sklep.martextruck.pl/clientcatalogue/searchform.aspx"
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

        if page.url.startswith(
            MARTEX_PREFIX
        ):

            return page

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

        await page.bring_to_front()

        search_input = page.locator(
            "#ctl00_box_3_tbQuickSearch"
        )

        await search_input.fill(
            query
        )

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