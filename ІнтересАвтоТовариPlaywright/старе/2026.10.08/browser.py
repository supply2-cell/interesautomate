import asyncio
import subprocess

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

def bring_edge_window_to_front():
    """
    Brings the Edge window associated with CDP port 9222
    to the foreground.

    Returns:
        True  - Edge window was activated
        False - Edge window was not found/activated
    """

    try:
        import ctypes
        import psutil
        import time

    except ImportError:
        return False

    try:

        user32 = ctypes.windll.user32

        # ----------------------------------------------------
        # Find the Edge PID listening on CDP port 9222.
        # ----------------------------------------------------

        edge_pids = set()

        for connection in psutil.net_connections(
            kind="tcp"
        ):

            try:

                if not connection.laddr:
                    continue

                if connection.laddr.port != 9222:
                    continue

                if connection.pid:
                    edge_pids.add(
                        connection.pid
                    )

            except Exception:
                continue

        if not edge_pids:
            return False

        # ----------------------------------------------------
        # Find a visible top-level Edge window.
        # ----------------------------------------------------

        target_hwnd = None

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_void_p,
            ctypes.c_void_p
        )

        def enum_callback(hwnd, lparam):

            nonlocal target_hwnd

            try:

                if not user32.IsWindowVisible(hwnd):
                    return True

                if user32.GetParent(hwnd):
                    return True

                process_id = ctypes.c_ulong()

                user32.GetWindowThreadProcessId(
                    hwnd,
                    ctypes.byref(process_id)
                )

                if process_id.value not in edge_pids:
                    return True

                target_hwnd = hwnd

                return False

            except Exception:

                return True

        callback = EnumWindowsProc(
            enum_callback
        )

        user32.EnumWindows(
            callback,
            0
        )

        if not target_hwnd:
            return False

        # ----------------------------------------------------
        # Restore Edge if minimized.
        # ----------------------------------------------------

        SW_RESTORE = 9

        user32.ShowWindow(
            target_hwnd,
            SW_RESTORE
        )

        # ----------------------------------------------------
        # Get foreground and target window threads.
        # ----------------------------------------------------

        foreground_hwnd = user32.GetForegroundWindow()

        target_thread_id = (
            user32.GetWindowThreadProcessId(
                target_hwnd,
                None
            )
        )

        foreground_thread_id = (
            user32.GetWindowThreadProcessId(
                foreground_hwnd,
                None
            )
        )

        # ----------------------------------------------------
        # Temporarily attach the input queues.
        #
        # This helps SetForegroundWindow() work even when
        # another application currently owns the foreground.
        # ----------------------------------------------------

        attached = False

        if (
            foreground_thread_id
            and target_thread_id
            and foreground_thread_id != target_thread_id
        ):

            attached = bool(
                user32.AttachThreadInput(
                    foreground_thread_id,
                    target_thread_id,
                    True
                )
            )

        try:

            # ------------------------------------------------
            # Put Edge above other windows.
            # ------------------------------------------------

            user32.BringWindowToTop(
                target_hwnd
            )

            # ------------------------------------------------
            # Make Edge the foreground window.
            # ------------------------------------------------

            user32.SetForegroundWindow(
                target_hwnd
            )

            # ------------------------------------------------
            # Set focus to Edge.
            # ------------------------------------------------

            user32.SetFocus(
                target_hwnd
            )

            # ------------------------------------------------
            # One more activation attempt.
            # ------------------------------------------------

            user32.ShowWindow(
                target_hwnd,
                SW_RESTORE
            )

            user32.SetForegroundWindow(
                target_hwnd
            )

        finally:

            if attached:

                user32.AttachThreadInput(
                    foreground_thread_id,
                    target_thread_id,
                    False
                )

        # ----------------------------------------------------
        # Give Windows a moment to process the activation.
        # ----------------------------------------------------

        time.sleep(0.1)

        # ----------------------------------------------------
        # Verify that Edge actually became foreground.
        # ----------------------------------------------------

        return (
            user32.GetForegroundWindow()
            == target_hwnd
        )

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

    # --------------------------------------------------------
    # bring_edge_window_to_front() синхронна,
    # тому виконуємо її після bring_to_front().
    # --------------------------------------------------------

    bring_edge_window_to_front()


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