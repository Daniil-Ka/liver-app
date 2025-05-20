import time
start_time = time.time()

from pathlib import Path
import torch
from ultralytics import YOLO

path = Path(__file__).parent / "best (10).pt"
model = YOLO(path)

print(
    f"CUDA: {torch.version.cuda} | "
    f"cuDNN: {torch.backends.cudnn.version()} | "
    f"GPU доступен: {torch.cuda.is_available()}"
)

if torch.cuda.is_available():
    print(f"Всего CUDA-устройств: {torch.cuda.device_count()}")
    for i in range(torch.cuda.device_count()):
        print(f"[{i}] {torch.cuda.get_device_name(i)}")
else:
    print("CUDA не доступна — будет использоваться CPU.")

end_time = time.time()
loading_time = end_time - start_time

print(f'Модель загружена за {round(loading_time, 3)}с')
