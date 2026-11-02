"""Relatórios locais de uma suíte: avaliação da plataforma e evidência do mock.

Este módulo não acessa a rede nem chama um avaliador. Os resultados e as
justificativas do avaliador já vêm na resposta da ElevenLabs.
"""

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


RESULTADOS = ("APROVADO", "REPROVADO", "REVISAR_EVIDENCIA", "INCONCLUSIVO", "CANCELADO")
CAMPOS = (
    "caso_id", "nome", "categoria", "finalidade", "assinatura", "resultado",
    "status_plataforma", "avaliacao_plataforma", "evidencia", "ferramenta_chamada",
    "mock_confirmado", "justificativa", "test_id", "test_run_id", "invocation_id",
    "agent_id", "branch_id", "version_id", "ran_against_draft", "credits_used", "nos_vistos",
)
ID_CASO = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}\Z")
RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {
    prefixo + str(numero) for prefixo in ("COM", "LPT") for numero in range(1, 10)
}


def _salvar_json(caminho, valor):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding="utf-8")


def _lista(valor):
    return valor if isinstance(valor, list) else []


def _metadado(run, dados, campo):
    valor = run.get(campo)
    return dados.get(campo) if valor is None else valor


def _validar_entradas(entradas):
    ids = set()
    for entrada in entradas:
        caso = entrada["caso"]
        identificador = caso["id"]
        if (not isinstance(identificador, str) or not ID_CASO.fullmatch(identificador)
                or identificador.upper() in RESERVADOS_WINDOWS):
            raise ValueError("ID de caso inválido para uma pasta local.")
        if identificador.casefold() in ids:
            raise ValueError("IDs de caso repetidos sobrescreveriam relatórios.")
        ids.add(identificador.casefold())
        if caso["expectativa_ferramenta"] not in ("obrigatoria", "opcional"):
            raise ValueError("Expectativa de ferramenta desconhecida.")
        if not isinstance(caso["mock"]["is_error"], bool):
            raise ValueError("mock.is_error deve ser booleano.")


def _eventos(run, campo):
    return [evento for mensagem in _lista(run.get("agent_responses"))
            if isinstance(mensagem, dict) for evento in _lista(mensagem.get(campo))
            if isinstance(evento, dict)]


def _evidencia(run, entrada):
    caso = entrada["caso"]
    nome = caso["ferramenta"]
    chamadas = [t for t in _eventos(run, "tool_calls")
                if t.get("tool_name") == nome and t.get("tool_has_been_called") is not False]
    retornos = [t for t in _eventos(run, "tool_results") if t.get("tool_name") == nome]
    if any(t.get("is_blocked") is True for t in retornos):
        return bool(chamadas), False, "INSUFICIENTE", "A ferramenta teve um retorno bloqueado; o mock não foi comprovado."
    if not chamadas:
        if caso["expectativa_ferramenta"] == "opcional":
            return False, None, "NA", "A ferramenta era opcional e não foi chamada."
        return False, False, "INSUFICIENTE", "Não houve chamada da ferramenta obrigatória."

    # Conferir a resposta esperada inclusive quando o cenário espera um erro.
    correto = bool(retornos)
    for retorno in retornos:
        try:
            correto = correto and (
                retorno.get("is_error", False) is caso["mock"]["is_error"]
                and json.loads(retorno.get("result_value", "")) == entrada["retorno"]
            )
        except (ValueError, TypeError):
            correto = False

    # Uma resposta correta não encobre outra chamada sem retorno ou mock incorreto.
    ids_chamados = {t["request_id"] for t in chamadas if t.get("request_id")}
    ids_retornados = {t["request_id"] for t in retornos if t.get("request_id")}
    if ids_chamados:
        correto = correto and ids_chamados.issubset(ids_retornados)
    else:
        correto = correto and len(retornos) >= len(chamadas)
    texto = ("Chamada e resposta do mock confirmadas." if correto
             else "A ferramenta foi chamada, mas os retornos não comprovam o mock esperado.")
    return True, correto, "CONFIRMADA" if correto else "INSUFICIENTE", texto


