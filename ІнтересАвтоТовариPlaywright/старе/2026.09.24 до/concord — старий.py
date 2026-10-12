import os
import ctypes

from playwright.async_api import async_playwright
from ctypes import wintypes

CDP_URL = "http://127.0.0.1:9222"

SEARCH_URL = (
    "https://concord-shop.com/search?q="
)

SEARCH_URL_PREFIX = (
    "https://concord-shop.com/search"
)

CONCORD_URL_PREFIX = (
    "https://concord-shop.com"
)

APP_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ARTICLES_FILE = os.path.join(
    APP_DIR,
    "concord_articles.txt"
)

NAMES_FILE = os.path.join(
    APP_DIR,
    "concord_names.txt"
)


_playwright = None
_browser = None
_context = None


# ============================================================
# Browser connection
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
# Bring Edge window to foreground
# ============================================================

def bring_edge_window_to_front():

    import subprocess

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    EnumWindows = user32.EnumWindows

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM
    )

    IsWindowVisible = user32.IsWindowVisible
    IsIconic = user32.IsIconic
    GetWindowThreadProcessId = user32.GetWindowThreadProcessId

    GetForegroundWindow = user32.GetForegroundWindow
    GetCurrentThreadId = kernel32.GetCurrentThreadId

    AttachThreadInput = user32.AttachThreadInput

    SetForegroundWindow = user32.SetForegroundWindow
    BringWindowToTop = user32.BringWindowToTop
    ShowWindow = user32.ShowWindow

    SW_RESTORE = 9

    # --------------------------------------------------------
    # Знаходимо PID Edge, який слухає CDP порт 9222
    # --------------------------------------------------------

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "(Get-NetTCPConnection "
                "-LocalAddress 127.0.0.1 "
                "-LocalPort 9222 "
                "-State Listen "
                "-ErrorAction SilentlyContinue).OwningProcess"
            )
        ],
        capture_output=True,
        text=True
    )

    pid_text = result.stdout.strip()

    if not pid_text:

        return False

    try:

        browser_pid = int(
            pid_text.splitlines()[0].strip()
        )

    except ValueError:

        return False

    # --------------------------------------------------------
    # Шукаємо HWND саме цього PID
    # --------------------------------------------------------

    edge_windows = []

    def enum_callback(hwnd, lparam):

        if not IsWindowVisible(hwnd):

            return True

        window_pid = wintypes.DWORD()

        GetWindowThreadProcessId(
            hwnd,
            ctypes.byref(window_pid)
        )

        if window_pid.value == browser_pid:

            edge_windows.append(hwnd)

        return True

    EnumWindows(
        EnumWindowsProc(enum_callback),
        0
    )

    if not edge_windows:

        return False

    hwnd = edge_windows[0]

    # --------------------------------------------------------
    # Якщо Edge мінімізований —
    # повертаємо його в попередній стан.
    #
    # Якщо вже відкритий — нічого не змінюємо.
    # --------------------------------------------------------

    if IsIconic(hwnd):

        ShowWindow(
            hwnd,
            SW_RESTORE
        )

    # --------------------------------------------------------
    # Поточне foreground-вікно
    # --------------------------------------------------------

    foreground_hwnd = GetForegroundWindow()

    foreground_thread = 0

    if foreground_hwnd:

        foreground_thread = GetWindowThreadProcessId(
            foreground_hwnd,
            None
        )

    current_thread = GetCurrentThreadId()

    attached = False

    try:

        # ----------------------------------------------------
        # Під'єднуємо Python до foreground input queue.
        # Це дозволяє SetForegroundWindow() спрацювати,
        # коли перед нами зараз Excel.
        # ----------------------------------------------------

        if (
            foreground_thread
            and foreground_thread != current_thread
        ):

            attached = bool(
                AttachThreadInput(
                    current_thread,
                    foreground_thread,
                    True
                )
            )

        BringWindowToTop(
            hwnd
        )

        result = SetForegroundWindow(
            hwnd
        )

        return bool(result)

    finally:

        if attached:

            AttachThreadInput(
                current_thread,
                foreground_thread,
                False
            )
    
