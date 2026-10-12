from pathlib import Path
from tkinter import ttk
from playwright_app_general import compact_button, bind_universal_clipboard

import playwright_app_general
import browser


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


# ============================================================
# UI references
# ============================================================

_name_entry = None
_oem_entry = None
_root = None


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
    Numer prod.

    Наприклад:
        Numer prod.: 1997220
    """

    fullname = page.locator(
        "#product-fullname"
    )

    if await fullname.count() == 0:

        return ""

    h4 = fullname.locator(
        "xpath=.//h4[starts-with("
        "normalize-space(.), "
        "'Numer prod.:')]"
    )

    if await h4.count() == 0:

        return ""

    text = await h4.first.inner_text()

    text = " ".join(
        text.split()
    ).strip()

    prefix = "Numer prod.:"

    if prefix.lower() in text.lower():

        oem = text.split(
            ":",
            1
        )[1].strip()

    else:

        oem = ""

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

        if "Producent:" not in text:

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
    Визначає основний OEM.

    Пріоритет:

    1. Numer prod.
    2. Якщо його немає:
       шукаємо OEM за Producent.
    3. Якщо виробника немає або
       відповідного OEM не знайдено:
       беремо перший OEM таблиці.
    """

    # --------------------------------------------------------
    # 1. Прямий Numer prod.
    # --------------------------------------------------------

    direct_oem = await extract_direct_oem(
        page
    )

    if direct_oem:

        return direct_oem

    # --------------------------------------------------------
    # Витягуємо OEM-таблицю
    # --------------------------------------------------------

    oems, producers = (
        await extract_oems_and_producers(
            page
        )
    )

    # --------------------------------------------------------
    # 2. Шукаємо OEM за виробником
    # --------------------------------------------------------

    producer = await extract_direct_producer(
        page
    )

    if producer:

        producer_normalized = (
            producer.strip().casefold()
        )

        for index, table_producer in enumerate(
            producers
        ):

            table_producer_normalized = (
                table_producer
                .strip()
                .casefold()
            )

            if (
                table_producer_normalized
                and
                table_producer_normalized
                == producer_normalized
            ):

                if index < len(oems):

                    return oems[
                        index
                    ].strip()

    # --------------------------------------------------------
    # 3. Беремо перший OEM
    # --------------------------------------------------------

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
# UI update
# ============================================================

