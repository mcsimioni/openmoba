"""
Barra de abas customizada que suporta desanexar aba ao arrastar para fora (Drag to Detach)
e receber abas soltas de volta (Drag to Reattach).
"""

from PySide6.QtCore import Qt, QPoint, Signal
from PySide6.QtWidgets import QTabBar, QTabWidget


class DetachableTabBar(QTabBar):
    tabDetached = Signal(int, QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_start_pos = None
        self._drag_tab_index = -1
        self._is_dragging_tab = False

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_start_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            self._drag_tab_index = self.tabAt(self._drag_start_pos)
            self._is_dragging_tab = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (event.buttons() & Qt.LeftButton) and self._drag_start_pos is not None:
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            # Se o usuário arrastou para fora da barra de abas (distância vertical ou fora do retângulo)
            if self._drag_tab_index >= 0:
                dist = (pos - self._drag_start_pos).manhattanLength()
                # Se arrastou significativamente para fora da barra
                if dist > 20 and not self.rect().contains(pos):
                    idx = self._drag_tab_index
                    global_pos = event.globalPosition().toPoint() if hasattr(event, "globalPosition") else event.globalPos()
                    self._drag_start_pos = None
                    self._drag_tab_index = -1
                    self.tabDetached.emit(idx, global_pos)
                    return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_start_pos = None
        self._drag_tab_index = -1
        self._is_dragging_tab = False
        super().mouseReleaseEvent(event)
