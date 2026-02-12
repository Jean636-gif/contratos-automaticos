import os
import streamlit as st

from services.banco import (
    criar_tabelas,
    atualizar_status,
    inserir_contrato_fornecedor,
    buscar_contrato_por_id,
    atualizar_numero_arquivo,
    listar_contratos_por_status,
    contar_por_status,
    listar_fornecedores_resumo,
    listar_versoes_por_fornecedor,
)
from services.auth import autenticar, garantir_admin_padrao
from services.cnpj import consultar_cnpj
from services.contrato import gerar_contrato, gerar_numero_contrato


# -----------------------------
# Constantes
# -----------------------------
STATUS_COLUNAS = {
    "FILA_INICIO": "🧾 Fila de Início",
    "ANALISE_JURIDICA_LGPD": "🟨 Jurídico/LGPD",
    "ANALISE_DEMANDANTE": "🟦 Demandante",
    "ANALISE_FORNECEDOR": "🟧 Fornecedor",
    "FINALIZADO": "🟩 Finalizado",
}
ORDEM_STATUS = list(STATUS_COLUNAS.keys())


# -----------------------------
# Init
# -----------------------------
criar_tabelas()
garantir_admin_padrao()

if "logado" not in st.session_state:
    st.session_state.logado = False
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "view" not in st.session_state:
    st.session_state.view = "RESUMO"  # RESUMO | LISTA | FORNECEDORES
if "filtro_status" not in st.session_state:
    st.session_state.filtro_status = "FILA_INICIO"


# -----------------------------
# Login
# -----------------------------
if not st.session_state.logado:
    st.title("🔐 Login – Gestão de Contratos")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        perfil = autenticar(usuario, senha)
        if perfil:
            st.session_state.logado = True
            st.session_state.perfil = perfil
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

    st.info("Primeiro acesso: usuário **admin** / senha **admin123**")
    st.stop()


# -----------------------------
# Sidebar / Navegação
# -----------------------------
perfil = st.session_state.perfil
st.sidebar.success(f"Perfil: {perfil}")

if st.sidebar.button("📊 Resumo por etapa"):
    st.session_state.view = "RESUMO"
    st.rerun()

if st.sidebar.button("📋 Lista por etapa"):
    st.session_state.view = "LISTA"
    st.rerun()

if st.sidebar.button("🏢 Fornecedores"):
    st.session_state.view = "FORNECEDORES"
    st.rerun()

if st.sidebar.button("Sair"):
    st.session_state.logado = False
    st.session_state.perfil = None
    st.session_state.view = "RESUMO"
    st.session_state.filtro_status = "FILA_INICIO"
    st.rerun()


st.title("📄 Gestão de Contratos")


# -----------------------------
# Permissões
# -----------------------------
def pode_criar_contrato():
    return perfil in ["ADMIN", "DEMANDANTE"]

def pode_mover_para(novo_status: str):
    if perfil == "ADMIN":
        return True

    if perfil == "DEMANDANTE" and novo_status in ["FILA_INICIO", "ANALISE_DEMANDANTE"]:
        return True
    if perfil == "JURIDICO" and novo_status == "ANALISE_JURIDICA_LGPD":
        return True
    if perfil == "FORNECEDOR" and novo_status == "ANALISE_FORNECEDOR":
        return True

    return False


# -----------------------------
# Helpers UI
# -----------------------------
def download_docx(contrato_id: int, arquivo: str):
    if arquivo and os.path.exists(arquivo):
        with open(arquivo, "rb") as f:
            st.download_button(
                "⬇️ Baixar contrato (.docx)",
                f.read(),
                file_name=os.path.basename(arquivo),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_{contrato_id}"
            )
    else:
        st.caption("Arquivo não encontrado no caminho salvo.")

def mover_status(contrato_id: int, novo_status: str):
    if not pode_mover_para(novo_status):
        st.warning("Você não tem permissão para mover para esse status.")
        return
    atualizar_status(contrato_id, novo_status)
    st.rerun()

def abrir_lista(status: str):
    st.session_state.view = "LISTA"
    st.session_state.filtro_status = status
    st.rerun()


