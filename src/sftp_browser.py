import os
import asyncio
from typing import Optional, List
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QPushButton, QLineEdit, QFileDialog, QMenu, QMessageBox, QInputDialog, QLabel
)
from PySide6.QtGui import QIcon, QAction
from .ssh_backend import SSHClientBackend


def format_size(bytes_val: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}" if unit != 'B' else f"{bytes_val} B"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"


class SftpTreeWidget(QTreeWidget):
    """
    QTreeWidget customizado para suportar arrastar e soltar (Drag and Drop)
    de arquivos e pastas locais do Windows Explorer ou do gerenciador do Linux
    diretamente para a listagem remota do SFTP.
    """
    def __init__(self, browser_widget: "SftpBrowserWidget", parent=None):
        super().__init__(parent)
        self.browser_widget = browser_widget
        self.setAcceptDrops(True)
        self.setDragDropMode(QTreeWidget.DropOnly)

    def dragEnterEvent(self, event):
        if not self.browser_widget.ssh_backend or not self.browser_widget.ssh_backend._sftp:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            self.setProperty("dragHover", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self.browser_widget.ssh_backend or not self.browser_widget.ssh_backend._sftp:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            item = self.itemAt(pos)
            if item and item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole).get("is_dir"):
                self.setCurrentItem(item)
            else:
                self.clearSelection()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.setProperty("dragHover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self.clearSelection()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.setProperty("dragHover", False)
        self.style().unpolish(self)
        self.style().polish(self)

        if not self.browser_widget.ssh_backend or not self.browser_widget.ssh_backend._sftp:
            event.ignore()
            return

        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            local_paths = []
            for u in urls:
                local_path = u.toLocalFile()
                if local_path and os.path.exists(local_path):
                    local_paths.append(local_path)

            if not local_paths:
                return

            pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
            item = self.itemAt(pos)
            target_subdir = None
            if item and item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole).get("is_dir"):
                target_subdir = item.data(0, Qt.UserRole).get("name")

            self.clearSelection()
            self.browser_widget._handle_dropped_files(local_paths, target_subdir)
        else:
            event.ignore()


