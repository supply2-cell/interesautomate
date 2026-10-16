from pathlib import Path
from tkinter import ttk
from playwright_app_general import compact_button

import playwright_app_general
import browser
import producer_map


# ============================================================
# Constants
# ============================================================

OPOLTRANS_PREFIX = (
    "https://webterminal.opoltrans.com.pl"
)

SEARCH_URL = (
    "https://webterminal.opoltrans.com.pl/"
    "search/v2/product?searchOption=-1"
)

SEARCH_PAGE_PREFIXES = (
    "https://webterminal.opoltrans.com.pl/search/v2/product",
    "https://webterminal.opoltrans.com.pl/product",
    "https://webterminal.opoltrans.com.pl/login",
)

PRODUCT_OUTPUT_DIR = Path(__file__).with_name(
    "product_output"
)


# Назва/опис товару для LLM.
# GOOGLE_LLM читає його кнопкою «Забрати товар».
NAME_DESC_FILE = "name_desc_to_process.txt"


# ============================================================
# Page validation
# ============================================================

def is_search_page(url):
    """
    Визначає, чи є сторінка Opoltrans сторінкою,
    з якої можна виконувати пошук.

    Пошук доступний як на стандартній сторінці:

        /search/v2/product

    так і безпосередньо зі сторінки товару:

        /product
    """

    return any(
        url.startswith(prefix)
        for prefix in SEARCH_PAGE_PREFIXES
    )


# ============================================================
# Page activation
# ============================================================

async def activate_page(page):
    """
    Робить вкладку Opoltrans активною та
    виводить вікно Edge на передній план.

    Після цієї функції можна виконувати
    Playwright-взаємодію зі сторінкою.
    """

    await browser.activate_page(
        page
    )


# ============================================================
# Browser preparation
# ============================================================

async def prepare_browser():
    """
    Підготовка браузера для Opoltrans.

    Якщо вже існує сторінка, з якої можна
    виконувати пошук — використовуємо її.

    Це може бути:

        /search/v2/product
        /product

    Якщо такої сторінки немає — відкриваємо
    стандартну сторінку пошуку.
    """

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        search_page = None

        # ----------------------------------------------------
        # Шукаємо вже відкриту валідну сторінку
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Якщо валідної сторінки немає —
        # відкриваємо стандартний пошук
        # ----------------------------------------------------

        if search_page is None:

            search_page = await context.new_page()

            await search_page.goto(
                SEARCH_URL,
                wait_until="domcontentloaded"
            )

        # ----------------------------------------------------
        # Робимо сторінку та Edge активними
        # ----------------------------------------------------

        await activate_page(
            search_page
        )

        return (
            "Opoltrans: "
            "сторінка пошуку підготовлена"
        )

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Search page
# ============================================================

async def get_search_page(
    context
):
    """
    Знаходить існуючу вкладку Opoltrans,
    з якої доступний пошук.

    Валідними вважаються:

        /search/v2/product
        /product

    Якщо такої вкладки немає —
    відкриває стандартну сторінку пошуку.
    """

    # --------------------------------------------------------
    # Шукаємо існуючу валідну сторінку
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Якщо немає — відкриваємо пошук
    # --------------------------------------------------------

    page = await context.new_page()

    await page.goto(
        SEARCH_URL,
        wait_until="domcontentloaded"
    )

    return page


# ============================================================
# Product page
# ============================================================

async def get_product_page(
    context
):
    """
    Знаходить саме сторінку товару.

    Ознака товарної сторінки:
        #product-fullname
    """

    for page in context.pages:

        try:

            if not page.url.startswith(
                OPOLTRANS_PREFIX
            ):

                continue

            product = page.locator(
                "#product-fullname"
            )

            if await product.count() > 0:

                return page

        except Exception:

            pass

    raise RuntimeError(
        "Не знайдено сторінку товару Opoltrans."
    )


# ============================================================
# Product name
# ============================================================

async def extract_product_name(page):
    """
    Назва товару:
    #product-fullname -> h2

    Наприклад:
    Zamek atrapy DAF XF106 z linką lewy 2013r- OE
    """

    fullname = page.locator(
        "#product-fullname"
    )

    if await fullname.count() == 0:

        raise RuntimeError(
            "Не знайдено #product-fullname."
        )

    h2 = fullname.locator(
        "xpath=following-sibling::h2[1]"
    )

    if await h2.count() == 0:

        raise RuntimeError(
            "Не знайдено назву товару "
            "(#product-fullname -> h2)."
        )

    name = (
        await h2.first.inner_text()
    ).strip()

    if not name:

        raise RuntimeError(
            "Назва товару порожня."
        )

    return name


