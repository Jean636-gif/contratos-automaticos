import os
import hmac
import base64
import hashlib
from services.banco import conectar

# PBKDF2 parâmetros
_ITERATIONS = 200_000
_SALT_BYTES = 16
_HASH_BYTES = 32  # SHA-256

def _hash_senha(senha: str) -> str:
    """Retorna string no formato: pbkdf2$iter$salt_b64$hash_b64"""
    if not isinstance(senha, str):
        raise TypeError("senha deve ser str")

    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, _ITERATIONS, dklen=_HASH_BYTES)

    salt_b64 = base64.urlsafe_b64encode(salt).decode("ascii")
    hash_b64 = base64.urlsafe_b64encode(dk).decode("ascii")
    return f"pbkdf2${_ITERATIONS}${salt_b64}${hash_b64}"

def _verificar_senha(senha: str, armazenado: str) -> bool:
    try:
        alg, it_s, salt_b64, hash_b64 = armazenado.split("$", 3)
        if alg != "pbkdf2":
            return False

        it = int(it_s)
        salt = base64.urlsafe_b64decode(salt_b64.encode("ascii"))
        hash_ref = base64.urlsafe_b64decode(hash_b64.encode("ascii"))

        dk = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, it, dklen=len(hash_ref))
        return hmac.compare_digest(dk, hash_ref)
    except Exception:
        return False

def criar_usuario(username: str, senha: str, perfil: str):
    senha_hash = _hash_senha(senha)

    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
        (username, senha_hash, perfil)
    )
    conn.commit()
    conn.close()

def autenticar(username: str, senha: str):
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT senha, perfil FROM usuarios WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    senha_hash, perfil = row
    return perfil if _verificar_senha(senha, senha_hash) else None

def garantir_admin_padrao():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM usuarios WHERE username = ?", ("admin",))
    existe = cursor.fetchone()

    if not existe:
        cursor.execute(
            "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
            ("admin", _hash_senha("admin123"), "ADMIN")
        )
        conn.commit()

    conn.close()
