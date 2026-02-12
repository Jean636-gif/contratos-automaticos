import requests

def consultar_cnpj(cnpj: str) -> dict:
    cnpj = cnpj.replace(".", "").replace("/", "").replace("-", "")
    url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}"

    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()
