import asyncio

from playwright.async_api import async_playwright


CDP_URL = "http://127.0.0.1:9222"


# ============================================================
# Target sites
# ============================================================

CONCORD_PREFIX = "https://concord-shop.com"
CONCORD_SEARCH_PREFIX = "https://concord-shop.com/search"

MARTEX_PREFIX = "https://sklep.martextruck.pl"

OPOLTRANS_PREFIX = "https://webterminal.opoltrans.com.pl"

MARTEX_SEARCH_URL = (
    "https://sklep.martextruck.pl/clientcatalogue/searchform.aspx"
)

OPOLTRANS_SEARCH_URL = (
    "https://webterminal.opoltrans.com.pl/search/v2/product?searchOption=-1"
)

CONCORD_SEARCH_URL = (
    "https://concord-shop.com/search?q="
)


# ============================================================
# Connect
# ============================================================

async def connect():

    playwright = await async_playwright().start()

    browser = await playwright.chromium.connect_over_cdp(
        CDP_URL
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
# URL helpers
# ============================================================

def is_concord_page(url):

    return url.startswith(
        CONCORD_PREFIX
    )


def is_concord_search(url):

    return url.startswith(
        CONCORD_SEARCH_PREFIX
    )


def is_martex_page(url):

    return url.startswith(
        MARTEX_PREFIX
    )


def is_opoltrans_page(url):

    return url.startswith(
        OPOLTRANS_PREFIX
    )


# ============================================================
# Prepare Concord
# ============================================================

async def prepare_concord(context):

    pages = list(context.pages)

    search_page = None
    other_pages = []

    # --------------------------------------------------------
    # Шукаємо першу search-вкладку зліва направо
    # --------------------------------------------------------

    for page in pages:

        url = page.url

        if is_concord_search(url):

            if search_page is None:

                search_page = page

            else:

                other_pages.append(page)

        elif is_concord_page(url):

            other_pages.append(page)

    # --------------------------------------------------------
    # Закриваємо зайві Concord-вкладки
    # --------------------------------------------------------

    for page in other_pages:

        try:
            await page.close()
        except Exception:
            pass

    # --------------------------------------------------------
    # Якщо search-вкладки немає — відкриваємо
    # --------------------------------------------------------

    if search_page is None:

        search_page = await context.new_page()

        await search_page.goto(
            CONCORD_SEARCH_URL,
            wait_until="domcontentloaded"
        )

    return search_page


# ============================================================
# Prepare Martex
# ============================================================

async def prepare_martex(context):

    pages = list(context.pages)

    first_page = None
    other_pages = []

    # --------------------------------------------------------
    # Просто залишаємо першу вкладку Martex.
    #
    # Нам байдуже, куди вона була перенаправлена:
    # login / logout / search / інша сторінка.
    # --------------------------------------------------------

    for page in pages:

        url = page.url

        if is_martex_page(url):

            if first_page is None:

                first_page = page

            else:

                other_pages.append(page)

    # --------------------------------------------------------
    # Закриваємо всі інші Martex-вкладки
    # --------------------------------------------------------

    for page in other_pages:

        try:
            await page.close()
        except Exception:
            pass

    # --------------------------------------------------------
    # Якщо Martex-вкладки взагалі немає —
    # відкриваємо стартову сторінку пошуку
    # --------------------------------------------------------

    if first_page is None:

        first_page = await context.new_page()

        await first_page.goto(
            MARTEX_SEARCH_URL,
            wait_until="domcontentloaded"
        )

    return first_page


# ============================================================
# Prepare Opoltrans
# ============================================================

async def prepare_opoltrans(context):

    pages = list(context.pages)

    first_page = None
    other_pages = []

    # --------------------------------------------------------
    # Так само, як Martex:
    # залишаємо першу вкладку незалежно від її URL
    # після редіректу.
    # --------------------------------------------------------

    for page in pages:

        url = page.url

        if is_opoltrans_page(url):

            if first_page is None:

                first_page = page

            else:

                other_pages.append(page)

    # --------------------------------------------------------
    # Закриваємо всі інші Opoltrans-вкладки
    # --------------------------------------------------------

    for page in other_pages:

        try:
            await page.close()
        except Exception:
            pass

    # --------------------------------------------------------
    # Якщо вкладки немає — відкриваємо пошук
    # --------------------------------------------------------

    if first_page is None:

        first_page = await context.new_page()

        await first_page.goto(
            OPOLTRANS_SEARCH_URL,
            wait_until="domcontentloaded"
        )

    return first_page


# ============================================================
# Prepare all tabs
# ============================================================

async def prepare_browser():

    playwright, browser, context = await connect()

    try:

        concord_page = await prepare_concord(
            context
        )

        martex_page = await prepare_martex(
            context
        )

        opoltrans_page = await prepare_opoltrans(
            context
        )

        # ----------------------------------------------------
        # Не закриваємо Edge.
        # Просто повертаємо інформацію для статусу.
        # ----------------------------------------------------

        return (
            "Вкладки підготовлено: "
            "Concord / Martex / Opoltrans"
        )

    finally:

        # ВАЖЛИВО:
        # browser.close() НЕ викликаємо.
        #
        # Edge повинен залишитися відкритим.
        #
        await playwright.stop()


# ============================================================
# Synchronous wrapper
# ============================================================

def prepare_browser_sync():

    return asyncio.run(
        prepare_browser()
    )