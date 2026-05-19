import json
import os
import uuid
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "yard_schedule.json")
DATETIME_FMT = "%Y-%m-%d %H:%M"

STUDIO_MAP = {
    "南流山スタジオ": "https://yard.hacomono.jp/reserve/schedule/4/10",
    "おおたかの森スタジオ": "https://yard.hacomono.jp/reserve/schedule/6/16",
}


def load_schedules() -> list[dict]:
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_schedules(schedules: list[dict]) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(schedules, f, ensure_ascii=False, indent=2)


def new_entry(class_name: str, studio: str, start_dt: datetime, memo: str) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "class_name": class_name,
        "studio": studio,
        "url": STUDIO_MAP.get(studio, ""),
        "start_datetime": start_dt.strftime(DATETIME_FMT),
        "memo": memo,
        "status": "待機中",
    }


def parse_datetime(s: str) -> datetime:
    return datetime.strptime(s, DATETIME_FMT)
