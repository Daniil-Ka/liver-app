import os
import pydicom
import numpy as np
from pydicom.uid import generate_uid

def merge_dicom_series_from_folder(folder_path, output_path):
    # Получаем список всех файлов с расширением .dcm из папки
    dicom_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith('.dcm')
    ]

    if not dicom_files:
        print("В указанной папке не найдено DICOM файлов.")
        return

    # Считываем все DICOM файлы
    slices = [pydicom.dcmread(f) for f in dicom_files]

    # Сортируем срезы по оси Z (ImagePositionPatient) или по InstanceNumber
    try:
        slices.sort(key=lambda s: float(s.ImagePositionPatient[2]))
    except (AttributeError, KeyError):
        slices.sort(key=lambda s: int(s.InstanceNumber))

    # Собираем 3D-массив пикселей (число срезов, высота, ширина)
    pixel_arrays = [s.pixel_array for s in slices]
    volume = np.stack(pixel_arrays, axis=0)

    # Используем первый срез как шаблон для нового DICOM
    new_ds = slices[0]
    new_ds.SOPInstanceUID = generate_uid()
    new_ds.file_meta.MediaStorageSOPInstanceUID = new_ds.SOPInstanceUID

    # Обновляем теги для многофреймового DICOM
    new_ds.NumberOfFrames = str(volume.shape[0])
    new_ds.Rows = volume.shape[1]
    new_ds.Columns = volume.shape[2]
    new_ds.PixelData = volume.tobytes()

    # Сохраняем объединённый DICOM-файл
    new_ds.save_as(output_path)
    print(f"Объединённый DICOM сохранён в: {output_path}")

if __name__ == '__main__':
    folder_path = "./"  # замените на путь к вашей папке с DICOM файлами
    output_file = "merged.dcm"
    merge_dicom_series_from_folder(folder_path, output_file)