def update_product_fields(data):
    """
    Оновлює поля Opoltrans.

    Викликається через root.after(),
    тобто в основному Tkinter thread.
    """

    name = str(
        data.get("name", "")
        if isinstance(data, dict)
        else ""
    ).strip()

    oem = str(
        data.get("oem", "")
        if isinstance(data, dict)
        else ""
    ).strip()

    if _name_entry is not None:

        _name_entry.delete(
            0,
            "end"
        )

        _name_entry.insert(
            0,
            name
        )

    if _oem_entry is not None:

        _oem_entry.delete(
            0,
            "end"
        )

        _oem_entry.insert(
            0,
            oem
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

        # ----------------------------------------------------
        # Активуємо вкладку та Edge
        # ----------------------------------------------------

        await activate_page(
            page
        )

        # ----------------------------------------------------
        # Тип пошуку
        # ----------------------------------------------------

        search_type = page.locator(
            'input[name="search-type"][value="-1"]'
        )

        if await search_type.count() > 0:

            await search_type.check()

        # ----------------------------------------------------
        # Поле пошуку
        # ----------------------------------------------------

        search_input = page.locator(
            "#text-input-searcher"
        )

        await search_input.click()

        # ----------------------------------------------------
        # Людський темп введення
        # ----------------------------------------------------

        await search_input.press_sequentially(
            query,
            delay=70
        )

        # ----------------------------------------------------
        # Кнопка пошуку
        # ----------------------------------------------------

        search_button = page.locator(
            "#search-submit"
        )

        await search_button.click()

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
    Повністю витягує товар:

        Name
        supplier_code
        main OEM
        price

    Name та OEM передаються
    у UI-поля Opoltrans.

    supplier_code, OEM
    та price записуються
    у product_output.
    """

    playwright, browser_instance, context = (
        await browser.connect()
    )

    try:

        page = await get_product_page(
            context
        )

        # ----------------------------------------------------
        # Активуємо сторінку ДО взаємодії
        # ----------------------------------------------------

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

        result = {
            "name": name,
            "oem": oem_main,
            "supplier_code": supplier_code,
            "price": price
        }

        if _root is not None:

            _root.after(
                0,
                lambda data=result:
                    update_product_fields(
                        data
                    )
            )

        return result

    finally:

        await browser.disconnect(
            playwright,
            browser_instance
        )


# ============================================================
# Article MG
# ============================================================

async def make_article_mg(page):
    """
    Формує внутрішній артикль MG.

    15-02-01-0293
    ->
    1502010293MG
    """

    supplier_code = (
        await extract_supplier_code(
            page
        )
    )

    article = (
        supplier_code
        .replace("-", "")
        .strip()
        + "MG"
    )

    if not article:

        raise RuntimeError(
            "Не вдалося сформувати Артикль-MG."
        )

    save_product_output(
        "article.txt",
        article
    )

    return article


# ============================================================
# Article OEM
# ============================================================

async def make_article_oem(page):
    """
    Формує OEM-артикль.

    При наявності виробника:
        1997220DAF

    Якщо виробника немає:
        1997220
    """

    oem = await extract_main_oem(
        page
    )

    if not oem:

        raise RuntimeError(
            "Не вдалося визначити "
            "основний OEM."
        )

    producer = (
        await extract_direct_producer(
            page
        )
    )

    if producer:

        article = (
            f"{oem}{producer}"
        )

    else:

        article = oem

    article = " ".join(
        article.split()
    ).strip()

    save_product_output(
        "article.txt",
        article
    )

    return article


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
            "[OPOLTRANS] "
            "Не задано назву товару для LLM."
        )

        return

    if not oem:

        print(
            "[OPOLTRANS] "
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
# opoltrans UI
# ============================================================

def create_ui(
    parent,
    run_command
):
    """
    Створює UI Opoltrans.
    """

    global _name_entry
    global _oem_entry
    global _root

    _root = parent.winfo_toplevel()

    frame = ttk.LabelFrame(
        parent,
        text="Opoltrans",
        padding=1,
        style="Compact.TLabelframe"
    )

    # --------------------------------------------------------
    # Name
    # --------------------------------------------------------

    title_frame = ttk.Frame(
        frame,
        style="Compact.TFrame"
    )

    title_frame.pack(
        fill="x",
        pady=(0, 1)
    )

    ttk.Label(
        title_frame,
        text="На розбір - ополтранс:",
        style="Compact.TLabel"
    ).pack(
        anchor="w"
    )

    _name_entry = ttk.Entry(
        title_frame,
        style="Compact.TEntry"
    )

    _name_entry.pack(
        fill="x"
    )

    bind_universal_clipboard(
        _name_entry
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
        text="OEM Opoltrans:",
        style="Compact.TLabel"
    ).pack(
        anchor="w"
    )

    _oem_entry = ttk.Entry(
        oem_frame,
        style="Compact.TEntry"
    )

    _oem_entry.pack(
        fill="x"
    )

    bind_universal_clipboard(
        _oem_entry
    )

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
    # Search
    # --------------------------------------------------------

    search_button = compact_button(
        buttons,
        text="Пошук",
        command=lambda:
            run_command(
                "OPOLTRANS",
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
    # Get product
    # --------------------------------------------------------

    product_button = compact_button(
        buttons,
        text="Витягнути товар",
        command=lambda:
            run_command(
                "OPOLTRANS",
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
    # Article MG
    # --------------------------------------------------------

    article_mg_button = compact_button(
        buttons,
        text="Артикль-MG",
        command=lambda:
            run_command(
                "OPOLTRANS",
                "ARTICLE_MG"
            )
    )

    article_mg_button.grid(
        row=1,
        column=0,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # Article OEM
    # --------------------------------------------------------

    article_oem_button = compact_button(
        buttons,
        text="Артикль-ОЕМ",
        command=lambda:
            run_command(
                "OPOLTRANS",
                "ARTICLE_OEM"
            )
    )

    article_oem_button.grid(
        row=1,
        column=1,
        padx=1,
        pady=1,
        sticky="ew"
    )

    # --------------------------------------------------------
    # OEMs
    # --------------------------------------------------------

    oems_button = compact_button(
        buttons,
        text="Витягнути ОЕМи",
        command=lambda:
            run_command(
                "OPOLTRANS",
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
    # LLM
    # --------------------------------------------------------

    llm_button = compact_button(
        buttons,
        text="Передати Name + OEM в LLM",
        command=lambda:
            send_name_oem_to_llm(
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

            value = value.strip()

            playwright_app_general.set_query(
                value
            )

        return await search()

    # --------------------------------------------------------
    # GET PRODUCT
    # --------------------------------------------------------

    if action == "GET_PRODUCT":

        return await get_product()

    # --------------------------------------------------------
    # ARTICLE MG
    # --------------------------------------------------------

    if action == "ARTICLE_MG":

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

            return await make_article_mg(
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