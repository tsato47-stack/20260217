import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import threading

from data_manager import load_schedules, save_schedules, new_entry, parse_datetime, STUDIO_MAP

STUDIOS = list(STUDIO_MAP.keys())

COLUMNS = ("class_name", "start_datetime", "studio", "status")
COL_LABELS = {
    "class_name": "クラス名",
    "start_datetime": "予約受付開始日時",
    "studio": "スタジオ",
    "status": "ステータス",
}
COL_WIDTHS = {
    "class_name": 200,
    "start_datetime": 150,
    "studio": 170,
    "status": 90,
}


# ─────────────────────────────────────────────────
# 予約登録/編集ダイアログ（画面3）
# ─────────────────────────────────────────────────
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
        self._name_var = tk.StringVar(value=entry["class_name"] if entry else "NAO - ")
        ttk.Entry(frm, textvariable=self._name_var, width=32).grid(row=0, column=1, sticky="ew", **pad)

        # スタジオ
        ttk.Label(frm, text="スタジオ *").grid(row=1, column=0, sticky="w", **pad)
        default_studio = entry.get("studio", STUDIOS[0]) if entry else STUDIOS[0]
        self._studio_var = tk.StringVar(value=default_studio)
        ttk.Combobox(
            frm, textvariable=self._studio_var, values=STUDIOS, state="readonly", width=30
        ).grid(row=1, column=1, sticky="w", **pad)

        # 予約受付開始日
        ttk.Label(frm, text="予約受付開始日 *\n(YYYY-MM-DD)").grid(row=2, column=0, sticky="w", **pad)
        default_date, default_time = "", "10:00"
        if entry:
            try:
                dt = parse_datetime(entry["start_datetime"])
                default_date = dt.strftime("%Y-%m-%d")
                default_time = dt.strftime("%H:%M")
            except ValueError:
                pass
        self._date_var = tk.StringVar(value=default_date)
        ttk.Entry(frm, textvariable=self._date_var, width=14).grid(row=2, column=1, sticky="w", **pad)

        # 時刻
        ttk.Label(frm, text="時刻 * (HH:MM)").grid(row=3, column=0, sticky="w", **pad)
        self._time_var = tk.StringVar(value=default_time)
        ttk.Entry(frm, textvariable=self._time_var, width=8).grid(row=3, column=1, sticky="w", **pad)

        # メモ
        ttk.Label(frm, text="メモ").grid(row=4, column=0, sticky="nw", **pad)
        self._memo_text = tk.Text(frm, width=32, height=4)
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
        studio = self._studio_var.get().strip()
        date_str = self._date_var.get().strip()
        time_str = self._time_var.get().strip()
        memo = self._memo_text.get("1.0", "end-1c").strip()

        if not name:
            messagebox.showerror("入力エラー", "クラス名を入力してください。", parent=self)
            return
        if not studio:
            messagebox.showerror("入力エラー", "スタジオを選択してください。", parent=self)
            return
        try:
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        except ValueError:
            messagebox.showerror(
                "入力エラー",
                "日付は YYYY-MM-DD、時刻は HH:MM 形式で入力してください。",
                parent=self,
            )
            return

        self.result = {"class_name": name, "studio": studio, "start_datetime": dt, "memo": memo}
        self.destroy()


# ─────────────────────────────────────────────────
# 5分前確認ダイアログ（画面4）
# ─────────────────────────────────────────────────
class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, entry, on_confirm, on_cancel):
        super().__init__(parent)
        self.title("自動予約 実行確認")
        self.resizable(False, False)
        self.grab_set()
        self._on_confirm = on_confirm
        self._on_cancel = on_cancel
        self._build(entry)

    def _build(self, entry):
        frm = ttk.Frame(self, padding=16)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="⚠️ 5分後に自動予約を実行します", font=("", 12, "bold")).pack(pady=(0, 10))

        info = ttk.LabelFrame(frm, text="予約情報", padding=8)
        info.pack(fill="x", pady=4)

        try:
            dt = parse_datetime(entry["start_datetime"])
            time_str = dt.strftime("%H:%M")
        except Exception:
            time_str = entry.get("start_datetime", "")

        ttk.Label(info, text=f"クラス: {entry['class_name']}").pack(anchor="w")
        ttk.Label(info, text=f"スタジオ: {entry.get('studio', '')}").pack(anchor="w")
        ttk.Label(info, text=f"実行時刻: {time_str}").pack(anchor="w")

        self._cred_label = ttk.Label(frm, text="", foreground="red")
        self._cred_label.pack(pady=6)

        ttk.Label(
            frm,
            text="※ログイン情報が未入力の場合は今すぐ入力してください",
            foreground="gray",
        ).pack()

        btn_frm = ttk.Frame(frm)
        btn_frm.pack(pady=(12, 0))
        ttk.Button(btn_frm, text="このまま実行", command=self._confirm).pack(side="left", padx=8)
        ttk.Button(btn_frm, text="キャンセル", command=self._cancel).pack(side="left", padx=8)

    def update_cred_status(self, has_creds: bool):
        if has_creds:
            self._cred_label.config(text="ログイン情報: ✓ セット済み", foreground="green")
        else:
            self._cred_label.config(text="ログイン情報: ✗ 未入力", foreground="red")

    def _confirm(self):
        self._on_confirm()
        self.destroy()

    def _cancel(self):
        self._on_cancel()
        self.destroy()


