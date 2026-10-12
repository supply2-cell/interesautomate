import os
import asyncio
import json
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from commands import CommandListener
from playwright_app_general import bind_universal_clipboard

import playwright_app_general
import concord
import google_llm
import martex
import opoltrans


# ============================================================
# Paths
# ============================================================

APP_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

COMMAND_FILE = os.path.join(
    APP_DIR,
    "playwright_command.txt"
)


# ============================================================
# Module groups
#
# Кожен dict = окремий рядок UI.
#
# GENERAL = загальний модуль програми.
#
# Він містить робоче поле Query.
# ============================================================

SITE_MODULES = [
    {
        "GENERAL": playwright_app_general,
    },
    {
        "CONCORD": concord,
        "GOOGLE_LLM": google_llm,
    },
    {
        "MARTEX": martex,
        "OPOLTRANS": opoltrans,
    },
]


# ============================================================
# Module registry
# ============================================================

def build_module_registry(module_groups):
    """
    Перетворює групи модулів у єдиний registry.

    SITE_MODULES використовується для UI,
    MODULES — для маршрутизації команд.
    """

    registry = {}

    for group in module_groups:

        if not isinstance(
            group,
            dict
        ):
            raise TypeError(
                "Елемент SITE_MODULES має бути dict."
            )

        for module_name, module in group.items():

            module_name = str(
                module_name
            ).strip().upper()

            if not module_name:

                raise RuntimeError(
                    "Порожнє ім'я модуля."
                )

            if module_name in registry:

                raise RuntimeError(
                    f"Дубль модуля: "
                    f"{module_name}"
                )

            registry[module_name] = module

    return registry


MODULES = build_module_registry(
    SITE_MODULES
)


# ============================================================
# Main window
# ============================================================

root = tk.Tk()

playwright_app_general.configure_styles()

root.title(
    "Playwright"
)

root.geometry(
    "700x850"
)

root.resizable(
    True,
    True
)

root.attributes(
    "-topmost",
    True
)


# ============================================================
# Status
# ============================================================

def set_status(text):

    timestamp = datetime.now().strftime(
        "%H:%M:%S"
    )

    message = (
        f"[{timestamp}] {text}\n"
    )

    status_text.insert(
        "end",
        message
    )

    status_text.see(
        "end"
    )


def copy_status():

    try:

        selected_text = status_text.get(
            "sel.first",
            "sel.last"
        )

        root.clipboard_clear()

        root.clipboard_append(
            selected_text
        )

        root.update()

    except tk.TclError:

        pass


def select_all_status():

    status_text.tag_add(
        "sel",
        "1.0",
        "end"
    )

    status_text.mark_set(
        "insert",
        "1.0"
    )

    status_text.see(
        "insert"
    )


def show_status_context_menu(event):

    context_menu = tk.Menu(
        root,
        tearoff=0
    )

    try:

        status_text.get(
            "sel.first",
            "sel.last"
        )

        copy_state = "normal"

    except tk.TclError:

        copy_state = "disabled"

    context_menu.add_command(
        label="Копіювати",
        command=copy_status,
        state=copy_state
    )

    context_menu.add_command(
        label="Виділити все",
        command=select_all_status
    )

    context_menu.tk_popup(
        event.x_root,
        event.y_root
    )


def status_key_handler(event):

    if (
        event.state & 0x0004
        and event.keysym.lower() == "c"
    ):

        copy_status()

        return "break"

    if (
        event.state & 0x0004
        and event.keysym.lower() == "a"
    ):

        select_all_status()

        return "break"


# ============================================================
# Async / sync runner
# ============================================================

def run_async(function):
    """
    Універсальний worker.

    function може повернути:

        - звичайне значення;
        - coroutine;
        - dict;
        - list;
        - None.

    Результат модуля автоматично
    показується у статусі.
    """

    def worker():

        try:

            result = function()

            if asyncio.iscoroutine(
                result
            ):

                result = asyncio.run(
                    result
                )

            if result is None:

                return

            if isinstance(
                result,
                (dict, list)
            ):

                result_text = json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2
                )

            else:

                result_text = str(
                    result
                )

            root.after(
                0,
                lambda text=result_text:
                    set_status(text)
            )

        except ValueError as e:

            print(
                f"[INFO] {e}"
            )

        except Exception:

            import traceback

            error_text = (
                traceback.format_exc()
            )

            print(
                error_text
            )

            root.after(
                0,
                lambda text=error_text:
                    set_status(text)
            )

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()


# ============================================================
# Module lifecycle
# ============================================================

def initialize_modules():
    """
    Загальний lifecycle hook.

    Будь-який модуль може мати:

        def initialize():

    Якщо його немає — нічого не відбувається.
    """

    for module_name, module in MODULES.items():

        initialize = getattr(
            module,
            "initialize",
            None
        )

        if not callable(
            initialize
        ):

            continue

        try:

            result = initialize()

            if asyncio.iscoroutine(
                result
            ):

                run_async(
                    lambda r=result: r
                )

            elif result:

                set_status(
                    f"{module_name}: "
                    f"{result}"
                )

        except Exception:

            import traceback

            error_text = (
                traceback.format_exc()
            )

            print(
                error_text
            )

            set_status(
                f"{module_name} initialize error:\n"
                f"{error_text}"
            )


