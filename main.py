"""Entry point cho BQH Merger Video.

Chạy: python main.py
"""

from __future__ import annotations

import customtkinter as ctk

from app.ui.main_window import MainWindow


def main() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
