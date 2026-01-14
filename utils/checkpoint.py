import os
import json
import atexit
import tempfile
from utils.logger import logger

class Checkpoint:
    def __init__(self, path: str):
        self.path = path
        self.data = {}
        self._last_saved_data = {}
        self.hit = False
        self._load_from_disk()
        atexit.register(self._auto_save)

    def _load_from_disk(self):
        if not os.path.exists(self.path):
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            logger.info(f"初始化 Checkpoint 文件: {self.path}")
            self._write()
        else:
            try:
                with open(self.path, "r", encoding="utf-8") as file:
                    self.data = json.load(file)
                self._last_saved_data = self.data.copy()  # 初始化备份
                logger.info(f"加载 Checkpoint 成功: {len(self.data)} 个键值对")
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                logger.error(f"Checkpoint 文件损坏，初始化为空: {e}")
                self.data = {}

    def _write(self):
        if self.data == self._last_saved_data:
            return

        directory = os.path.dirname(self.path)
        with tempfile.NamedTemporaryFile('w', dir=directory, delete=False, encoding='utf-8') as tf:
            json.dump(self.data, tf, indent=4, ensure_ascii=False)
            temp_name = tf.name
        
        os.replace(temp_name, self.path)
        self._last_saved_data = self.data.copy()

    def _auto_save(self):
        if self.data != self._last_saved_data:
            logger.info(f"程序退出，正在自动保存 Checkpoint 至 {self.path}...")
            self._write()

    def seek(self, data: dict) -> bool:
        is_same = (data == self.data)

        if is_same:
            self.hit = True
        else:
            if not self.hit:
                return False

        self.data = data
        self._write()
        return self.hit
