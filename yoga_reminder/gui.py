import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime, date
import threading

from data_manager import load_schedules, save_schedules, new_entry, parse_datetime

COLUMNS = ("class_name", "start_datetime", "url", "status")
COL_LABELS = {
    "class_name": "クラス名",
    "start_datetime": "予約受付開始日時",
    "url": "予約URL",
    "status": "ステータス",
}
COL_WIDTHS = {
    "class_name": 150,
    "start_datetime": 140,
    "url": 250,
    "status": 90,
}


class EntryDialog(tk.Toplevel):
    def __init__(self, parent, entry=None):
        super().__init__(parent)
        self.title("予約登録" if entry is None else "予約編集")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build(entry)
        self.wait_window()

    def _build(self, entry):
        pad = {"padx": 8, "pady": 4}
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        # クラス名
        ttk.Label(frm, text="クラス名 *").grid(row=0, column=0, sticky="w", **pad)
        self._name_var = tk.StringVar(value=entry["class_name"] if entry else "")
        ttk.Entry(frm, textvariable=self._name_var, width=30).grid(row=0, column=1, sticky="ew", **pad)

        # 日付
        ttk.Label(frm, text="予約受付開始日 *\n(YYYY-MM-DD)").grid(row=1, column=0, sticky="w", **pad)
        default_date = ""
        default_time = "10:00"
        if entry:
            try:
                dt = parse_datetime(entry["start_datetime"])
                default_date = dt.strftime("%Y-%m-%d")
                default_time = dt.strftime("%H:%M")
            except ValueError:
                pass
        self._date_var = tk.StringVar(value=default_date)
        ttk.Entry(frm, textvariable=self._date_var, width=14).grid(row=1, column=1, sticky="w", **pad)

        # 時刻
        ttk.Label(frm, text="時刻 * (HH:MM)").grid(row=2, column=0, sticky="w", **pad)
        self._time_var = tk.StringVar(value=default_time)
        ttk.Entry(frm, textvariable=self._time_var, width=8).grid(row=2, column=1, sticky="w", **pad)

        # URL
        ttk.Label(frm, text="予約ページURL").grid(row=3, column=0, sticky="w", **pad)
        self._url_var = tk.StringVar(value=entry["url"] if entry else "")
        ttk.Entry(frm, textvariable=self._url_var, width=40).grid(row=3, column=1, sticky="ew", **pad)

        # メモ
        ttk.Label(frm, text="メモ").grid(row=4, column=0, sticky="nw", **pad)
        self._memo_text = tk.Text(frm, width=30, height=4)
        self._memo_text.grid(row=4, column=1, sticky="ew", **pad)
        if entry and entry.get("memo"):
            self._memo_text.insert("1.0", entry["memo"])

        # ボタン
        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=5, column=0, columnspan=2, pady=8)
        ttk.Button(btn_frm, text="保存", command=self._save).pack(side="left", padx=4)
        ttk.Button(btn_frm, text="キャンセル", command=self.destroy).pack(side="left", padx=4)

        frm.columnconfigure(1, weight=1)

    def _save(self):
        name = self._name_var.get().strip()
        date_str = self._date_var.get().strip()
        time_str = self._time_var.get().strip()
        url = self._url_var.get().strip()
        memo = self._memo_text.get("1.0", "end-1c").strip()

        if not name:
            messagebox.showerror("入力エラー", "クラス名を入力してください。", parent=self)
            return
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror("入力エラー", "日付は YYYY-MM-DD、時刻は HH:MM 形式で入力してください。", parent=self)
            return

        self.result = {"class_name": name, "start_datetime": dt, "url": url, "memo": memo}
        self.destroy()


