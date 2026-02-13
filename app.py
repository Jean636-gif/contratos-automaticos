# app.py (CONSOLIDADO)
import os
from datetime import datetime, timedelta, timezone

import streamlit as st

from services.banco import (
    criar_tabelas,
    inserir_contrato_fornecedor,
    atualizar_numero_arquivo,
    listar_contratos_por_status,
    contar_por_status,
    listar_fornecedores_resumo,
    listar_versoes_por_fornecedor,
    buscar_contrato_por_id,
    atualizar_status,
    excluir_contrato,
    listar_finalizados,
    obter_status_logs,
)
from services.auth import autenticar, garantir_admin_padrao
from services.cnpj import consultar_cnpj
from services.contrato import gerar_contrato, gerar_numero_contrato


# -----------------------------
# Config
# -----------------------------
MODELOS = {
    "NDA": "templates/nda.docx",
    "Contrato de API": "templates/contrato_api.docx",
}

STATUS_LABEL = {
    "FILA_INICIO": "🧾 Fila de Início",
    "ANALISE_JURIDICA_LGPD": "🟨 Jurídico/LGPD",
    "ANALISE_DEMANDANTE": "🟦 Demandante",
    "ANALISE_FORNECEDOR": "🟧 Fornecedor",
    "FINALIZADO": "🟩 Finalizado",
}
STATUS_ORDEM = list(STATUS_LABEL.keys())


# -----------------------------
# SLA (horas úteis seg-sex 09-18)
# -----------------------------
def parse_iso(ts: str) -> datetime:
    # banco salva ISO com timezone UTC
    return datetime.fromisoformat(ts)

def business_seconds(start: datetime, end: datetime) -> int:
    """
    Conta segundos dentro do horário útil (09:00–18:00) em dias úteis (seg-sex).
    Observação: Streamlit Cloud roda em UTC; aqui consideramos 09–18 UTC.
    Se quiser 09–18 America/Sao_Paulo, eu ajusto com timezone depois.
    """
    if not start or not end or end <= start:
        return 0

    work_start_h = 9
    work_end_h = 18

    cur = start
    total = 0

    while cur < end:
        # fim de semana
        if cur.weekday() >= 5:
            cur = datetime(cur.year, cur.month, cur.day, 0, 0, tzinfo=cur.tzinfo) + timedelta(days=1)
            continue

        day_start = datetime(cur.year, cur.month, cur.day, work_start_h, 0, tzinfo=cur.tzinfo)
        day_end = datetime(cur.year, cur.month, cur.day, work_end_h, 0, tzinfo=cur.tzinfo)

        window_start = max(cur, day_start)
        window_end = min(end, day_end)

        if window_end > window_start:
            total += int((window_end - window_start).total_seconds())

        cur = datetime(cur.year, cur.month, cur.day, 0, 0, tzinfo=cur.tzinfo) + timedelta(days=1)

    return total

def sec_to_hours(sec: int) -> float:
    return round(sec / 3600, 2)

def sec_to_business_days(sec: int) -> float:
    # 9h úteis = 1 dia útil
    return round((sec / 3600) / 9, 2)

def sla_por_etapa(contrato_id: int) -> dict:
    """
    Retorna {status: segundos_uteis} para um contrato, até FINALIZADO.
    Usa status_log (entrada em cada etapa).
    """
    logs = obter_status_logs(contrato_id)  # (de_status, para_status, alterado_em)
    timeline = []
    for _de, para, ts in logs:
        if para and ts:
            timeline.append((para, parse_iso(ts)))

    if not timeline:
        return {}

    by_stage = {}
    for i, (status_i, t_i) in enumerate(timeline):
        if status_i == "FINALIZADO":
            break
        if i + 1 >= len(timeline):
            break
        status_next, t_next = timeline[i + 1]
        # Se o próximo já é FINALIZADO, conta tempo até ele e para
        sec = business_seconds(t_i, t_next)
        by_stage[status_i] = by_stage.get(status_i, 0) + sec
        if status_next == "FINALIZADO":
            break

    return by_stage

def sla_medias_finalizados():
    """
    Retorna médias (dias úteis) para:
      - Total (criado_em -> finalizado_em)
      - Por etapa: Jurídico, Demandante, Fornecedor (e fila se quiser)
    Considera apenas contratos FINALIZADOS.
    """
    finalizados = listar_finalizados()  # (id, criado_em, finalizado_em)
    if not finalizados:
        return None

    soma_total = 0
    soma_etapas = {s: 0 for s in STATUS_ORDEM}
    n = 0

    for cid, criado_em, finalizado_em in finalizados:
        try:
            ini = parse_iso(criado_em)
            fim = parse_iso(finalizado_em)
        except Exception:
            continue

        total_sec = business_seconds(ini, fim)
        soma_total += total_sec

        etapas = sla_por_etapa(cid)
        for etapa, sec in etapas.items():
            if etapa in soma_etapas:
                soma_etapas[etapa] += sec

        n += 1

    if n == 0:
        return None

    medias = {
        "N": n,
        "TOTAL_DIAS_UTEIS": sec_to_business_days(int(soma_total / n)),
        "POR_ETAPA_DIAS_UTEIS": {
            k: sec_to_business_days(int(v / n))
            for k, v in soma_etapas.items()
            if k != "FINALIZADO"
        },
    }
    return medias


