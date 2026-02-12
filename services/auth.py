from passlib.context import CryptContext
from passlib.exc import UnknownHashError

from services.banco import conectar

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def criar_usuario(username: str, senha: str, perfil: str):
    conn = conectar()
    cur = conn.cursor()
    senha_hash = _hash_senha(senha)
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

    if not row:
        conn.close()
        return None

    senha_salva, perfil = row

    # 1) Tenta verificar como hash bcrypt (normal)
    try:
        ok = pwd_context.verify(senha, senha_salva)
        conn.close()
        return perfil if ok else None

    except UnknownHashError:
        # 2) Caso antigo: senha salva não é hash reconhecido.
        #    Estratégia: se for senha em texto puro (ou outro formato),
        #    compara direto. Se bater, rehash pra bcrypt e salva.
        if senha_salva == senha:
            novo_hash = _hash_senha(senha)
            cur.execute(
                "UPDATE usuarios SET senha = ? WHERE username = ?",
                (novo_hash, username),
            )
            conn.commit()
            conn.close()
            return perfil

        conn.close()
        return None


def garantir_admin_padrao():
    """
    Garante que exista um admin com senha BCRYPT.
    Se existir admin com senha inválida (não-hash), corrige para uma senha segura padrão.
    """
    senha_segura = "TroqueEssaSenhaAgora!2026"

    conn = conectar()
    cur = conn.cursor()

    cur.execute("SELECT senha FROM usuarios WHERE username = 'admin'")
    row = cur.fetchone()

    if not row:
        # cria admin novo
        cur.execute(
            "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
            ("admin", _hash_senha(senha_segura), "ADMIN"),
        )
        conn.commit()
        conn.close()
        return

    senha_salva = row[0]

    # Se o hash for reconhecido, não mexe
    try:
        pwd_context.identify(senha_salva)
        conn.close()
        return
    except Exception:
        # Senha antiga em formato estranho → força migração para bcrypt
        cur.execute(
            "UPDATE usuarios SET senha = ?, perfil = ? WHERE username = ?",
            (_hash_senha(senha_segura), "ADMIN", "admin"),
        )
        conn.commit()
        conn.close()
        return
