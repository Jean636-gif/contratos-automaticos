from passlib.context import CryptContext
from services.banco import conectar

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def criar_usuario(username: str, senha: str, perfil: str):
    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
    existe = cur.fetchone()

    senha_hash = _hash_senha(senha)

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

    cur.execute(
        "SELECT senha, perfil FROM usuarios WHERE username = ?",
        (username,),
    )

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


def garantir_admin_padrao():
    """
    Garante que o usuário jean.silva exista e tenha a senha correta.
    """
    usuario = "jean.silva"
    senha = "Wiz@2019"
    perfil = "ADMIN"

    criar_usuario(usuario, senha, perfil)