# -----------------------------
# Criar contrato (Fila de início + número manual)
# -----------------------------
if pode_criar_contrato():
    st.subheader("➕ Gerar contrato (entra na Fila de Início)")

    col1, col2 = st.columns([2, 1])
    with col1:
        cnpj = st.text_input("CNPJ do fornecedor (BrasilAPI)")
    with col2:
        numero_manual = st.text_input("Número do contrato (opcional)", placeholder="ex: CT-2026-ABC-01")

    if st.button("Gerar contrato e colocar na fila"):
        try:
            dados = consultar_cnpj(cnpj)
            fornecedor_cnpj = dados.get("cnpj", "")
            fornecedor_razao = dados.get("razao_social", "")

            contrato_id = inserir_contrato_fornecedor(
                fornecedor_cnpj=fornecedor_cnpj,
                fornecedor_razao=fornecedor_razao,
                status="FILA_INICIO"
            )

            row = buscar_contrato_por_id(contrato_id)
            versao = int(row[7])

            numero_final = (numero_manual or "").strip()
            if not numero_final:
                numero_final = gerar_numero_contrato(contrato_id)

            arquivo = gerar_contrato(dados, numero_final, fornecedor_cnpj, versao)
            atualizar_numero_arquivo(contrato_id, numero_final, arquivo)

            st.success(f"Contrato {numero_final} gerado (v{versao}) e colocado na Fila de Início.")
            st.caption(f"Arquivo: {arquivo}")

        except Exception as e:
            st.error(f"Erro ao gerar contrato: {e}")


# -----------------------------
# Views
# -----------------------------
if st.session_state.view == "RESUMO":
    st.divider()
    st.header("📊 Resumo por etapa")

    counts = contar_por_status()

    resumo_cols = st.columns(len(ORDEM_STATUS))
    for i, status in enumerate(ORDEM_STATUS):
        with resumo_cols[i]:
            with st.container(border=True):
                st.metric(label=STATUS_COLUNAS[status], value=counts.get(status, 0))
                if st.button("Acessar contratos", key=f"box_acessar_{status}"):
                    abrir_lista(status)


elif st.session_state.view == "LISTA":
    st.divider()
    st.header("📋 Contratos por etapa")

    status_escolhido = st.selectbox(
        "Etapa",
        ORDEM_STATUS,
        index=ORDEM_STATUS.index(st.session_state.filtro_status) if st.session_state.filtro_status in ORDEM_STATUS else 0,
        format_func=lambda s: STATUS_COLUNAS[s]
    )
    st.session_state.filtro_status = status_escolhido

    contratos = listar_contratos_por_status(status_escolhido)

    with st.container(border=True):
        st.metric(label=f"Total em {STATUS_COLUNAS[status_escolhido]}", value=len(contratos))
        if st.button("⬅️ Voltar para Resumo"):
            st.session_state.view = "RESUMO"
            st.rerun()

    for c in contratos:
        contrato_id, numero, razao, stt, arquivo, forn_cnpj, forn_razao, versao = c

        with st.container(border=True):
            st.markdown(f"**{numero or '(sem número)'}** · `v{int(versao)}`")
            st.write(forn_razao or razao or "(sem razão social)")
            st.caption(f"CNPJ: {forn_cnpj}")

            download_docx(contrato_id, arquivo)

            atual_idx = ORDEM_STATUS.index(stt)
            novo = st.selectbox(
                "Mover para",
                ORDEM_STATUS,
                index=atual_idx,
                format_func=lambda s: STATUS_COLUNAS[s],
                key=f"mv_lista_{contrato_id}"
            )
            if novo != stt:
                mover_status(contrato_id, novo)


elif st.session_state.view == "FORNECEDORES":
    st.divider()
    st.header("🏢 Fornecedores (consolidado)")

    fornecedores = listar_fornecedores_resumo()
    if not fornecedores:
        st.info("Ainda não há fornecedores com contratos.")
    else:
        with st.container(border=True):
            st.metric(label="Fornecedores com contratos", value=len(fornecedores))

        for forn_cnpj, forn_razao, total, max_versao in fornecedores:
            titulo = f"{forn_razao} | {forn_cnpj} — {int(total)} contrato(s), até v{int(max_versao)}"
            with st.expander(titulo, expanded=False):
                versoes = listar_versoes_por_fornecedor(forn_cnpj)
                for (cid, num, stt, arq, ver) in versoes:
                    with st.container(border=True):
                        st.markdown(f"**{num or '(sem número)'}** · `v{int(ver)}` · {STATUS_COLUNAS.get(stt, stt)}")
                        download_docx(cid, arq)
