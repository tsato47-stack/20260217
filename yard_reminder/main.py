import sys
import os
import tkinter as tk

sys.path.insert(0, os.path.dirname(__file__))

from gui import MainWindow
from scheduler import ReminderScheduler


def main():
    root = tk.Tk()

    scheduler = ReminderScheduler()
    scheduler.start()

    win = MainWindow(root, scheduler)

    def on_quit():
        scheduler.clear_credentials()
        scheduler.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", win._on_close)
    root.bind("<Destroy>", lambda e: scheduler.stop() if e.widget is root else None)

    root.mainloop()
    scheduler.clear_credentials()
    scheduler.stop()


if __name__ == "__main__":
    main()
