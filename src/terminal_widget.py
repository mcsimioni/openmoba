import os
import json
import asyncio
from PySide6.QtCore import QObject, Signal, Slot, QUrl
from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebChannel import QWebChannel
from .ssh_backend import SSHClientBackend


class TerminalBridge(QObject):
    userInput = Signal(str)
    resized = Signal(int, int)
    ready = Signal(int, int)

    @Slot(str)
    def on_terminal_input(self, data: str):
        self.userInput.emit(data)

    @Slot(int, int)
    def on_terminal_resize(self, cols: int, rows: int):
        self.resized.emit(cols, rows)

    @Slot(int, int)
    def on_terminal_ready(self, cols: int, rows: int):
        self.ready.emit(cols, rows)


class TerminalWidget(QWidget):
    def __init__(self, ssh_backend: SSHClientBackend, parent=None):
        super().__init__(parent)
        self.ssh_backend = ssh_backend
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.web_view = QWebEngineView(self)
        self.layout.addWidget(self.web_view)

        # Configura Canal Web
        self.channel = QWebChannel(self)
        self.bridge = TerminalBridge(self)
        self.channel.registerObject("backend", self.bridge)
        self.web_view.page().setWebChannel(self.channel)

        # Conecta sinais do bridge com o backend
        self.bridge.userInput.connect(self.ssh_backend.write_data)
        self.bridge.resized.connect(self.ssh_backend.set_terminal_size)
        self.bridge.ready.connect(self._on_terminal_ready)

        # Conecta saída do backend SSH para envio ao terminal xterm.js
        self.ssh_backend.data_received.connect(self._write_to_terminal)

        # Carrega o arquivo HTML local
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(current_dir, "resources", "web", "terminal.html")
        self.web_view.load(QUrl.fromLocalFile(html_path))

    def _on_terminal_ready(self, cols: int, rows: int):
        self.ssh_backend.set_terminal_size(cols, rows)
        # Dispara a conexão assíncrona
        asyncio.create_task(self.ssh_backend.connect())

    def _write_to_terminal(self, text: str):
        # Escapa adequadamente para chamada javascript
        escaped = json.dumps(text)
        script = f"if (typeof writeToTerminal === 'function') {{ writeToTerminal({escaped}); }}"
        self.web_view.page().runJavaScript(script)

    def cleanup(self):
        """Libera de forma limpa a página WebEngine e o canal para evitar falhas de memória."""
        try:
            self.ssh_backend.data_received.disconnect(self._write_to_terminal)
        except Exception:
            pass
        try:
            self.web_view.stop()
            self.web_view.setPage(None)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.web_view.page().runJavaScript("if (typeof fitTerminal === 'function') { fitTerminal(); }")
