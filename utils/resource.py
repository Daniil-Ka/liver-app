import os
import sys


def resource_path(relative_path: str) -> str:
    """Возвращает корректный путь к файлу (в .exe и в разработке)"""
    return os.path.join(getattr(sys, "_MEIPASS", os.path.abspath(".")), relative_path)
