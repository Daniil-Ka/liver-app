import sys

import numpy as np
import vtk
from PyQt6 import uic, QtWidgets
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QFileDialog
from vtk import vtkInteractorStyleTrackballCamera
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.util.numpy_support import vtk_to_numpy


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super(MainWindow, self).__init__(*args, **kwargs)
        self.reader2 = None
        self.actor = None

        self.body_data = None
        self.liver_data = None

        self.mapper = None
        self.volume = None

        self.bounds = None
        self.slicing_planes = None

        self.init_ui()

        # Добавляем обработчик нажатия левой кнопки мыши для рисования кистью
        self.render_window_interactor.AddObserver("KeyPressEvent", self.on_key_press)

        self.render_window_interactor.AddObserver("LeftButtonPressEvent", self.on_left_button_press)

        self.render_window_interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())

    ###############################################################################################
    #                                   UI Initialization                                         #
    ###############################################################################################

    def init_ui(self):
        """
        Загружает UI, настраивает окно, VTK-виджет и соединяет сигналы.
        """
        self.ui = uic.loadUi('mainwindow.ui', self)
        self.setWindowTitle("DICOM Viewer")
        self.setWindowIcon(QIcon("icons\\skull.png"))
        # Инициализация переменных
        self.reader = None
        self.actor = None
        self.iso_value = 50

        # Создаём VTK render window
        self.vtk_widget = QVTKRenderWindowInteractor(self.ui.viewWidget)
        self.ui.loadButton.clicked.connect(self.load_dicom_folder)
        self.ui.renderButton.clicked.connect(self.render_volume)

        self.ui.iso_slider.setMinimum(1)
        self.ui.iso_slider.setMaximum(255)
        self.ui.iso_slider.setValue(50)
        self.ui.iso_slider.valueChanged.connect(self.update_iso_value)

        self.set_slider_properties(self.ui.ambientSlider, self.ui.diffuseSlider, self.ui.specularSlider)

        # Настраиваем VTK renderer
        self.renderer = vtk.vtkRenderer()
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self.render_window_interactor = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.render_window = self.vtk_widget.GetRenderWindow()

        # Режим рендеринга: ray casting по умолчанию
        self.ui.rayCastRadio.setChecked(True)
        self.ui.realTimeCheck.setChecked(True)
        self.ui.ambientSlider.valueChanged.connect(self.update_ambient)
        self.ui.diffuseSlider.valueChanged.connect(self.update_diffuse)
        self.ui.specularSlider.valueChanged.connect(self.update_specular)

        self.hide_surface_widgets()

    def show_surface_widgets(self):
        self.ui.iso_slider.show()
        self.ui.isoValue.show()
        self.ui.frameRayCast.hide()

    def hide_surface_widgets(self):
        self.ui.iso_slider.hide()
        self.ui.isoValue.hide()
        self.ui.frameRayCast.show()

    def set_slider_properties(self, ambient_slider, diffuse_slider, specular_slider):
        ambient_slider.setMinimum(0)
        ambient_slider.setMaximum(10)
        diffuse_slider.setMinimum(0)
        diffuse_slider.setMaximum(10)
        specular_slider.setMinimum(0)
        specular_slider.setMaximum(10)
        ambient_slider.setValue(4)
        diffuse_slider.setValue(6)
        specular_slider.setValue(2)

    def resizeEvent(self, event):
        super(MainWindow, self).resizeEvent(event)
        self.vtk_widget.resize(self.ui.viewWidget.size())

    ###############################################################################################
    #                                   Property Update Functions                                 #
    ###############################################################################################

    def update_color_property(self, slider, label, render_method):
        property_value = slider.value() / 10.0
        label.setText(f"{label.text().split(':')[0]}: {property_value}")
        if self.ui.realTimeCheck.isChecked():
            if self.ui.rayCastRadio.isChecked():
                render_method()

    def update_ambient(self):
        self.update_color_property(self.ui.ambientSlider, self.ui.AmbientLabel, self.render_ray_casting)

    def update_diffuse(self):
        self.update_color_property(self.ui.diffuseSlider, self.ui.DiffuseLabel, self.render_ray_casting)

    def update_specular(self):
        self.update_color_property(self.ui.specularSlider, self.ui.SpecularLabel, self.render_ray_casting)

    def update_iso_value(self):
        self.iso_value = self.ui.iso_slider.value()
        self.ui.isoValue.setText(f"ISO Value: {self.iso_value}")
        if self.ui.surfaceRadio.isChecked() and self.ui.realTimeCheck.isChecked():
            self.render_iso_surface()

    ###############################################################################################
    #                                  Loading & Rendering Functions                              #
    ###############################################################################################

    def load_dicom_folder(self):
        """
        Загружает DICOM-серию из фиксированных папок.
        folder1 – для исходного объёма (для лучевого рендеринга),
        folder2 – для редактирования (операции кисти будут изменять только этот объект).
        Таким образом, луч (при ray casting) будет проходить через данные из folder1.
        """
        if self.actor:
            self.renderer.RemoveActor(self.actor)
        self.renderer.RemoveAllViewProps()

        # Задаём фиксированные пути к папкам (закомментирован вызов диалога)
        folder_dialog = QFileDialog.getExistingDirectory(self, "Выберите папку с снимками DICOM")
        folder1 = r"DICOM_DATASET"
        folder2 = r"DICOM_MASKED"

        # Загрузка исходного объёма из folder1 (для лучевого рендеринга)
        self.reader1 = vtk.vtkDICOMImageReader()
        self.reader1.SetDirectoryName(folder1)
        self.reader1.Update()
        self.body_data = vtk.vtkImageData()
        self.body_data.DeepCopy(self.reader1.GetOutput())

        # Загрузка редактируемого объекта из folder2 (для операций кистью)
        self.reader2 = vtk.vtkDICOMImageReader()
        self.reader2.SetDirectoryName(folder2)
        self.reader2.Update()
        self.liver_data = vtk.vtkImageData()
        self.liver_data.DeepCopy(self.reader2.GetOutput())

        # Для первичного отображения используем 2D-актер, привязанный к данным из folder1
        self.mapper = vtk.vtkImageMapper()
        self.mapper.SetInputConnection(self.reader1.GetOutputPort())
        self.actor = vtk.vtkActor2D()
        self.actor.SetMapper(self.mapper)
        self.renderer.AddActor(self.actor)

        # Рендерим объём и настраиваем окно
        self.render_volume()
        self.vtk_widget.resize(self.ui.viewWidget.size())
        self.renderer.ResetCamera()
        self.render_window.Render()

        # Получаем камеру
        camera = self.renderer.GetActiveCamera()
        # Центр объёма
        center = self.body_data.GetCenter()
        bounds = self.body_data.GetBounds()
        # Радиус сцены — например, высота по оси Y
        y_range = bounds[3] - bounds[2]  # ymax - ymin

        # Настраиваем фокус на центр объекта
        camera.SetFocalPoint(center)

        # Ставим камеру выше по Y, чтобы смотреть "с фронта"
        camera.SetPosition(center[0], center[1] + y_range * 1.5, center[2])

        # Указываем, что вверх — ось Z
        camera.SetViewUp(0, 0, -1)

        # Обновляем обрезку (важно!)
        self.renderer.ResetCameraClippingRange()

        self.render_ray_casting()


    def render_volume(self):
        """
        Выбирает режим рендеринга и вызывает соответствующий метод.
        """
        if self.reader:
            if self.ui.surfaceRadio.isChecked():
                print(2)
                self.show_surface_widgets()
                self.render_iso_surface()
            elif self.ui.rayCastRadio.isChecked():
                print(1)
                self.hide_surface_widgets()
                self.render_ray_casting()

    def render_iso_surface(self):
        """
        Рендерит изоповерхность с помощью vtkMarchingCubes.
        """
        if self.reader:
            camera = self.renderer.GetActiveCamera()
            position = camera.GetPosition()
            focal_point = camera.GetFocalPoint()

            marching_cubes = vtk.vtkMarchingCubes()
            marching_cubes.SetInputConnection(self.reader.GetOutputPort())
            marching_cubes.SetValue(0, self.ui.iso_slider.value())

            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(marching_cubes.GetOutputPort())

            actor = vtk.vtkActor()
            actor.SetMapper(mapper)

            # Создаём копию актора со сдвигом (для примера)
            copy_actor = vtk.vtkActor()
            copy_actor.SetMapper(mapper)
            transform = vtk.vtkTransform()
            transform.Translate(100, 0, 0)
            copy_actor.SetUserTransform(transform)

            self.renderer.RemoveAllViewProps()
            self.renderer.AddActor(actor)
            self.renderer.AddActor(copy_actor)

            camera.SetPosition(position)
            camera.SetFocalPoint(focal_point)
            self.render_window.Render()

    def calculate_liver_volume(self, threshold=50):
        """
        Вычисляет объём красного тела по заданному пороговому значению интенсивности.
        :param threshold: пороговое значение, выше которого воксель считается принадлежащим красной области.
        :return: объём красного тела (например, в мм³, если spacing в мм)
        """
        # Получаем скалярное поле редактируемого объёма (красного тела)
        scalars = self.liver_data.GetPointData().GetScalars()
        # Преобразуем данные в массив NumPy
        np_scalars = vtk_to_numpy(scalars)

        # Подсчитываем число вокселей, где интенсивность >= threshold
        red_voxel_count = np.count_nonzero(np_scalars >= threshold)

        # Получаем параметры spacing (размеры вокселя)
        spacing = self.liver_data.GetSpacing()  # (dx, dy, dz)
        voxel_volume = spacing[0] * spacing[1] * spacing[2]

        # Общий объём вычисляем как число вокселей, умноженное на объём одного вокселя
        total_volume = red_voxel_count * voxel_volume

        print("Объём печени:", round(total_volume / 1e6, 4), 'дц^3')
        return total_volume

    def init_slicing_plane(self):
        """
        Инициализирует срез (движущуюся плоскость) по данным исходного объёма.
        Плоскость охватывает область по осям X и Y при фиксированном значении Z,
        которое будет анимированно изменяться.
        """
        if not self.body_data:
            return

        bounds = self.body_data.GetBounds()  # (xmin, xmax, ymin, ymax, zmin, zmax)
        xmin, xmax, ymin, ymax, zmin, zmax = bounds
        self.slice_z_position = zmin
        self.slice_direction = 1  # 1 – движение вверх, -1 – вниз

        self.plane_source = vtk.vtkPlaneSource()
        self.plane_source.SetOrigin(xmin, ymin, self.slice_z_position)
        self.plane_source.SetPoint1(xmax, ymin, self.slice_z_position)
        self.plane_source.SetPoint2(xmin, ymax, self.slice_z_position)
        self.plane_source.SetResolution(10, 10)

        self.plane_mapper = vtk.vtkPolyDataMapper()
        self.plane_mapper.SetInputConnection(self.plane_source.GetOutputPort())

        self.plane_actor = vtk.vtkActor()
        self.plane_actor.SetMapper(self.plane_mapper)
        self.plane_actor.GetProperty().SetColor(0, 1, 0)  # зеленый цвет
        self.plane_actor.GetProperty().SetOpacity(0.5)  # полупрозрачность

        self.renderer.AddActor(self.plane_actor)

        # Запускаем таймер для анимации среза
        self.slice_timer = QTimer(self)
        self.slice_timer.timeout.connect(self.update_slicing_plane)
        self.slice_timer.start(20)  # обновление каждые 100 мс

    def calculate_visible_slice_volume(self, threshold=50):
        """
        Вычисляет объем печени только для видимых вокселей в пределах текущих границ (bounding box).
        """
        if not self.liver_data:
            print("No liver data to calculate volume")
            return 0.0

        # Получаем скалярные данные среза
        scalars = self.liver_data.GetPointData().GetScalars()
        np_scalars = vtk_to_numpy(scalars)

        # Получаем параметры среза и области
        origin = self.liver_data.GetOrigin()
        spacing = self.liver_data.GetSpacing()
        dims = self.liver_data.GetDimensions()

        # Преобразуем одномерный массив в трехмерный
        np_scalars_3d = np_scalars.reshape(dims[2], dims[1], dims[0])

        # Вычисляем объем одного вокселя
        voxel_volume = spacing[0] * spacing[1] * spacing[2]

        # Получаем текущие границы среза
        xmin, xmax, ymin, ymax, zmin, zmax = self.bounds

        # Переводим индексы среза в координаты
        ixmin = int((xmin - origin[0]) / spacing[0])
        ixmax = int((xmax - origin[0]) / spacing[0])
        iymin = int((ymin - origin[1]) / spacing[1])
        iymax = int((ymax - origin[1]) / spacing[1])
        izmin = int((zmin - origin[2]) / spacing[2])
        izmax = int((zmax - origin[2]) / spacing[2])

        # Ограничиваем индексы допустимыми значениями, чтобы не выйти за пределы массива
        ixmin = max(ixmin, 0)
        ixmax = min(ixmax, dims[0])
        iymin = max(iymin, 0)
        iymax = min(iymax, dims[1])
        izmin = max(izmin, 0)
        izmax = min(izmax, dims[2])

        # Подсчитываем количество видимых вокселей в пределах этих границ
        visible_voxel_count = np.count_nonzero(np_scalars_3d[izmin:izmax, iymin:iymax, ixmin:ixmax] >= threshold)

        # Общий объем = количество видимых вокселей * объем одного вокселя
        total_volume = visible_voxel_count * voxel_volume

        # Преобразуем объем в кубические сантиметры
        volume_in_cubic_centimeters = total_volume / 1000.0  # если spacing в мм, то объем в куб. см

        # Обновляем текст на UI для отображения объема
        self.ui.volume.setText(f"Объем печени: {round(volume_in_cubic_centimeters, 4)} см^3")

        print(f"Объем печени на видимом срезе: {round(volume_in_cubic_centimeters, 4)} cc")
        return total_volume

    def update_slicing_plane(self):

        bounds = self.body_data.GetBounds()
        zmin = bounds[4]
        zmax = bounds[5]
        delta = (zmax - zmin) / 100.0 / 5  # шаг перемещения

        self.slice_z_position += delta * self.slice_direction

        if self.slice_z_position >= zmax:
            self.slice_z_position = zmax
            self.slice_direction = -1
        elif self.slice_z_position <= zmin:
            self.slice_z_position = zmin
            self.slice_direction = 1

        xmin, xmax, ymin, ymax, _, _ = bounds
        self.plane_source.SetOrigin(xmin, ymin, self.slice_z_position)
        self.plane_source.SetPoint1(xmax, ymin, self.slice_z_position)
        self.plane_source.SetPoint2(xmin, ymax, self.slice_z_position)
        self.plane_source.Update()

        # Обновляем положение clipping plane для синего объёма
        if hasattr(self, 'clipping_plane'):
            self.clipping_plane.SetOrigin(xmin, ymin, self.slice_z_position)

        print('UPDATE SLICING PLANE')

        # Вычисление объема для видимых вокселей на текущем срезе
        self.calculate_visible_slice_volume()

        self.render_window.Render()

    def render_ray_casting(self):
        if self.body_data and self.liver_data:
            camera = self.renderer.GetActiveCamera()
            position = camera.GetPosition()
            focal_point = camera.GetFocalPoint()

            if self.bounds:
                self.slicing_planes = []
                # x y z pairs
                x_min, x_max, y_min, y_max, z_min, z_max = self.bounds

                slicing_z_min = vtk.vtkPlane()
                slicing_z_min.SetOrigin(0, 0, z_min)
                slicing_z_min.SetNormal(0, 0, 1)
                self.slicing_planes.append(slicing_z_min)

                slicing_z_max = vtk.vtkPlane()
                slicing_z_max.SetOrigin(0, 0, z_max)
                slicing_z_max.SetNormal(0, 0, -1)
                self.slicing_planes.append(slicing_z_max)

                slicing_y_min = vtk.vtkPlane()
                slicing_y_min.SetOrigin(0, y_min, 0)
                slicing_y_min.SetNormal(0, 1, 0)
                self.slicing_planes.append(slicing_y_min)

                slicing_y_max = vtk.vtkPlane()
                slicing_y_max.SetOrigin(0, y_max, 0)
                slicing_y_max.SetNormal(0, -1, 0)
                self.slicing_planes.append(slicing_y_max)

                slicing_x_min = vtk.vtkPlane()
                slicing_x_min.SetOrigin(x_min, 0, 0)
                slicing_x_min.SetNormal(1, 0, 0)
                self.slicing_planes.append(slicing_x_min)

                slicing_x_max = vtk.vtkPlane()
                slicing_x_max.SetOrigin(x_max, 0, 0)
                slicing_x_max.SetNormal(-1, 0, 0)
                self.slicing_planes.append(slicing_x_max)

            # Объём 1: Исходный (folder1) – синий оттенок
            mapper1 = vtk.vtkGPUVolumeRayCastMapper()
            mapper1.SetInputData(self.body_data)
            if self.slicing_planes:
                for plane in self.slicing_planes:
                    mapper1.AddClippingPlane(plane)

            volume_property1 = vtk.vtkVolumeProperty()

            color_transfer1 = vtk.vtkColorTransferFunction()

            intensities = [-643.78106689453125, -584.65887451171875, -382.65924072265625, -237.65838623046875,
                           -75.40606689453125, 114.5941162109375, 316.5936279296875, 461.59375]

            colors = [
                (0.0, 0.0, 0.0),  # черный
                (1.0, 0.0, 0.0),  # красный
                (1.0, 0.99920654296875, 0.0),  # желтый
                (1.0, 1.0, 1.0),  # белый
                (0.0, 0.0, 0.0),  # черный снова

                # (0, 1, 0),
                # (0, 1, 1),

                (1.0, 0.0, 0.0),  # красный снова
                (1.0, 0.99920654296875, 0.0),  # желтый снова
                (1.0, 1.0, 1.0)  # белый снова
            ]

            for intensity, color in zip(intensities, colors):
                r, g, b = color
                color_transfer1.AddRGBPoint(intensity, r, g, b)

            volume_property1.SetColor(color_transfer1)

            scalar_opacity = vtk.vtkPiecewiseFunction()

            # Данные из XML:
            opacity_points = [
                (-643.78106689453125, 0.0),
                (-584.65887451171875, 0.26931655406951904),
                (-382.65924072265625, 0.46969130635261536),
                (-237.65838623046875, 0.51899993419647217),
                (-75.40606689453125, 0.0),

                # (40, 1.0),
                # (80, 1.0),

                (114.5941162109375, 0.27931660413742065),
                (316.5936279296875, 0.28899994492530823),
                (461.59375, 0.28899994492530823)
            ]

            for intensity, opacity in opacity_points:
                scalar_opacity.AddPoint(intensity, opacity)

            volume_property1.SetScalarOpacity(scalar_opacity)
            #volume_property1.SetGradientOpacity(self.gradient_opacity_transfer_function())
            volume_property1.SetInterpolationTypeToLinear()
            volume_property1.ShadeOn()
            volume_property1.SetAmbient(self.ui.ambientSlider.value() / 10.0)
            volume_property1.SetDiffuse(self.ui.diffuseSlider.value() / 10.0)
            volume_property1.SetSpecular(self.ui.specularSlider.value() / 10.0)
            volume1 = vtk.vtkVolume()
            volume1.SetMapper(mapper1)
            volume1.SetProperty(volume_property1)

            mapper2 = vtk.vtkGPUVolumeRayCastMapper()
            mapper2.SetInputData(self.liver_data)
            if self.slicing_planes:
                for plane in self.slicing_planes:
                    mapper2.AddClippingPlane(plane)
            volume_property2 = vtk.vtkVolumeProperty()
            color_transfer2 = vtk.vtkColorTransferFunction()
            color_transfer2.AddRGBPoint(0, 1, 0, 0)  # красный
            color_transfer2.AddRGBPoint(1000, 1, 0, 0)
            volume_property2.SetColor(color_transfer2)
            volume_property2.SetScalarOpacity(self.scalar_opacity_transfer_function())
            volume_property2.SetGradientOpacity(self.gradient_opacity_transfer_function())
            volume_property2.SetInterpolationTypeToLinear()
            volume_property2.ShadeOn()
            volume_property2.SetAmbient(self.ui.ambientSlider.value() / 10.0)
            volume_property2.SetDiffuse(self.ui.diffuseSlider.value() / 10.0)
            volume_property2.SetSpecular(self.ui.specularSlider.value() / 10.0)
            volume2 = vtk.vtkVolume()
            volume2.SetMapper(mapper2)
            volume2.SetProperty(volume_property2)


            self.renderer.RemoveAllViewProps()
            self.renderer.AddVolume(volume1)
            self.renderer.AddVolume(volume2)

            # Восстанавливаем положение камеры
            camera.SetPosition(position)
            camera.SetFocalPoint(focal_point)
            if hasattr(self, 'box_widget'):
                self.box_widget.SetInteractor(self.render_window_interactor)
                self.box_widget.SetRepresentation(self.box_rep)
                self.box_widget.On()
                self.renderer.AddViewProp(self.box_rep)
            self.render_window.Render()

            self.volume1 = volume1
            #self.volume2 = volume2

            if not hasattr(self, 'box_widget'):
                self.box_rep = vtk.vtkBoxRepresentation()
                self.box_widget = vtk.vtkBoxWidget2()
                self.box_widget.SetInteractor(self.render_window_interactor)
                self.box_widget.SetRepresentation(self.box_rep)

                self.box_rep.SetPlaceFactor(1.0)
                self.box_rep.PlaceWidget(self.volume1.GetBounds())
                self.box_widget.On()

                self.box_widget.ScalingEnabledOff()  # Запрет масштабирования
                self.box_widget.TranslationEnabledOff()  # Запрет перемещения центра
                self.box_widget.RotationEnabledOff()  # Запрет вращения
                self.box_widget.AddObserver("InteractionEvent", self.on_bounding_box_update)

    def on_bounding_box_update(self, caller, event):
        bounds = caller.GetRepresentation().GetBounds()
        self.bounds = bounds

        # Вычисляем объем для видимых вокселей в пределах этих новых границ
        self.calculate_visible_slice_volume()

        self.render_ray_casting()


    def volume_color_transfer_function(self):
        volume_color = vtk.vtkColorTransferFunction()
        overall_color_scalar_value = 0
        overall_color_rgb = [0.0, 0.0, 0.0]
        volume_color.AddRGBPoint(overall_color_scalar_value, *overall_color_rgb)
        volume_color.AddRGBPoint(500, 1.0, 0.5, 0.3)
        volume_color.AddRGBPoint(1000, 1.0, 0.5, 0.3)
        volume_color.AddRGBPoint(1150, 1.0, 1.0, 0.9)
        return volume_color

    def scalar_opacity_transfer_function(self):
        volume_scalar_opacity = vtk.vtkPiecewiseFunction()
        volume_scalar_opacity.AddPoint(0, 0.00)
        volume_scalar_opacity.AddPoint(500, 1.0)
        volume_scalar_opacity.AddPoint(1000, 0.7)
        volume_scalar_opacity.AddPoint(1150, 0.03)
        return volume_scalar_opacity

    def gradient_opacity_transfer_function(self):
        volume_gradient_opacity = vtk.vtkPiecewiseFunction()
        volume_gradient_opacity.AddPoint(0, 0.0)
        volume_gradient_opacity.AddPoint(90, 0.5)
        volume_gradient_opacity.AddPoint(100, 1.0)
        return volume_gradient_opacity

    ###############################################################################################
    #                          Brush (editing model with mouse) Functions                         #
    ###############################################################################################

    def on_left_button_press(self, obj, event):
        """
        Обработчик левого клика мыши.
        Использует vtkVolumePicker для определения мировой координаты клика,
        затем вызывает изменение интенсивности вокселей.
        """
        click_pos = self.render_window_interactor.GetEventPosition()
        print("Click position (screen):", click_pos)
        picker = vtk.vtkVolumePicker()
        picker.Set
        picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        pick_position = picker.GetPickPosition()
        print("Picked world coordinates:", pick_position)
        if pick_position != (0.0, 0.0, 0.0):
            self.brush_stroke_at_position(pick_position)
        obj.InvokeEvent("LeftButtonPressEvent")

    def brush_stroke_at_position(self, world_coord):
        """
        Преобразует мировые координаты в индексы вокселей для self.liver_data и увеличивает их интенсивность.
        """
        if not self.liver_data:
            return

        # Используем мировые координаты напрямую
        local_coord = world_coord

        # Получаем параметры изображения
        origin = self.liver_data.GetOrigin()
        spacing = self.liver_data.GetSpacing()
        dims = self.liver_data.GetDimensions()

        # Преобразуем мировые координаты в индексы вокселей
        i = int((local_coord[0] - origin[0]) / spacing[0])
        j = int((local_coord[1] - origin[1]) / spacing[1])
        k = int((local_coord[2] - origin[2]) / spacing[2])

        # Проверяем, что индексы в пределах допустимого диапазона
        extent = self.liver_data.GetExtent()  # (xmin, xmax, ymin, ymax, zmin, zmax)
        if i < extent[0] or i > extent[1] or j < extent[2] or j > extent[3] or k < extent[4] or k > extent[5]:
            print("Picked voxel is out of bounds")
            return

        # Задаём радиус кисти (в вокселях)
        brush_radius = 10
        intensity_increment = 200.0  # увеличение интенсивности

        # Получаем скалярное поле
        scalars = self.liver_data.GetPointData().GetScalars()
        if not scalars:
            print("No scalar data in image")
            return

        # Проходим по вокселям в пределах заданного куба
        for kk in range(max(k - brush_radius, extent[4]), min(k + brush_radius + 1, extent[5] + 1)):
            for jj in range(max(j - brush_radius, extent[2]), min(j + brush_radius + 1, extent[3] + 1)):
                for ii in range(max(i - brush_radius, extent[0]), min(i + brush_radius + 1, extent[1] + 1)):
                    # Проверяем, находится ли воксель внутри сферы кисти
                    dist = ((ii - i)**2 + (jj - j)**2 + (kk - k)**2)**0.5
                    if dist <= brush_radius:
                        index = ii + (jj * dims[0]) + (kk * dims[0] * dims[1])
                        curr_val = scalars.GetTuple1(index)
                        new_val = curr_val + intensity_increment
                        scalars.SetTuple1(index, new_val)
        scalars.Modified()
        self.liver_data.Modified()
        if self.mapper:
            self.mapper.Modified()
        self.render_window.Render()

    def on_key_press(self, obj, event):
        key = obj.GetKeySym()

        if key == '1':
            self.drawing_mode = 'add'  # Режим добавления
            print("Mode switched to Add")
        elif key == '2':
            self.drawing_mode = 'remove'  # Режим удаления
            print("Mode switched to Remove")

        if key.lower() == 'v':
            self.on_left_button_press(obj, event)

    ###############################################################################################
    #                                  Key Event Handling                                         #
    ###############################################################################################

    def keyPressEvent(self, event):
        super(MainWindow, self).keyPressEvent(event)

def main():
    app = QtWidgets.QApplication([])
    # app.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
