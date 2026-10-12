from tkinter import ttk
from pathlib import Path
from playwright_app_general import compact_button, bind_universal_clipboard

import playwright_app_general
import browser


# ============================================================
# Constants
# ============================================================

MARTEX_PREFIX = (
    "https://sklep.martextruck.pl"
)

SEARCH_URL = (
    "https://sklep.martextruck.pl/"
    "clientcatalogue/searchform.aspx"
)

MARTEX_SEARCH_PAGE_PREFIXES = (
    "https://sklep.martextruck.pl/"
    "clientcatalogue/searchform.aspx",

    "https://sklep.martextruck.pl/"
    "partscatalogue/",
)

PRODUCT_OUTPUT_DIR = Path(__file__).with_name(
    "product_output"
)


# ============================================================
# UI state
# ============================================================

_name_entry = None
_oem_entry = None
_root = None


# ============================================================
# Browser / page helpers
# ============================================================

def is_search_page(url):
    """
    Визначає, чи є сторінка Martex сторінкою,
    з якої можна виконувати пошук.

    Пошук доступний з:

        /clientcatalogue/searchform.aspx

    а також з:

        /partscatalogue/

    тобто безпосередньо зі сторінки товару.
    """

    return any(
        url.startswith(prefix)
        for prefix in MARTEX_SEARCH_PAGE_PREFIXES
    )


