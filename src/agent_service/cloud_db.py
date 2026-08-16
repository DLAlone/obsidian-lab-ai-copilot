import os
import json
from datetime import datetime

class CloudDB:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), "cloud_database.json")
        self._init_db()

    def _init_db(self):
        if not os.path.exists(self.db_path):
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump({"members": {}, "qa": []}, f, ensure_ascii=False, indent=2)

    def _read(self):
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"members": {}, "qa": []}

    def _write(self, data):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def update_member_upload(self, username, file_count=1):
        data = self._read()
        if username not in data["members"]:
            data["members"][username] = {
                "total_docs": 0,
                "last_sync": ""
            }
        
        data["members"][username]["total_docs"] += file_count
        data["members"][username]["last_sync"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._write(data)

    def get_cloud_status(self):
        data = self._read()
        return [
            {"username": k, "total_docs": v["total_docs"], "last_sync": v["last_sync"]}
            for k, v in data.get("members", {}).items()
        ]

db = CloudDB()