# -----------------------------
# Init
# -----------------------------
criar_tabelas()
admin_ok = garantir_admin_padrao()

if "logado" not in st.session_state:
    st.session_state.logado = False
if "perfil" not in st.session_state:
    st.session_state.perfil = None
if "username" not in st.session_state:
    st.session_state.username = None
if "view" not in st.session_state:
    st.session_state.view = "RESUMO"  # RESUMO | LISTA | FORNECEDORES
if "filtro_status" not in st.session_state:
    st.session_state.filtro_status = "FILA_INICIO"


# -----------------------------
# Login
# -----------------------------
if not st.session_state.logado:
    st.title("🔐 Login – Gestão de Contratos")

    if not admin_ok:
        st.error(
            "Admin não configurado (Secrets ausentes).\n\n"
            "No Streamlit Cloud: Manage app → Settings → Secrets e adicione:\n"
            'ADMIN_USERNAME = "jean.silva"\n'
            'ADMIN_PASSWORD = "Wiz@2019"\n'
        )
        st.stop()

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        perfil = autenticar(usuario, senha)
        if perfil:
            st.session_state.logado = True
            st.session_state.perfil = perfil
            st.session_state.username = usuario
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

    st.stop()


perfil = st.session_state.perfil
username = st.session_state.username


# -----------------------------
# Sidebar
# -----------------------------
st.sidebar.success(f"Logado: {username} ({perfil})")

if st.sidebar.button("📊 Resumo"):
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
    st.session_state.username = None
    st.session_state.view = "RESUMO"
    st.session_state.filtro_status = "FILA_INICIO"
    st.rerun()


# -----------------------------
# Permissões
# -----------------------------
def pode_criar_contrato():
    return perfil in ["ADMIN", "DEMANDANTE"]

def pode_mover_status():
    # você pediu mover manualmente
    return perfil == "ADMIN"

def pode_excluir():
    return perfil == "ADMIN"


# -----------------------------
# UI helpers
# -----------------------------
def download_docx(contrato_id: int, arquivo: str):
    if arquivo and os.path.exists(arquivo):
        with open(arquivo, "rb") as f:
            st.download_button(
                "⬇️ Baixar contrato (.docx)",
                f.read(),
                file_name=os.path.basename(arquivo),
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"dl_{contrato_id}",
            )
    else:
        st.caption("Arquivo não encontrado (pode ter sido removido no deploy).")

def mover_status_ui(contrato_id: int, atual: str):
    if not pode_mover_status():
        return
    novo = st.selectbox(
        "Mover para",
        STATUS_ORDEM,
        index=STATUS_ORDEM.index(atual),
        format_func=lambda s: STATUS_LABEL[s],
        key=f"mv_{contrato_id}",
    )
    if novo != atual:
        atualizar_status(contrato_id, novo, username)
        st.rerun()

def excluir_contrato_ui(contrato_id: int, numero: str, arquivo: str):
    if not pode_excluir():
        return
    with st.expander("🗑️ Excluir contrato (com justificativa)", expanded=False):
        st.warning("A exclusão remove o contrato das listas, mas mantém auditoria no banco.")
        justificativa = st.text_area("Justificativa (mínimo 15 caracteres)", key=f"just_{contrato_id}")
        ok = (justificativa or "").strip()
        if st.button("Excluir", key=f"exc_{contrato_id}", disabled=len(ok) < 15):
            # tenta remover arquivo gerado (se existir)
            if arquivo and os.path.exists(arquivo):
                try:
                    os.remove(arquivo)
                except Exception:
                    pass
            afetadas = excluir_contrato(contrato_id, ok, username)
            if afetadas == 1:
                st.success("Contrato excluído.")
                st.rerun()
            else:
                st.error("Não foi possível excluir (ID não encontrado).")


# -----------------------------
# Página
# -----------------------------
st.title("📄 Gestão de Contratos")


# -----------------------------
# Gerar contrato (NDA / API) + número manual obrigatório
# -----------------------------
if pode_criar_contrato():
    st.subheader("➕ Gerar contrato (entra na Fila de Início)")

    c1, c2 = st.columns([1.1, 1])
    with c1:
        tipo_modelo = st.selectbox("Tipo de contrato", list(MODELOS.keys()))
    with c2:
        numero_manual = st.text_input("Número do contrato (obrigatório)", placeholder="Ex: CT-2026-001")

    cnpj = st.text_input("CNPJ do fornecedor (BrasilAPI)")

    if st.button("Gerar contrato"):
        try:
            if not numero_manual.strip():
                st.error("O número do contrato é obrigatório.")
                st.stop()

            if not cnpj.strip():
                st.error("Informe o CNPJ.")
                st.stop()

            template_path = MODELOS[tipo_modelo]
            if not os.path.exists(template_path):
                st.error(f"Modelo não encontrado: {template_path}")
                st.stop()

            dados = consultar_cnpj(cnpj)

            fornecedor_cnpj = dados.get("cnpj", "")
            fornecedor_razao = dados.get("razao_social", "")

            contrato_id = inserir_contrato_fornecedor(
                fornecedor_cnpj=fornecedor_cnpj,
                fornecedor_razao=fornecedor_razao,
                status="FILA_INICIO",
                tipo_modelo=tipo_modelo,
            )

            numero_final = gerar_numero_contrato(numero_manual)

            arquivo = gerar_contrato(
                dados_fornecedor=dados,
                numero_contrato=numero_final,
                template_path=template_path,
            )

            atualizar_numero_arquivo(contrato_id, numero_final, arquivo)

            st.success(f"{tipo_modelo} gerado com sucesso: {numero_final}")
            download_docx(contrato_id, arquivo)

        except Exception as e:
            st.error(f"Erro ao gerar contrato: {e}")


