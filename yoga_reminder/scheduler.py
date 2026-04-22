import threading
import time
import webbrowser
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
            app_name="ヨガ予約リマインダー",
            timeout=10,
        )
    else:
        print(f"[通知] {title}: {message}")


class ReminderScheduler:
    def __init__(self, on_status_change=None):
        self._stop_event = threading.Event()
        self._thread = None
        self._sent: set[str] = set()
        self.on_status_change = on_status_change

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
            if entry["status"] == "予約完了":
                continue

            try:
                start = parse_datetime(entry["start_datetime"])
            except ValueError:
                continue

            eid = entry["id"]
            name = entry["class_name"]
            url = entry["url"]

            # 前日同時刻 (±1分以内)
            key_1d = f"{eid}_1d"
            if key_1d not in self._sent:
                target = start - timedelta(days=1)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【前日リマインド】{name}",
                        f"明日 {start.strftime('%H:%M')} から予約受付開始です！",
                    )
                    self._sent.add(key_1d)

            # 1時間前
            key_1h = f"{eid}_1h"
            if key_1h not in self._sent:
                target = start - timedelta(hours=1)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【1時間前リマインド】{name}",
                        f"1時間後（{start.strftime('%H:%M')}）に予約受付開始です！",
                    )
                    self._sent.add(key_1h)

            # 5分前
            key_5m = f"{eid}_5m"
            if key_5m not in self._sent:
                target = start - timedelta(minutes=5)
                if abs((now - target).total_seconds()) < 60:
                    _notify(
                        f"【5分前リマインド】{name}",
                        f"あと5分で予約受付開始（{start.strftime('%H:%M')}）です！",
                    )
                    self._sent.add(key_5m)

            # 予約受付開始
            key_open = f"{eid}_open"
            if key_open not in self._sent:
                if now >= start and (now - start).total_seconds() < 90:
                    _notify(
                        f"【予約受付開始】{name}",
                        "予約受付が開始されました！ブラウザを起動します。",
                    )
                    if url:
                        webbrowser.open(url)
                    entry["status"] = "通知済"
                    changed = True
                    self._sent.add(key_open)

        if changed:
            save_schedules(schedules)
            if self.on_status_change:
                self.on_status_change()
