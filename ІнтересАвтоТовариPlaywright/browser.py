import asyncio
import subprocess
import ctypes
import time
import psutil

user32 = ctypes.windll.user32
user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
user32.GetWindowThreadProcessId.restype = ctypes.c_ulong
user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
user32.IsWindowVisible.restype = ctypes.c_bool
user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
user32.GetWindowTextLengthW.restype = ctypes.c_int

from playwright.async_api import async_playwright
from playwright_stealth import Stealth


# ============================================================
# CDP
# ============================================================

CDP_URL = "http://127.0.0.1:9222"


# ============================================================
# Connect
# ============================================================

async def connect():
    """
    Підключається до вже запущеного Edge/Chromium
    через CDP.

    browser.py НЕ відкриває жодних сторінок.

    browser.py НЕ визначає, які сайти потрібні
    конкретним модулям.

    Повертає:

        playwright
        browser
        context
    """

    playwright = await async_playwright().start()

    try:

        browser = await playwright.chromium.connect_over_cdp(
            CDP_URL
        )

    except Exception:

        await playwright.stop()

        raise

    if not browser.contexts:

        await playwright.stop()

        raise RuntimeError(
            "Не знайдено BrowserContext"
        )

    context = browser.contexts[0]

    # --------------------------------------------------------
    # Playwright Stealth
    #
    # Stealth застосовується централізовано.
    #
    # Модулі не повинні дублювати цю логіку.
    # --------------------------------------------------------

    stealth = Stealth()

    await stealth.apply_stealth_async(
        context
    )

    return (
        playwright,
        browser,
        context
    )

# ============================================================
# Edge window activation
# ============================================================

class WINDOWPLACEMENT(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_uint),
        ("flags", ctypes.c_uint),
        ("showCmd", ctypes.c_uint),
        ("ptMinPosition", ctypes.c_long * 2),
        ("ptMaxPosition", ctypes.c_long * 2),
        ("rcNormalPosition", ctypes.c_long * 4),
    ]


user32.GetWindowPlacement.argtypes = [ctypes.c_void_p, ctypes.POINTER(WINDOWPLACEMENT)]
user32.GetWindowPlacement.restype = ctypes.c_bool
user32.IsIconic.argtypes = [ctypes.c_void_p]
user32.IsIconic.restype = ctypes.c_bool

SW_SHOWMAXIMIZED = 3
SW_SHOW = 5
SW_MINIMIZE = 6
SW_RESTORE = 9
WPF_RESTORETOMAXIMIZED = 0x0002


def restore_window_keep_state(hwnd):
    """
    Показує вікно, НЕ змінюючи його розмір:

        - не згорнуте          -> нічого не чіпаємо
                                  (розгорнуте лишається розгорнутим);
        - згорнуте з maximized -> розгортаємо на весь екран;
        - згорнуте з normal    -> повертаємо звичайний розмір.

    Раніше завжди викликався SW_RESTORE, який
    розгорнуте вікно перетворював на маленьке.
    """

    if not user32.IsIconic(hwnd):
        return

    placement = WINDOWPLACEMENT()
    placement.length = ctypes.sizeof(WINDOWPLACEMENT)

    if (
        user32.GetWindowPlacement(hwnd, ctypes.byref(placement))
        and placement.flags & WPF_RESTORETOMAXIMIZED
    ):
        user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
    else:
        user32.ShowWindow(hwnd, SW_RESTORE)


def minimize_excel():
    """Minimize the active foreground window if it belongs to Excel."""
    try:
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return

        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        # Згортаємо ТІЛЬКИ Excel. Раніше згортався будь-який
        # активний застосунок (включно з самим Playwright-вікном).
        if psutil.Process(pid.value).name().lower() != "excel.exe":
            return

        user32.ShowWindow(hwnd, SW_MINIMIZE)
    except Exception:
        pass