# ============================================================
# Price
# ============================================================

async def extract_price(page):

    prices = page.locator(
        "#pricetable .price-net span"
    )

    count = await prices.count()

    if count == 0:

        raise RuntimeError(
            "Не знайдено жодної Netto ціни."
        )

    values = []

    for i in range(count):

        text = await prices.nth(i).inner_text()

        text = (
            text
            .strip()
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

        raise RuntimeError(
            "Не вдалося розпізнати "
            "жодну Netto ціну."
        )

    return min(values)


# ============================================================
# Supplier code
# ============================================================

async def extract_supplier_code(page):
    """
    Витягує внутрішній артикул Symbol.

    HTML:
        <h1 id="product-fullname">
            <span>Symbol:&nbsp;</span> 15-02-01-0293
            <div ...>
        </h1>

    Потрібно отримати:
        15-02-01-0293
    """

    fullname = page.locator(
        "#product-fullname"
    )

    if await fullname.count() == 0:

        raise RuntimeError(
            "Не знайдено #product-fullname."
        )

    symbol_span = fullname.locator(
        "xpath=./span[1]"
    )

    if await symbol_span.count() == 0:

        raise RuntimeError(
            "Не знайдено перший span "
            "всередині #product-fullname."
        )

    supplier_code = await symbol_span.evaluate(
        """
        el => {
            let node = el.nextSibling;

            while (node) {
                if (node.nodeType === Node.TEXT_NODE) {
                    return node.textContent.trim();
                }

                node = node.nextSibling;
            }

            return "";
        }
        """
    )

    supplier_code = str(
        supplier_code or ""
    ).strip()

    if not supplier_code:

        raise RuntimeError(
            "Не вдалося витягнути "
            "Symbol / supplier code."
        )

    return supplier_code


# ============================================================
# Direct OEM
# ============================================================

async def extract_direct_oem(page):
    """
    Extracts the OEM from Numer prod.
    Example: KS27/32
    """

    fullname = page.locator("#product-fullname")

    if await fullname.count() == 0:
        return ""

    parent = fullname.locator("xpath=..")

    h4 = parent.locator(
        "xpath=./h4[starts-with(normalize-space(.), 'Numer prod.:')]"
    )

    if await h4.count() == 0:
        return ""

    oem_span = h4.first.locator("xpath=./span")

    if await oem_span.count() == 0:
        return ""

    # Playwright-локатори не вміють повертати текстові вузли (xpath=text()),
    # тому беремо лише прямий текст span-а, без вкладених кнопок/іконок.
    oem = await oem_span.first.evaluate(
        """el => Array.from(el.childNodes)
            .filter(n => n.nodeType === Node.TEXT_NODE)
            .map(n => n.textContent)
            .join('')"""
    )

    oem = " ".join((oem or "").split()).strip()

    if not oem:
        # запасний варіант: атрибут кнопки копіювання
        btn = oem_span.first.locator("[data-js-copyphrase-phrase]")
        if await btn.count() > 0:
            oem = (await btn.first.get_attribute("data-js-copyphrase-phrase") or "").strip()

    return oem



# ============================================================
# Direct producer
# ============================================================

async def extract_direct_producer(page):
    """
    Витягує виробника з блоку товару.
 
    Структура:
        div.mod-item-view
            └── div.content
                └── h4
                    Producent: DAF
    """
 
    content = page.locator(
        "div.mod-item-view div.content"
    )
 
    if await content.count() == 0:
 
        return ""
 
    h4_list = content.locator(
        "h4"
    )
 
    count = await h4_list.count()
 
    for i in range(count):
 
        text = await h4_list.nth(i).inner_text()
 
        text = " ".join(
            text.split()
        ).strip()
 
        if not text:
 
            continue
 
        if not text.startswith("Producent:"):
 
            continue
 
        producer = text.split(
            "Producent:",
            1
        )[1].strip()
 
        if producer:
 
            return producer
 
    return ""


# ============================================================
# OEM table
# ============================================================

async def extract_oems_and_producers(page):
    """
    Витягує всі OEM та виробників
    з таблиці OEM.

    Структура:

        td[0] — технічна/порожня колонка
        td[1] — OEM
        td[2] — Producer
    """

    oems = []
    producers = []

    rows = page.locator(
        "#tab-oem-codes-container "
        "table tbody tr"
    )

    row_count = await rows.count()

    for index in range(row_count):

        row = rows.nth(index)

        cells = row.locator(
            "td"
        )

        if await cells.count() < 3:

            continue

        oem = (
            await cells.nth(1).inner_text()
        ).strip()

        producer = (
            await cells.nth(2).inner_text()
        ).strip()

        if not oem:

            continue

        oems.append(oem)
        producers.append(producer)

    return oems, producers


# ============================================================
# Main OEM
# ============================================================

async def extract_main_oem(page):
    """
    Основний OEM (для oem_main.txt та артикля-OEM).

    Без пошуку по виробниках:

    1. Numer prod.
    2. Якщо його немає — перший OEM таблиці.
    """

    direct_oem = await extract_direct_oem(
        page
    )

    if direct_oem:

        return direct_oem

    oems, _producers = (
        await extract_oems_and_producers(
            page
        )
    )

    if oems:

        return oems[0].strip()

    return ""


# ============================================================
# Save product output
# ============================================================

def save_product_output(
    file_name,
    output_text
):

    PRODUCT_OUTPUT_DIR.mkdir(
        exist_ok=True
    )

    file = PRODUCT_OUTPUT_DIR / file_name

    file.write_text(
        str(output_text or "").strip(),
        encoding="utf-8"
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

        await activate_page(
            page
        )

        # Edge на передній план.
        browser.bring_edge_window_to_front()

        # ----------------------------------------------------
        # Тип пошуку
        # ----------------------------------------------------

        search_type = page.locator(
            'input[name="search-type"][value="-1"]'
        )

        if await search_type.count() > 0:

            await search_type.check()

        # Поле очищається повністю перед введенням.
        await browser.type_search_query(
            page,
            "#text-input-searcher",
            query
        )

        # Результатів НЕ чекаємо.
        await page.locator(
            "#search-submit"
        ).click()

        return (
            f"Пошук Opoltrans: "
            f"{query} — виконано"
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
    """
    Витягує товар:

        name           -> name_desc_to_process.txt
        main OEM       -> oem_main.txt
        supplier_code  -> supplier_code.txt
        price          -> price.txt

    GOOGLE_LLM забирає name + OEM з файлів
    кнопкою «Забрати товар».
    """

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_product_page(
            context
        )

        await activate_page(
            page
        )

        name = await extract_product_name(
            page
        )

        supplier_code = (
            await extract_supplier_code(
                page
            )
        )

        oem_main = await extract_main_oem(
            page
        )

        price = await extract_price(
            page
        )

        save_product_output(
            "supplier_code.txt",
            supplier_code
        )

        save_product_output(
            "oem_main.txt",
            oem_main
        )

        save_product_output(
            "price.txt",
            str(price).replace(
                ".",
                ","
            )
        )

        save_product_output(
            NAME_DESC_FILE,
            name
        )

        return {
            "name": name,
            "oem": oem_main,
            "supplier_code": supplier_code,
            "price": price
        }

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Articles
#
# Підстановка виробника — producers_opoltrans.csv.
# Виробника немає у словнику -> пишемо як є.
# Виробника немає взагалі    -> тільки основа.
# ============================================================

def _save_article(article):

    article = " ".join(
        str(article or "").split()
    ).strip()

    if not article:

        raise RuntimeError(
            "Не вдалося сформувати артикль."
        )

    save_product_output(
        "article.txt",
        article
    )

    return article


async def make_article_symbol(page):
    """
    Варіант 2: Symbol + виробник(підстановка).

        15-02-01-0293 + DAF -> 1502010293DAF
    """

    supplier_code = (
        await extract_supplier_code(
            page
        )
    )

    producer = await extract_direct_producer(
        page
    )

    return _save_article(
        producer_map.build_article(
            supplier_code.replace("-", ""),
            producer,
            producer_map.OPOLTRANS_PRODUCERS_FILE
        )
    )


async def make_article_oem(page):
    """
    Варіант 1: OEM + виробник(підстановка).

        1997220 + DAF -> 1997220DAF
    """

    oem = await extract_main_oem(
        page
    )

    if not oem:

        raise RuntimeError(
            "Не вдалося визначити "
            "основний OEM."
        )

    producer = await extract_direct_producer(
        page
    )

    return _save_article(
        producer_map.build_article(
            oem,
            producer,
            producer_map.OPOLTRANS_PRODUCERS_FILE
        )
    )


# ============================================================
# Extract OEMs
# ============================================================

async def handle_extract_oems(page):
    """
    Обробник кнопки "Витягнути ОЕМи".

    Витягує OEM + Producer та записує
    відповідні списки у файли.
    """

    oems, producers = (
        await extract_oems_and_producers(
            page
        )
    )

    if not oems:

        raise RuntimeError(
            "Не знайдено жодного OEM."
        )

    save_product_output(
        "oems.txt",
        "\n".join(oems)
    )

    save_product_output(
        "prods.txt",
        "\n".join(producers)
    )

    return {
        "count": len(oems),
        "oems": oems,
        "producers": producers
    }


# ============================================================
# Opoltrans UI
#
# Текстових полів немає: назва та OEM пишуться у файли
# (name_desc_to_process.txt, oem_main.txt),
# а GOOGLE_LLM забирає їх кнопкою «Забрати товар».
# ============================================================

def create_ui(
    parent,
    run_command
):

    frame = ttk.LabelFrame(
        parent,
        text="Opoltrans",
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

    buttons.columnconfigure(
        0,
        weight=1
    )

    buttons.columnconfigure(
        1,
        weight=1
    )

    layout = [
        ("Пошук", "SEARCH", 0, 0, 1),
        ("Витягнути товар", "GET_PRODUCT", 0, 1, 1),
        ("Артикль = OEM + вир.", "ARTICLE_OEM", 1, 0, 1),
        ("Артикль = Symbol + вир.", "ARTICLE_SYMBOL", 1, 1, 1),
        ("Витягнути ОЕМи", "EXTRACT_OEMS", 2, 0, 2),
    ]

    for text, command, row, column, span in layout:

        compact_button(
            buttons,
            text=text,
            command=lambda c=command: run_command(
                "OPOLTRANS",
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

    # --------------------------------------------------------
    # SEARCH
    # --------------------------------------------------------

    if action == "SEARCH":

        if value is not None:

            if not isinstance(
                value,
                str
            ):

                raise ValueError(
                    "Opoltrans SEARCH: "
                    "value має бути рядком."
                )

            playwright_app_general.set_query(
                value.strip()
            )

        return await search()

    # --------------------------------------------------------
    # GET PRODUCT
    # --------------------------------------------------------

    if action == "GET_PRODUCT":

        return await get_product()

    # --------------------------------------------------------
    # ARTICLE SYMBOL (ARTICLE_MG — стара назва для VBA)
    # --------------------------------------------------------

    if action in ("ARTICLE_SYMBOL", "ARTICLE_MG"):

        playwright, browser_instance, context = (
            await browser.connect()
        )

        try:

            page = await get_product_page(
                context
            )

            await activate_page(
                page
            )

            return await make_article_symbol(
                page
            )

        finally:

            await browser.disconnect(
                playwright,
                browser_instance
            )

    # --------------------------------------------------------
    # ARTICLE OEM
    # --------------------------------------------------------

    if action == "ARTICLE_OEM":

        playwright, browser_instance, context = (
            await browser.connect()
        )

        try:

            page = await get_product_page(
                context
            )

            await activate_page(
                page
            )

            return await make_article_oem(
                page
            )

        finally:

            await browser.disconnect(
                playwright,
                browser_instance
            )

    # --------------------------------------------------------
    # EXTRACT OEMS
    # --------------------------------------------------------

    if action == "EXTRACT_OEMS":

        playwright, browser_instance, context = (
            await browser.connect()
        )

        try:

            page = await get_product_page(
                context
            )

            await activate_page(
                page
            )

            return await handle_extract_oems(
                page
            )

        finally:

            await browser.disconnect(
                playwright,
                browser_instance
            )

    # --------------------------------------------------------
    # UNKNOWN
    # --------------------------------------------------------

    return (
        f"Невідома команда Opoltrans: "
        f"{action}"
    )