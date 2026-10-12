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

def minimize_excel():
    """Minimize the active foreground window if it belongs to Excel."""
    try:
        hwnd = user32.GetForegroundWindow()
        if hwnd:
            SW_MINIMIZE = 6
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

        # Restore if minimized
        SW_RESTORE = 9
        user32.ShowWindow(target_hwnd, SW_RESTORE)

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