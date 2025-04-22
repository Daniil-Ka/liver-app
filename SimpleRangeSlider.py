import sys
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor
from PyQt6.QtWidgets import QWidget, QApplication


class SimpleRangeSlider(QWidget):
    """
    Простой RangeSlider с двумя ручками (нижнее и верхнее значение).

    Свойства:
      - minimum: минимальное возможное значение
      - maximum: максимальное возможное значение
      - lower: текущее нижнее значение
      - upper: текущее верхнее значение

    Сигнал valueChanged испускается при изменении одного из значений.
    """
    valueChanged = pyqtSignal(int, int)

    def __init__(self, minimum=0, maximum=100, lower=20, upper=80, parent=None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._lower = lower
        self._upper = upper

        self.handleRadius = 8  # Радиус ручки
        self.grooveHeight = 4  # Высота дорожки
        self.margin = self.handleRadius  # Отступы (чтобы ручки не обрезались)
        self._activeHandle = None  # Какая именно ручка сейчас перемещается ('lower' или 'upper')

        self.setMinimumSize(150, 2 * self.handleRadius + 10)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Определяем координаты дорожки
        grooveY = height / 2 - self.grooveHeight / 2
        grooveStart = self.margin
        grooveEnd = width - self.margin

        # Рисуем дорожку
        grooveRect = QRect(int(grooveStart), int(grooveY), int(grooveEnd - grooveStart), int(self.grooveHeight))
        painter.setPen(QPen(Qt.GlobalColor.darkGray))
        painter.setBrush(QBrush(Qt.GlobalColor.lightGray))
        painter.drawRect(grooveRect)

        # Вычисляем позиции ручек в зависимости от значений
        span = self._maximum - self._minimum
        if span == 0:
            span = 1  # защита от деления на ноль

        lowerPos = grooveStart + (self._lower - self._minimum) / span * (grooveEnd - grooveStart)
        upperPos = grooveStart + (self._upper - self._minimum) / span * (grooveEnd - grooveStart)

        # Выделяем область между ручками
        selectedRect = QRect(int(lowerPos), int(grooveY), int(upperPos - lowerPos), int(self.grooveHeight))
        painter.setBrush(QBrush(QColor(100, 180, 250)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(selectedRect)

        # Рисуем левую ручку
        painter.setBrush(QBrush(QColor(80, 80, 80)))
        painter.setPen(QPen(Qt.GlobalColor.black))
        painter.drawEllipse(QPointF(lowerPos, height / 2), self.handleRadius, self.handleRadius)

        # Рисуем правую ручку
        painter.drawEllipse(QPointF(upperPos, height / 2), self.handleRadius, self.handleRadius)

    def _pixelPosToValue(self, x):
        """Преобразует координату X в значение слайдера."""
        grooveStart = self.margin
        grooveEnd = self.width() - self.margin
        ratio = (x - grooveStart) / (grooveEnd - grooveStart)
        value = self._minimum + ratio * (self._maximum - self._minimum)
        return round(value)

    def mousePressEvent(self, event):
        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        grooveStart = self.margin
        grooveEnd = self.width() - self.margin
        span = self._maximum - self._minimum

        lowerPos = grooveStart + (self._lower - self._minimum) / span * (grooveEnd - grooveStart)
        upperPos = grooveStart + (self._upper - self._minimum) / span * (grooveEnd - grooveStart)

        # Определяем, какая ручка ближе по координате X к месту клика
        if abs(pos.x() - lowerPos) < abs(pos.x() - upperPos):
            self._activeHandle = 'lower'
        else:
            self._activeHandle = 'upper'
        self.mouseMoveEvent(event)

    def mouseMoveEvent(self, event):
        if not self._activeHandle:
            return

        pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
        value = self._pixelPosToValue(pos.x())

        if self._activeHandle == 'lower':
            if value < self._minimum:
                value = self._minimum
            if value > self._upper:
                value = self._upper
            self._lower = value
        elif self._activeHandle == 'upper':
            if value > self._maximum:
                value = self._maximum
            if value < self._lower:
                value = self._lower
            self._upper = value

        self.valueChanged.emit(self._lower, self._upper)
        self.update()

    def mouseReleaseEvent(self, event):
        self._activeHandle = None

if __name__ == '__main__':
    app = QApplication(sys.argv)
    slider = SimpleRangeSlider(minimum=0, maximum=100, lower=30, upper=70)
    slider.setWindowTitle("Простой RangeSlider")
    slider.resize(300, 60)

    # Пример использования сигнала
    def on_value_changed(low, high):
        print(f"Нижнее значение: {low}, Верхнее значение: {high}")
    slider.valueChanged.connect(on_value_changed)

    slider.show()
    sys.exit(app.exec())