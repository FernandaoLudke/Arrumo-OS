"""Sobe o relatório para o sistema e devolve o link público /d/<token> (igual ao Envio.cs)."""
import json
import urllib.error
import urllib.request

from . import SERVIDOR, VERSAO


def enviar(relatorio):
    corpo = json.dumps(relatorio, ensure_ascii=False).encode()
    req = urllib.request.Request(f"{SERVIDOR}/api/diagnostico", data=corpo, method="POST", headers={
        "Content-Type": "application/json", "User-Agent": f"Arrumo-App-Linux/{VERSAO}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dados = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            dados = json.loads(e.read())
        except ValueError:
            dados = {}
        raise RuntimeError(dados.get("erro") or f"HTTP {e.code}") from None
    if "link" not in dados:
        raise RuntimeError(dados.get("erro") or "Resposta inesperada do servidor")
    return dados["link"]