# ============================================================
# Search page
# ============================================================

async def get_search_page(context):

    for page in reversed(context.pages):

        try:

            url = page.url

            if url.startswith(
                "https://concord-shop.com/search"
            ):

                return page

        except Exception:
            pass

    raise RuntimeError(
        "Не знайдено відкриту сторінку пошуку Concord"
    )

# ============================================================
# Last Concord page
# ============================================================

async def get_last_concord_page(context):

    pages = context.pages

    if not pages:

        raise RuntimeError(
            "Не знайдено відкритих вкладок"
        )

    for page in reversed(pages):

        if page.url.startswith(
            "https://concord-shop.com"
        ):

            return page

    raise RuntimeError(
        "Не знайдено вкладку Concord"
    )


# ============================================================
# Search
# ============================================================

async def search(value):

    playwright, browser, context = await connect()

    try:

        # ----------------------------------------------------
        # Очищаємо старі результати
        # ----------------------------------------------------

        with open(
            ARTICLES_FILE,
            "w",
            encoding="utf-8"
        ):
            pass

        with open(
            NAMES_FILE,
            "w",
            encoding="utf-8"
        ):
            pass

        # ----------------------------------------------------
        # Знаходимо сторінку пошуку Concord
        # ----------------------------------------------------

        page = await get_search_page(context)

        # ----------------------------------------------------
        # Вводимо пошуковий запит
        # ----------------------------------------------------

        search_input = page.locator(
            "#universal-search"
        )

        await search_input.click()

        await search_input.fill(value)

        await page.locator(
            "#search-btn"
        ).click()

        await page.wait_for_load_state(
            "domcontentloaded"
        )

        await page.bring_to_front()
        
        bring_edge_window_to_front()

        return (
            f"Concord: пошук виконано — "
            f"{value}"
        )

    finally:

        await playwright.stop()


# ============================================================
# Helper: get text
# ============================================================

async def get_text(
    page,
    selector
):

    locator = page.locator(
        selector
    )

    if await locator.count() == 0:
        return ""

    return (
        await locator.first.inner_text()
    ).strip()


# ============================================================
# Get product
# ============================================================

async def get_product():

    playwright, browser, context = await connect()

    try:

        # ----------------------------------------------------
        # Беремо останню вкладку Concord
        # ----------------------------------------------------

        page = await get_last_concord_page(
            context
        )

        # ----------------------------------------------------
        # Назва товару
        # ----------------------------------------------------

        name_locator = page.locator(
            "h1.fw-bold.fs-3"
        )

        name = (
            await name_locator.inner_text()
        ).strip()

        if not name:

            raise RuntimeError(
                "На сторінці Concord "
                "не знайдено назву товару"
            )

        # ----------------------------------------------------
        # Артикль
        # ----------------------------------------------------

        article = ""

        code_block = page.locator(
            "text=Код товара"
        )

        if await code_block.count() > 0:

            text = (
                await code_block.first.inner_text()
            ).strip()

            article = text.replace(
                "Код товара",
                ""
            ).strip()

        # ----------------------------------------------------
        # Якщо артикль не знайшли —
        # шукаємо його серед тексту сторінки
        # ----------------------------------------------------

        if not article:

            page_text = await page.locator(
                "body"
            ).inner_text()

            lines = [
                line.strip()
                for line in page_text.splitlines()
                if line.strip()
            ]

            for index, line in enumerate(lines):

                if line.startswith(
                    "Код товара"
                ):

                    article = line.replace(
                        "Код товара",
                        ""
                    ).strip()

                    if (
                        not article
                        and index + 1 < len(lines)
                    ):
                        article = lines[
                            index + 1
                        ]

                    break

        if not article:

            raise RuntimeError(
                "На сторінці Concord "
                "не знайдено артикль"
            )

        # ----------------------------------------------------
        # Запис результату
        # ----------------------------------------------------

        with open(
            ARTICLES_FILE,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                article + "\n"
            )

        with open(
            NAMES_FILE,
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                name + "\n"
            )

        return (
            f"Concord: товар витягнуто — "
            f"{article} — {name}"
        )

    finally:

        await playwright.stop()


