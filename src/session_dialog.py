import uuid
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit,
    QSpinBox, QPushButton, QFileDialog, QDialogButtonBox, QLabel, QGroupBox
)


class SessionDialog(QDialog):
    def __init__(self, session_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuração de Sessão SSH")
        self.resize(480, 360)
        self.session_data = session_data or {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)

        group = QGroupBox("Parâmetros de Conexão SSH")
        form = QFormLayout(group)
        form.setContentsMargins(14, 16, 14, 14)
        form.setSpacing(10)

        self.name_edit = QLineEdit(self.session_data.get("name", "Nova Sessão"))
        self.name_edit.setPlaceholderText("Ex: Servidor Produção / Web Dev")
        form.addRow("Nome da Sessão:", self.name_edit)

        self.host_edit = QLineEdit(self.session_data.get("host", ""))
        self.host_edit.setPlaceholderText("Ex: 192.168.1.100 ou meuservidor.com")
        form.addRow("Host Remoto:", self.host_edit)

        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.session_data.get("port", 22))
        form.addRow("Porta:", self.port_spin)

        self.user_edit = QLineEdit(self.session_data.get("username", "root"))
        self.user_edit.setPlaceholderText("Ex: root, ubuntu, admin")
        form.addRow("Usuário:", self.user_edit)

        self.pass_edit = QLineEdit(self.session_data.get("password", "") or "")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        self.pass_edit.setPlaceholderText("(Deixe em branco para perguntar ao conectar)")
        form.addRow("Senha:", self.pass_edit)

        # Chave Privada
        key_layout = QHBoxLayout()
        key_layout.setSpacing(6)
        self.key_edit = QLineEdit(self.session_data.get("key_path", "") or "")
        self.key_edit.setPlaceholderText("(Opcional) Chave .pem, .id_rsa ou .key")
        self.browse_key_btn = QPushButton("Procurar...")
        self.browse_key_btn.clicked.connect(self._browse_key)
        key_layout.addWidget(self.key_edit)
        key_layout.addWidget(self.browse_key_btn)
        form.addRow("Chave Privada:", key_layout)

        layout.addWidget(group)

        buttons = QDialogButtonBox()
        self.ok_btn = buttons.addButton("Salvar e Conectar", QDialogButtonBox.AcceptRole)
        self.ok_btn.setProperty("primary", "true")
        self.cancel_btn = buttons.addButton("Cancelar", QDialogButtonBox.RejectRole)

        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_key(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Chave Privada", "", "Chaves Privadas (*.pem *.key *.id_rsa *);;Todos os Arquivos (*)"
        )
        if filename:
            self.key_edit.setText(filename)

    def _on_accept(self):
        if not self.host_edit.text().strip():
            self.host_edit.setFocus()
            return
        if not self.user_edit.text().strip():
            self.user_edit.setFocus()
            return
        self.accept()

    def get_data(self) -> Dict[str, Any]:
        return {
            "id": self.session_data.get("id", str(uuid.uuid4())),
            "name": self.name_edit.text().strip() or self.host_edit.text().strip(),
            "host": self.host_edit.text().strip(),
            "port": self.port_spin.value(),
            "username": self.user_edit.text().strip(),
            "password": self.pass_edit.text() or None,
            "key_path": self.key_edit.text().strip() or None,
        }