def get_edge_pids(port=9222):
    """
    Finds the main browser process and all child/parent process PIDs 
    associated with the CDP port.
    """
    pids = set()
    for conn in psutil.net_connections(kind="tcp"):
        try:
            if conn.laddr and conn.laddr.port == port and conn.pid:
                pids.add(conn.pid)
                # Expand process tree (parent & children)
                proc = psutil.Process(conn.pid)
                pids.add(proc.pid)
                for child in proc.children(recursive=True):
                    pids.add(child.pid)
                if proc.parent():
                    pids.add(proc.parent().pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def bring_edge_window_to_front():
    minimize_excel()
    time.sleep(0.1)

    try:
        edge_pids = get_edge_pids(9222)
        target_hwnd = None

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p
        )

        def enum_callback(hwnd, lparam):
            nonlocal target_hwnd

            try:
                # 1. Must be a visible window
                if not user32.IsWindowVisible(hwnd):
                    return True

                # 2. Main browser windows always have text length > 0
                if user32.GetWindowTextLengthW(hwnd) == 0:
                    return True

                pid = ctypes.c_ulong()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

                # 3. Match against the process tree of the CDP port
                if edge_pids and pid.value not in edge_pids:
                    # Fallback check by process name if tree resolution missed it
                    try:
                        proc = psutil.Process(pid.value)
                        if proc.name().lower() != "msedge.exe":
                            return True
                    except Exception:
                        return True

                target_hwnd = hwnd
                return False  # Stop enumeration (found main window)

            except Exception:
                return True

        callback = EnumWindowsProc(enum_callback)
        user32.EnumWindows(callback, 0)

        if not target_hwnd:
            return False

        # Розгортаємо тільки якщо згорнуте,
        # зберігаючи попередній стан (maximized / normal).
        restore_window_keep_state(target_hwnd)

        # Bypass Windows SetForegroundWindow restrictions using ALT key pulse
        VK_MENU = 0x12
        KEYEVENTF_KEYUP = 0x0002

        user32.keybd_event(VK_MENU, 0, 0, 0)
        user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

        user32.SetForegroundWindow(target_hwnd)
        user32.BringWindowToTop(target_hwnd)

        time.sleep(0.1)
        return user32.GetForegroundWindow() == target_hwnd

    except Exception:
        return False
        
# ============================================================
# Page activation
# ============================================================

async def activate_page(page):
    """
    Робить конкретну Playwright-сторінку
    активною вкладкою, а потім виводить Edge
    на передній план.

    Порядок:

        1. page.bring_to_front()
        2. Edge foreground

    Викликати безпосередньо перед взаємодією
    модуля зі сторінкою.
    """

    if page is None:

        raise ValueError(
            "activate_page отримав page=None"
        )

    await page.bring_to_front()


# ============================================================
# Search input helper
# ============================================================

async def type_search_query(
    page,
    selector,
    query,
    delay=70
):
    """
    Єдина логіка введення в поле пошуку
    (взята з Concord):

        1. дочекатися поля;
        2. клік;
        3. повністю очистити (fill "");
        4. ввести query людським темпом.

    Очищення через fill("") гарантує, що в полі
    не залишиться запит з попереднього сеансу.
    """

    search_input = page.locator(
        selector
    ).first

    await search_input.wait_for(
        state="visible",
        timeout=10000
    )

    await search_input.click()

    await search_input.fill(
        ""
    )

    await search_input.press_sequentially(
        query,
        delay=delay
    )

    return search_input

# ============================================================
# Browser lifecycle helper
# ============================================================

async def disconnect(
    playwright,
    browser=None
):
    """
    Завершує Playwright-клієнт.

    ВАЖЛИВО:

    browser.close() НЕ викликається.

    Це означає, що Edge залишається відкритим.

    browser параметр залишений у сигнатурі,
    щоб можна було передавати стандартний
    результат connect().
    """

    if playwright is None:

        return

    try:

        await playwright.stop()

    except Exception:

        pass


# ============================================================
# Synchronous connect helper
# ============================================================

def connect_sync():
    """
    Синхронна обгортка над connect().

    Повертає:

        playwright
        browser
        context

    Увага:

    Для довгих Playwright-операцій краще використовувати
    async connect() всередині async-функції.
    """

    return asyncio.run(
        connect()
    )