def prepare_modules():
    """
    Готує браузерні сторінки кожного модуля.

    ВАЖЛИВО:

    playwright_app.py НЕ знає,
    які саме сторінки потрібні модулю.

    Кожен модуль сам реалізує:

        async def prepare_browser():

    або:

        def prepare_browser():

    Модуль сам відповідає за:

        - пошук уже відкритої сторінки;
        - перевірку правильної сторінки;
        - відкриття відсутньої сторінки;
        - власну логіку роботи з браузером.
    """

    for module_name, module in MODULES.items():

        prepare_browser = getattr(
            module,
            "prepare_browser",
            None
        )

        if not callable(
            prepare_browser
        ):

            continue

        set_status(
            f"{module_name}: "
            f"підготовка браузера..."
        )

        try:

            result = prepare_browser()

            if asyncio.iscoroutine(
                result
            ):

                run_async(
                    lambda r=result: r
                )

            elif result:

                set_status(
                    f"{module_name}: "
                    f"{result}"
                )

        except Exception:

            import traceback

            error_text = (
                traceback.format_exc()
            )

            print(
                error_text
            )

            set_status(
                f"{module_name} "
                f"prepare_browser error:\n"
                f"{error_text}"
            )


def shutdown_modules():
    """
    Загальний lifecycle hook.

    Будь-який модуль може мати:

        def shutdown():

    Викликається при закритті програми.
    """

    for module_name, module in MODULES.items():

        shutdown = getattr(
            module,
            "shutdown",
            None
        )

        if not callable(
            shutdown
        ):

            continue

        try:

            result = shutdown()

            if asyncio.iscoroutine(
                result
            ):

                run_async(
                    lambda r=result: r
                )

            elif result:

                set_status(
                    f"{module_name}: "
                    f"{result}"
                )

        except Exception:

            import traceback

            error_text = (
                traceback.format_exc()
            )

            print(
                error_text
            )


# ============================================================
# Module command
# ============================================================

def run_module_command(
    source,
    target,
    command,
    value=None
):
    """
    Універсальний міст між модулями.

    source:
        хто відправив команду.

    target:
        кому команда адресована.

    command:
        назва команди.

    value:
        ЄДИНИЙ аргумент команди.

        Може бути будь-яким JSON-compatible
        значенням:

            string
            number
            bool
            null
            list
            dict

    playwright_app.py НЕ розбирає value.

    Модуль сам вирішує,
    що з ним робити.
    """

    source = str(
        source or ""
    ).strip().upper()

    target = str(
        target or ""
    ).strip().upper()

    command = str(
        command or ""
    ).strip().upper()

    if not target:

        set_status(
            f"{source}: "
            f"не вказано target."
        )

        return

    module = MODULES.get(
        target
    )

    if module is None:

        set_status(
            f"{source}: "
            f"невідомий модуль "
            f"{target}"
        )

        return

    # --------------------------------------------------------
    # Єдиний внутрішній контракт модуля:
    #
    # handle_command(
    #     command,
    #     value
    # )
    # --------------------------------------------------------

    set_status(
        f"{source} → {target}: "
        f"{command} — виконання..."
    )

    run_async(
        lambda:
            module.handle_command(
                command,
                value
            )
    )


# ============================================================
# Module UI runner
# ============================================================

def make_module_runner(
    source
):
    """
    Створює універсальний callback
    для конкретного модуля.

    Модуль може викликати:

        run_command(
            "GOOGLE_LLM",
            "LLM_SET_DATA",
            value
        )

    або будь-яку іншу команду
    іншого модуля.
    """

    def runner(
        target,
        command,
        value=None
    ):

        run_module_command(
            source=source,
            target=target,
            command=command,
            value=value
        )

    return runner


# ============================================================
# External command
# ============================================================

def handle_command(command):
    """
    Загальний handler зовнішніх команд.

    VBA надсилає:

        {
            "site": "MARTEX",
            "command": "SEARCH",
            "value": "1997220"
        }

    або:

        {
            "site": "GENERAL",
            "command": "SET_QUERY",
            "value": "1997220"
        }

    або:

        {
            "site": "GOOGLE_LLM",
            "command": "LLM_SET_DATA",
            "value": {
                "name": "...",
                "oem": "1997220"
            }
        }

    Handler тільки маршрутизує команду.
    Спеціальна логіка знаходиться
    всередині відповідного модуля.
    """

    if not isinstance(
        command,
        dict
    ):

        set_status(
            "Зовнішня команда: "
            "очікувався JSON object."
        )

        return

    target = str(
        command.get(
            "site",
            ""
        )
    ).strip().upper()

    command_name = str(
        command.get(
            "command",
            ""
        )
    ).strip().upper()

    value = command.get(
        "value"
    )

    if not target:

        set_status(
            "Зовнішня команда: "
            "не вказано site."
        )

        return

    if target not in MODULES:

        set_status(
            f"Невідомий модуль: "
            f"{target}"
        )

        return

    source = str(
        command.get(
            "source",
            target
        )
    ).strip().upper()

    run_module_command(
        source=source,
        target=target,
        command=command_name,
        value=value
    )


