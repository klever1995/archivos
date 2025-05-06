------------metodos que van a ayudar a controlar la linea donde se quedo---------------------archivo state_manager.py
import json
import os
from pathlib import Path

class LogStateManager:
    def __init__(self, state_file=".log_processor_state.json"):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self):
        if Path(self.state_file).exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {}

    def save_state(self, file_path, inode, offset, line_number):
        self.state[file_path] = {
            "inode": inode,
            "last_offset": offset,
            "last_line": line_number,
            "timestamp": int(os.path.getmtime(file_path))
        }
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def get_last_position(self, file_path):
        file_info = self.state.get(file_path)
        if not file_info:
            return 0  # Archivo nuevo
        
        current_inode = os.stat(file_path).st_ino
        if file_info["inode"] == current_inode:
            return file_info["last_offset"]
        return 0  # Archivo rotado/modificado
