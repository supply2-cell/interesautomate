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