# ============================================================
# Command callback
# ============================================================

def command_callback(command):

    root.after(
        0,
        lambda data=command:
            handle_command(data)
    )


# ------------------------------------------------------------
# Site modules UI
#
# Кожна група = окремий рядок.
#
# GENERAL тепер містить Query.
# ------------------------------------------------------------

sites_frame = ttk.Frame(
    root,
    style="Compact.TFrame"
)

sites_frame.pack(
    fill="x",
    padx=1,
    pady=1
)


for row_index, group in enumerate(
    SITE_MODULES
):

    visible_modules = []

    for module_name, module in group.items():

        if not hasattr(
            module,
            "create_ui"
        ):

            continue

        visible_modules.append(
            (
                module_name,
                module
            )
        )

    if not visible_modules:

        continue

    row_frame = ttk.Frame(
        sites_frame,
        style="Compact.TFrame"
    )

    row_frame.pack(
        fill="x",
        expand=True,
        pady=1
    )

    # --------------------------------------------------------
    # Всі модулі в цьому рядку
    # мають однакову ширину.
    # --------------------------------------------------------

    for column_index in range(
        len(visible_modules)
    ):

        row_frame.columnconfigure(
            column_index,
            weight=1,
            uniform="module_row"
        )

    for column_index, (
        module_name,
        module
    ) in enumerate(
        visible_modules
    ):

        module_frame = ttk.Frame(
            row_frame,
            style="Compact.TFrame"
        )

        module_frame.grid(
            row=0,
            column=column_index,
            padx=1,
            pady=0,
            sticky="nsew"
        )

        create_ui = getattr(
            module,
            "create_ui",
            None
        )

        if callable(
            create_ui
        ):

            try:

                frame = create_ui(
                    module_frame,
                    make_module_runner(
                        module_name
                    )
                )

                if frame is not None:

                    frame.pack(
                        fill="both",
                        expand=True
                    )

            except Exception:

                import traceback

                error_text = (
                    traceback.format_exc()
                )

                print(
                    error_text
                )

                error_label = ttk.Label(
                    module_frame,
                    text=(
                        f"{module_name}: "
                        f"помилка UI\n"
                        f"{error_text}"
                    ),
                    justify="left",
                    style="Compact.TLabel"
                )

                error_label.pack(
                    fill="both",
                    expand=True
                )


# ============================================================
# Status window
# ============================================================

status_frame = ttk.LabelFrame(
    root,
    text="Статус",
    padding=1,
    style="Compact.TLabelframe"
)

status_frame.pack(
    fill="both",
    expand=True,
    padx=1,
    pady=(1, 1)
)


# ------------------------------------------------------------
# Контейнер для Text + Scrollbar
#
# Це важливо:
# scrollbar знаходиться СПРАВА від Text,
# а не займає нижній рядок.
# ------------------------------------------------------------

status_content = ttk.Frame(
    status_frame,
    style="Compact.TFrame"
)

status_content.pack(
    fill="both",
    expand=True
)

status_content.columnconfigure(
    0,
    weight=1
)

status_content.rowconfigure(
    0,
    weight=1
)


# ------------------------------------------------------------
# Status Text
# ------------------------------------------------------------

status_text = tk.Text(
    status_content,
    height=12,
    wrap="word",
    font=(
        "TkDefaultFont",
        8
    ),
    padx=1,
    pady=1,
    borderwidth=1,
    highlightthickness=0
)

status_text.grid(
    row=0,
    column=0,
    sticky="nsew"
)


# ------------------------------------------------------------
# Scrollbar справа
# ------------------------------------------------------------

status_scrollbar = ttk.Scrollbar(
    status_content,
    orient="vertical",
    command=status_text.yview
)

status_scrollbar.grid(
    row=0,
    column=1,
    sticky="ns"
)

status_text.configure(
    yscrollcommand=status_scrollbar.set
)


# ------------------------------------------------------------
# Clipboard / selection
# ------------------------------------------------------------

bind_universal_clipboard(
    status_text
)


# ------------------------------------------------------------
# Існуючі обробники
# ------------------------------------------------------------

status_text.bind(
    "<Button-3>",
    show_status_context_menu
)


# ============================================================
# External command listener
# ============================================================

command_listener = CommandListener(
    COMMAND_FILE,
    command_callback
)

command_listener.start()


# ============================================================
# Close handler
# ============================================================

def on_close():

    try:

        command_listener.stop()

    except Exception:

        pass

    try:

        shutdown_modules()

    except Exception:

        pass

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# Startup
# ============================================================

set_status(
    "Playwright app запущено."
)

initialize_modules()

prepare_modules()

root.mainloop()