# ─────────────────────────────────────────────────
# メインウィンドウ（画面1 + 画面2）
# ─────────────────────────────────────────────────
class MainWindow:
    def __init__(self, root, scheduler):
        self.root = root
        self.scheduler = scheduler
        self._schedules: list[dict] = []
        # ログイン情報はメモリのみ保持
        self._email: str = ""
        self._password: str = ""
        self._build_ui()
        self.refresh()

    # ── 認証情報アクセサ ──────────────────────────
    def get_credentials(self) -> tuple[str, str]:
        return self._email, self._password

    # ── UI 構築 ───────────────────────────────────
    def _build_ui(self):
        self.root.title("YARD ヨガ予約リマインダー")
        self.root.geometry("840x520")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # ── 画面1: ログイン情報パネル ──
        login_frm = ttk.LabelFrame(
            self.root, text="🔐 ログイン情報（保存されません）", padding=8
        )
        login_frm.pack(fill="x", padx=8, pady=(8, 0))

        grid = ttk.Frame(login_frm)
        grid.pack(fill="x")

        ttk.Label(grid, text="メールアドレス:").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        self._email_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self._email_var, width=34).grid(
            row=0, column=1, sticky="w", padx=4
        )

        ttk.Label(grid, text="パスワード:").grid(row=1, column=0, sticky="w", padx=4, pady=2)
        self._pass_var = tk.StringVar()
        ttk.Entry(grid, textvariable=self._pass_var, show="*", width=34).grid(
            row=1, column=1, sticky="w", padx=4
        )

        btn_col = ttk.Frame(grid)
        btn_col.grid(row=0, column=2, rowspan=2, padx=8)
        ttk.Button(btn_col, text="セット", width=8, command=self._set_credentials).pack(pady=2)
        ttk.Button(btn_col, text="クリア", width=8, command=self._clear_credentials).pack(pady=2)

        self._cred_status = ttk.Label(grid, text="未入力", foreground="gray")
        self._cred_status.grid(row=0, column=3, rowspan=2, padx=12)

        # ── 画面2: ツールバー ──
        toolbar = ttk.Frame(self.root, padding=4)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="新規追加", command=self._add).pack(side="left", padx=2)
        ttk.Button(toolbar, text="編集", command=self._edit).pack(side="left", padx=2)
        ttk.Button(toolbar, text="削除", command=self._delete).pack(side="left", padx=2)
        ttk.Separator(toolbar, orient="vertical").pack(side="left", padx=6, fill="y")
        ttk.Button(toolbar, text="予約完了に更新", command=self._mark_done).pack(side="left", padx=2)
        ttk.Button(toolbar, text="ステータス変更", command=self._update_status).pack(side="left", padx=2)
        ttk.Button(toolbar, text="更新", command=self.refresh).pack(side="right", padx=2)

        # ── 画面2: スケジュール一覧 ──
        tree_frm = ttk.Frame(self.root)
        tree_frm.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.tree = ttk.Treeview(
            tree_frm, columns=COLUMNS, show="headings", selectmode="browse"
        )
        for col in COLUMNS:
            self.tree.heading(col, text=COL_LABELS[col])
            self.tree.column(col, width=COL_WIDTHS[col], minwidth=60)

        vsb = ttk.Scrollbar(tree_frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self.tree.tag_configure("done", foreground="gray")
        self.tree.tag_configure("running", foreground="orange")
        self.tree.tag_configure("notified", foreground="blue")
        self.tree.tag_configure("error", foreground="red")

        self._status_bar = ttk.Label(self.root, text="", anchor="w", relief="sunken")
        self._status_bar.pack(fill="x", side="bottom")

    # ── ログイン情報操作 ──────────────────────────
    def _set_credentials(self):
        email = self._email_var.get().strip()
        password = self._pass_var.get()
        if not email or not password:
            messagebox.showwarning(
                "入力エラー", "メールアドレスとパスワードを両方入力してください。"
            )
            return
        self._email = email
        self._password = password
        self._cred_status.config(text="✓ 入力済み（メモリ保持中）", foreground="green")

    def _clear_credentials(self):
        self._email = ""
        self._password = ""
        self._email_var.set("")
        self._pass_var.set("")
        self._cred_status.config(text="未入力", foreground="gray")

    # ── 確認ダイアログ（スケジューラーから呼び出し） ──
    def show_confirm_dialog(self, entry, on_confirm, on_cancel=None):
        dlg = ConfirmDialog(
            self.root, entry, on_confirm, on_cancel if on_cancel else lambda: None
        )
        dlg.update_cred_status(bool(self._email and self._password))

    # ── 一覧更新 ─────────────────────────────────
    def refresh(self):
        self._schedules = load_schedules()
        self.tree.delete(*self.tree.get_children())
        for entry in self._schedules:
            status = entry["status"]
            tag = {
                "予約完了": "done",
                "実行中": "running",
                "通知済": "notified",
                "エラー": "error",
            }.get(status, "")
            self.tree.insert(
                "",
                "end",
                iid=entry["id"],
                values=(
                    entry["class_name"],
                    entry["start_datetime"],
                    entry.get("studio", ""),
                    status,
                ),
                tags=(tag,),
            )
        self._status_bar.config(text=f"登録件数: {len(self._schedules)}")

    def _selected_entry(self) -> dict | None:
        sel = self.tree.selection()
        if not sel:
            return None
        eid = sel[0]
        return next((e for e in self._schedules if e["id"] == eid), None)

    # ── CRUD ────────────────────────────────────
    def _add(self):
        dlg = EntryDialog(self.root)
        if dlg.result is None:
            return
        r = dlg.result
        entry = new_entry(r["class_name"], r["studio"], r["start_datetime"], r["memo"])
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
        entry["studio"] = r["studio"]
        entry["url"] = STUDIO_MAP.get(r["studio"], "")
        entry["start_datetime"] = r["start_datetime"].strftime("%Y-%m-%d %H:%M")
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

    def _mark_done(self):
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("選択なし", "スケジュールを選択してください。")
            return
        entry["status"] = "予約完了"
        save_schedules(self._schedules)
        self.refresh()

    def _update_status(self):
        entry = self._selected_entry()
        if entry is None:
            messagebox.showinfo("選択なし", "スケジュールを選択してください。")
            return
        statuses = ["待機中", "通知済", "実行中", "予約完了", "エラー"]
        win = tk.Toplevel(self.root)
        win.title("ステータス変更")
        win.resizable(False, False)
        win.grab_set()
        ttk.Label(win, text="新しいステータスを選択:").pack(padx=12, pady=(12, 4))
        var = tk.StringVar(value=entry["status"])
        for s in statuses:
            ttk.Radiobutton(win, text=s, variable=var, value=s).pack(anchor="w", padx=20)

        def apply():
            entry["status"] = var.get()
            save_schedules(self._schedules)
            self.refresh()
            win.destroy()

        ttk.Button(win, text="適用", command=apply).pack(pady=8)
        win.wait_window()

    # ── ウィンドウ閉じる → トレイ格納 ──────────
    def _on_close(self):
        self._try_minimize_to_tray()

    def _try_minimize_to_tray(self):
        try:
            import pystray
            from PIL import Image, ImageDraw

            def _make_icon():
                img = Image.new("RGB", (64, 64), color=(72, 153, 105))
                d = ImageDraw.Draw(img)
                d.ellipse([8, 8, 56, 56], outline="white", width=4)
                d.line([32, 14, 32, 50], fill="white", width=3)
                d.line([14, 32, 50, 32], fill="white", width=3)
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
            icon = pystray.Icon(
                "yard_yoga", _make_icon(), "YARD ヨガ予約リマインダー", menu
            )
            self.root.withdraw()
            threading.Thread(target=icon.run, daemon=True).start()
        except ImportError:
            self.root.quit()