class SftpBrowserWidget(QWidget):
    """
    Navegador e gerenciador de arquivos SFTP remoto.
    Suporta navegação, download, upload manual e upload via Drag & Drop.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ssh_backend: Optional[SSHClientBackend] = None
        self.current_path: str = "."
        self.setAcceptDrops(True)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # Barra de navegação moderna
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(4)

        icon_dir = os.path.join(os.path.dirname(__file__), "resources", "icons")
        up_icon_path = os.path.join(icon_dir, "arrow_up.svg")
        refresh_icon_path = os.path.join(icon_dir, "refresh.svg")

        self.up_btn = QPushButton()
        if os.path.exists(up_icon_path):
            self.up_btn.setIcon(QIcon(up_icon_path))
            self.up_btn.setIconSize(QSize(16, 16))
        else:
            self.up_btn.setText("▲")
        self.up_btn.setToolTip("Subir um diretório (Pasta Pai)")
        self.up_btn.setFixedSize(32, 30)
        self.up_btn.clicked.connect(self.go_up)

        self.refresh_btn = QPushButton()
        if os.path.exists(refresh_icon_path):
            self.refresh_btn.setIcon(QIcon(refresh_icon_path))
            self.refresh_btn.setIconSize(QSize(16, 16))
        else:
            self.refresh_btn.setText("⟳")
        self.refresh_btn.setToolTip("Atualizar arquivos (F5)")
        self.refresh_btn.setFixedSize(32, 30)
        self.refresh_btn.clicked.connect(self.refresh)

        self.path_edit = QLineEdit(".")
        self.path_edit.setPlaceholderText("Caminho remoto...")
        self.path_edit.returnPressed.connect(self._on_path_entered)

        nav_layout.addWidget(self.up_btn)
        nav_layout.addWidget(self.refresh_btn)
        nav_layout.addWidget(self.path_edit)
        layout.addLayout(nav_layout)

        # Árvore de arquivos com suporte nativo a Drag & Drop
        self.tree = SftpTreeWidget(self, self)
        self.tree.setHeaderLabels(["Nome", "Tamanho"])
        self.tree.setColumnWidth(0, 190)
        self.tree.setAlternatingRowColors(True)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        # Rótulo de status de transferência (Upload / Notificações)
        self.status_label = QLabel(self)
        self.status_label.setObjectName("sftpStatusLabel")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.hide()
        layout.addWidget(self.status_label)

        # Barra de ações inferiores
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        self.upload_btn = QPushButton("⬆ Upload")
        self.upload_btn.setToolTip("Enviar arquivo(s) locais para esta pasta remota")
        self.upload_btn.clicked.connect(self.upload_file)

        self.download_btn = QPushButton("⬇ Download")
        self.download_btn.setToolTip("Baixar o arquivo selecionado")
        self.download_btn.clicked.connect(self.download_file)

        self.mkdir_btn = QPushButton("📁 Nova Pasta")
        self.mkdir_btn.setToolTip("Criar diretório remoto")
        self.mkdir_btn.clicked.connect(self.create_folder)

        actions_layout.addWidget(self.upload_btn)
        actions_layout.addWidget(self.download_btn)
        actions_layout.addWidget(self.mkdir_btn)
        layout.addLayout(actions_layout)

    # Suporte a Drag & Drop em qualquer área do widget SFTP
    def dragEnterEvent(self, event):
        if not self.ssh_backend or not self.ssh_backend._sftp:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if not self.ssh_backend or not self.ssh_backend._sftp:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self.ssh_backend or not self.ssh_backend._sftp:
            event.ignore()
            return
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            local_paths = [u.toLocalFile() for u in urls if u.toLocalFile() and os.path.exists(u.toLocalFile())]
            if local_paths:
                self._handle_dropped_files(local_paths, target_subdir=None)
        else:
            event.ignore()

    def attach_backend(self, backend: SSHClientBackend):
        self.ssh_backend = backend
        self.current_path = "."
        self.path_edit.setText(self.current_path)
        self.status_label.hide()
        self.ssh_backend.sftp_ready.connect(self.refresh)
        if self.ssh_backend._sftp:
            self.refresh()

    def detach_backend(self):
        self.ssh_backend = None
        self.tree.clear()
        self.path_edit.setText(".")
        self.status_label.hide()

    def _on_path_entered(self):
        self.current_path = self.path_edit.text().strip() or "."
        self.refresh()

    def go_up(self):
        if not self.ssh_backend:
            return
        if self.current_path in [".", "/", ""]:
            self.current_path = ".."
        else:
            self.current_path = os.path.dirname(self.current_path.rstrip("/")) or "/"
        self.path_edit.setText(self.current_path)
        self.refresh()

    def refresh(self):
        if not self.ssh_backend or not self.ssh_backend._sftp:
            return
        asyncio.create_task(self._async_refresh())

    async def _async_refresh(self):
        self.tree.clear()
        items = await self.ssh_backend.sftp_list_dir(self.current_path)
        for item in items:
            name = item["name"]
            is_dir = item["is_dir"]
            size_str = "" if is_dir else format_size(item["size"])
            icon = "📁 " if is_dir else "📄 "
            
            tree_item = QTreeWidgetItem([f"{icon}{name}", size_str])
            tree_item.setData(0, Qt.UserRole, item)
            self.tree.addTopLevelItem(tree_item)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        if data["is_dir"]:
            if self.current_path == "/":
                self.current_path = f"/{data['name']}"
            elif self.current_path == ".":
                self.current_path = data['name']
            else:
                self.current_path = f"{self.current_path.rstrip('/')}/{data['name']}"
            self.path_edit.setText(self.current_path)
            self.refresh()
        else:
            self.download_file()

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)

        if item:
            data = item.data(0, Qt.UserRole)
            if not data["is_dir"]:
                dl_action = menu.addAction("⬇ Baixar arquivo...")
                dl_action.triggered.connect(self.download_file)
            del_action = menu.addAction("🗑 Excluir")
            del_action.triggered.connect(lambda: self.delete_remote_item(data))
            menu.addSeparator()

        upload_action = menu.addAction("⬆ Enviar arquivos aqui...")
        upload_action.triggered.connect(self.upload_file)

        upload_folder_action = menu.addAction("📁 Enviar pasta aqui...")
        upload_folder_action.triggered.connect(self.upload_folder)

        mkdir_action = menu.addAction("📁 Criar nova pasta...")
        mkdir_action.triggered.connect(self.create_folder)

        refresh_action = menu.addAction("🔄 Atualizar")
        refresh_action.triggered.connect(self.refresh)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def upload_file(self):
        if not self.ssh_backend or not self.ssh_backend._sftp:
            QMessageBox.warning(self, "SFTP Desconectado", "Conecte-se a uma sessão SSH antes de enviar arquivos.")
            return
        local_files, _ = QFileDialog.getOpenFileNames(self, "Selecionar arquivos para Upload")
        if local_files:
            self._handle_dropped_files(local_files)

    def upload_folder(self):
        if not self.ssh_backend or not self.ssh_backend._sftp:
            QMessageBox.warning(self, "SFTP Desconectado", "Conecte-se a uma sessão SSH antes de enviar arquivos.")
            return
        folder = QFileDialog.getExistingDirectory(self, "Selecionar pasta para Upload")
        if folder:
            self._handle_dropped_files([folder])

    def _handle_dropped_files(self, local_paths: List[str], target_subdir: Optional[str] = None):
        """
        Recebe a lista de arquivos ou pastas arrastados e inicia o envio.
        Se target_subdir for especificado (solto em cima de uma subpasta), envia diretamente para ela.
        """
        if not self.ssh_backend or not self.ssh_backend._sftp:
            QMessageBox.warning(self, "SFTP Desconectado", "Conecte-se a uma sessão SSH antes de enviar arquivos.")
            return

        dest_dir = self.current_path
        if target_subdir:
            if dest_dir == "/":
                dest_dir = f"/{target_subdir}"
            elif dest_dir in [".", ""]:
                dest_dir = target_subdir
            else:
                dest_dir = f"{dest_dir.rstrip('/')}/{target_subdir}"

        asyncio.create_task(self._do_upload_batch(local_paths, dest_dir))

    async def _do_upload_batch(self, local_paths: List[str], dest_dir: str):
        total_count = len(local_paths)
        if total_count == 0:
            return

        self.status_label.setText(f"⬆ Enviando {total_count} item(ns)...")
        self.status_label.show()

        failed = []
        try:
            for idx, local_path in enumerate(local_paths, 1):
                base_name = os.path.basename(os.path.normpath(local_path))
                self.status_label.setText(f"⬆ Enviando ({idx}/{total_count}): {base_name}...")
                try:
                    await self.ssh_backend.sftp_upload(local_path, dest_dir)
                except Exception as ex:
                    failed.append((base_name, str(ex)))

            await self._async_refresh()

            if failed:
                err_msg = "\n".join([f"• {name}: {err}" for name, err in failed])
                QMessageBox.warning(
                    self,
                    "Falha no Upload",
                    f"Alguns arquivos não puderam ser enviados:\n\n{err_msg}"
                )
                self.status_label.setText(f"⚠ Concluído com {len(failed)} erro(s)")
            else:
                self.status_label.setText(f"✔ {total_count} item(ns) enviado(s) com sucesso!")
                QTimer.singleShot(4000, lambda: self.status_label.hide() if self.status_label.text().startswith("✔") else None)
        except Exception as e:
            QMessageBox.critical(self, "Erro de Upload", f"Erro ao enviar: {e}")
            self.status_label.setText("❌ Erro no envio")

    def download_file(self):
        item = self.tree.currentItem()
        if not item or not self.ssh_backend:
            return
        data = item.data(0, Qt.UserRole)
        if not data or data["is_dir"]:
            return
        filename = data["name"]
        remote_path = f"{self.current_path.rstrip('/')}/{filename}"

        dest_path, _ = QFileDialog.getSaveFileName(self, "Salvar arquivo como", filename)
        if not dest_path:
            return
        asyncio.create_task(self._do_download(remote_path, dest_path))

    async def _do_download(self, remote_path: str, local_path: str):
        try:
            await self.ssh_backend.sftp_download(remote_path, local_path)
            QMessageBox.information(self, "Download Concluído", f"Arquivo baixado com sucesso:\n{local_path}")
        except Exception as e:
            QMessageBox.critical(self, "Erro de Download", str(e))

    def create_folder(self):
        if not self.ssh_backend:
            return
        name, ok = QInputDialog.getText(self, "Nova Pasta Remota", "Nome do diretório:")
        if ok and name.strip():
            remote_folder = f"{self.current_path.rstrip('/')}/{name.strip()}"
            asyncio.create_task(self._do_mkdir(remote_folder))

    async def _do_mkdir(self, path: str):
        try:
            await self.ssh_backend.sftp_mkdir(path)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao criar pasta", str(e))

    def delete_remote_item(self, data: dict):
        if not self.ssh_backend:
            return
        name = data["name"]
        is_dir = data["is_dir"]
        ret = QMessageBox.question(
            self, "Confirmar Exclusão Remota",
            f"Tem certeza que deseja excluir '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.Yes:
            target = f"{self.current_path.rstrip('/')}/{name}"
            asyncio.create_task(self._do_delete(target, is_dir))

    async def _do_delete(self, path: str, is_dir: bool):
        try:
            await self.ssh_backend.sftp_remove(path, is_dir)
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao excluir", str(e))
