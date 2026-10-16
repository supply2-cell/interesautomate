import sys
import tkinter as tk
from tkinter import ttk


# ============================================================
# UI state
# ============================================================

_query_entry = None

# Кеш Query.
#
# get_query() викликається з робочих потоків модулів,
# а Tk-віджети не можна чіпати не з головного потоку.
# Тому читаємо кеш, який оновлюється з самого Entry.
_current_query = ""


# ============================================================
# Query
# ============================================================

def set_query(value):
    """
    Встановлює Query у головному полі General.

    Викликати з головного Tk-потоку
    (playwright_app робить це сам для команд з Excel).
    """

    global _current_query

    if not isinstance(
        value,
        str
    ):

        raise ValueError(
            "GENERAL SET_QUERY: "
            "value має бути рядком."
        )

    query = value.strip()

    if not query:

        raise ValueError(
            "GENERAL SET_QUERY: "
            "порожній запит."
        )

    _current_query = query

    if _query_entry is not None:

        _query_entry.delete(
            0,
            tk.END
        )

        _query_entry.insert(
            0,
            query
        )

    return query


def peek_query():
    """
    Поточний Query без перевірок (може бути "").
    """

    return _current_query


def get_query():
    """
    Повертає поточний Query з General.
    """

    query = _current_query.strip()

    if not query:

        raise ValueError(
            "GENERAL: "
            "Query порожній."
        )

    return query


def _on_query_changed(*_args):

    global _current_query

    if _query_entry is not None:

        _current_query = _query_entry.get()


# ============================================================
# General UI
# ============================================================

def create_ui(
    parent,
    run_command
):

    global _query_entry

    frame = ttk.LabelFrame(
        parent,
        text="General",
        padding=10
    )

    query_frame = ttk.Frame(
        frame
    )

    query_frame.pack(
        fill="x"
    )

    ttk.Label(
        query_frame,
        text="Query:"
    ).pack(
        anchor="w"
    )

    query_var = tk.StringVar(
        master=query_frame
    )

    query_var.trace_add(
        "write",
        _on_query_changed
    )

    _query_entry = ttk.Entry(
        query_frame,
        textvariable=query_var
    )

    # StringVar має жити разом з віджетом.
    _query_entry._query_var = query_var

    _query_entry.pack(
        fill="x"
    )

    bind_universal_clipboard(
        _query_entry
    )

    return frame


# ============================================================
# Command handler
# ============================================================

async def handle_command(
    command,
    value
):

    action = str(
        command or ""
    ).strip().upper()

    if action == "SET_QUERY":

        # Сюди потрапляє лише якщо playwright_app
        # не обробив SET_QUERY сам у головному потоці.
        return set_query(
            value
        )

    if action == "GET_QUERY":

        return get_query()

    return (
        f"Невідома команда General: "
        f"{action}"
    )


# ------------------------------------------------------------
# Налаштування ttk
# ------------------------------------------------------------
def configure_styles():

    # ============================================================
    # COMPACT UI HELPERS
    # ============================================================

    # ------------------------------------------------------------
    # Компактні стилі
    # ------------------------------------------------------------


    try:
        _compact_font = (
            "TkDefaultFont",
            8
        )

        _compact_small_font = (
            "TkDefaultFont",
            7
        )

    except Exception:
        _compact_font = None
        _compact_small_font = None
    
    style = ttk.Style()

    try:

        style.configure(
            "Compact.TLabelframe",
            padding=1
        )

        style.configure(
            "Compact.TLabelframe.Label",
            font=_compact_font
        )

        style.configure(
            "Compact.TFrame",
            padding=0
        )

        style.configure(
            "Compact.TLabel",
            font=_compact_font
        )

        style.configure(
            "Compact.TEntry",
            padding=1,
            font=_compact_font
        )

        style.configure(
            "Compact.TButton",
            padding=(1, 1),
            font=_compact_small_font
        )

    except Exception:
        pass


# ============================================================
# Буфер обміну / редагування
#
# Ми НЕ пишемо власну логіку копіювання/вставки.
# Tk уже вміє це робити у полях Entry/Text через
# стандартні віртуальні події:
#
#     <<Copy>>  <<Paste>>  <<Cut>>
#
# Проблема лише в тому, що стандартні прив'язки Tk
# реагують на Control-c / Control-v за СИМВОЛОМ клавіші,
# тому в українській/російській розкладці (Ctrl+С = "с")
# вони не спрацьовують.
#
# Тому ловимо Ctrl+клавіша за фізичним кодом клавіші
# (Windows virtual-key code, однаковий у будь-якій
# розкладці) і просто генеруємо стандартну подію Tk.
#
# readonly=True:
#     дозволено виділення, копіювання, Ctrl+A, навігацію;
#     заборонено введення, вставку, вирізання, видалення.
#     Програмне insert()/delete() працює як і раніше.
# ============================================================

# Windows virtual-key codes (не залежать від розкладки).
_VK_ACTIONS = {
    65: "select_all",   # A
    67: "copy",         # C
    86: "paste",        # V
    88: "cut",          # X
}

