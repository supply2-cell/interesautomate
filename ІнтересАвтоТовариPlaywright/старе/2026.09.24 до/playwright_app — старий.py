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


APP_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

COMMAND_FILE = os.path.join(
    APP_DIR,
    "playwright_command.txt"
)


SITE_MODULES = {
    "CONCORD": concord,
    "MARTEX": martex,
    "OPOLTRANS": opoltrans,
}


# ============================================================
# UI
# ============================================================

root = tk.Tk()

root.title("Playwright")

root.geometry("500x400")

root.resizable(False, False)

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
                    lambda: set_status(
                        result
                    )
                )

        except Exception as e:

            import traceback
            error_text = traceback.format_exc()
            print(error_text)

            root.after(
                0,
                lambda: set_status(
                    error_text
                )
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

            result = browser.prepare_browser_sync()

            root.after(
                0,
                lambda: set_status(
                    result
                )
            )

        except Exception as e:

            import traceback

            error_text = traceback.format_exc()

            print(error_text)

            root.after(
                0,
                lambda: set_status(
                    error_text
                )
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

    module = SITE_MODULES.get(
        site
    )

    if module is None:

        set_status(
            f"Невідомий сайт: {site}"
        )

        return

    command_data = {
        "command": command,
        "site": site,
        "value": value
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
# Concord search
# ============================================================

def start_concord_search():

    query = query_entry.get().strip()

    if not query:

        set_status(
            "Пошук Concord: запит порожній"
        )

        return

    set_status(
        f"Пошук Concord: {query} — виконання..."
    )

    run_async(
        lambda: concord.search(
            query
        )
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
    # Перед виконанням записуємо значення
    # у поле "Запит".
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
        lambda: handle_command(
            command
        )
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
# Concord
# ============================================================

concord_frame = ttk.LabelFrame(
    root,
    text="Concord",
    padding=10
)

concord_frame.pack(
    fill="x",
    padx=10,
    pady=5
)


concord_buttons = ttk.Frame(
    concord_frame
)

concord_buttons.pack(
    fill="x"
)


search_button = ttk.Button(
    concord_buttons,
    text="Пошук",
    command=start_concord_search
)

search_button.grid(
    row=0,
    column=0,
    padx=3,
    pady=3,
    sticky="ew"
)


products_button = ttk.Button(
    concord_buttons,
    text="Витягнути товари",
    command=lambda: run_site_command(
        "CONCORD",
        "GET_PRODUCTS"
    )
)

products_button.grid(
    row=0,
    column=1,
    padx=3,
    pady=3,
    sticky="ew"
)


analogs_button = ttk.Button(
    concord_buttons,
    text="Витягнути аналоги",
    command=lambda: run_site_command(
        "CONCORD",
        "GET_ANALOGS"
    )
)

analogs_button.grid(
    row=1,
    column=0,
    padx=3,
    pady=3,
    sticky="ew"
)


product_button = ttk.Button(
    concord_buttons,
    text="Витягнути товар",
    command=lambda: run_site_command(
        "CONCORD",
        "GET_PRODUCT"
    )
)

product_button.grid(
    row=1,
    column=1,
    padx=3,
    pady=3,
    sticky="ew"
)

delete_last_button = ttk.Button(
    concord_buttons,
    text="Витерти останній",
    command=lambda: run_site_command(
        "CONCORD",
        "DELETE_LAST"
    )
)

delete_last_button.grid(
    row=3,
    column=0,
    padx=3,
    pady=(12, 3),
    sticky="ew"
)


delete_all_button = ttk.Button(
    concord_buttons,
    text="Витерти всі",
    command=lambda: run_site_command(
        "CONCORD",
        "DELETE_ALL"
    )
)

delete_all_button.grid(
    row=3,
    column=1,
    padx=3,
    pady=(12, 3),
    sticky="ew"
)

concord_buttons.columnconfigure(
    0,
    weight=1
)

concord_buttons.columnconfigure(
    1,
    weight=1
)

# ============================================================
# Martex
# ============================================================

martex_frame = ttk.LabelFrame(
    root,
    text="Martex",
    padding=8
)
martex_frame.pack(
    fill="x",
    padx=10,
    pady=(0, 8)
)

martex_buttons = ttk.Frame(
    martex_frame
)
martex_buttons.pack(
    fill="x"
)

martex_search_button = ttk.Button(
    martex_buttons,
    text="Пошук",
    command=lambda: run_site_command(
        "MARTEX",
        "SEARCH",
        query_entry.get().strip()
    )
)
martex_search_button.grid(
    row=0,
    column=0,
    padx=3,
    pady=3,
    sticky="ew"
)

martex_product_button = ttk.Button(
    martex_buttons,
    text="Витягнути товар",
    command=lambda: run_site_command(
        "MARTEX",
        "GET_PRODUCT"
    )
)
martex_product_button.grid(
    row=0,
    column=1,
    padx=3,
    pady=3,
    sticky="ew"
)

martex_buttons.columnconfigure(
    0,
    weight=1
)

martex_buttons.columnconfigure(
    1,
    weight=1
)


# ============================================================
# Opoltrans
# ============================================================

opoltrans_frame = ttk.LabelFrame(
    root,
    text="Opoltrans",
    padding=8
)
opoltrans_frame.pack(
    fill="x",
    padx=10,
    pady=(0, 8)
)

opoltrans_buttons = ttk.Frame(
    opoltrans_frame
)
opoltrans_buttons.pack(
    fill="x"
)

opoltrans_search_button = ttk.Button(
    opoltrans_buttons,
    text="Пошук",
    command=lambda: run_site_command(
        "OPOLTRANS",
        "SEARCH",
        query_entry.get().strip()
    )
)
opoltrans_search_button.grid(
    row=0,
    column=0,
    padx=3,
    pady=3,
    sticky="ew"
)

opoltrans_product_button = ttk.Button(
    opoltrans_buttons,
    text="Витягнути товар",
    command=lambda: run_site_command(
        "OPOLTRANS",
        "GET_PRODUCT"
    )
)
opoltrans_product_button.grid(
    row=0,
    column=1,
    padx=3,
    pady=3,
    sticky="ew"
)

opoltrans_buttons.columnconfigure(
    0,
    weight=1
)

opoltrans_buttons.columnconfigure(
    1,
    weight=1
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

# Copy status text

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


# Status context menu

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

# Scrollbar

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