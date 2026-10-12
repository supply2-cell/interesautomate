import tkinter as tk
from tkinter import ttk


# ============================================================
# UI state
# ============================================================

_query_entry = None


# ============================================================
# Query
# ============================================================

def set_query(value):
    """
    Встановлює Query у головному полі General.
    """

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

    if _query_entry is None:

        raise RuntimeError(
            "GENERAL: "
            "не підключено Query entry."
        )

    _query_entry.delete(
        0,
        tk.END
    )

    _query_entry.insert(
        0,
        query
    )

    return query


def get_query():
    """
    Повертає поточний Query з General.
    """

    if _query_entry is None:

        raise RuntimeError(
            "GENERAL: "
            "не підключено Query entry."
        )

    query = _query_entry.get().strip()

    if not query:

        raise ValueError(
            "GENERAL: "
            "Query порожній."
        )

    return query


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

    _query_entry = ttk.Entry(
        query_frame
    )

    _query_entry.pack(
        fill="x"
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


# ------------------------------------------------------------
# Незалежні від локалі Ctrl+C / Ctrl+V / Ctrl+A
# ------------------------------------------------------------

def _is_ctrl_key(event):
    """
    Визначає Ctrl незалежно від поточної розкладки.
    """

    try:
        return bool(
            event.state & 0x0004
        )

    except Exception:
        return False


def _is_key(event, *keys):
    """
    Перевірка клавіші без залежності від текстового символу.
    """

    try:

        keysym = (
            str(
                event.keysym
            ).lower()
        )

        keycode = getattr(
            event,
            "keycode",
            None
        )

        return (
            keysym in keys
            or
            (
                keycode is not None
                and str(keycode) in keys
            )
        )

    except Exception:

        return False


def universal_copy(event):
    """
    Ctrl+C незалежно від локалі клавіатури.
    Працює з Text та Entry.
    """

    if not _is_ctrl_key(event):
        return

    if not _is_key(
        event,
        "c",
        "67"
    ):
        return

    widget = event.widget

    try:

        # Text
        if isinstance(
            widget,
            tk.Text
        ):

            try:

                selected = widget.get(
                    "sel.first",
                    "sel.last"
                )

            except tk.TclError:

                return "break"

        # Entry
        else:

            try:

                selected = widget.selection_get()

            except Exception:

                return "break"

        widget.clipboard_clear()

        widget.clipboard_append(
            selected
        )

        widget.update()

    except Exception:

        pass

    return "break"


def universal_paste(event):
    """
    Ctrl+V незалежно від локалі клавіатури.
    Працює з Text та Entry.
    """

    if not _is_ctrl_key(event):
        return

    if not _is_key(
        event,
        "v",
        "86"
    ):
        return

    widget = event.widget

    try:

        value = widget.clipboard_get()

    except Exception:

        return "break"

    try:

        # Text
        if isinstance(
            widget,
            tk.Text
        ):

            try:
                widget.delete(
                    "sel.first",
                    "sel.last"
                )
            except tk.TclError:
                pass

            widget.insert(
                tk.INSERT,
                value
            )

        # Entry
        else:

            try:

                widget.delete(
                    "sel.first",
                    "sel.last"
                )

            except Exception:
                pass

            widget.insert(
                tk.INSERT,
                value
            )

    except Exception:

        pass

    return "break"


def universal_select_all(event):
    """
    Ctrl+A незалежно від локалі клавіатури.
    """

    if not _is_ctrl_key(event):
        return

    if not _is_key(
        event,
        "a",
        "65"
    ):
        return

    widget = event.widget

    try:

        if isinstance(
            widget,
            tk.Text
        ):

            widget.tag_add(
                "sel",
                "1.0",
                "end-1c"
            )

            widget.mark_set(
                "insert",
                "1.0"
            )

        else:

            widget.selection_range(
                0,
                "end"
            )

            widget.icursor(
                "end"
            )

    except Exception:

        pass

    return "break"


def bind_universal_clipboard(widget):
    """
    Підключає універсальні Ctrl+C / Ctrl+V / Ctrl+A.
    """

    widget.bind(
        "<KeyPress>",
        universal_copy,
        add="+"
    )

    widget.bind(
        "<KeyPress>",
        universal_paste,
        add="+"
    )

    widget.bind(
        "<KeyPress>",
        universal_select_all,
        add="+"
    )


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
