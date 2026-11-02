"""Exporta relatórios locais para uma demonstração, sem API nem credenciais.

Exemplo (origem e destino devem ser pastas separadas):
    python scripts/exportar_demo.py --origem CAMINHO_DO_PROJETO_LOCAL --destino .

Somente manifesto.json, resumo.json, entradas.json e os detalhes dos casos
listados no resumo são lidos. A projeção aceita campos conhecidos; novos campos
da plataforma não são publicados automaticamente. Metadados de conta, corpos
arbitrários de ferramentas e configurações de autenticação são omitidos.

IDs da plataforma viram aliases determinísticos, sem arquivo reversível de
correspondência. Aprovações, consumo, critérios e contagem de chamadas permanecem
iguais aos originais. A conversa pode ter e-mails, URLs, caminhos e IDs redigidos.
O resultado é uma cópia sanitizada para estudo, não o retorno bruto da API.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import re
import shutil
import tempfile


NOME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}\Z")
EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+", re.I)
URL = re.compile(r"https?://[^\s<>\"']+", re.I)
CAMINHO_WINDOWS = re.compile(r"(?<!\w)[A-Za-z]:[\\/][^\s<>\"']+")
CAMINHO_UNIX = re.compile(r"/(?:Users|home|tmp|mnt|private|var|opt)/(?:[^\s<>\"']+)")
TOKEN = re.compile(r"\b(?:sk[-_][A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9_.~+/-]{12,})\b", re.I)
ID_PLATAFORMA = re.compile(r"\b(?:agent|agtbrch|agtvrsn|suite|test|trun|conv|tool|node|workspace|request|req|call|user|folder)_[A-Za-z0-9_-]{4,}\b")
UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
IDS_CASO = ("test_id", "test_run_id", "invocation_id", "agent_id", "branch_id", "version_id")
TEXTOS_CASO = ("caso_id", "nome", "categoria", "finalidade", "assinatura", "resultado", "status_plataforma", "avaliacao_plataforma", "evidencia", "justificativa")
RESULTADOS = ("APROVADO", "REPROVADO", "REVISAR_EVIDENCIA", "INCONCLUSIVO", "CANCELADO")


def alias_id(valor):
    """A mesma identidade mantém o mesmo alias em todos os arquivos/lotes."""
    if not isinstance(valor, str) or not valor:
        return None
    return "demo_" + hashlib.sha256(valor.encode("utf-8")).hexdigest()[:20]


def texto(valor):
    if not isinstance(valor, str):
        return None
    valor = EMAIL.sub("[e-mail removido]", valor)
    valor = URL.sub("[URL removida]", valor)
    valor = CAMINHO_WINDOWS.sub("[caminho local removido]", valor)
    valor = CAMINHO_UNIX.sub("[caminho local removido]", valor)
    valor = TOKEN.sub("[credencial removida]", valor)
    valor = ID_PLATAFORMA.sub(lambda m: alias_id(m.group()), valor)
    return UUID.sub(lambda m: alias_id(m.group()), valor)


def numero(valor):
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) else None


def booleano(valor):
    return valor if isinstance(valor, bool) else None


def strings(valor):
    return [texto(v) for v in valor if isinstance(v, str)] if isinstance(valor, list) else []


def nome_seguro(valor):
    if not isinstance(valor, str) or not NOME.fullmatch(valor):
        raise ValueError("Identificador de pasta inválido.")
    return valor


def ler_json(raiz, caminho, tipo):
    caminho = caminho.resolve()
    if not caminho.is_relative_to(raiz):
        raise ValueError("Uma referência sai da pasta de origem.")
    dado = json.loads(caminho.read_text(encoding="utf-8-sig"))
    if not isinstance(dado, tipo):
        raise ValueError("Formato de relatório incompatível.")
    return dado


def projetar_caso(caso):
    saida = {campo: texto(caso.get(campo)) for campo in TEXTOS_CASO}
    saida.update({campo: alias_id(caso.get(campo)) for campo in IDS_CASO})
    saida.update({campo: booleano(caso.get(campo)) for campo in ("ferramenta_chamada", "mock_confirmado", "ran_against_draft")})
    saida["credits_used"] = numero(caso.get("credits_used"))
    saida["nos_vistos"] = [alias_id(v) for v in caso.get("nos_vistos", []) if isinstance(v, str)]
    return saida


def projetar_resumo(resumo):
    geral = resumo.get("visao_geral", {})
    return {
        "visao_geral": {
            **{k: numero(geral.get(k)) for k in ("planejados", "taxa_aprovacao_decisivos", "cobertura_decisiva", "creditos_informados", "total_sem_creditos")},
            "por_resultado": {k: numero(geral.get("por_resultado", {}).get(k)) for k in RESULTADOS},
            "alertas": strings(geral.get("alertas")),
        },
        "casos": [projetar_caso(c) for c in resumo.get("casos", []) if isinstance(c, dict)],
    }


def projetar_manifesto(manifesto):
    saida = {k: texto(manifesto.get(k)) for k in ("rotulo", "criado_em_utc", "suite_versao", "sdk_versao", "fase", "assinatura_dataset")}
    saida.update({k: alias_id(manifesto.get(k)) for k in ("agent_id", "branch_id", "invocation_id")})
    saida["repeat_count"] = numero(manifesto.get("repeat_count"))
    saida["casos"] = strings(manifesto.get("casos"))
    saida["publicacao"] = "Demonstração sanitizada; identificadores substituídos e metadados privados omitidos."
    return saida


def projetar_catalogo(retorno):
    saida = {k: texto(retorno.get(k)) for k in ("status", "consultado_em", "mensagem", "erro") if k in retorno}
    if "total" in retorno:
        saida["total"] = numero(retorno.get("total"))
    cursos = []
    for curso in retorno.get("cursos", []):
        if not isinstance(curso, dict):
            continue
        item = {k: texto(curso.get(k)) for k in ("curso_id", "nome", "idioma", "nivel", "modalidade", "dias", "horario")}
        item.update({k: numero(curso.get(k)) for k in ("mensalidade_brl", "duracao_meses")})
        item["ativo"] = booleano(curso.get("ativo"))
        cursos.append(item)
    if "cursos" in retorno:
        saida["cursos"] = cursos
    return saida


def projetar_entradas(entradas):
    saida = []
    for entrada in entradas:
        if not isinstance(entrada, dict) or not isinstance(entrada.get("caso"), dict):
            continue
        caso = entrada["caso"]
        item = {k: texto(caso.get(k)) for k in ("id", "nome", "ferramenta", "cenario", "categoria", "finalidade", "fonte", "expectativa_ferramenta")}
        item["max_turnos"] = numero(caso.get("max_turnos"))
        item["criterios_sucesso"] = strings(caso.get("criterios_sucesso"))
        saida.append({"caso": item, "retorno": projetar_catalogo(entrada.get("retorno", {})), "assinatura": texto(entrada.get("assinatura")), "test_id": alias_id(entrada.get("test_id"))})
    return saida


def projetar_chamada(chamada):
    # Parâmetros livres podem conter dados privados/autenticação. Os eventos
    # de execução e a contagem permanecem; o corpo bruto não é publicado.
    return {
        "request_id": alias_id(chamada.get("request_id")),
        "tool_id": alias_id(chamada.get("tool_id")),
        "tool_name": texto(chamada.get("tool_name")),
        "type": texto(chamada.get("type")),
        "tool_has_been_called": booleano(chamada.get("tool_has_been_called")),
    }


def projetar_retorno_tool(retorno):
    return {
        "request_id": alias_id(retorno.get("request_id")),
        "tool_name": texto(retorno.get("tool_name")),
        "type": texto(retorno.get("type")),
        **{k: booleano(retorno.get(k)) for k in ("tool_has_been_called", "is_error", "is_blocked")},
        "tool_latency_secs": numero(retorno.get("tool_latency_secs")),
        "error_type": texto(retorno.get("error_type")),
    }


def projetar_mensagem(mensagem):
    saida = {k: texto(mensagem.get(k)) for k in ("role", "message", "producing_llm")}
    saida["time_in_call_secs"] = numero(mensagem.get("time_in_call_secs"))
    saida["interrupted"] = booleano(mensagem.get("interrupted"))
    saida["tool_calls"] = [projetar_chamada(t) for t in mensagem.get("tool_calls", []) if isinstance(t, dict)]
    saida["tool_results"] = [projetar_retorno_tool(t) for t in mensagem.get("tool_results", []) if isinstance(t, dict)]
    # Somente nomes de modelos geradores: nada de metadados livres da conta.
    uso = mensagem.get("llm_usage") or {}
    nomes = set(uso.get("model_usage", {})) if isinstance(uso.get("model_usage"), dict) else set()
    for detalhe in uso.get("detailed_model_usage", []):
        if isinstance(detalhe, dict) and isinstance(detalhe.get("config"), dict):
            nome = detalhe["config"].get("model")
            if isinstance(nome, str):
                nomes.add(nome)
    saida["llm_usage"] = {"model_usage": {texto(nome): {} for nome in sorted(nomes)}}
    return saida


def projetar_resultado(raw):
    runs = []
    for run in raw.get("test_runs", []):
        if not isinstance(run, dict):
            continue
        saida = {k: alias_id(run.get(k)) for k in ("test_run_id", "test_invocation_id", "test_id", "agent_id", "branch_id", "version_id")}
        saida.update({k: texto(run.get(k)) for k in ("status", "test_name")})
        saida["ran_against_draft"] = booleano(run.get("ran_against_draft"))
        saida["credits_used"] = numero(run.get("credits_used"))
        saida["agent_responses"] = [projetar_mensagem(m) for m in run.get("agent_responses", []) if isinstance(m, dict)]
        condicao = run.get("condition_result") or {}
        rationale = condicao.get("rationale") or {}
        saida["condition_result"] = {"result": texto(condicao.get("result")), "rationale": {"summary": texto(rationale.get("summary")), "messages": strings(rationale.get("messages"))}}
        # Preserva a decomposição numérica relevante, sem tier/metadata/uso livre.
        charging = run.get("charging") or {}
        saida["charging"] = {k: numero(charging.get(k)) for k in ("call_charge", "llm_charge", "platform_charge", "subagent_charge", "voice_surcharge_charge") if k in charging}
        runs.append(saida)
    return {"invocation_id": alias_id(raw.get("invocation_id")), "test_id": alias_id(raw.get("test_id")), "sanitizado": True, "test_runs": runs}


def contagem_chamadas(raw):
    """Regra equivalente ao painel, incluindo confirmação por retorno e dedupe."""
    total = Counter()
    for run in raw.get("test_runs", []):
        mensagens = run.get("agent_responses", [])
        confirmadas = {(t.get("request_id"), t.get("tool_name")) for m in mensagens if m.get("role") == "agent" for t in m.get("tool_results", []) if t.get("tool_has_been_called") is True and t.get("is_blocked") is not True and t.get("request_id")}
        vistas = set()
        for m in mensagens:
            if m.get("role") != "agent":
                continue
            for t in m.get("tool_calls", []):
                nome, request, flag = t.get("tool_name"), t.get("request_id"), t.get("tool_has_been_called")
                chave = (request, nome)
                if not nome or flag is False or (flag is not True and chave not in confirmadas):
                    continue
                if request and chave in vistas:
                    continue
                if request:
                    vistas.add(chave)
                total[nome] += 1
    return total


def escrever_json(caminho, dado):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dado, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def exportar(origem, destino):
    origem, destino = Path(origem).resolve(), Path(destino).resolve()
    if origem == destino or origem.is_relative_to(destino) or destino.is_relative_to(origem):
        raise ValueError("Origem e destino devem ser pastas separadas, sem sobreposição.")
    raiz = (origem / "lotes").resolve()
    if not raiz.is_relative_to(origem) or not raiz.is_dir():
        raise ValueError("Pasta de lotes inválida ou fora do projeto de origem.")
    alvo = destino / "lotes"
    if alvo.exists() or alvo.is_symlink():
        raise ValueError("O destino já contém lotes. Use uma pasta nova para preservar os arquivos existentes.")
    destino.mkdir(parents=True, exist_ok=True)
    temporaria = Path(tempfile.mkdtemp(prefix=".exportacao-demo-", dir=destino))
    total_lotes = total_casos = 0
    try:
        lotes_temp = temporaria / "lotes"
        lotes_temp.mkdir()
        for pasta in sorted(raiz.iterdir()):
            if not pasta.name.startswith("lote_"):
                continue
            nome_seguro(pasta.name)
            if not pasta.resolve().is_relative_to(raiz) or not pasta.is_dir():
                raise ValueError("Uma pasta de lote sai da origem.")
            manifesto = ler_json(raiz, pasta / "manifesto.json", dict)
            resumo = ler_json(raiz, pasta / "resumo.json", dict)
            entradas = ler_json(raiz, pasta / "entradas.json", list)
            novo_resumo = projetar_resumo(resumo)
            nova_pasta = lotes_temp / pasta.name
            escrever_json(nova_pasta / "manifesto.json", projetar_manifesto(manifesto))
            escrever_json(nova_pasta / "resumo.json", novo_resumo)
            escrever_json(nova_pasta / "entradas.json", projetar_entradas(entradas))
            for original, novo in zip(resumo["casos"], novo_resumo["casos"], strict=True):
                caso_id = nome_seguro(original["caso_id"])
                caminho_raw = pasta / "casos" / caso_id / "resultado-completo.json"
                raw = ler_json(raiz, caminho_raw, dict)
                sanitizado = projetar_resultado(raw)
                if contagem_chamadas(raw) != contagem_chamadas(sanitizado):
                    raise ValueError("A sanitização alterou a contagem de ferramentas.")
                caso_destino = nova_pasta / "casos" / caso_id
                escrever_json(caso_destino / "resultado-completo.json", sanitizado)
                escrever_json(caso_destino / "resumo.json", novo)
                conversa = pasta / "casos" / caso_id / "conversa.txt"
                if not conversa.resolve().is_relative_to(raiz):
                    raise ValueError("A transcrição sai da pasta de origem.")
                (caso_destino / "conversa.txt").write_text(texto(conversa.read_text(encoding="utf-8-sig")) or "", encoding="utf-8")
                total_casos += 1
            buffer = io.StringIO(newline="")
            campos = list(novo_resumo["casos"][0]) if novo_resumo["casos"] else ["caso_id", "resultado"]
            writer = csv.DictWriter(buffer, fieldnames=campos)
            writer.writeheader()
            writer.writerows(novo_resumo["casos"])
            # O csv.Writer já define as quebras de linha. Evita duplicar CR
            # ao salvar no Windows, o que criaria linhas vazias no arquivo.
            (nova_pasta / "resumo.csv").write_text(buffer.getvalue(), encoding="utf-8", newline="")
            total_lotes += 1
        if not total_lotes:
            raise ValueError("Nenhum lote completo encontrado.")
        lotes_temp.rename(alvo)
    finally:
        # Só remove a pasta temporária criada neste destino; nunca a origem.
        if temporaria.resolve().is_relative_to(destino):
            shutil.rmtree(temporaria)
    return {"lotes": total_lotes, "casos": total_casos}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", required=True, type=Path, help="Projeto local que contém a pasta lotes; nunca lê .env.")
    parser.add_argument("--destino", required=True, type=Path, help="Cópia publicável, separada da origem e sem pasta lotes existente.")
    args = parser.parse_args()
    try:
        resultado = exportar(args.origem, args.destino)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # Erros de sistema podem conter caminhos: não revelar valores locais.
        parser.exit(1, f"Exportação não concluída ({type(exc).__name__}). Confira origem, destino e formato dos relatórios.\n")
    print(f"Exportação concluída: {resultado['lotes']} lotes, {resultado['casos']} execuções. Nenhuma chamada à API.")


if __name__ == "__main__":
    main()