# ============================================================
# Get products
# ============================================================

async def get_products():

    playwright, browser, context = await connect()

    try:

        page = await get_search_page(context)

        products = page.locator(
            "#searchresult-v2 > .product-card-container"
        )

        count = await products.count()

        if count == 0:

            return (
                "Concord: товарів не знайдено"
            )

        articles = []
        names = []

        for index in range(count):

            product = products.nth(index)

            name_locator = product.locator(
                "h5.card-title"
            )

            name = (
                await name_locator.inner_text()
            ).strip()

            article_locator = product.locator(
                "p:has-text('Артикул:') span.fw-bold"
            )

            article = (
                await article_locator.inner_text()
            ).strip()

            if article and name:

                articles.append(article)
                names.append(name)

        if articles:

            with open(
                ARTICLES_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                for article in articles:

                    file.write(
                        article + "\n"
                    )

        if names:

            with open(
                NAMES_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                for name in names:

                    file.write(
                        name + "\n"
                    )

        return (
            f"Concord: витягнуто товарів — "
            f"{len(articles)}"
        )

    finally:

        await playwright.stop()


# ============================================================
# Get analogs
# ============================================================

async def get_analogs():

    playwright, browser, context = await connect()

    try:

        page = await get_search_page(context)

        analogs_block = page.locator(
            "#searchresult-v2 > .mt-4"
        )

        if await analogs_block.count() == 0:

            return (
                "Concord: аналогів не знайдено"
            )

        products = analogs_block.locator(
            ".product-card-container"
        )

        count = await products.count()

        if count == 0:

            return (
                "Concord: аналогів не знайдено"
            )

        articles = []
        names = []

        for index in range(count):

            product = products.nth(index)

            name_locator = product.locator(
                "h5.card-title"
            )

            name = (
                await name_locator.inner_text()
            ).strip()

            article_locator = product.locator(
                "p:has-text('Артикул:') span.fw-bold"
            )

            article = (
                await article_locator.inner_text()
            ).strip()

            if article and name:

                articles.append(article)
                names.append(name)

        if articles:

            with open(
                ARTICLES_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                for article in articles:

                    file.write(
                        article + "\n"
                    )

        if names:

            with open(
                NAMES_FILE,
                "a",
                encoding="utf-8"
            ) as file:

                for name in names:

                    file.write(
                        name + "\n"
                    )

        return (
            f"Concord: витягнуто аналогів — "
            f"{len(articles)}"
        )

    finally:

        await playwright.stop()

        
# ============================================================
# Delete last saved product
# ============================================================

async def delete_last():

    def read_lines(path):

        try:

            with open(
                path,
                "r",
                encoding="utf-8"
            ) as file:

                return file.readlines()

        except FileNotFoundError:

            return []


    articles = read_lines(
        ARTICLES_FILE
    )

    names = read_lines(
        NAMES_FILE
    )

    if not articles and not names:
        return "Concord: збережених товарів немає"

    if articles:
        articles.pop()

    if names:
        names.pop()

    with open(
        ARTICLES_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.writelines(
            articles
        )

    with open(
        NAMES_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        file.writelines(
            names
        )

    return "Concord: останній товар видалено"


# ============================================================
# Delete all saved products
# ============================================================

async def delete_all():

    with open(
        ARTICLES_FILE,
        "w",
        encoding="utf-8"
    ):
        pass

    with open(
        NAMES_FILE,
        "w",
        encoding="utf-8"
    ):
        pass

    return "Concord: всі товари видалено"        
        

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

    if action == "GET_PRODUCTS":
        return await get_products()

    if action == "GET_ANALOGS":
        return await get_analogs()

    if action == "GET_PRODUCT":
        return await get_product()
        
    if action == "DELETE_LAST":
        return await delete_last()

    if action == "DELETE_ALL":
        return await delete_all()

    return (
        f"Невідома команда Concord: "
        f"{action}"
    )
    
    