import os
from passlib.context import CryptContext
from services.banco import conectar

try:
    import streamlit as st
except Exception:
    st = None

# ✅ seguro e 100% Python (não depende de bcrypt)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def criar_ou_atualizar_usuario(username: str, senha: str, perfil: str):
    conn = conectar()
    cur = conn.cursor()

    senha_hash = _hash_senha(senha)

    cur.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
    existe = cur.fetchone()

    if existe:
        cur.execute(
            "UPDATE usuarios SET senha = ?, perfil = ? WHERE username = ?",
            (senha_hash, perfil, username),
        )
    else:
        cur.execute(
            "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
            (username, senha_hash, perfil),
        )

    conn.commit()
    conn.close()


def autenticar(username: str, senha: str):
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT senha, perfil FROM usuarios WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None

    senha_hash, perfil = row

    try:
        if pwd_context.verify(senha, senha_hash):
            return perfil
    except Exception:
        return None

    return None


def _ler_admin_credenciais():
    # 1) Secrets (Streamlit Cloud)
    username = ""
    password = ""
    if st is not None:
        try:
            username = str(st.secrets.get("ADMIN_USERNAME", "")).strip()
            password = str(st.secrets.get("ADMIN_PASSWORD", ""))
        except Exception:
            username = ""
            password = ""

    # 2) Env vars (fallback)
    if not username or not password:
        username = os.getenv("ADMIN_USERNAME", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "")

    return username, password


def garantir_admin_padrao():
    """
    Cria/atualiza o admin SEMPRE a partir de Secrets/env.
    Retorna True se conseguiu ler credenciais; False se não.
    """
    username, password = _ler_admin_credenciais()
    if not username or not password:
        return False

    criar_ou_atualizar_usuario(username, password, "ADMIN")
    return True
