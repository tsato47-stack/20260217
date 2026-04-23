import threading
import time
from datetime import datetime, timedelta

from data_manager import parse_datetime, load_schedules, save_schedules

try:
    from plyer import notification as plyer_notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


def _notify(title: str, message: str) -> None:
    if PLYER_AVAILABLE:
        plyer_notification.notify(
            title=title,
            message=message,
            app_name="YARD ヨガ予約リマインダー",
            timeout=10,
        )
    else:
        print(f"[通知] {title}: {message}")


class ReminderScheduler:
    def __init__(self):
        self._stop_event = threading.Event()
        self._thread = None
        self._sent: set[str] = set()
        self.on_status_change = None
        # ログイン情報はメモリのみ（スケジューラーは参照のみ）
        self._credentials: dict | None = None
        # 5分前ダイアログコールバック（gui.py がセット）
        self.on_pre_booking_warning = None
        # 予約実行コールバック（gui.py がセット）
        self.on_execute_booking = None

    def set_credentials(self, email: str, password: str):
        self._credentials = {"email": email, "password": password}

    def clear_credentials(self):
        self._credentials = None

    def has_credentials(self) -> bool:
        return self._credentials is not None

    def get_credentials(self) -> tuple[str, str] | None:
        if self._credentials:
            return self._credentials["email"], self._credentials["password"]
        return None

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    def _run(self):
        while not self._stop_event.is_set():
            self._check_schedules()
            time.sleep(30)

    def _check_schedules(self):
        schedules = load_schedules()
        changed = False
        now = datetime.now().replace(second=0, microsecond=0)

        for entry in schedules:
            if entry["status"] in ("予約完了",):
                continue

            try:
                start = parse_datetime(entry["start_datetime"])
            except ValueError:
                continue

            eid = entry["id"]
            name = entry["class_name"]
            studio = entry.get("studio", "")
            start_str = start.strftime("%H:%M")

            # 前日同時刻 (±1分以内)
            key_1d = f"{eid}_1d"
            if key_1d not in self._sent:
                target = start - timedelta(days=1)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【前日リマインド】{name}",
                        f"明日 {start_str} に {studio} の予約受付が開始します！",
                    )
                    self._sent.add(key_1d)

            # 1時間前
            key_1h = f"{eid}_1h"
            if key_1h not in self._sent:
                target = start - timedelta(hours=1)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【1時間前リマインド】{name}",
                        f"1時間後（{start_str}）に自動予約を実行します。ログイン情報を入力してください。",
                    )
                    self._sent.add(key_1h)

            # 5分前 → 確認ダイアログ
            key_5m = f"{eid}_5m"
            if key_5m not in self._sent:
                target = start - timedelta(minutes=5)
                if abs((now - target).total_seconds()) < 60:
                    self._sent.add(key_5m)
                    if self.on_pre_booking_warning:
                        self.on_pre_booking_warning(entry)

            # 予約受付開始 → 自動実行
            key_open = f"{eid}_open"
            if key_open not in self._sent:
                if now >= start and (now - start).total_seconds() < 90:
                    self._sent.add(key_open)
                    if self.on_execute_booking:
                        self.on_execute_booking(entry)
                    entry["status"] = "実行中"
                    changed = True

        if changed:
            save_schedules(schedules)
            if self.on_status_change:
                self.on_status_change()


def send_booking_success_notification(class_name: str, shot_path: str):
    _notify(
        f"【予約完了】{class_name}",
        f"予約が完了しました！ スクリーンショット: {shot_path}",
    )


def send_booking_failure_notification(class_name: str, reason: str):
    _notify(
        f"【予約失敗】{class_name}",
        reason,
    )
