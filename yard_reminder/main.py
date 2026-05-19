import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import tkinter as tk
from gui import MainWindow
from scheduler import ReminderScheduler


def main():
    root = tk.Tk()

    scheduler = ReminderScheduler()
    win = MainWindow(root, scheduler)

    scheduler.set_credential_getter(win.get_credentials)
    scheduler.set_gui_callbacks(
        on_status_change=lambda: root.after(0, win.refresh),
        on_confirm_dialog=lambda entry, on_confirm, on_cancel: root.after(
            0, lambda: win.show_confirm_dialog(entry, on_confirm, on_cancel)
        ),
    )
    scheduler.start()

    root.mainloop()
    scheduler.stop()


if __name__ == "__main__":
    main()