def _justificativa(run):
    condicao = run.get("condition_result") or {}
    razao = condicao.get("rationale") or {}
    if isinstance(razao, str):
        return razao
    partes = [razao.get("summary"), *_lista(razao.get("messages"))]
    return " | ".join(p for p in partes if isinstance(p, str) and p.strip())


def _nos_vistos(run):
    nos = []
    if run.get("workflow_node_id"):
        nos.append(str(run["workflow_node_id"]))
    for mensagem in _lista(run.get("agent_responses")):
        if not isinstance(mensagem, dict):
            continue
        metadata = mensagem.get("agent_metadata") or {}
        if isinstance(metadata, dict) and metadata.get("workflow_node_id"):
            nos.append(str(metadata["workflow_node_id"]))
    return list(dict.fromkeys(nos))  # Observação; nunca aprova ou reprova um caso.


def _linha(entrada, runs, dados, test_id_repetido=False):
    caso = entrada["caso"]
    linha = {campo: None for campo in CAMPOS}
    linha.update({
        "caso_id": caso["id"], "nome": caso.get("nome"),
        "categoria": caso.get("categoria"), "finalidade": caso.get("finalidade"),
        "assinatura": entrada.get("assinatura"), "test_id": entrada.get("test_id"),
        "invocation_id": dados.get("id"), "resultado": "INCONCLUSIVO",
        "evidencia": "INCONCLUSIVA", "ferramenta_chamada": False, "nos_vistos": [],
        "agent_id": dados.get("agent_id"), "branch_id": dados.get("branch_id"),
        "version_id": dados.get("version_id"), "ran_against_draft": dados.get("ran_against_draft"),
    })
    if test_id_repetido or len(runs) != 1:
        if not test_id_repetido and not runs and dados.get("cancelled") is True:
            linha["resultado"] = "CANCELADO"
            linha["justificativa"] = "O lote foi cancelado e nenhuma execução retornou para este teste."
            return linha
        linha["justificativa"] = (
            "O mesmo test_id foi associado a mais de um caso planejado." if test_id_repetido
            else "Nenhuma execução retornada para este teste." if not runs
            else "Mais de uma execução retornada para este teste; associação ambígua."
        )
        return linha

    run = runs[0]
    condicao = run.get("condition_result") or {}
    status, grade = run.get("status"), condicao.get("result")
    chamada, mock, evidencia, detalhe = _evidencia(run, entrada)
    if status == "cancelled":
        resultado = "CANCELADO"
    elif status == "passed" and grade == "success":
        resultado = "APROVADO" if evidencia in ("CONFIRMADA", "NA") else "REVISAR_EVIDENCIA"
    elif status == "failed" and grade == "failure":
        resultado = "REPROVADO"
    else:
        resultado = "INCONCLUSIVO"
    linha.update({
        "resultado": resultado, "status_plataforma": status,
        "avaliacao_plataforma": grade, "evidencia": evidencia,
        "ferramenta_chamada": chamada, "mock_confirmado": mock,
        "justificativa": " | ".join(filter(None, [_justificativa(run), detalhe])),
        "test_run_id": run.get("test_run_id"), "credits_used": run.get("credits_used"),
        "nos_vistos": _nos_vistos(run),
    })
    for campo in ("agent_id", "branch_id", "version_id", "ran_against_draft"):
        linha[campo] = _metadado(run, dados, campo)
    return linha


def _alertas(dados, runs, esperados, contagens):
    alertas = []
    inesperados = sorted({str(r.get("test_id", "<ausente>")) for r in runs
                          if r.get("test_id") not in esperados})
    if inesperados:
        alertas.append("IDs de teste inesperados no retorno: " + ", ".join(inesperados))
    repetidos = sorted(str(t) for t, n in contagens.items() if n > 1)
    if repetidos:
        alertas.append("IDs de teste repetidos nas entradas: " + ", ".join(repetidos))
    versoes = {str(dados["version_id"])} if dados.get("version_id") else set()
    versoes.update(str(r["version_id"]) for r in runs if r.get("version_id"))
    if len(versoes) > 1:
        alertas.append("Mais de uma versão informada neste lote: " + ", ".join(sorted(versoes)))
    rascunhos = [_metadado(r, dados, "ran_against_draft") for r in runs]
    if True in rascunhos:
        alertas.append("Há execução com ran_against_draft=true; confira o alvo avaliado.")
    if True in rascunhos and False in rascunhos:
        alertas.append("O lote mistura execuções com e sem rascunho.")
    if runs and any(not _metadado(r, dados, "version_id") for r in runs):
        alertas.append("A versão do agente não foi informada em todas as execuções.")
    if runs and any(not isinstance(v, bool) for v in rascunhos):
        alertas.append("O indicador de rascunho não foi informado em todas as execuções.")
    return alertas


