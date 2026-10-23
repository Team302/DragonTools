"""Dependency-free, orbitable 3D mounting preview rendered with Qt."""

import math

from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QWidget


def rotate_point(point, roll, pitch, yaw):
    """Apply WPILib's Rz(yaw) * Ry(pitch) * Rx(roll), with angles in degrees."""
    r, p, y = map(math.radians, (roll, pitch, yaw))
    x0, y0, z0 = point
    y1 = math.cos(r) * y0 - math.sin(r) * z0
    z1 = math.sin(r) * y0 + math.cos(r) * z0
    x2 = math.cos(p) * x0 + math.sin(p) * z1
    z2 = -math.sin(p) * x0 + math.cos(p) * z1
    return (
        math.cos(y) * x2 - math.sin(y) * y1,
        math.sin(y) * x2 + math.cos(y) * y1,
        z2,
    )


class CameraPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 320)
        self.config = None
        self.selected = -1
        self.azimuth = -55.0
        self.elevation = 28.0
        self.zoom = 1.0
        self._drag_position = None
        self.setToolTip("Drag to orbit the 3D view. Scroll to zoom.")

    def set_config(self, config, selected=-1):
        self.config = config
        self.selected = selected
        self.update()

    def set_view(self, azimuth=-55.0, elevation=28.0):
        self.azimuth, self.elevation, self.zoom = azimuth, elevation, 1.0
        self.update()

    def view_coordinates(self, point):
        a, e = math.radians(self.azimuth), math.radians(self.elevation)
        x, y, z = point
        depth = math.cos(a) * x + math.sin(a) * y
        return (
            -math.sin(a) * x + math.cos(a) * y,
            -math.sin(e) * depth + math.cos(e) * z,
            math.cos(e) * depth + math.sin(e) * z,
        )

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_position = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_position is not None:
            delta = event.position() - self._drag_position
            self.azimuth -= delta.x() * 0.5
            self.elevation = max(-85.0, min(89.9, self.elevation + delta.y() * 0.5))
            self._drag_position = event.position()
            self.update()

    def mouseReleaseEvent(self, _event):
        self._drag_position = None
        self.unsetCursor()

    def wheelEvent(self, event):
        self.zoom = max(0.25, min(8.0, self.zoom * 1.001 ** event.angleDelta().y()))
        self.update()
        event.accept()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#191e27"))
        if self.config is None:
            painter.setPen(QColor("#dddddd"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select or add a robot in Mechanism Generator.")
            return

        length = self.config["robot_length_in"]
        width = self.config["robot_width_in"]
        cameras = self.config["cameras"]
        extent = max(length, width, 10.0)
        axis_size = extent * 0.7
        arrow_size = max(5.0, extent * 0.25)
        faces, lines, labels, points = [], [], [], []

        def line(start, end, color, dashed=False, thickness=2):
            lines.append((start, end, color, dashed, thickness))
            points.extend((start, end))

        def box(vertices, color, outline):
            points.extend(vertices)
            for indices in (
                (0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
                (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3),
            ):
                faces.append(([vertices[i] for i in indices], color, outline))

        box(
            [(x, y, z) for x in (-length / 2, length / 2)
             for y in (-width / 2, width / 2) for z in (-1.0, 0.0)],
            "#344e68", "#94a9bd",
        )
        labels.append(((length / 2, 0, 1), "FRONT", "#ffffff"))
        for point, label, color in (
            ((axis_size, 0, 0), "+X Forward", "#ff7373"),
            ((0, axis_size, 0), "+Y Left", "#75d68a"),
            ((0, 0, axis_size), "+Z Up", "#79b6ff"),
        ):
            line((0, 0, 0), point, color)
            labels.append((point, label, color))

        for index, camera in enumerate(cameras):
            origin = (camera["x"], camera["y"], camera["z"])
            color = "#5ee08c" if camera["type"] == "Limelight" else "#b999ff"
            outline = "#ffe175" if index == self.selected else color

            def transform(point):
                rotated = rotate_point(point, camera["roll"], camera["pitch"], camera["yaw"])
                return tuple(a + b for a, b in zip(origin, rotated))

            box(
                [transform((x, y, z)) for x in (-1.5, 1.5)
                 for y in (-2.0, 2.0) for z in (-1.0, 1.0)],
                color, outline,
            )
            line((origin[0], origin[1], 0), origin, color, True, 1)
            tip = transform((arrow_size, 0, 0))
            line(origin, tip, outline, thickness=3)
            for side in (-1, 1):
                line(tip, transform((arrow_size * 0.75, side * arrow_size * 0.12, 0)), outline)
            line(origin, transform((0, 0, arrow_size * 0.5)), "#79b6ff")
            labels.append((origin, camera["name"], outline))

        projected = [self.view_coordinates(p) for p in points]
        min_x, max_x = min(p[0] for p in projected), max(p[0] for p in projected)
        min_y, max_y = min(p[1] for p in projected), max(p[1] for p in projected)
        scale = min(
            max(1, self.width() - 150) / max(1, max_x - min_x),
            max(1, self.height() - 130) / max(1, max_y - min_y),
        ) * self.zoom

        def project(point):
            x, y, _ = self.view_coordinates(point)
            return QPointF(
                self.width() / 2 + (x - (min_x + max_x) / 2) * scale,
                self.height() / 2 - (y - (min_y + max_y) / 2) * scale,
            )

        faces.sort(key=lambda face: sum(self.view_coordinates(p)[2] for p in face[0]) / 4)
        for vertices, color, outline in faces:
            painter.setPen(QPen(QColor(outline), 1.5))
            painter.setBrush(QColor(color))
            painter.drawPolygon(QPolygonF([project(p) for p in vertices]))
        for start, end, color, dashed, thickness in lines:
            pen = QPen(QColor(color), thickness)
            if dashed:
                pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(project(start), project(end))
        for point, text, color in labels:
            painter.setPen(QColor(color))
            painter.drawText(project(point) + QPointF(6, -8), text)
        painter.setPen(QColor("#c0cad7"))
        painter.drawText(12, 22, "3D mounting preview | Drag: orbit | Wheel: zoom")
        painter.drawText(12, self.height() - 28, "Origin: robot center at floor level. Arrow: camera +X; blue: camera up.")
        painter.drawText(12, self.height() - 10, "Robot slab and device sizes are illustrative; mounting positions are to scale.")
