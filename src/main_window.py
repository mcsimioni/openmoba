import sys
import os
import asyncio
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QTreeWidget, QTreeWidgetItem, QPushButton,
    QToolBar, QStatusBar, QMessageBox, QMenu, QLabel, QInputDialog, QLineEdit,
    QFrame, QStackedWidget, QFileDialog
)
from PySide6.QtGui import QIcon, QAction, QCloseEvent

from .session_store import SessionStore
from .session_dialog import SessionDialog
from .ssh_backend import SSHClientBackend
from .terminal_widget import TerminalWidget
from .sftp_browser import SftpBrowserWidget
from .detached_window import DetachedTerminalWindow
from .detachable_tab_bar import DetachableTabBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("OpenMoba - Terminal SSH & Cliente SFTP")
        self.resize(1180, 740)

        icon_path = os.path.join(os.path.dirname(__file__), "resources", "icons", "app_icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.session_store = SessionStore()
        self.active_backends: Dict[int, SSHClientBackend] = {}
        self.session_sftp_widgets: Dict[int, SftpBrowserWidget] = {}
        self.detached_windows = []

        self._setup_ui()
        self._load_sessions_tree()

    def _setup_ui(self):
        # Toolbar Moderna
        toolbar = QToolBar("Barra Principal", self)
        toolbar.setIconSize(QSize(18, 18))
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        new_sess_act = QAction("➕  Nova Sessão", self)
        new_sess_act.setStatusTip("Criar e conectar a uma nova sessão SSH")
        new_sess_act.triggered.connect(self._create_new_session)
        toolbar.addAction(new_sess_act)

        quick_connect_act = QAction("⚡  Conexão Rápida", self)
        quick_connect_act.setStatusTip("Conectar rapidamente sem salvar")
        quick_connect_act.triggered.connect(self._quick_connect)
        toolbar.addAction(quick_connect_act)

        # Exibe o botão de sincronização somente se detectar o MobaXterm instalado no computador
        from .session_store import is_mobaxterm_installed
        if is_mobaxterm_installed():
            toolbar.addSeparator()
            reload_act = QAction("🔄  Sincronizar MobaXterm", self)
            reload_act.setStatusTip("Importar/atualizar sessões a partir do MobaXterm local")
            reload_act.triggered.connect(self._reload_moba_sessions)
            toolbar.addAction(reload_act)

        # Central Splitter (Painel Esquerdo + Área Principal de Abas)
        self.main_splitter = QSplitter(Qt.Horizontal, self)
        self.setCentralWidget(self.main_splitter)

        # Painel Esquerdo
        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(6)

        # Abas do painel lateral (Sessões Salvas e Navegador SFTP)
        self.left_tabs = QTabWidget(left_panel)

        self.sessions_tab = QWidget()
        sess_layout = QVBoxLayout(self.sessions_tab)
        sess_layout.setContentsMargins(4, 4, 4, 4)
        sess_layout.setSpacing(6)

        # Campo de filtro de busca rápida para sessões
        self.search_sess_edit = QLineEdit()
        self.search_sess_edit.setPlaceholderText("🔍 Filtrar sessões...")
        self.search_sess_edit.textChanged.connect(self._filter_sessions)
        sess_layout.addWidget(self.search_sess_edit)

        self.sessions_tree = QTreeWidget()
        self.sessions_tree.setHeaderLabel("Sessões SSH Salvas")
        self.sessions_tree.setRootIsDecorated(False)
        self.sessions_tree.itemDoubleClicked.connect(self._on_session_item_double_clicked)
        self.sessions_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.sessions_tree.customContextMenuRequested.connect(self._on_session_tree_context)
        sess_layout.addWidget(self.sessions_tree)

        sess_btns = QHBoxLayout()
        sess_btns.setSpacing(6)
        add_sess_btn = QPushButton("➕ Nova")
        add_sess_btn.clicked.connect(self._create_new_session)
        del_sess_btn = QPushButton("🗑 Excluir")
        del_sess_btn.clicked.connect(self._delete_selected_session)
        sess_btns.addWidget(add_sess_btn)
        sess_btns.addWidget(del_sess_btn)
        sess_layout.addLayout(sess_btns)

        self.left_tabs.addTab(self.sessions_tab, "Sessões")

        # Aba 2: SFTP independente por sessão (QStackedWidget)
        self.sftp_stack = QStackedWidget(self)
        self.sftp_empty_label = QLabel("Nenhuma sessão SSH ativa.\nConecte-se para explorar arquivos via SFTP.")
        self.sftp_empty_label.setAlignment(Qt.AlignCenter)
        self.sftp_empty_label.setStyleSheet("color: #71717a; font-size: 13px; padding: 20px;")
        self.sftp_stack.addWidget(self.sftp_empty_label)

        self.left_tabs.addTab(self.sftp_stack, "SFTP Remoto")

        left_layout.addWidget(self.left_tabs)
        self.main_splitter.addWidget(left_panel)

        # Painel Direito: Abas de Terminais SSH
        self.term_tabs = QTabWidget(self)
        self.tab_bar = DetachableTabBar(self.term_tabs)
        self.term_tabs.setTabBar(self.tab_bar)
        self.term_tabs.setTabsClosable(True)
        self.term_tabs.setMovable(True)
        self.term_tabs.tabCloseRequested.connect(self._close_terminal_tab)
        self.term_tabs.currentChanged.connect(self._on_tab_changed)

        # Evento de arrastar aba para fora (Drag to Detach)
        self.tab_bar.tabDetached.connect(self._on_tab_dragged_out)

        # Menu de contexto com botão direito na barra de abas
        self.tab_bar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._on_tab_context_menu)

        self.main_splitter.addWidget(self.term_tabs)

        # Proporção inicial: 310px para barra lateral e restante para terminal
        self.main_splitter.setSizes([310, 870])

        # Status Bar moderna
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        self.status_indicator = QLabel("● Desconectado")
        self.status_indicator.setStyleSheet("color: #71717a; font-weight: 500; margin-right: 12px;")
        self.status_bar.addPermanentWidget(self.status_indicator)
        self.status_bar.showMessage("Pronto para conectar")

    def _filter_sessions(self, text: str):
        query = text.lower().strip()
        for i in range(self.sessions_tree.topLevelItemCount()):
            item = self.sessions_tree.topLevelItem(i)
            matches = query in item.text(0).lower()
            item.setHidden(not matches)

    def _reload_moba_sessions(self):
        from .session_store import import_mobaxterm_sessions, find_default_mobaxterm_ini

        ini_path = find_default_mobaxterm_ini()
        if not ini_path or not os.path.exists(ini_path):
            # Se não encontrar nas pastas do perfil do usuário atual, oferece localizar manualmente
            ret = QMessageBox.question(
                self,
                "MobaXterm.ini Não Localizado",
                "O arquivo 'MobaXterm.ini' não foi encontrado automaticamente na pasta padrão do seu usuário Windows (%APPDATA%\\MobaXterm).\n\n"
                "Deseja selecionar o arquivo MobaXterm.ini manualmente?",
                QMessageBox.Yes | QMessageBox.No
            )
            if ret == QMessageBox.Yes:
                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Selecionar MobaXterm.ini",
                    os.path.expanduser("~"),
                    "Configuração MobaXterm (*.ini);;Todos os Arquivos (*.*)"
                )
                if file_path:
                    ini_path = file_path
                else:
                    return
            else:
                return

        imported = import_mobaxterm_sessions(ini_path)
        if not imported:
            QMessageBox.warning(
                self,
                "Nenhuma Sessão Encontrada",
                f"Nenhuma sessão SSH foi encontrada no arquivo:\n{ini_path}"
            )
            return

        existing_hosts = {s.get("host") for s in self.session_store.sessions}
        existing_names = {s.get("name") for s in self.session_store.sessions}
        added = 0
        for item in imported:
            # Não duplica se o mesmo host ou mesmo nome já existir
            if item.get("host") not in existing_hosts and item.get("name") not in existing_names:
                self.session_store.sessions.append(item)
                added += 1

        if added > 0:
            self.session_store.save_sessions()
            self._load_sessions_tree()
            self.status_bar.showMessage(f"{added} nova(s) sessão(ões) sincronizada(s) do MobaXterm.")
            QMessageBox.information(
                self,
                "Sincronização Concluída",
                f"Foram sincronizadas {added} nova(s) sessão(ões) com sucesso a partir de:\n{ini_path}"
            )
        else:
            self.status_bar.showMessage("Sessões do MobaXterm já estão atualizadas.")
            QMessageBox.information(
                self,
                "Sincronização Concluída",
                f"Todas as {len(imported)} sessões do MobaXterm já estão salvas no OpenMoba.\nNenhuma duplicata foi inserida.\n\nArquivo lido: {ini_path}"
            )

    def _load_sessions_tree(self):
        selected_id = None
        current_item = self.sessions_tree.currentItem()
        if current_item:
            current_data = current_item.data(0, Qt.UserRole)
            if current_data:
                selected_id = current_data.get("id")

        self.sessions_tree.clear()
        sessions = self.session_store.load_sessions()
        
        item_to_select = None
        for sess in sessions:
            label = f"💻 {sess.get('name', 'SSH')} ({sess.get('username', 'root')}@{sess.get('host')})"
            item = QTreeWidgetItem([label])
            item.setData(0, Qt.UserRole, sess)
            self.sessions_tree.addTopLevelItem(item)
            if selected_id and sess.get("id") == selected_id:
                item_to_select = item

        if item_to_select:
            self.sessions_tree.setCurrentItem(item_to_select)

        # Reaplica o filtro atual se houver busca digitada
        if hasattr(self, "search_sess_edit") and self.search_sess_edit.text():
            self._filter_sessions(self.search_sess_edit.text())

    def _create_new_session(self):
        dialog = SessionDialog(parent=self)
        if dialog.exec():
            sess_data = dialog.get_data()
            self.session_store.add_or_update_session(sess_data)
            self._load_sessions_tree()
            self._open_session(sess_data)

    def _quick_connect(self):
        dialog = SessionDialog(parent=self)
        if dialog.exec():
            sess_data = dialog.get_data()
            self._open_session(sess_data)

    def _delete_selected_session(self):
        item = self.sessions_tree.currentItem()
        if not item:
            return
        sess = item.data(0, Qt.UserRole)
        if not sess:
            return
        ret = QMessageBox.question(
            self, "Excluir Sessão",
            f"Excluir a sessão '{sess.get('name')}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            self.session_store.delete_session(sess.get("id"))
            self._load_sessions_tree()

    def _on_session_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        sess = item.data(0, Qt.UserRole)
        if sess:
            self._open_session(sess)

    def _on_session_tree_context(self, pos):
        item = self.sessions_tree.itemAt(pos)
        if not item:
            return
        sess = item.data(0, Qt.UserRole)
        if not sess:
            return
        menu = QMenu(self)
        conn_act = menu.addAction("⚡ Conectar")
        conn_act.triggered.connect(lambda: self._open_session(sess))

        edit_act = menu.addAction("✏ Editar...")
        def edit():
            dlg = SessionDialog(sess, parent=self)
            if dlg.exec():
                new_data = dlg.get_data()
                self.session_store.add_or_update_session(new_data)
                self._load_sessions_tree()
        edit_act.triggered.connect(edit)

        del_act = menu.addAction("🗑 Excluir")
        del_act.triggered.connect(self._delete_selected_session)

        menu.exec(self.sessions_tree.viewport().mapToGlobal(pos))

    def _open_session(self, sess: Dict[str, Any]):
        host = sess.get("host")
        port = sess.get("port", 22)
        username = sess.get("username", "root")
        password = sess.get("password")
        key_path = sess.get("key_path")

        # Pede senha sob demanda se não houver senha nem chave privada
        if not password and not key_path:
            pwd, ok = QInputDialog.getText(
                self, "Autenticação SSH",
                f"Digite a senha para {username}@{host}:",
                QLineEdit.Password
            )
            if ok:
                password = pwd
                if sess.get("id"):
                    sess["password"] = password
                    self.session_store.add_or_update_session(sess)
            else:
                return

        backend = SSHClientBackend(
            host=host,
            port=port,
            username=username,
            password=password,
            key_path=key_path
        )

        term_widget = TerminalWidget(backend, parent=self)
        title = sess.get("name") or f"{username}@{host}"
        tab_idx = self.term_tabs.addTab(term_widget, f"💻 {title}")
        self.term_tabs.setCurrentIndex(tab_idx)

        # Mapeia backend pelo widget
        self.active_backends[id(term_widget)] = backend

        # Cria um navegador SFTP exclusivo e independente para esta aba
        sftp_browser = SftpBrowserWidget(self)
        self.session_sftp_widgets[id(term_widget)] = sftp_browser
        self.sftp_stack.addWidget(sftp_browser)
        self.sftp_stack.setCurrentWidget(sftp_browser)

        # Sinais de status e controle da aba lateral
        def on_connected(target):
            self.status_bar.showMessage(f"Conectado: {target}")
            self.status_indicator.setText("● Conectado")
            self.status_indicator.setStyleSheet("color: #22c55e; font-weight: 600; margin-right: 12px;")
            # Conecta o SFTP browser exclusivo e foca nele
            sftp_browser.attach_backend(backend)
            self.sftp_stack.setCurrentWidget(sftp_browser)
            self.left_tabs.setCurrentWidget(self.sftp_stack)

        def on_disconnected(msg):
            self.status_bar.showMessage(f"Sessão finalizada: {msg}")
            self.status_indicator.setText("● Desconectado")
            self.status_indicator.setStyleSheet("color: #ef4444; font-weight: 500; margin-right: 12px;")
            sftp_browser.detach_backend()
            if self.term_tabs.count() <= 1:
                self.left_tabs.setCurrentWidget(self.sessions_tab)

        def on_error(err):
            self.status_bar.showMessage(f"Erro de conexão: {err}")
            self.status_indicator.setText("● Erro de Conexão")
            self.status_indicator.setStyleSheet("color: #ef4444; font-weight: 600; margin-right: 12px;")
            sftp_browser.detach_backend()
            self.left_tabs.setCurrentWidget(self.sessions_tab)

        backend.connection_established.connect(on_connected)
        backend.connection_closed.connect(on_disconnected)
        backend.error_occurred.connect(on_error)

    def _on_tab_changed(self, index: int):
        if index < 0:
            self.sftp_stack.setCurrentWidget(self.sftp_empty_label)
            self.left_tabs.setCurrentWidget(self.sessions_tab)
            self.status_indicator.setText("● Desconectado")
            self.status_indicator.setStyleSheet("color: #71717a; font-weight: 500; margin-right: 12px;")
            return
        widget = self.term_tabs.widget(index)
        if widget:
            # Alterna para o navegador SFTP exclusivo desta aba
            sftp_browser = self.session_sftp_widgets.get(id(widget))
            if sftp_browser:
                self.sftp_stack.setCurrentWidget(sftp_browser)
            else:
                self.sftp_stack.setCurrentWidget(self.sftp_empty_label)

            if id(widget) in self.active_backends:
                backend = self.active_backends[id(widget)]
                if backend._is_connected:
                    self.status_indicator.setText("● Conectado")
                    self.status_indicator.setStyleSheet("color: #22c55e; font-weight: 600; margin-right: 12px;")
                else:
                    self.status_indicator.setText("● Conectando...")
                    self.status_indicator.setStyleSheet("color: #eab308; font-weight: 500; margin-right: 12px;")

    def _on_tab_context_menu(self, pos):
        tab_bar = self.term_tabs.tabBar()
        index = tab_bar.tabAt(pos)
        if index < 0:
            return

        menu = QMenu(self)

        close_act = menu.addAction("❌  Fechar Aba")
        close_act.triggered.connect(lambda: self._close_terminal_tab(index))

        close_others_act = menu.addAction("🚫  Fechar Outras Abas")
        close_others_act.triggered.connect(lambda: self._close_other_tabs(index))

        menu.addSeparator()

        detach_act = menu.addAction("🔲  Destacar Aba (Nova Janela)")
        detach_act.triggered.connect(lambda: self._detach_tab(index))

        menu.exec(tab_bar.mapToGlobal(pos))

    def _close_other_tabs(self, keep_index: int):
        keep_widget = self.term_tabs.widget(keep_index)
        for i in reversed(range(self.term_tabs.count())):
            if self.term_tabs.widget(i) != keep_widget:
                self._close_terminal_tab(i)

    def _on_tab_dragged_out(self, index: int, global_pos):
        self._detach_tab(index, initial_pos=global_pos)

    def _detach_tab(self, index: int, initial_pos=None):
        widget = self.term_tabs.widget(index)
        if not widget:
            return

        title = self.term_tabs.tabText(index)
        backend = self.active_backends.get(id(widget))

        # Recupera o navegador SFTP exclusivo desta sessão para ir junto com a janela destacada
        sftp_browser = self.session_sftp_widgets.pop(id(widget), None)
        if sftp_browser:
            self.sftp_stack.removeWidget(sftp_browser)

        # Remove do tab widget sem destruir o widget nem fechar a conexão
        self.term_tabs.removeTab(index)

        detached_win = DetachedTerminalWindow(
            widget=widget,
            title=title,
            backend=backend,
            on_reattach=self._reattach_tab,
            on_close=self._on_detached_window_closed,
            sftp_browser=sftp_browser,
            main_window_ref=self,
            parent=None
        )
        self.detached_windows.append(detached_win)

        if initial_pos:
            # Posiciona suavemente próximo do cursor onde o usuário soltou
            detached_win.move(initial_pos.x() - 100, initial_pos.y() - 30)

        detached_win.show()
        # Força o fit do terminal após a janela abrir
        if hasattr(widget, "web_view"):
            widget.web_view.page().runJavaScript("if (typeof fitTerminal === 'function') { fitTerminal(); }")

        # Atualiza a janela principal para apontar o SFTP para a aba restante (se houver)
        if self.term_tabs.count() > 0:
            current_active = self.term_tabs.currentWidget()
            if current_active:
                remaining_sftp = self.session_sftp_widgets.get(id(current_active))
                if remaining_sftp:
                    self.sftp_stack.setCurrentWidget(remaining_sftp)
        else:
            self.sftp_stack.setCurrentWidget(self.sftp_empty_label)
            self.left_tabs.setCurrentWidget(self.sessions_tab)

    def _reattach_tab(self, widget: QWidget, title: str, sftp_browser: Optional[SftpBrowserWidget] = None):
        # Reanexa a aba na janela principal
        idx = self.term_tabs.addTab(widget, title)
        self.term_tabs.setCurrentIndex(idx)
        widget.show()

        # Se veio com sftp_browser da janela destacada, re-insere no stack preservando a pasta
        if sftp_browser:
            self.session_sftp_widgets[id(widget)] = sftp_browser
            self.sftp_stack.addWidget(sftp_browser)
            self.sftp_stack.setCurrentWidget(sftp_browser)
            self.left_tabs.setCurrentWidget(self.sftp_stack)

        # Força o xterm a redimensionar corretamente para o tamanho da aba principal
        if hasattr(widget, "web_view"):
            widget.web_view.page().runJavaScript("if (typeof fitTerminal === 'function') { fitTerminal(); }")

        # Limpa referências a janelas fechadas
        self.detached_windows = [w for w in self.detached_windows if w.isVisible()]

    def _on_detached_window_closed(self, widget: QWidget):
        # Fecha a conexão e limpa backend se a janela destacada for fechada
        backend = self.active_backends.pop(id(widget), None)
        if backend:
            asyncio.create_task(backend.close())
        if hasattr(widget, "cleanup"):
            widget.cleanup()
        widget.deleteLater()
        self.detached_windows = [w for w in self.detached_windows if w.isVisible()]

        # Se a janela principal já foi fechada e esta era a última janela destacada, encerra o app
        if not self.isVisible() and len(self.detached_windows) == 0:
            from PySide6.QtWidgets import QApplication
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                loop.stop()
            QApplication.quit()

    def _close_terminal_tab(self, index: int):
        widget = self.term_tabs.widget(index)
        if widget:
            backend = self.active_backends.pop(id(widget), None)
            if backend:
                asyncio.create_task(backend.close())

            # Destrói e limpa o navegador SFTP exclusivo desta aba
            sftp_browser = self.session_sftp_widgets.pop(id(widget), None)
            if sftp_browser:
                sftp_browser.detach_backend()
                self.sftp_stack.removeWidget(sftp_browser)
                sftp_browser.deleteLater()

            self.term_tabs.removeTab(index)
            if hasattr(widget, "cleanup"):
                widget.cleanup()
            widget.deleteLater()

            if self.term_tabs.count() == 0:
                self.sftp_stack.setCurrentWidget(self.sftp_empty_label)
                self.left_tabs.setCurrentWidget(self.sessions_tab)
                self.status_indicator.setText("● Desconectado")
                self.status_indicator.setStyleSheet("color: #71717a; font-weight: 500; margin-right: 12px;")

    def closeEvent(self, event: QCloseEvent):
        open_tabs_count = self.term_tabs.count()
        if open_tabs_count > 0:
            ret = QMessageBox.question(
                self,
                "Confirmar Encerramento",
                f"Existem {open_tabs_count} conexões ativas na janela principal.\n"
                "Deseja encerrar estas conexões e fechar a janela principal?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if ret != QMessageBox.Yes:
                event.ignore()
                return

            # Fecha e encerra as abas anexadas na janela principal
            while self.term_tabs.count() > 0:
                self._close_terminal_tab(0)

        event.accept()

        # Se não há mais janelas destacadas ativas, encerra a aplicação de forma limpa
        has_detached_alive = any(w.isVisible() for w in self.detached_windows)
        if not has_detached_alive:
            from PySide6.QtWidgets import QApplication
            loop = asyncio.get_event_loop()
            if loop and loop.is_running():
                loop.stop()
            QApplication.quit()