# -----------------------------
# Views
# -----------------------------
if st.session_state.view == "RESUMO":
    st.divider()
    st.header("📊 Resumo por etapa")

    counts = contar_por_status()
    cols = st.columns(len(STATUS_ORDEM))

    for i, status in enumerate(STATUS_ORDEM):
        with cols[i]:
            with st.container(border=True):
                st.metric(label=STATUS_LABEL[status], value=counts.get(status, 0))
                if st.button("Acessar contratos", key=f"ac_{status}"):
                    st.session_state.view = "LISTA"
                    st.session_state.filtro_status = status
                    st.rerun()

    st.divider()
    st.header("⏱️ SLA (média em dias úteis) – Finalizados")

    medias = sla_medias_finalizados()
    if not medias:
        st.info("Ainda não há contratos finalizados suficientes para calcular SLA.")
    else:
        with st.container(border=True):
            st.metric("SLA médio TOTAL (dias úteis)", medias["TOTAL_DIAS_UTEIS"])
            st.caption(f"Base: {medias['N']} contrato(s) finalizado(s).")

        # cards por etapa (principais)
        order = ["ANALISE_JURIDICA_LGPD", "ANALISE_DEMANDANTE", "ANALISE_FORNECEDOR"]
        ecols = st.columns(3)
        for idx, etapa in enumerate(order):
            with ecols[idx]:
                with st.container(border=True):
                    st.metric(
                        f"SLA médio {STATUS_LABEL[etapa]} (dias úteis)",
                        medias["POR_ETAPA_DIAS_UTEIS"].get(etapa, 0.0),
                    )


elif st.session_state.view == "LISTA":
    st.divider()
    st.header("📋 Contratos por etapa")

    status_escolhido = st.selectbox(
        "Etapa",
        STATUS_ORDEM,
        index=STATUS_ORDEM.index(st.session_state.filtro_status)
        if st.session_state.filtro_status in STATUS_ORDEM
        else 0,
        format_func=lambda s: STATUS_LABEL[s],
    )
    st.session_state.filtro_status = status_escolhido

    contratos = listar_contratos_por_status(status_escolhido)

    with st.container(border=True):
        st.metric(f"Total em {STATUS_LABEL[status_escolhido]}", len(contratos))
        if st.button("⬅️ Voltar para Resumo"):
            st.session_state.view = "RESUMO"
            st.rerun()

    for row in contratos:
        # banco.py consolidado retorna:
        # id, numero, razao_social, status, arquivo, fornecedor_cnpj, fornecedor_razao, versao, tipo_modelo, criado_em
        contrato_id, numero, _razao, stt, arquivo, forn_cnpj, forn_razao, versao, tipo_modelo, criado_em = row

        with st.container(border=True):
            st.markdown(f"**{numero or '(sem número)'}** · `v{int(versao)}` · **{tipo_modelo or 'modelo?'}**")
            st.write(forn_razao or "(sem razão social)")
            st.caption(f"CNPJ: {forn_cnpj}")

            download_docx(contrato_id, arquivo)
            mover_status_ui(contrato_id, stt)
            excluir_contrato_ui(contrato_id, numero or "(sem número)", arquivo)


elif st.session_state.view == "FORNECEDORES":
    st.divider()
    st.header("🏢 Fornecedores (consolidado)")

    fornecedores = listar_fornecedores_resumo()
    if not fornecedores:
        st.info("Ainda não há fornecedores com contratos.")
    else:
        with st.container(border=True):
            st.metric("Fornecedores com contratos", len(fornecedores))

        for forn_cnpj, forn_razao, total, max_versao in fornecedores:
            titulo = f"{forn_razao} | {forn_cnpj} — {int(total)} contrato(s), até v{int(max_versao)}"
            with st.expander(titulo, expanded=False):
                versoes = listar_versoes_por_fornecedor(forn_cnpj)
                for (cid, num, stt, arq, ver, tipo_modelo) in versoes:
                    with st.container(border=True):
                        st.markdown(
                            f"**{num or '(sem número)'}** · `v{int(ver)}` · **{tipo_modelo or 'modelo?'}** · {STATUS_LABEL.get(stt, stt)}"
                        )
                        download_docx(cid, arq)
                        excluir_contrato_ui(cid, num or "(sem número)", arq)
