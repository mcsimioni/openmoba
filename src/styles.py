"""
Estilos e paleta de cores moderna e profissional para o OpenMoba (Tema Dark Pro inspirado no VS Code / MobaXterm Modern)
"""

DARK_THEME_QSS = """
/* ==================== ESTILO GERAL E TIPOGRAFIA ==================== */
QWidget {
    background-color: #1e1e24;
    color: #e2e8f0;
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
    font-size: 13px;
    selection-background-color: #3b82f6;
    selection-color: #ffffff;
    outline: none;
}

QMainWindow {
    background-color: #18181b;
}

/* ==================== TOOLBAR SUPERIOR ==================== */
QToolBar {
    background: #18181b;
    border-bottom: 1px solid #27272a;
    padding: 6px 10px;
    spacing: 8px;
}

QToolBar QToolButton {
    background: #27272a;
    color: #f1f5f9;
    font-weight: 500;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 12px;
    margin: 2px;
}

QToolBar QToolButton:hover {
    background: #3b82f6;
    border-color: #60a5fa;
    color: #ffffff;
}

QToolBar QToolButton:pressed {
    background: #2563eb;
}

QToolBar::separator {
    background-color: #3f3f46;
    width: 1px;
    margin: 4px 6px;
}

/* ==================== SPLITTER & DIVISORES ==================== */
QSplitter::handle {
    background-color: #27272a;
}

QSplitter::handle:horizontal {
    width: 2px;
}

QSplitter::handle:vertical {
    height: 2px;
}

QSplitter::handle:hover {
    background-color: #3b82f6;
}

/* ==================== ABAS (TAB WIDGET) ==================== */
QTabWidget::pane {
    border: 1px solid #27272a;
    background: #18181b;
}

QTabBar::tab {
    background: #18181b;
    color: #94a3b8;
    border: 1px solid transparent;
    border-bottom: none;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: 500;
}

QTabBar::tab:selected {
    background: #1e1e24;
    color: #38bdf8;
    border: 1px solid #27272a;
    border-bottom: 2px solid #38bdf8;
}

QTabBar::tab:hover:!selected {
    background: #27272a;
    color: #e2e8f0;
}

QTabBar::close-button {
    image: url("src/resources/icons/close.svg");
    subcontrol-position: right;
    margin-left: 6px;
    margin-right: 2px;
    padding: 3px;
    width: 14px;
    height: 14px;
    border-radius: 4px;
}

QTabBar::close-button:hover {
    image: url("src/resources/icons/close_hover.svg");
    background: #ef4444;
}

/* ==================== ÁRVORES E LISTAS (SESSÕES E SFTP) ==================== */
QTreeWidget {
    background-color: #18181b;
    border: 1px solid #27272a;
    border-radius: 6px;
    padding: 4px;
    font-size: 13px;
    show-decoration-selected: 1;
}

QTreeWidget::item {
    padding: 5px 6px;
    border-radius: 4px;
    margin: 1px 0;
}

QTreeWidget::item:hover {
    background: #27272a;
    color: #f8fafc;
}

QTreeWidget::item:selected {
    background: #1e3a8a;
    color: #93c5fd;
    font-weight: 500;
}

QHeaderView::section {
    background-color: #27272a;
    color: #94a3b8;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #3f3f46;
    border-bottom: 1px solid #3f3f46;
    font-size: 12px;
    font-weight: 600;
}

/* ==================== ENTRADAS DE TEXTO & BUSCA ==================== */
QLineEdit, QSpinBox {
    background-color: #18181b;
    color: #f1f5f9;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #3b82f6;
}

QLineEdit:focus, QSpinBox:focus {
    border: 1px solid #38bdf8;
    background-color: #141416;
}

/* ==================== BOTÕES ==================== */
QPushButton {
    background: #27272a;
    color: #f1f5f9;
    border: 1px solid #3f3f46;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background: #3f3f46;
    border-color: #52525b;
    color: #ffffff;
}

QPushButton:pressed {
    background: #18181b;
}

QPushButton:disabled {
    background: #18181b;
    color: #52525b;
    border-color: #27272a;
}

/* Botões primários / de destaque */
QPushButton[primary="true"] {
    background: #2563eb;
    border: 1px solid #3b82f6;
    color: #ffffff;
}

QPushButton[primary="true"]:hover {
    background: #1d4ed8;
    border-color: #60a5fa;
}

/* ==================== MENUS DE CONTEXTO ==================== */
QMenu {
    background-color: #27272a;
    color: #f1f5f9;
    border: 1px solid #3f3f46;
    border-radius: 8px;
    padding: 5px;
}

QMenu::item {
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
    margin: 1px;
}

QMenu::item:selected {
    background-color: #3b82f6;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background: #3f3f46;
    margin: 4px 6px;
}

/* ==================== SCROLLBARS MODERNAS ==================== */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #3f3f46;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #52525b;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0px;
}

QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0;
}

QScrollBar::handle:horizontal {
    background: #3f3f46;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #52525b;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0px;
}

/* ==================== BARRA DE STATUS ==================== */
QStatusBar {
    background-color: #18181b;
    color: #94a3b8;
    border-top: 1px solid #27272a;
    font-size: 12px;
    padding: 3px 10px;
}

QStatusBar QLabel {
    color: #94a3b8;
}

/* ==================== DIÁLOGOS ==================== */
QDialog {
    background-color: #1e1e24;
}

QGroupBox {
    border: 1px solid #27272a;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
    color: #93c5fd;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    background-color: #1e1e24;
}

/* ==================== DRAG & DROP E STATUS DO SFTP ==================== */
QTreeWidget[dragHover="true"] {
    border: 2px dashed #38bdf8 !important;
    background-color: #1e293b !important;
}

QLabel#sftpStatusLabel {
    background-color: #1e293b;
    color: #38bdf8;
    border: 1px solid #0284c7;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}
"""
