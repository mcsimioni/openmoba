#!/usr/bin/env python3
"""
OpenMoba Auto-Bootstrapper & Launcher
- Detecta o sistema operacional (Windows, Linux, macOS).
- Cria automaticamente um ambiente virtual (.venv) se não existir ou se faltarem dependências.
- Instala automaticamente apenas os pacotes que faltam via pip.
- Inicia o OpenMoba dentro do ambiente virtual isolado.
"""

import sys
import os

# Configuração de flags Chromium / WebEngine para suprimir logs sem quebrar aceleração gráfica
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS",
    "--log-level=3 --disable-logging"
)

import subprocess
import venv
import importlib.util

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_ROOT, ".venv")

# Dependências obrigatórias e seus nomes de importação
REQUIRED_PACKAGES = {
    "PySide6": "PySide6",
    "asyncssh": "asyncssh",
    "cryptography": "cryptography",
    "qasync": "qasync",
}


def get_venv_python():
    """Retorna o caminho do interpretador Python dentro do venv."""
    if sys.platform == "win32":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        return os.path.join(VENV_DIR, "bin", "python")


def is_running_inside_venv():
    """Verifica se o script já está sendo executado pelo Python do .venv local."""
    current_exe = os.path.abspath(sys.executable).lower()
    expected_exe = os.path.abspath(get_venv_python()).lower()
    return current_exe == expected_exe


def check_missing_dependencies(python_bin):
    """Executa checagem para descobrir quais pacotes faltam instalar."""
    missing = []
    for pkg_name, module_name in REQUIRED_PACKAGES.items():
        cmd = [python_bin, "-c", f"import {module_name}"]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode != 0:
            missing.append(pkg_name)
    return missing


def setup_virtual_environment():
    """Cria o venv se necessário e garante que todas as dependências estejam instaladas."""
    venv_python = get_venv_python()

    # 1. Cria o .venv se não existir
    if not os.path.exists(venv_python):
        print("\n" + "=" * 55)
        print("  [OpenMoba] Criando ambiente virtual dedicado (.venv)...")
        print("=" * 55)
        builder = venv.EnvBuilder(with_pip=True)
        builder.create(VENV_DIR)

    # 2. Verifica se o pip está disponível dentro do venv
    if not os.path.exists(venv_python):
        print(f"[OpenMoba ERRO] Não foi possível localizar o interpretador em: {venv_python}")
        sys.exit(1)

    # 3. Detecta dependências ausentes
    missing = check_missing_dependencies(venv_python)
    if missing:
        print("\n" + "=" * 55)
        print(f"  [OpenMoba] Instalando dependências ausentes no .venv:")
        for m in missing:
            print(f"   -> {m}")
        print("=" * 55 + "\n")

        # Atualiza pip silenciosamente e instala os pacotes faltantes
        cmd_install = [venv_python, "-m", "pip", "install", *missing]
        res = subprocess.run(cmd_install)
        if res.returncode != 0:
            print("[OpenMoba ERRO] Falha ao instalar dependências.")
            sys.exit(res.returncode)
        print("\n[OpenMoba] Todas as dependências foram instaladas com sucesso!\n")


def launch_application():
    """Executa o aplicativo OpenMoba."""
    venv_python = get_venv_python()

    # Se já estamos dentro do venv dedicado, executa a aplicação normalmente
    if is_running_inside_venv():
        _start_qt_app()
    else:
        # Se estamos fora, prepara o .venv e relança o processo com o Python do venv
        setup_virtual_environment()
        cmd = [venv_python, os.path.abspath(__file__)] + sys.argv[1:]
        try:
            exit_code = subprocess.call(cmd)
            sys.exit(exit_code)
        except KeyboardInterrupt:
            sys.exit(0)


def _start_qt_app():
    """Função interna que carrega a interface gráfica PySide6."""
    import asyncio

    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QFont, QIcon
    from qasync import QEventLoop

    from src.main_window import MainWindow
    from src.styles import DARK_THEME_QSS

    app = QApplication(sys.argv)
    app.setApplicationName("OpenMoba")
    app.setStyle("Fusion")

    # Ícone oficial do aplicativo
    icon_path = os.path.join(PROJECT_ROOT, "src", "resources", "icons", "app_icon.png")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    font = QFont("Segoe UI" if sys.platform == "win32" else "Sans Serif", 10)
    app.setFont(font)
    app.setStyleSheet(DARK_THEME_QSS)

    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MainWindow()
    if os.path.exists(icon_path):
        window.setWindowIcon(QIcon(icon_path))
    window.show()

    with loop:
        try:
            loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
        except Exception:
            pass

    # Encerra o processo limpo ao fechar as janelas, prevenindo
    # condição de corrida entre o Garbage Collector do Python e threads nativas do Chromium
    os._exit(0)


if __name__ == "__main__":
    launch_application()
