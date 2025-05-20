import os
from typing import List

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from PIL import ImageOps, ImageChops
from dicom2jpg import dicom2img

import pydicom
from pydicom.uid import generate_uid
from skimage.transform import resize

from model.model import model


def show_masks_grid(images, cols=5):
    rows = (len(images) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(cols * 3, rows * 3))

    for idx, ax in enumerate(axes.flat):
        if idx < len(images):
            ax.imshow(images[idx], cmap="gray")
            ax.set_title(f"Mask {idx}")
        ax.axis('off')

    plt.tight_layout()
    plt.show()


def find_dicom_files(folder_path, recursive: bool = True) -> List[os.PathLike]:
    """
    Ищет все dicom файлы в каталоге
    :param recursive:  Искать во вложенныз папках?
    :param folder_path: Целевавая папка
    :return: список путей файлов .dcm
    """
    find_dicom = []

    if recursive:
        for root, _, files in os.walk(folder_path):
            for file in files:
                if file.lower().endswith(".dcm"):
                    find_dicom.append(os.path.join(root, file))
    else:
        # Только файлы в указанной директории (без рекурсии)
        for file in os.listdir(folder_path):
            full_path = os.path.join(folder_path, file)
            if os.path.isfile(full_path) and file.lower().endswith(".dcm"):
                find_dicom.append(full_path)
                
    return find_dicom


def process_dicom(file: os.PathLike, output_dir="DICOM_MASKED1") -> os.PathLike:
    """
    Обрабывает dicom и оставляет на нем только печень, остальное зануляет.
    :param file: источник
    :param output_dir: папка, куда сохранится новый файл
    :return: Путь к обработанному изображению
    """

    # 1) Читаем исходный DICOM
    ds = pydicom.dcmread(file)
    original_pixels = ds.pixel_array  # e.g. shape (H, W), dtype uint16

    # 2) Формируем 640×640 grayscale для модели
    img_data = dicom2img(file)
    if img_data.ndim == 3:
        img_data = img_data[:, :, 0]
    img_data = ((img_data - img_data.min()) / (img_data.max() - img_data.min()) * 255).astype(np.uint8)
    base_image = Image.fromarray(img_data).convert("L")
    base_image = ImageOps.fit(base_image, (640, 640), Image.Resampling.LANCZOS)
    rgb = np.array(base_image.convert("RGB"))

    # 3) Получаем маски от модели и собираем их в один слой
    results = model.predict(rgb)
    combined_mask = Image.new("L", base_image.size, 0)
    if results[0].masks is not None:
        for mask in results[0].masks.data.cpu().numpy():
            m = (mask.astype(np.uint8) * 255)
            combined_mask = ImageChops.lighter(combined_mask, Image.fromarray(m))

    # 4) Преобразуем маску в булев массив и масштабируем обратно к исходному размеру
    mask_arr_640 = (np.array(combined_mask) > 0).astype(np.uint8)
    mask_resized = resize(
        mask_arr_640,
        original_pixels.shape,
        order=0,           # nearest-neighbor, чтобы сохранить четкую границу
        preserve_range=True,
        anti_aliasing=False
    ).astype(bool)

    # 5) Применяем маску к оригинальным пикселям
    masked_pixels = np.where(mask_resized, original_pixels, 0)

    # 6) Обновляем PixelData, не трогаем BitsAllocated/BitsStored и т.д.
    ds.PixelData = masked_pixels.tobytes()
    # Rows/Columns в ds уже исходные, не нужно менять
    # Генерим новый UID, чтобы не было дублирования
    ds.SOPInstanceUID = generate_uid()
    ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID

    # Сохраняем
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, f"masked_{os.path.basename(file)}")
    ds.save_as(out_path)

    return out_path

if __name__ == "__main__":
    dicom_files = find_dicom_files('../DICOM_DATASET')
    processed_dicom = [process_dicom(dicom) for dicom in dicom_files]
