"""
Janela flutuante destacada para abas de terminal (Detached Window).
Inclui o Terminal SSH e o Explorador SFTP dedicado lado a lado (com botão de toggle),
mantendo a sessão SSH e a navegação SFTP 100% ativas e funcionais na janela destacada.
"""

from typing import Callable, Optional
from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtWidgets import QMainWindow, QWidget, QToolBar, QSplitter, QVBoxLayout
from PySide6.QtGui import QAction, QCloseEvent, QIcon

from .sftp_browser import SftpBrowserWidget


class DetachedTerminalWindow(QMainWindow):
    def __init__(
        self,
        widget: QWidget,
        title: str,
        backend,
        on_reattach: Callable[[QWidget, str, Optional[SftpBrowserWidget]], None],
        on_close: Callable[[QWidget], None],
        sftp_browser: Optional[SftpBrowserWidget] = None,
        main_window_ref=None,
        parent=None
    ):
        super().__init__(parent)
        self.widget = widget
        self.tab_title = title
        self.backend = backend
        self.on_reattach_callback = on_reattach
        self.on_close_callback = on_close
        self.main_window_ref = main_window_ref
        self._is_closing_for_reattach = False

        self.setWindowTitle(f"OpenMoba - {title}")
        self.resize(1050, 650)

        import os
        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Toolbar superior
        toolbar = QToolBar("Janela Destacada", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        reattach_act = QAction("📌 Reanexar à Janela Principal", self)
        reattach_act.setStatusTip("Devolve esta sessão como aba na janela principal")
        reattach_act.triggered.connect(self.reattach)
        toolbar.addAction(reattach_act)

        toolbar.addSeparator()

        # Botão para alternar exibição do painel SFTP na janela destacada
        self.toggle_sftp_act = QAction("📁 Painel SFTP", self)
        self.toggle_sftp_act.setCheckable(True)
        self.toggle_sftp_act.setChecked(True)
        self.toggle_sftp_act.setStatusTip("Exibir ou ocultar o navegador SFTP nesta janela")
        self.toggle_sftp_act.triggered.connect(self._toggle_sftp_panel)
        toolbar.addAction(self.toggle_sftp_act)

        # Splitter com SFTP à esquerda e Terminal à direita
        self.splitter = QSplitter(Qt.Horizontal, self)

        # Usa o navegador SFTP já ativo da sessão ou cria um novo se não houver
        if sftp_browser:
            self.sftp_browser = sftp_browser
            self.sftp_browser.setParent(self)
        else:
            self.sftp_browser = SftpBrowserWidget(self)
            if self.backend:
                self.sftp_browser.attach_backend(self.backend)

        self.splitter.addWidget(self.sftp_browser)
        self.splitter.addWidget(self.widget)
        self.splitter.setSizes([280, 770])

        self.setCentralWidget(self.splitter)
        self.widget.show()

    def _toggle_sftp_panel(self, checked: bool):
        self.sftp_browser.setVisible(checked)
        if hasattr(self.widget, "web_view"):
            self.widget.web_view.page().runJavaScript("if (typeof fitTerminal === 'function') { fitTerminal(); }")

    def reattach(self):
        """Reanexa este terminal e seu SFTP de volta como aba na janela principal."""
        if self._is_closing_for_reattach:
            return
        self._is_closing_for_reattach = True

        # Desvincula o terminal e o SFTP do splitter para que não sejam destruídos no close()
        self.widget.setParent(None)
        self.sftp_browser.setParent(None)

        self.on_reattach_callback(self.widget, self.tab_title, self.sftp_browser)
        self.close()

    def closeEvent(self, event: QCloseEvent):
        if not self._is_closing_for_reattach:
            self.widget.setParent(None)
            self.sftp_browser.detach_backend()
            self.sftp_browser.deleteLater()
            self.on_close_callback(self.widget)
        event.accept()