# Fallback за keysym (Linux/macOS та латиниця/кирилиця).
_KEYSYM_ACTIONS = {
    "a": "select_all",
    "c": "copy",
    "v": "paste",
    "x": "cut",
    # Ті самі фізичні клавіші в кириличній розкладці
    "cyrillic_ef": "select_all",   # ф
    "cyrillic_es": "copy",         # с
    "cyrillic_em": "paste",        # м
    "cyrillic_che": "cut",         # ч
}

_VIRTUAL_EVENTS = {
    "copy": "<<Copy>>",
    "paste": "<<Paste>>",
    "cut": "<<Cut>>",
}

# Клавіші, які дозволені в readonly-полі.
_READONLY_ALLOWED_KEYS = {
    "left", "right", "up", "down",
    "home", "end", "prior", "next",
    "tab", "iso_left_tab", "escape",
    "shift_l", "shift_r",
    "control_l", "control_r",
    "alt_l", "alt_r",
    "caps_lock", "num_lock",
    "insert",  # Ctrl+Insert = копіювати
}


def _ctrl_action(event):

    if sys.platform == "win32":

        action = _VK_ACTIONS.get(
            getattr(event, "keycode", None)
        )

        if action:
            return action

    return _KEYSYM_ACTIONS.get(
        str(event.keysym).lower()
    )


def _is_readonly(widget):

    return bool(
        getattr(widget, "_clipboard_readonly", False)
    )


def _select_all(widget):

    if isinstance(widget, tk.Text):

        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "end-1c")
        widget.see("insert")

    else:

        widget.selection_range(0, "end")
        widget.icursor("end")


def _run_action(widget, action):

    if action == "select_all":

        _select_all(widget)
        return

    if _is_readonly(widget) and action in ("paste", "cut"):

        return

    widget.event_generate(
        _VIRTUAL_EVENTS[action]
    )


def _on_ctrl_key(event):

    action = _ctrl_action(event)

    if action is not None:

        try:
            _run_action(event.widget, action)

        except tk.TclError:
            pass

        return "break"

    # Інші Ctrl-комбінації в readonly-полі:
    # дозволяємо лише навігацію (Ctrl+Home/End/стрілки).
    if (
        _is_readonly(event.widget)
        and str(event.keysym).lower() not in _READONLY_ALLOWED_KEYS
    ):

        return "break"

    return None


def _on_readonly_key(event):

    if str(event.keysym).lower() in _READONLY_ALLOWED_KEYS:

        return None

    return "break"


def _block(_event=None):

    return "break"


def _show_context_menu(event):

    widget = event.widget
    readonly = _is_readonly(widget)

    try:
        widget.focus_set()

    except tk.TclError:
        pass

    menu = tk.Menu(
        widget,
        tearoff=0
    )

    if not readonly:

        menu.add_command(
            label="Вирізати",
            accelerator="Ctrl+X",
            command=lambda: _run_action(widget, "cut")
        )

    menu.add_command(
        label="Копіювати",
        accelerator="Ctrl+C",
        command=lambda: _run_action(widget, "copy")
    )

    if not readonly:

        menu.add_command(
            label="Вставити",
            accelerator="Ctrl+V",
            command=lambda: _run_action(widget, "paste")
        )

    menu.add_separator()

    menu.add_command(
        label="Виділити все",
        accelerator="Ctrl+A",
        command=lambda: _run_action(widget, "select_all")
    )

    try:
        menu.tk_popup(event.x_root, event.y_root)

    finally:
        menu.grab_release()

    return "break"


def bind_universal_clipboard(widget, readonly=False):
    """
    Підключає стандартне редагування до Entry / Text:

        Ctrl+C / Ctrl+V / Ctrl+X / Ctrl+A
        у будь-якій розкладці клавіатури
        + контекстне меню на правій кнопці миші.

    readonly=True — поле лише для читання
    (виділення та копіювання дозволені).
    """

    widget._clipboard_readonly = bool(readonly)

    widget.bind(
        "<Control-KeyPress>",
        _on_ctrl_key
    )

    widget.bind(
        "<Button-3>",
        _show_context_menu
    )

    if readonly:

        widget.bind(
            "<KeyPress>",
            _on_readonly_key
        )

        for sequence in (
            "<<Paste>>",
            "<<Cut>>",
            "<<Clear>>",
            "<<PasteSelection>>",
            "<Button-2>",
        ):

            widget.bind(
                sequence,
                _block
            )

    return widget


# ============================================================
# Компактна кнопка
# ============================================================

def compact_button(
    parent,
    text,
    command,
    **kwargs
):
    """
    Створює компактну ttk-кнопку.

    Текст може переноситися на 2+ рядки.
    """

    button = ttk.Button(
        parent,
        text=text,
        command=command,
        style="Compact.TButton",
        **kwargs
    )

    try:

        # Дозволяємо перенесення тексту.
        button.configure(
            wraplength=90
        )

    except Exception:

        pass

    return button
