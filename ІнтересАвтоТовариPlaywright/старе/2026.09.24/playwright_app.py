import os
import asyncio
import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime

from commands import CommandListener

import concord
import martex
import opoltrans
import browser


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
# Site modules
# ============================================================

SITE_MODULES = {
    "CONCORD": concord,
    "MARTEX": martex,
    "OPOLTRANS": opoltrans,
}


# ============================================================
# Main window
# ============================================================

root = tk.Tk()

root.title("Playwright")
root.geometry("600x600")
root.resizable(True, True)
root.attributes("-topmost", True)


# ============================================================
# Status
# ============================================================

def set_status(text):
    timestamp = datetime.now().strftime("%H:%M:%S")

    message = (
        f"[{timestamp}] {text}\n"
    )

    status_text.insert(
        "end",
        message
    )

    status_text.see("end")


# ============================================================
# Async
# ============================================================

def run_async(coro_factory):

    def worker():
        try:
            result = asyncio.run(
                coro_factory()
            )

            if result:
                root.after(
                    0,
                    lambda: set_status(result)
                )

        except Exception:
            import traceback

            error_text = (
                traceback.format_exc()
            )

            print(error_text)

            root.after(
                0,
                lambda: set_status(error_text)
            )

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()


# ============================================================
# Browser preparation
# ============================================================

def prepare_browser_on_start():

    def worker():
        try:
            result = (
                browser.prepare_browser_sync()
            )

            root.after(
                0,
                lambda: set_status(result)
            )

        except Exception:
            import traceback

            error_text = (
                traceback.format_exc()
            )

            print(error_text)

            root.after(
                0,
                lambda: set_status(error_text)
            )

    thread = threading.Thread(
        target=worker,
        daemon=True
    )

    thread.start()


# ============================================================
# Site command
# ============================================================

def run_site_command(
    site,
    command,
    value=""
):

    module = SITE_MODULES.get(site)

    if module is None:
        set_status(
            f"Невідомий сайт: {site}"
        )
        return

    command_data = {
        "command": command,
        "site": site,
        "value": value,
    }

    set_status(
        f"{site}: {command} — виконання..."
    )

    run_async(
        lambda: module.handle_command(
            command_data
        )
    )


# ============================================================
# Module command
#
# This function is passed to every site module.
# The module only needs to say:
#
# run_command("MARTEX", "SEARCH")
#
# ============================================================

def run_module_command(
    site,
    command
):

    value = ""

    if command == "SEARCH":

        value = query_entry.get().strip()

        if not value:
            set_status(
                f"Пошук {site}: запит порожній"
            )
            return

    run_site_command(
        site,
        command,
        value
    )


# ============================================================
# External command
# ============================================================

def handle_command(command):

    site = command["site"]

    module = SITE_MODULES.get(
        site
    )

    if module is None:
        set_status(
            f"Невідомий сайт: {site}"
        )
        return

    # --------------------------------------------------------
    # SEARCH
    #
    # Показуємо отриманий запит у головному полі.
    # --------------------------------------------------------

    if command["command"] == "SEARCH":

        value = command["value"].strip()

        query_entry.delete(
            0,
            tk.END
        )

        query_entry.insert(
            0,
            value
        )

    run_site_command(
        site,
        command["command"],
        command["value"]
    )


# ============================================================
# Command callback
# ============================================================

def command_callback(command):

    root.after(
        0,
        lambda: handle_command(command)
    )


# ============================================================
# Query
# ============================================================

query_frame = ttk.LabelFrame(
    root,
    text="Запит",
    padding=10
)

query_frame.pack(
    fill="x",
    padx=10,
    pady=(10, 5)
)

query_entry = ttk.Entry(
    query_frame
)

query_entry.pack(
    fill="x"
)


# ============================================================
# Site modules UI
# ============================================================

sites_frame = ttk.Frame(
    root
)

sites_frame.pack(
    fill="x",
    padx=10,
    pady=5
)


for site_name, module in SITE_MODULES.items():

    if not hasattr(
        module,
        "create_ui"
    ):
        continue

    frame = module.create_ui(
        sites_frame,
        run_module_command
    )

    if frame is not None:
        frame.pack(
            fill="x",
            pady=(0, 8)
        )


# ============================================================
# Status window
# ============================================================

status_frame = ttk.LabelFrame(
    root,
    text="Статус",
    padding=10
)

status_frame.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=(5, 10)
)

status_text_frame = ttk.Frame(
    status_frame
)

status_text_frame.pack(
    fill="both",
    expand=True
)

status_text = tk.Text(
    status_text_frame,
    height=8,
    wrap="word"
)

status_text.pack(
    side="left",
    fill="both",
    expand=True
)


# ============================================================
# Copy status text
# ============================================================

def copy_status(event=None):

    try:
        selected_text = status_text.get(
            "sel.first",
            "sel.last"
        )

    except tk.TclError:
        return "break"

    root.clipboard_clear()

    root.clipboard_append(
        selected_text
    )

    root.update_idletasks()

    return "break"


status_text.bind(
    "<Control-c>",
    copy_status
)


# ============================================================
# Status context menu
# ============================================================

def show_status_menu(event):

    menu = tk.Menu(
        root,
        tearoff=0
    )

    menu.add_command(
        label="Копіювати",
        command=copy_status
    )

    menu.tk_popup(
        event.x_root,
        event.y_root
    )

    menu.grab_release()


status_text.bind(
    "<Button-3>",
    show_status_menu
)


# ============================================================
# Scrollbar
# ============================================================

status_scrollbar = ttk.Scrollbar(
    status_text_frame,
    orient="vertical",
    command=status_text.yview
)

status_scrollbar.pack(
    side="right",
    fill="y"
)

status_text.configure(
    yscrollcommand=status_scrollbar.set
)


# ============================================================
# Command listener
# ============================================================

command_listener = CommandListener(
    COMMAND_FILE,
    command_callback
)

command_listener.start()


# ============================================================
# Close
# ============================================================

def on_close():

    command_listener.stop()

    root.destroy()


root.protocol(
    "WM_DELETE_WINDOW",
    on_close
)


# ============================================================
# Start
# ============================================================

set_status(
    "Готово"
)

root.after(
    100,
    prepare_browser_on_start
)

root.mainloop()
