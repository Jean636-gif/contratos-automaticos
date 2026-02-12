from passlib.context import CryptContext
from services.banco import conectar

# ✅ NÃO usa bcrypt (evita erro no Streamlit Cloud).
# PBKDF2-SHA256 é seguro e não precisa de libs nativas.
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

    senha_salva, perfil = row

    # Se for hash reconhecido, verifica
    try:
        if pwd_context.verify(senha, senha_salva):
            return perfil
    except Exception:
        # Se tiver senhas antigas em texto puro, você pode migrar aqui.
        # Por enquanto, só falha o login.
        return None

    return None


def garantir_admin_padrao():
    """
    Garante o usuário ADMIN fixo solicitado.
    """
    criar_ou_atualizar_usuario("jean.silva", "Wiz@2019", "ADMIN")
