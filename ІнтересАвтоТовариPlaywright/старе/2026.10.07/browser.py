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
    Намагатиметься вивести вікно Edge,
    яке слухає CDP-порт 9222,
    на передній план.

    Функція не взаємодіє з DOM
    і не змінює активну вкладку.

    Активну вкладку Playwright повинен
    встановлювати через:

        await page.bring_to_front()
    """

    try:

        import ctypes
        import psutil

    except ImportError:

        return False

    try:

        edge_pids = set()

        # ----------------------------------------------------
        # Шукаємо процес, який слухає CDP-порт 9222.
        # ----------------------------------------------------

        for connection in psutil.net_connections(
            kind="tcp"
        ):

            try:

                if not connection.laddr:

                    continue

                if connection.laddr.port != 9222:

                    continue

                if not connection.pid:

                    continue

                edge_pids.add(
                    connection.pid
                )

            except Exception:

                continue

        if not edge_pids:

            return False

        user32 = ctypes.windll.user32

        found_window = False

        # ----------------------------------------------------
        # Перебираємо процеси та їхні HWND.
        # ----------------------------------------------------

        for pid in edge_pids:

            def enum_callback(
                hwnd,
                lparam
            ):

                nonlocal found_window

                if found_window:

                    return True

                try:

                    process_id = ctypes.c_ulong()

                    user32.GetWindowThreadProcessId(
                        hwnd,
                        ctypes.byref(
                            process_id
                        )
                    )

                    if process_id.value != pid:

                        return True

                    # ----------------------------------------
                    # Перевіряємо, що вікно видиме.
                    # ----------------------------------------

                    if not user32.IsWindowVisible(
                        hwnd
                    ):

                        return True

                    # ----------------------------------------
                    # Перевіряємо, що це не дочірнє вікно.
                    # ----------------------------------------

                    if user32.GetParent(
                        hwnd
                    ):

                        return True

                    # ----------------------------------------
                    # Виводимо вікно на передній план.
                    # ----------------------------------------

                    user32.ShowWindow(
                        hwnd,
                        9  # SW_RESTORE
                    )

                    user32.SetForegroundWindow(
                        hwnd
                    )

                    found_window = True

                    return False

                except Exception:

                    return True

            callback = ctypes.WINFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_void_p,
                ctypes.c_void_p
            )

            user32.EnumWindows(
                callback(
                    enum_callback
                ),
                0
            )

            if found_window:

                return True

        return False

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