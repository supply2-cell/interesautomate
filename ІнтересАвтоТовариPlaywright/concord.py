import os
from pathlib import Path
from tkinter import ttk
from playwright_app_general import compact_button

import playwright_app_general
import browser


# ============================================================
# Constants
# ============================================================

SEARCH_URL = (
    "https://concord-shop.com/search?q="
)

SEARCH_PAGE_PREFIXES = (
    "https://concord-shop.com/search",
    "https://concord-shop.com/shop/product",
)

CONCORD_URL_PREFIX = (
    "https://concord-shop.com"
)

PRODUCT_OUTPUT_DIR = Path(__file__).with_name(
    "product_output"
)


# ============================================================
# Paths
# ============================================================

ARTICLES_FILE = os.path.join(
    PRODUCT_OUTPUT_DIR,
    "concord_articles.txt"
)

NAMES_FILE = os.path.join(
    PRODUCT_OUTPUT_DIR,
    "concord_names.txt"
)


# ============================================================
# Browser / pages
# ============================================================

def is_search_page(url):
    return any(
        str(url or "").startswith(prefix)
        for prefix in SEARCH_PAGE_PREFIXES
    )


async def prepare_browser():
    """
    Підготовка Concord при старті програми.

    Валідними сторінками для пошуку є:

        /search
        /shop/product

    Якщо одна з них уже відкрита —
    використовуємо її.

    Якщо ні —
    відкриваємо /search.
    """

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        search_page = None

        for page in reversed(
            context.pages
        ):

            try:

                if is_search_page(
                    page.url
                ):

                    search_page = page
                    break

            except Exception:

                pass

        if search_page is None:

            search_page = await context.new_page()

            await search_page.goto(
                SEARCH_URL,
                wait_until="domcontentloaded"
            )

        await browser.activate_page(
            search_page
        )

        return (
            "Concord: "
            "Search вкладка підготовлена"
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


async def activate_page(page):

    await browser.activate_page(
        page
    )


async def get_search_page(
    context
):
    """
    Повертає останню сторінку Concord,
    на якій доступний пошук.

    Валідні:

        /search
        /shop/product
    """

    for page in reversed(
        context.pages
    ):

        try:

            if is_search_page(
                page.url
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


async def get_last_concord_page(
    context
):
    """
    Повертає останню відкриту
    сторінку Concord.
    """

    pages = context.pages

    if not pages:

        raise RuntimeError(
            "Не знайдено відкритих вкладок"
        )

    for page in reversed(
        pages
    ):

        try:

            if page.url.startswith(
                CONCORD_URL_PREFIX
            ):

                return page

        except Exception:

            pass

    raise RuntimeError(
        "Не знайдено вкладку Concord"
    )


# ============================================================
# Search
# ============================================================

async def search():

    query = (
        playwright_app_general.get_query()
    )

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        # ----------------------------------------------------
        # Очищаємо старі результати
        # ----------------------------------------------------

        PRODUCT_OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

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

        page = await get_search_page(
            context
        )

        await activate_page(
            page
        )

        # ----------------------------------------------------
        # Виносимо Edge на передній план
        # ----------------------------------------------------

        browser.bring_edge_window_to_front()

        # ----------------------------------------------------
        # Вводимо Query
        # ----------------------------------------------------

        await browser.type_search_query(
            page,
            "#universal-search",
            query
        )

        # ----------------------------------------------------
        # Запускаємо пошук.
        #
        # Результатів НЕ чекаємо — далі користувач
        # працює зі сторінкою сам.
        # ----------------------------------------------------

        await page.locator(
            "#search-btn"
        ).click()

        return (
            f"Concord: пошук виконано — "
            f"{query}"
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )

# ============================================================
# Get product
# ============================================================

async def get_product():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        # ----------------------------------------------------
        # Беремо останню вкладку Concord
        # ----------------------------------------------------

        page = await get_last_concord_page(
            context
        )

        await activate_page(
            page
        )

        # ----------------------------------------------------
        # Назва товару
        # ----------------------------------------------------

        name_locator = page.locator(
            "h1.fw-bold.fs-3"
        )

        if await name_locator.count() == 0:

            raise RuntimeError(
                "На сторінці Concord "
                "не знайдено назву товару"
            )

        name = (
            await name_locator.first.inner_text()
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

            for index, line in enumerate(
                lines
            ):

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

        PRODUCT_OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

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

        await browser.disconnect(
            playwright,
            browser_instance
        )

# ============================================================
# Get products
# ============================================================

async def get_products():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_search_page(
            context
        )

        await activate_page(
            page
        )

        # ----------------------------------------------------
        # Виносимо Edge на передній план
        # ----------------------------------------------------

        # browser.bring_edge_window_to_front()

        products = page.locator(
            "#searchresult-v2 > "
            ".product-card-container"
        )

        count = await products.count()

        if count == 0:

            return (
                "Concord: товарів не знайдено"
            )

        articles = []
        names = []

        for index in range(
            count
        ):

            product = products.nth(
                index
            )

            name_locator = product.locator(
                "h5.card-title"
            )

            name = (
                await name_locator.inner_text()
            ).strip()

            article_locator = product.locator(
                "p:has-text('Артикул:') "
                "span.fw-bold"
            )

            article = (
                await article_locator.inner_text()
            ).strip()

            if article and name:

                articles.append(
                    article
                )

                names.append(
                    name
                )

        # ----------------------------------------------------
        # Записуємо артикули построчно
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Записуємо назви построчно
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Формуємо рядок артикулів
        # ----------------------------------------------------

        articles_text = ", ".join(
            f'"{article}"'
            for article in articles
        )

        return (
            f"Concord: витягнуто товарів — "
            f"{len(articles)}\n"
            f"Артикули: {articles_text}"
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Get analogs
# ============================================================

async def get_analogs():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_search_page(
            context
        )

        await activate_page(
            page
        )

        # ----------------------------------------------------
        # Виносимо Edge на передній план
        # ----------------------------------------------------

        # browser.bring_edge_window_to_front()

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

        for index in range(
            count
        ):

            product = products.nth(
                index
            )

            name_locator = product.locator(
                "h5.card-title"
            )

            name = (
                await name_locator.inner_text()
            ).strip()

            article_locator = product.locator(
                "p:has-text('Артикул:') "
                "span.fw-bold"
            )

            article = (
                await article_locator.inner_text()
            ).strip()

            if article and name:

                articles.append(
                    article
                )

                names.append(
                    name
                )

        # ----------------------------------------------------
        # Записуємо артикули построчно
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Записуємо назви построчно
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Формуємо рядок артикулів
        # ----------------------------------------------------

        articles_text = ", ".join(
            f'"{article}"'
            for article in articles
        )

        return (
            f"Concord: витягнуто аналогів — "
            f"{len(articles)}\n"
            f"Артикули: {articles_text}"
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Delete last saved product
# ============================================================

async def delete_last():

    def read_lines(
        path
    ):

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

        return (
            "Concord: збережених товарів немає"
        )

    if articles:

        articles.pop()

    if names:

        names.pop()

    PRODUCT_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

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

    return (
        "Concord: останній товар видалено"
    )


# ============================================================
# Delete all saved products
# ============================================================

async def delete_all():

    PRODUCT_OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

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

    return (
        "Concord: всі товари видалено"
    )

# ============================================================
# Concord UI
#
# Цей блок належить самому модулю Concord.
# playwright_app.py не знає, які саме кнопки тут є.
# ============================================================

def create_ui(
    parent,
    run_command
):

    frame = ttk.LabelFrame(
        parent,
        text="Concord",
        padding=1,
        style="Compact.TLabelframe"
    )

    buttons = ttk.Frame(
        frame,
        style="Compact.TFrame"
    )

    buttons.pack(
        fill="x"
    )

    # --------------------------------------------------------
    # Пошук
    # --------------------------------------------------------

    search_button = compact_button(
        buttons,
        text="Пошук",
        command=lambda: run_command(
            "CONCORD",
            "SEARCH"
        )
    )

    search_button.grid(
        row=0,
        column=0,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витягнути товари
    # --------------------------------------------------------

    products_button = compact_button(
        buttons,
        text="Витягнути товари",
        command=lambda: run_command(
            "CONCORD",
            "GET_PRODUCTS"
        )
    )

    products_button.grid(
        row=0,
        column=1,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витягнути аналоги
    # --------------------------------------------------------

    analogs_button = compact_button(
        buttons,
        text="Витягнути аналоги",
        command=lambda: run_command(
            "CONCORD",
            "GET_ANALOGS"
        )
    )

    analogs_button.grid(
        row=0,
        column=2,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витягнути товар
    # --------------------------------------------------------

    product_button = compact_button(
        buttons,
        text="Витягнути товар",
        command=lambda: run_command(
            "CONCORD",
            "GET_PRODUCT"
        )
    )

    product_button.grid(
        row=1,
        column=0,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витерти останній
    # --------------------------------------------------------

    delete_last_button = compact_button(
        buttons,
        text="Витерти останній",
        command=lambda: run_command(
            "CONCORD",
            "DELETE_LAST"
        )
    )

    delete_last_button.grid(
        row=1,
        column=1,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витерти всі
    # --------------------------------------------------------

    delete_all_button = compact_button(
        buttons,
        text="Витерти всі",
        command=lambda: run_command(
            "CONCORD",
            "DELETE_ALL"
        )
    )

    delete_all_button.grid(
        row=1,
        column=2,
        padx=1,
        pady=1,
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

    buttons.columnconfigure(
        2,
        weight=1
    )

    return frame


# ============================================================
# Command dispatcher
#
# ЄДИНИЙ універсальний контракт:
#
#     handle_command(command, value=None)
#
# value може бути будь-яким типом JSON.
# ============================================================

async def handle_command(
    command,
    value=None
):

    action = str(
        command or ""
    ).strip().upper()

    if action == "SEARCH":

        # ----------------------------------------------------
        # Якщо SEARCH прийшов зовні,
        # спочатку записуємо value в GENERAL.
        # ----------------------------------------------------

        if value is not None:

            if not isinstance(
                value,
                str
            ):

                raise ValueError(
                    "Concord SEARCH: "
                    "value має бути рядком."
                )

            value = value.strip()

            playwright_app_general.set_query(
                value
            )

        # ----------------------------------------------------
        # Сам пошук завжди бере Query
        # з General.
        # ----------------------------------------------------

        return await search()

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