async def prepare_browser():
    """
    Підготовка Martex при старті програми.

    Якщо вже відкрита сторінка Martex, з якої
    доступний пошук, використовуємо її.

    Це може бути:

        /clientcatalogue/searchform.aspx
        /partscatalogue/...

    Якщо такої сторінки немає —
    відкриваємо стандартну сторінку пошуку.
    """

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        martex_page = None

        for page in reversed(
            context.pages
        ):

            try:

                if is_search_page(
                    page.url
                ):

                    martex_page = page
                    break

            except Exception:

                pass

        if martex_page is None:

            martex_page = await context.new_page()

            await martex_page.goto(
                SEARCH_URL,
                wait_until="domcontentloaded"
            )

        await browser.activate_page(
            martex_page
        )

        return (
            "Martex: сторінка пошуку підготовлена"
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Page activation
# ============================================================

async def activate_page(page):
    """
    Робить вкладку Martex активною.

    Реальна логіка активації знаходиться
    в загальному browser.py.
    """

    await browser.activate_page(
        page
    )


# ============================================================
# Product output
# ============================================================

def save_product_output(
    file_name,
    value
):

    PRODUCT_OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    file = PRODUCT_OUTPUT_DIR / file_name

    file.write_text(
        str(value),
        encoding="utf-8"
    )


# ============================================================
# Search page
# ============================================================

async def get_search_page(
    context
):
    """
    Знаходить сторінку, з якої можна виконувати
    пошук Martex.

    Пріоритет — остання відкрита валідна сторінка.

    Валідними вважаються:

        /clientcatalogue/searchform.aspx
        /partscatalogue/...
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


# ============================================================
# OEM / Producer helpers
# ============================================================

def normalize_text(value):

    return " ".join(
        str(value or "").strip().casefold().split()
    )


def is_original_producer(producer):
    """
    Визначає, чи є товар оригінальним.

    Підтримує:
        OE
        OE DAF
        OE-DAF
        DAF OE
        DAF-OE
        OE ...
        ... OE
    """

    value = normalize_text(
        producer
    )

    if not value:
        return False

    normalized = (
        value
        .replace("-", " ")
        .replace("_", " ")
    )

    parts = normalized.split()

    return "oe" in parts


def normalize_original_producer(
    producer
):

    value = str(
        producer or ""
    ).strip()

    if not value:
        return ""

    value = (
        value
        .replace("-", " ")
        .replace("_", " ")
    )

    parts = [
        part
        for part in value.split()
        if part.casefold() != "oe"
    ]

    return " ".join(
        parts
    ).strip()


def producers_match(
    product_producer,
    table_producer
):
    """
    Перевіряє відповідність виробника товару
    виробнику в OEM-таблиці.

    Наприклад:

        OE DAF  <-> DAF-OE
        DAF OE  <-> DAF-OE
        DAF     <-> DAF
    """

    product = normalize_text(
        product_producer
    )

    table = normalize_text(
        table_producer
    )

    if not product or not table:
        return False

    if is_original_producer(
        product
    ):

        product = normalize_original_producer(
            product
        )

        table = normalize_original_producer(
            table
        )

    return product == table


def normalize_oem_producer(
    producer
):
    """
    Нормалізує виробника з OEM-таблиці.

    Приклади:

        DAF-OE   -> DAF
        DAF OE   -> DAF
        OE DAF   -> DAF
        OE-DAF   -> DAF

        SCANIA   -> SCANIA
        DT SPARE PARTS -> DT SPARE PARTS
    """

    value = str(
        producer or ""
    ).strip()

    if not value:
        return ""

    value = (
        value
        .replace("-", " ")
        .replace("_", " ")
    )

    parts = value.split()

    parts = [
        part
        for part in parts
        if part.casefold() != "oe"
    ]

    return " ".join(
        parts
    ).strip()


# ============================================================
# Product extraction
# ============================================================

async def get_product_page(
    context
):
    """
    Знаходить саме сторінку товару Martex.

    Ознака товарної сторінки:
        #ctl00_pagecontext_ordercontrol1_PanelArticle
    """

    for page in context.pages:

        try:

            if not page.url.startswith(
                MARTEX_PREFIX
            ):
                continue

            product_panel = page.locator(
                "#ctl00_pagecontext_ordercontrol1_PanelArticle"
            )

            if await product_panel.count() > 0:

                return page

        except Exception:

            pass

    raise RuntimeError(
        "Не знайдено сторінку товару Martex."
    )


async def extract_martex_product_article(
    page
):

    article = page.locator(
        '#ctl00_pagecontext_ordercontrol1_PanelArticle '
        '.ofpCode[itemprop="productID"]'
    )

    if await article.count() == 0:

        raise ValueError(
            "Martex: не знайдено артикул товару."
        )

    value = (
        await article.first.inner_text()
    ).strip()

    if not value:

        raise ValueError(
            "Martex: артикул товару порожній."
        )

    return value


async def extract_product_name(
    page
):

    name = page.locator(
        '#ctl00_pagecontext_ordercontrol1_PanelArticle '
        '.ofpName[itemprop="name"]'
    )

    if await name.count() == 0:

        raise ValueError(
            "Martex: не знайдено назву товару."
        )

    value = (
        await name.first.inner_text()
    ).strip()

    if not value:

        raise ValueError(
            "Martex: назва товару порожня."
        )

    return value


async def extract_product_producer(
    page
):

    panel = page.locator(
        "#ctl00_pagecontext_ordercontrol1_PanelArticle"
    )

    # --------------------------------------------------------
    # Основний варіант — ofpProducerName
    # --------------------------------------------------------

    producer = panel.locator(
        ".ofpProducerNamerow .ofpProducerName"
    )

    if await producer.count() > 0:

        value = (
            await producer.first.inner_text()
        ).strip()

        if value:
            return value

    # --------------------------------------------------------
    # Fallback — meta itemprop="brand"
    # --------------------------------------------------------

    brand = panel.locator(
        'meta[itemprop="brand"]'
    )

    if await brand.count() > 0:

        value = (
            await brand.first.get_attribute(
                "content"
            )
        )

        value = str(
            value or ""
        ).strip()

        if value:
            return value

    return ""


async def extract_product_prices(
    page
):

    prices = page.locator(
        "#ctl00_pagecontext_ordercontrol1_PanelArticle "
        ".ofpClientNetPricerow .ofpClientNetPrice"
    )

    count = await prices.count()

    if count == 0:

        raise ValueError(
            "Martex: не знайдено жодної ціни нетто."
        )

    values = []

    for i in range(count):

        text = (
            await prices.nth(i).inner_text()
        ).strip()

        text = text.split(
            "EUR",
            1
        )[0].strip()

        text = (
            text
            .replace(" ", "")
            .replace(",", ".")
        )

        try:

            values.append(
                float(text)
            )

        except ValueError:

            continue

    if not values:

        raise ValueError(
            "Martex: не вдалося розпізнати "
            "жодну ціну нетто."
        )

    return min(values)


async def extract_oems_and_producers(
    page,
    article=None,
    producer=None
):

    table = page.locator(
        "table.partmanufacturercodescontrol"
    )

    oems = []
    producers = []

    if await table.count() == 0:

        return oems, producers

    rows = table.first.locator(
        "tbody tr"
    )

    row_count = await rows.count()

    for i in range(row_count):

        row = rows.nth(i)

        producer_cell = row.locator(
            "td.mname"
        )

        oem_cell = row.locator(
            "td.mcode"
        )

        if (
            await producer_cell.count() == 0
            or await oem_cell.count() == 0
        ):

            continue

        table_producer = (
            await producer_cell.first.inner_text()
        ).strip()

        oem = (
            await oem_cell.first.inner_text()
        ).strip()

        if not oem:

            continue

        oems.append(
            oem
        )

        producers.append(
            table_producer
        )

    return oems, producers


async def extract_main_oem(
    page,
    article,
    producer
):

    oems, producers = (
        await extract_oems_and_producers(
            page
        )
    )

    article = str(
        article or ""
    ).strip()

    producer = str(
        producer or ""
    ).strip()

    if not article:

        raise ValueError(
            "Martex: неможливо визначити main OEM "
            "без артикля."
        )

    # ========================================================
    # ВИЗНАЧАЄМО ОРИГІНАЛ / НЕОРИГІНАЛ
    # ========================================================

    original = is_original_producer(
        producer
    )

    # ========================================================
    # ОРИГІНАЛЬНИЙ ТОВАР
    # ========================================================

    if original:

        for i, table_producer in enumerate(
            producers
        ):

            if not producers_match(
                producer,
                table_producer
            ):

                continue

            if i < len(oems):

                oem = str(
                    oems[i]
                ).strip()

                if oem:

                    return oem

        return article

    # ========================================================
    # НЕОРИГІНАЛЬНИЙ ТОВАР
    # ========================================================

    for i, table_producer in enumerate(
        producers
    ):

        if i >= len(oems):

            continue

        table_oem = str(
            oems[i]
        ).strip()

        table_producer_value = str(
            table_producer or ""
        ).strip()

        if not table_oem:

            continue

        if is_original_producer(
            table_producer_value
        ):

            return table_oem

    if oems:

        return str(
            oems[0]
        ).strip()

    return article


async def extract_our_product_article(
    page,
    article,
    producer
):

    article = str(
        article or ""
    ).strip()

    producer = str(
        producer or ""
    ).strip()

    if not article:

        raise ValueError(
            "Martex: порожній article."
        )

    oems, producers = (
        await extract_oems_and_producers(
            page
        )
    )

    # ========================================================
    # ОРИГІНАЛЬНИЙ ТОВАР
    # ========================================================

    if is_original_producer(
        producer
    ):

        original_producer = (
            normalize_original_producer(
                producer
            )
        )

        if not original_producer:

            return article

        for i, table_producer in enumerate(
            producers
        ):

            if i >= len(oems):

                continue

            if not producers_match(
                original_producer,
                table_producer
            ):

                continue

            oem = str(
                oems[i]
            ).strip()

            if not oem:

                continue

            return (
                f"{oem}"
                f"{original_producer}"
            )

        return (
            f"{article}"
            f"{original_producer}"
        )

    # ========================================================
    # НЕОРИГІНАЛЬНИЙ ТОВАР
    # ========================================================

    if not oems:

        return article

    # --------------------------------------------------------
    # 1. Спочатку шукаємо оригінальний OEM
    # --------------------------------------------------------

    for i, table_producer in enumerate(
        producers
    ):

        if i >= len(oems):

            continue

        if not is_original_producer(
            table_producer
        ):

            continue

        oem = str(
            oems[i]
        ).strip()

        if not oem:

            continue

        original_producer = (
            normalize_original_producer(
                table_producer
            )
        )

        if not original_producer:

            continue

        return (
            f"{oem}"
            f"{original_producer}"
        )

    # --------------------------------------------------------
    # 2. Оригінального OEM немає.
    # --------------------------------------------------------

    first_oem = str(
        oems[0]
    ).strip()

    first_producer = ""

    if producers:

        first_producer = (
            normalize_original_producer(
                producers[0]
            )
        )

    if first_oem and first_producer:

        return (
            f"{first_oem}"
            f"{first_producer}"
        )

    if first_oem:

        return first_oem

    return article


# ============================================================
# Alternative product article
# ============================================================

async def extract_product_article_with_producer(
    page,
    article,
    producer
):
    """
    Alternative article:

        supplier article + producer

    No OEM logic is applied.
    No OEM table is used.
    No producer mapping is used.

    Example:

        article  = 1997220
        producer = OE DAF

        result = 1997220OE DAF
    """

    article = str(
        article or ""
    ).strip()

    producer = str(
        producer or ""
    ).strip()

    if not article:

        raise ValueError(
            "Martex: порожній supplier article."
        )

    if not producer:

        raise ValueError(
            "Martex: порожній producer."
        )

    return (
        f"{article}"
        f"{producer}"
    )


# ============================================================
# Search
# ============================================================

async def search():

    query = playwright_app_general.get_query()

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_search_page(
            context
        )

        # Спочатку активуємо вкладку
        # і саме вікно Edge.
        await activate_page(
            page
        )

        search_input = page.locator(
            "#ctl00_box_3_tbQuickSearch"
        )

        await search_input.click()
        await search_input.press("Control+A")
        await search_input.press("Backspace")

        await search_input.press_sequentially(
            query,
            delay=70
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

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Get product - standard
# ============================================================

async def get_product():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_product_page(
            context
        )

        # Активуємо сторінку ДО взаємодії
        await activate_page(
            page
        )

        # ====================================================
        # Дані товару Martex
        # ====================================================

        supplier_code = (
            await extract_martex_product_article(
                page
            )
        )

        name = await extract_product_name(
            page
        )

        producer = (
            await extract_product_producer(
                page
            )
        )

        price = (
            await extract_product_prices(
                page
            )
        )

        # ====================================================
        # Наш внутрішній article
        # ====================================================

        article = (
            await extract_our_product_article(
                page,
                supplier_code,
                producer
            )
        )

        # ====================================================
        # Main OEM
        # ====================================================

        oem = await extract_main_oem(
            page,
            supplier_code,
            producer
        )

        # ====================================================
        # Запис результатів
        # ====================================================

        save_product_output(
            "article.txt",
            article
        )

        save_product_output(
            "price.txt",
            price
        )

        save_product_output(
            "supplier_code.txt",
            supplier_code
        )

        save_product_output(
            "oem_main.txt",
            oem
        )

        # ====================================================
        # Результат
        # ====================================================

        result = {
            "name": name,
            "oem": oem,
            "supplier_code": supplier_code,
            "article": article,
            "producer": producer,
            "price": price,
        }

        if _root is not None:

            _root.after(
                0,
                lambda data=result:
                    update_product_fields(
                        data.get(
                            "name",
                            ""
                        ),
                        data.get(
                            "oem",
                            ""
                        )
                    )
            )

        return result

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Get standard article only
# ============================================================

async def get_product_article_standard():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_product_page(
            context
        )

        # Activate page before interaction
        await activate_page(
            page
        )

        # Supplier article
        supplier_code = (
            await extract_martex_product_article(
                page
            )
        )

        # Producer
        producer = (
            await extract_product_producer(
                page
            )
        )

        # Standard internal article
        article = (
            await extract_our_product_article(
                page,
                supplier_code,
                producer
            )
        )

        # Save only article
        save_product_output(
            "article.txt",
            article
        )

        return article

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Get alternative article only
# ============================================================

async def get_product_article_producer():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_product_page(
            context
        )

        # Activate page before interaction
        await activate_page(
            page
        )

        # Supplier article
        supplier_code = (
            await extract_martex_product_article(
                page
            )
        )

        # Producer
        producer = (
            await extract_product_producer(
                page
            )
        )

        # Alternative article:
        # supplier article + producer
        article = (
            await extract_product_article_with_producer(
                page,
                supplier_code,
                producer
            )
        )

        # Save only article
        save_product_output(
            "article.txt",
            article
        )

        return article

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Extract OEMs
# ============================================================

async def extract_oems():

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_product_page(
            context
        )

        # Активуємо сторінку ДО взаємодії
        await activate_page(
            page
        )

        article = (
            await extract_martex_product_article(
                page
            )
        )

        producer = (
            await extract_product_producer(
                page
            )
        )

        oems, producers = (
            await extract_oems_and_producers(
                page,
                article=article,
                producer=producer
            )
        )

        if not oems:

            raise ValueError(
                "Martex: не знайдено жодного OEM."
            )

        # ----------------------------------------------------
        # Записуємо OEM
        # ----------------------------------------------------

        save_product_output(
            "oems.txt",
            "\n".join(oems)
        )

        # ----------------------------------------------------
        # Записуємо виробників
        # ----------------------------------------------------

        save_product_output(
            "prods.txt",
            "\n".join(producers)
        )

        return {
            "count": len(oems),
            "oems": oems,
            "producers": producers,
        }

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Update UI fields
# ============================================================

def update_product_fields(
    name="",
    oem=""
):

    if _name_entry is not None:

        _name_entry.delete(
            0,
            "end"
        )

        _name_entry.insert(
            0,
            str(name or "").strip()
        )

    if _oem_entry is not None:

        _oem_entry.delete(
            0,
            "end"
        )

        _oem_entry.insert(
            0,
            str(oem or "").strip()
        )


# ============================================================
# Send Name + OEM to LLM
# ============================================================

def send_name_oem_to_llm(
    run_command
):

    name = ""

    if _name_entry is not None:

        name = _name_entry.get().strip()

    oem = ""

    if _oem_entry is not None:

        oem = _oem_entry.get().strip()

    if not name:

        print(
            "[MARTEX] "
            "Не задано назву товару для LLM."
        )

        return

    if not oem:

        print(
            "[MARTEX] "
            "Не задано OEM для LLM."
        )

        return

    value = {
        "name": name,
        "oem": oem
    }

    run_command(
        "GOOGLE_LLM",
        "LLM_SET_DATA",
        value
    )

# ============================================================
# Martex UI
# ============================================================

def create_ui(
    parent,
    run_command
):

    global _name_entry
    global _oem_entry
    global _root

    _root = parent.winfo_toplevel()

    frame = ttk.LabelFrame(
        parent,
        text="Martex",
        padding=1,
        style="Compact.TLabelframe"
    )

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    name_frame = ttk.Frame(
        frame,
        style="Compact.TFrame"
    )

    name_frame.pack(
        fill="x",
        pady=(0, 1)
    )

    ttk.Label(
        name_frame,
        text="На розбір - Martex:",
        style="Compact.TLabel"
    ).pack(
        anchor="w"
    )

    name_entry = ttk.Entry(
        name_frame,
        style="Compact.TEntry"
    )

    name_entry.pack(
        fill="x"
    )

    bind_universal_clipboard(
        name_entry
    )

    # --------------------------------------------------------
    # OEM
    # --------------------------------------------------------

    oem_frame = ttk.Frame(
        frame,
        style="Compact.TFrame"
    )

    oem_frame.pack(
        fill="x",
        pady=(0, 1)
    )

    ttk.Label(
        oem_frame,
        text="OEM Martex:",
        style="Compact.TLabel"
    ).pack(
        anchor="w"
    )

    oem_entry = ttk.Entry(
        oem_frame,
        style="Compact.TEntry"
    )

    oem_entry.pack(
        fill="x"
    )

    bind_universal_clipboard(
        oem_entry
    )

    _name_entry = name_entry
    _oem_entry = oem_entry

    # --------------------------------------------------------
    # Buttons
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

    # --------------------------------------------------------
    # Пошук
    # --------------------------------------------------------

    search_button = compact_button(
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
            "MARTEX",
            "GET_PRODUCT"
        )
    )

    product_button.grid(
        row=0,
        column=1,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Standard article
    # --------------------------------------------------------

    standard_button = compact_button(
        buttons,
        text="Стандартний артикль",
        command=lambda: run_command(
            "MARTEX",
            "GET_PRODUCT_STANDARD"
        )
    )

    standard_button.grid(
        row=1,
        column=0,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Article + producer
    # --------------------------------------------------------

    producer_button = compact_button(
        buttons,
        text="Артикль + виробник",
        command=lambda: run_command(
            "MARTEX",
            "GET_PRODUCT_PRODUCER"
        )
    )

    producer_button.grid(
        row=1,
        column=1,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Витягнути OEMи
    # --------------------------------------------------------

    oems_button = compact_button(
        buttons,
        text="Витягнути OEMи",
        command=lambda: run_command(
            "MARTEX",
            "EXTRACT_OEMS"
        )
    )

    oems_button.grid(
        row=2,
        column=0,
        columnspan=2,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Передати Name + OEM в LLM
    # --------------------------------------------------------

    llm_button = compact_button(
        buttons,
        text="Передати Name + OEM в LLM",
        command=lambda: send_name_oem_to_llm(
            run_command
        )
    )

    llm_button.grid(
        row=3,
        column=0,
        columnspan=2,
        padx=1,
        pady=1,
        sticky="ew"
    )

    return frame

# ============================================================
# Command dispatcher
# ============================================================

async def handle_command(
    command,
    value=None
):

    action = str(
        command or ""
    ).strip().upper()

    if action == "SEARCH":

        if value is not None:

            if not isinstance(
                value,
                str
            ):

                raise ValueError(
                    "Martex SEARCH: "
                    "value має бути рядком."
                )

            value = value.strip()

            playwright_app_general.set_query(
                value
            )

        return await search()

    # --------------------------------------------------------
    # Existing standard command
    # --------------------------------------------------------

    if action == "GET_PRODUCT":

        return await get_product()

    if action == "GET_PRODUCT_STANDARD":

        return await get_product_article_standard()

    if action == "GET_PRODUCT_PRODUCER":

        return await get_product_article_producer()

    if action == "EXTRACT_OEMS":

        return await extract_oems()

    return (
        f"Невідома команда Martex: "
        f"{action}"
    )