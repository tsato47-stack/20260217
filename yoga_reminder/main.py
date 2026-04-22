import sys
import os
import tkinter as tk

sys.path.insert(0, os.path.dirname(__file__))

from gui import MainWindow
from scheduler import ReminderScheduler


def main():
    root = tk.Tk()

    scheduler = ReminderScheduler()

    win = MainWindow(root, scheduler)

    # スケジューラーに GUI 更新コールバックを設定
    scheduler.on_status_change = lambda: root.after(0, win.refresh)
    scheduler.start()

    root.mainloop()
    scheduler.stop()


if __name__ == "__main__":
    main()
