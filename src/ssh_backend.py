import asyncio
import os
import stat
from typing import Optional, Callable, List, Dict, Any
import asyncssh
from PySide6.QtCore import QObject, Signal, Slot


class SSHClientBackend(QObject):
    data_received = Signal(str)
    connection_closed = Signal(str)
    connection_established = Signal(str)
    sftp_ready = Signal()
    error_occurred = Signal(str)

    def __init__(self, host: str, port: int, username: str, password: Optional[str] = None, key_path: Optional[str] = None):
        super().__init__()
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.key_path = key_path

        self._conn: Optional[asyncssh.SSHClientConnection] = None
        self._process: Optional[asyncssh.SSHClientProcess] = None
        self._sftp: Optional[asyncssh.SFTPClient] = None
        self._cols = 80
        self._rows = 24
        self._is_connected = False

    def set_terminal_size(self, cols: int, rows: int):
        self._cols = max(10, cols)
        self._rows = max(5, rows)
        if self._process and hasattr(self._process, "terminal_size_changed"):
            try:
                self._process.terminal_size_changed(width=self._cols, height=self._rows)
            except Exception:
                pass

    async def connect(self):
        try:
            client_keys = None
            if self.key_path and os.path.exists(self.key_path):
                client_keys = [self.key_path]

            self.data_received.emit(f"\r\n\x1b[36m[OpenMoba] Connecting to {self.username}@{self.host}:{self.port}...\x1b[0m\r\n")

            # Conexão SSH completa com suporte a todos os tipos de chave, cifras e algoritmos legados e modernos
            options = asyncssh.SSHClientConnectionOptions(
                username=self.username,
                password=self.password,
                client_keys=client_keys,
                known_hosts=None,
                # Aceita algoritmos legados (ssh-rsa, sha1, diffie-hellman) e modernos (ed25519)
                server_host_key_algs=[
                    "ssh-ed25519", "ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521",
                    "rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"
                ],
                kex_algs=[
                    "curve25519-sha256", "curve25519-sha256@libssh.org",
                    "ecdh-sha2-nistp256", "ecdh-sha2-nistp384", "ecdh-sha2-nistp521",
                    "diffie-hellman-group14-sha256", "diffie-hellman-group16-sha512",
                    "diffie-hellman-group-exchange-sha256", "diffie-hellman-group14-sha1",
                    "diffie-hellman-group1-sha1"
                ],
                encryption_algs=[
                    "chacha20-poly1305@openssh.com",
                    "aes128-gcm@openssh.com", "aes256-gcm@openssh.com",
                    "aes128-ctr", "aes192-ctr", "aes256-ctr",
                    "aes128-cbc", "aes256-cbc", "3des-cbc"
                ]
            )

            self._conn = await asyncssh.connect(
                host=self.host,
                port=self.port,
                options=options,
                encoding=None,
            )

            self._is_connected = True
            self.connection_established.emit(f"{self.username}@{self.host}")
            self.data_received.emit(f"\x1b[32m[OpenMoba] SSH Connection established successfully.\x1b[0m\r\n\r\n")

            # Inicia SFTP em background
            asyncio.create_task(self._init_sftp())

            # Cria processo interativo de PTY com terminal xterm-256color
            self._process = await self._conn.create_process(
                term_type="xterm-256color",
                term_size=(self._cols, self._rows),
                encoding=None
            )

            # Loop de leitura do stdout/stderr remoto
            asyncio.create_task(self._read_loop())

        except Exception as e:
            self.error_occurred.emit(str(e))
            self.data_received.emit(f"\r\n\x1b[31m[OpenMoba Connection Error] {str(e)}\x1b[0m\r\n")

    async def _init_sftp(self):
        try:
            if self._conn:
                self._sftp = await self._conn.start_sftp_client()
                self.sftp_ready.emit()
        except Exception as e:
            self.error_occurred.emit(f"SFTP init: {e}")

    async def _read_loop(self):
        try:
            while self._process and not self._process.is_closing():
                chunk = await self._process.stdout.read(4096)
                if not chunk:
                    break
                text = chunk.decode("utf-8", errors="replace")
                self.data_received.emit(text)
        except Exception:
            pass
        finally:
            self._is_connected = False
            self.connection_closed.emit("Disconnected")
            self.data_received.emit("\r\n\x1b[33m[OpenMoba] Session disconnected.\x1b[0m\r\n")

    def write_data(self, data: str):
        if self._process and self._process.stdin and not self._process.stdin.is_closing():
            try:
                self._process.stdin.write(data.encode("utf-8", errors="replace"))
            except Exception:
                pass

    async def close(self):
        self._is_connected = False
        if self._sftp:
            try:
                self._sftp.exit()
            except Exception:
                pass
            self._sftp = None
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
            try:
                self._process.kill()
            except Exception:
                pass
            self._process = None
        if self._conn:
            try:
                self._conn.close()
                await self._conn.wait_closed()
            except Exception:
                pass
            self._conn = None

    # SFTP Operações
    async def sftp_list_dir(self, remote_path: str = ".") -> List[Dict[str, Any]]:
        if not self._sftp:
            return []
        items = []
        try:
            dir_attrs = await self._sftp.readdir(remote_path)
            for entry in dir_attrs:
                filename = entry.filename
                if filename in [".", ".."]:
                    continue
                attrs = entry.attrs
                is_dir = stat.S_ISDIR(attrs.permissions) if attrs.permissions else False
                size = attrs.size if attrs.size is not None else 0
                mtime = attrs.mtime if attrs.mtime is not None else 0
                items.append({
                    "name": filename,
                    "is_dir": is_dir,
                    "size": size,
                    "mtime": mtime,
                    "permissions": oct(attrs.permissions) if attrs.permissions else ""
                })
            # Ordena: pastas primeiro, depois nomes em ordem alfabética
            items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        except Exception as e:
            self.error_occurred.emit(f"SFTP List error: {e}")
        return items

    async def sftp_upload(self, local_path: str, remote_dest_dir: str):
        """
        Faz upload de um arquivo ou pasta local para o diretório remoto de destino.
        Se local_path for pasta, realiza envio recursivo automaticamente.
        """
        if not self._sftp:
            return
        is_dir = os.path.isdir(local_path)
        base_name = os.path.basename(os.path.normpath(local_path))
        if is_dir:
            if remote_dest_dir in [".", ""]:
                await self._sftp.put(local_path, recurse=True)
            else:
                await self._sftp.put(local_path, remote_dest_dir, recurse=True)
        else:
            if remote_dest_dir in [".", ""]:
                remote_file = base_name
            elif remote_dest_dir == "/":
                remote_file = f"/{base_name}"
            else:
                remote_file = f"{remote_dest_dir.rstrip('/')}/{base_name}"
            await self._sftp.put(local_path, remote_file, recurse=False)

    async def sftp_download(self, remote_path: str, local_path: str):
        if not self._sftp:
            return
        await self._sftp.get(remote_path, local_path)

    async def sftp_remove(self, remote_path: str, is_dir: bool = False):
        if not self._sftp:
            return
        if is_dir:
            await self._sftp.rmdir(remote_path)
        else:
            await self._sftp.remove(remote_path)

    async def sftp_mkdir(self, remote_path: str):
        if not self._sftp:
            return
        await self._sftp.mkdir(remote_path)
