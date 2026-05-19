import threading
import time
from datetime import datetime, timedelta

from data_manager import parse_datetime, load_schedules, save_schedules

try:
    from plyer import notification as plyer_notification
    _PLYER = True
except ImportError:
    _PLYER = False


def _notify(title: str, message: str) -> None:
    if _PLYER:
        try:
            plyer_notification.notify(
                title=title,
                message=message,
                app_name="YARD ヨガ予約リマインダー",
                timeout=10,
            )
        except Exception:
            pass
    print(f"[通知] {title}: {message}")


class ReminderScheduler:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._sent: set[str] = set()
        self._pending: set[str] = set()  # 自動予約が確認済みのエントリID

        self.on_status_change = None
        self.on_confirm_dialog = None
        self._credential_getter = None

    def set_credential_getter(self, getter):
        self._credential_getter = getter

    def set_gui_callbacks(self, on_status_change=None, on_confirm_dialog=None):
        self.on_status_change = on_status_change
        self.on_confirm_dialog = on_confirm_dialog

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self._check_schedules()
            except Exception as exc:
                print(f"[スケジューラー] チェック中にエラー: {exc}")
            time.sleep(30)

    def _check_schedules(self):
        schedules = load_schedules()
        changed = False
        now = datetime.now().replace(second=0, microsecond=0)

        for entry in schedules:
            if entry["status"] == "予約完了":
                continue

            try:
                start = parse_datetime(entry["start_datetime"])
            except ValueError:
                continue

            eid = entry["id"]
            name = entry["class_name"]

            # 前日同時刻リマインド
            key_1d = f"{eid}_1d"
            if key_1d not in self._sent:
                target = start - timedelta(days=1)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【前日リマインド】{name}",
                        f"明日 {start.strftime('%H:%M')} にNAOクラスの予約受付が始まります",
                    )
                    self._sent.add(key_1d)

            # 1時間前リマインド
            key_1h = f"{eid}_1h"
            if key_1h not in self._sent:
                target = start - timedelta(hours=1)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【1時間前リマインド】{name}",
                        "1時間後に自動予約を実行します。ログイン情報を入力してください",
                    )
                    self._sent.add(key_1h)

            # 5分前 → 確認ダイアログ
            key_5m = f"{eid}_5m"
            if key_5m not in self._sent:
                target = start - timedelta(minutes=5)
                if abs((now - target).total_seconds()) < 60:
                    self._sent.add(key_5m)
                    if self.on_confirm_dialog:
                        def _make_cb(entry_id):
                            def on_confirm():
                                self._pending.add(entry_id)
                            def on_cancel():
                                self._pending.discard(entry_id)
                            return on_confirm, on_cancel
                        on_confirm, on_cancel = _make_cb(eid)
                        self.on_confirm_dialog(entry, on_confirm, on_cancel)
                    else:
                        # GUIなし時は自動でキューに積む
                        self._pending.add(eid)

            # 予約受付開始 → 自動予約実行
            key_open = f"{eid}_open"
            if key_open not in self._sent:
                if now >= start and (now - start).total_seconds() < 90:
                    self._sent.add(key_open)
                    if eid in self._pending:
                        self._pending.discard(eid)
                        entry["status"] = "実行中"
                        changed = True
                        self._launch_booking(entry, schedules)
                    else:
                        _notify(
                            f"【予約受付開始】{name}",
                            "自動予約がキャンセル済みです。手動で予約してください。",
                        )
                        entry["status"] = "通知済"
                        changed = True

        if changed:
            save_schedules(schedules)
            if self.on_status_change:
                self.on_status_change()

    def _launch_booking(self, entry: dict, schedules: list[dict]):
        if self._credential_getter is None:
            _notify("【エラー】", "ログイン情報取得関数が未設定です。")
            entry["status"] = "エラー"
            return

        email, password = self._credential_getter()
        if not email or not password:
            _notify(
                f"【警告】{entry['class_name']}",
                "ログイン情報が未入力のため自動予約をキャンセルしました。",
            )
            entry["status"] = "エラー"
            save_schedules(schedules)
            if self.on_status_change:
                self.on_status_change()
            return

        _notify(f"【自動予約開始】{entry['class_name']}", "Chromiumを起動して予約を試みます...")

        def run():
            from auto_booking import AutoBooker
            booker = AutoBooker(email, password)
            success = booker.book(entry)
            for e in schedules:
                if e["id"] == entry["id"]:
                    e["status"] = "予約完了" if success else "エラー"
                    break
            save_schedules(schedules)
            if self.on_status_change:
                self.on_status_change()

        threading.Thread(target=run, daemon=True).start()
