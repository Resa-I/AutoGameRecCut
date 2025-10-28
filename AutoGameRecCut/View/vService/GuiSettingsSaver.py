import json
import os

#Save and load input values
class GuiSettingsSaver:
    FILE = "settings.json"

    @staticmethod
    def load():
        if os.path.exists(GuiSettingsSaver.FILE):
            with open(GuiSettingsSaver.FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    @staticmethod
    def save(data: dict):
        with open(GuiSettingsSaver.FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