class MainWindow:
    def __init__(self, root, scheduler):
        self.root = root
        self.scheduler = scheduler
        self._schedules: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        self.root.title("ヨガ予約リマインダー")
        self.root.geometry("780x420")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        toolbar = ttk.Frame(self.root, padding=4)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="新規追加", command=self._add).pack(side="left", padx=2)
        ttk.Button(toolbar, text="編集", command=self._edit).pack(side="left", padx=2)
        ttk.Button(toolbar, text="削除", command=self._delete).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", padx=6, fill="y")
        ttk.Button(toolbar, text="ステータス更新", command=self._update_status).pack(side="left", padx=2)
        ttk.Button(toolbar, text="更新", command=self.refresh).pack(side="right", padx=2)

        tree_frm = ttk.Frame(self.root)
        tree_frm.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.tree = ttk.Treeview(tree_frm, columns=COLUMNS, show="headings", selectmode="browse")
        for col in COLUMNS:
            self.tree.heading(col, text=COL_LABELS[col])
            self.tree.column(col, width=COL_WIDTHS[col], minwidth=60)

        vsb = ttk.Scrollbar(tree_frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("done", foreground="gray")
        self.tree.tag_configure("notified", foreground="blue")

        self._status_bar = ttk.Label(self.root, text="", anchor="w", relief="sunken")
        self._status_bar.pack(fill="x", side="bottom")

    def refresh(self):
        self._schedules = load_schedules()
        self.tree.delete(*self.tree.get_children())
        for entry in self._schedules:
            tag = ""
            if entry["status"] == "予約完了":
                tag = "done"
            elif entry["status"] == "通知済":
                tag = "notified"
            self.tree.insert("", "end", iid=entry["id"], values=(
                entry["class_name"],
                entry["start_datetime"],
                entry["url"],
                entry["status"],
            ), tags=(tag,))
        self._status_bar.config(text=f"登録件数: {len(self._schedules)}")

    def _selected_entry(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        eid = sel[0]
        return next((e for e in self._schedules if e["id"] == eid), None)

    def _add(self):
        dlg = EntryDialog(self.root)
        if dlg.result is None:
            return
        r = dlg.result
        entry = new_entry(r["class_name"], r["start_datetime"], r["url"], r["memo"])
        self._schedules.append(entry)
        save_schedules(self._schedules)
        self.refresh()

    def _edit(self):
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("選択なし", "編集するスケジュールを選択してください。")
            return
        dlg = EntryDialog(self.root, entry)
        if dlg.result is None:
            return
        r = dlg.result
        entry["class_name"] = r["class_name"]
        entry["start_datetime"] = r["start_datetime"].strftime("%Y-%m-%d %H:%M")
        entry["url"] = r["url"]
        entry["memo"] = r["memo"]
        save_schedules(self._schedules)
        self.refresh()

    def _delete(self):
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("選択なし", "削除するスケジュールを選択してください。")
            return
        if not messagebox.askyesno("確認", f"「{entry['class_name']}」を削除しますか？"):
            return
        self._schedules = [e for e in self._schedules if e["id"] != entry["id"]]
        save_schedules(self._schedules)
        self.refresh()

    def _update_status(self):
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("選択なし", "スケジュールを選択してください。")
            return
        statuses = ["待機中", "通知済", "予約完了"]
        menu_win = tk.Toplevel(self.root)
        menu_win.title("ステータス変更")
        menu_win.resizable(False, False)
        menu_win.grab_set()
        ttk.Label(menu_win, text="新しいステータスを選択:").pack(padx=12, pady=(12, 4))
        var = tk.StringVar(value=entry["status"])
        for s in statuses:
            ttk.Radiobutton(menu_win, text=s, variable=var, value=s).pack(anchor="w", padx=20)

        def apply():
            entry["status"] = var.get()
            save_schedules(self._schedules)
            self.refresh()
            menu_win.destroy()

        ttk.Button(menu_win, text="適用", command=apply).pack(pady=8)
        menu_win.wait_window()

    def _on_close(self):
        self._try_minimize_to_tray()

    def _try_minimize_to_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            def make_icon():
                img = Image.new("RGB", (64, 64), color=(72, 153, 105))
                d = ImageDraw.Draw(img)
                d.ellipse([8, 8, 56, 56], outline="white", width=4)
                d.line([32, 12, 32, 52], fill="white", width=3)
                d.line([12, 32, 52, 32], fill="white", width=3)
                return img

            def show_window(icon, item):
                icon.stop()
                self.root.after(0, self.root.deiconify)

            def quit_app(icon, item):
                icon.stop()
                self.root.after(0, self.root.quit)

            menu = pystray.Menu(
                pystray.MenuItem("開く", show_window, default=True),
                pystray.MenuItem("終了", quit_app),
            )
            icon = pystray.Icon("yoga_reminder", make_icon(), "ヨガ予約リマインダー", menu)
            self.root.withdraw()
            threading.Thread(target=icon.run, daemon=True).start()
        except ImportError:
            self.root.quit()
