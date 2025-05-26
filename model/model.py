import time

from utils import resource_path

start_time = time.time()

from pathlib import Path
import torch
from ultralytics import YOLO

path = resource_path("model/weights.pt")
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
    model.to('cuda')
else:
    print("CUDA не доступна — будет использоваться CPU.")
device = next(model.parameters()).device
print(f"YOLOv8 работает на устройстве: {device}")

end_time = time.time()
loading_time = end_time - start_time

print(f'Модель загружена за {round(loading_time, 3)}с')
