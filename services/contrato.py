import os
from docx import Document
from datetime import datetime


def _somente_numeros(texto: str) -> str:
    return "".join([c for c in (texto or "") if c.isdigit()])


def gerar_numero_contrato(id_: int) -> str:
    ano = datetime.now().year
    return f"CT-{ano}-{str(id_).zfill(5)}"


def gerar_contrato(dados: dict, numero: str, fornecedor_cnpj: str, versao: int) -> str:
    """
    Salva em:
      contratos/<CNPJ>/<NUMERO>_v<versao>.docx
    Retorna caminho absoluto.
    """
    fornecedor_cnpj = _somente_numeros(fornecedor_cnpj)
    pasta_fornecedor = os.path.abspath(os.path.join("contratos", fornecedor_cnpj))
    os.makedirs(pasta_fornecedor, exist_ok=True)

    nome_arquivo = f"{numero}_v{int(versao)}.docx"
    caminho_abs = os.path.join(pasta_fornecedor, nome_arquivo)

    doc = Document("templates/contrato_padrao.docx")

    endereco = (
        f"{dados.get('logradouro','')}, "
        f"{dados.get('numero','')} - "
        f"{dados.get('municipio','')}/{dados.get('uf','')}"
    )

    replaces = {
        "{{numero_contrato}}": numero,
        "{{razao_social}}": dados.get("razao_social", ""),
        "{{cnpj}}": dados.get("cnpj", ""),
        "{{endereco}}": endereco.strip()
    }

    for p in doc.paragraphs:
        for k, v in replaces.items():
            if k in p.text:
                p.text = p.text.replace(k, v)

    doc.save(caminho_abs)
    return caminho_abs