def _conversa(entrada, runs):
    linhas = ["Ponte Idiomas — avaliação por texto", "Caso: " + entrada["caso"]["id"], ""]
    if not runs:
        linhas.append("Nenhuma conversa retornada para este caso.")
    for run in runs:
        linhas.append("Execução: " + str(run.get("test_run_id", "não informada")))
        for mensagem in _lista(run.get("agent_responses")):
            if not isinstance(mensagem, dict):
                continue
            if mensagem.get("message"):
                linhas.append(str(mensagem.get("role", "?")) + ": " + str(mensagem["message"]))
            for campo, rotulo in (("tool_calls", "chamada"), ("tool_results", "retorno")):
                for evento in _lista(mensagem.get(campo)):
                    if isinstance(evento, dict):
                        linhas.append("  [" + rotulo + ": " + str(evento.get("tool_name", "?")) + "]")
    return "\n".join(linhas)


def gerar_relatorios(pasta: Path, dados: dict, entradas: list[dict]) -> dict:
    """Gera arquivos locais; cada linha planejada é associada pelo test_id."""
    _validar_entradas(entradas)  # Validar caminhos antes de criar qualquer arquivo.
    pasta = Path(pasta)
    runs = [r for r in _lista(dados.get("test_runs")) if isinstance(r, dict)]
    indice = defaultdict(list)
    for run in runs:
        indice[run.get("test_id")].append(run)
    contagens = Counter(e.get("test_id") for e in entradas)
    linhas = [_linha(e, indice[e.get("test_id")], dados, contagens[e.get("test_id")] > 1)
              for e in entradas]
    contagem_resultados = Counter(linha["resultado"] for linha in linhas)
    decisivos = contagem_resultados["APROVADO"] + contagem_resultados["REPROVADO"]
    creditos, sem_creditos = 0, 0
    for run in runs:
        valor = run.get("credits_used")
        if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor) and valor >= 0:
            creditos += valor
        else:
            sem_creditos += 1
    sem_creditos += sum(not indice[e.get("test_id")] for e in entradas)
    resumo = {
        "visao_geral": {
            "planejados": len(entradas),
            "por_resultado": {resultado: contagem_resultados[resultado] for resultado in RESULTADOS},
            "taxa_aprovacao_decisivos": contagem_resultados["APROVADO"] / decisivos if decisivos else None,
            "cobertura_decisiva": decisivos / len(entradas) if entradas else None,
            "creditos_informados": creditos,
            "total_sem_creditos": sem_creditos,
            "alertas": _alertas(dados, runs, set(contagens), contagens),
        },
        "casos": linhas,
    }
    _salvar_json(pasta / "resultado-completo.json", dados)
    _salvar_json(pasta / "resumo.json", resumo)
    with (pasta / "resumo.csv").open("w", encoding="utf-8-sig", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=CAMPOS, delimiter=";")
        escritor.writeheader()
        for linha in linhas:
            escritor.writerow({**linha, "nos_vistos": json.dumps(linha["nos_vistos"], ensure_ascii=False)})
    for entrada, linha in zip(entradas, linhas):
        destino = pasta / "casos" / entrada["caso"]["id"]
        encontrados = indice[entrada.get("test_id")]
        _salvar_json(destino / "resumo.json", linha)
        _salvar_json(destino / "resultado-completo.json", {
            "invocation_id": dados.get("id"), "test_id": entrada.get("test_id"), "test_runs": encontrados,
        })
        (destino / "conversa.txt").write_text(_conversa(entrada, encontrados), encoding="utf-8")
    return resumo
