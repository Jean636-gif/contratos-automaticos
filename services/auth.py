from passlib.context import CryptContext
from services.banco import conectar

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def criar_usuario(username, senha, perfil):
    conn = conectar()
    cursor = conn.cursor()

    senha_hash = pwd_context.hash(senha)

    cursor.execute(
        "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
        (username, senha_hash, perfil)
    )

    conn.commit()
    conn.close()


def autenticar(username, senha):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT senha, perfil FROM usuarios WHERE username = ?",
        (username,)
    )

    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        senha_hash, perfil = resultado
        if pwd_context.verify(senha, senha_hash):
            return perfil

    return None


def garantir_admin_padrao():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE username = 'admin'")
    existe = cursor.fetchone()

    if not existe:
        # 🔐 ALTERE AQUI A SENHA
        senha_segura = "TroqueEssaSenhaAgora!2026"

        senha_hash = pwd_context.hash(senha_segura)

        cursor.execute(
            "INSERT INTO usuarios (username, senha, perfil) VALUES (?, ?, ?)",
            ("admin", senha_hash, "ADMIN")
        )

        conn.commit()

    conn.close()
