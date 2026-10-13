import os
import json
import base64
import uuid
from typing import List, Dict, Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DATA_DIR = os.path.join(os.path.expanduser("~"), ".openmoba")
SESSIONS_FILE = os.path.join(DATA_DIR, "sessions.enc")
SALT_FILE = os.path.join(DATA_DIR, "salt.bin")


def _get_or_create_salt() -> bytes:
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(SALT_FILE):
        salt = os.urandom(16)
        with open(SALT_FILE, "wb") as f:
            f.write(salt)
        return salt
    with open(SALT_FILE, "rb") as f:
        return f.read()


def _get_cipher(master_key: str = "openmoba-default-local-key") -> Fernet:
    salt = _get_or_create_salt()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
    return Fernet(key)


def find_default_mobaxterm_ini() -> Optional[str]:
    """
    Localiza dinamicamente o arquivo MobaXterm.ini para o usuário atualmente logado no sistema operacional.
    Testa pastas padrão do instalador no perfil do usuário (%APPDATA%) e diretórios comuns.
    """
    candidates = [
        # Pasta de dados de aplicativos padrão do Windows do usuário atual (%APPDATA%)
        os.path.join(os.environ.get("APPDATA", ""), "MobaXterm", "MobaXterm.ini"),
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "MobaXterm", "MobaXterm.ini"),
        # Documentos do usuário
        os.path.join(os.path.expanduser("~"), "Documents", "MobaXterm", "MobaXterm.ini"),
        # Versões portáteis no diretório de execução ou Desktop
        os.path.join(os.path.expanduser("~"), "Desktop", "MobaXterm.ini"),
        os.path.join(os.getcwd(), "MobaXterm.ini"),
        os.path.join(os.path.dirname(os.getcwd()), "MobaXterm.ini"),
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def is_mobaxterm_installed() -> bool:
    """
    Verifica se o MobaXterm está instalado ou presente no computador.
    Checa arquivo de configuração do usuário (%APPDATA%), executáveis em Program Files ou Registro do Windows.
    """
    # 1. Verifica arquivo de configuração/sessões
    if find_default_mobaxterm_ini() is not None:
        return True

    # 2. Verifica executáveis no Windows (Program Files)
    exe_candidates = [
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Mobatek", "MobaXterm", "MobaXterm.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Mobatek", "MobaXterm", "MobaXterm.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Mobatek", "MobaXterm Personal Edition", "MobaXterm.exe"),
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Mobatek", "MobaXterm Personal Edition", "MobaXterm.exe"),
    ]
    for exe in exe_candidates:
        if os.path.exists(exe):
            return True

    # 3. Verifica Registro do Windows (HKCU / HKLM)
    try:
        import winreg
        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(root, r"Software\Mobatek\MobaXterm"):
                    return True
            except OSError:
                pass
    except Exception:
        pass

    return False


def import_mobaxterm_sessions(ini_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Lê as sessões SSH salvas no MobaXterm.ini do usuário atualmente conectado.
    Se ini_path não for especificado, descobre o arquivo automaticamente no perfil do usuário.
    """
    if not ini_path:
        ini_path = find_default_mobaxterm_ini()

    if not ini_path or not os.path.exists(ini_path):
        return []

    sessions = []
    try:
        with open(ini_path, "r", errors="ignore") as f:
            in_bookmarks = False
            for line in f:
                line = line.strip()
                if line.startswith("[Bookmarks") or line.startswith("[Sessions"):
                    in_bookmarks = True
                    continue
                if in_bookmarks:
                    if line.startswith("["):
                        if not line.startswith("[Bookmarks_"):
                            break
                        continue
                    if not line or line.startswith("SubRep=") or line.startswith("ImgNum="):
                        continue
                    if "=" in line:
                        name, val = line.split("=", 1)
                        if "#109#" in val:  # Código 109 = SSH no MobaXterm
                            parts = val.split("#")
                            if len(parts) >= 3:
                                cfg = parts[2].split("%")
                                host = cfg[1] if len(cfg) > 1 else ""
                                port = int(cfg[2]) if len(cfg) > 2 and cfg[2].isdigit() else 22
                                user = cfg[3] if len(cfg) > 3 and cfg[3] else "root"
                                key = cfg[14] if len(cfg) > 14 and cfg[14] else None
                                if key:
                                    key = key.replace("_ProfileDir_", os.path.expanduser("~"))
                                sessions.append({
                                    "id": str(uuid.uuid4()),
                                    "name": name,
                                    "host": host,
                                    "port": port,
                                    "username": user,
                                    "password": None,
                                    "key_path": key if key and os.path.exists(key) else None,
                                    "imported_from": "MobaXterm"
                                })
    except Exception:
        pass
    return sessions


class SessionStore:
    def __init__(self, master_key: str = "openmoba-default-local-key"):
        self.master_key = master_key
        self.cipher = _get_cipher(master_key)
        self.sessions: List[Dict[str, Any]] = []
        self.load_sessions()

    def load_sessions(self) -> List[Dict[str, Any]]:
        if not os.path.exists(SESSIONS_FILE):
            # Se não existe ainda arquivo local, importa automaticamente as do MobaXterm existente
            moba_sessions = import_mobaxterm_sessions()
            if moba_sessions:
                self.sessions = moba_sessions
                self.save_sessions()
                return self.sessions
            self.sessions = []
            return self.sessions
        try:
            with open(SESSIONS_FILE, "rb") as f:
                data = f.read()
            decrypted = self.cipher.decrypt(data).decode("utf-8")
            self.sessions = json.loads(decrypted)
        except Exception:
            self.sessions = []
        return self.sessions

    def save_sessions(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        raw_json = json.dumps(self.sessions, indent=2).encode("utf-8")
        encrypted = self.cipher.encrypt(raw_json)
        with open(SESSIONS_FILE, "wb") as f:
            f.write(encrypted)

    def add_or_update_session(self, session: Dict[str, Any]) -> None:
        for idx, s in enumerate(self.sessions):
            if s.get("id") == session.get("id"):
                self.sessions[idx] = session
                self.save_sessions()
                return
        self.sessions.append(session)
        self.save_sessions()

    def delete_session(self, session_id: str) -> None:
        self.sessions = [s for s in self.sessions if s.get("id") != session_id]
        self.save_sessions()
