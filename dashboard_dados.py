"""Leitura dos relatórios locais para o dashboard, sem rede ou alterações.

Interface pública:
    descobrir_lotes(base) -> (lotes, avisos)
        ``base`` é a pasta do projeto ou a própria pasta ``lotes``. Cada lote
        contém os metadados do manifesto, ``visao_geral`` e cópias das linhas
        de ``resumo.json``. Ausências numéricas permanecem ``None``: ausência
        de medição não vira zero ou aprovação. A descoberta não abre os raws.

    ler_detalhe(base, lote_id, caso_id) -> dict
        Lê somente um caso permitido pelo resumo, o snapshot das entradas e
        seu resultado completo. ``mensagens`` preserva eventos de todos os
        papéis. ``modelos`` vem apenas de eventos do agente, nunca do consumo
        agregado de avaliadores ou do usuário simulado. A contagem de chamadas
        usa os eventos top-level efetivamente executados, sem somar novamente
        ferramentas aninhadas nos retornos do workflow.

Os arquivos originais e as aprovações automáticas são preservados. Não há
campo de revisão humana inventado. Erros de leitura ficam em ``avisos``; no
detalhe, ``aviso`` é um alias da mesma lista para consumidores existentes.
"""

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re


RESULTADOS = ("APROVADO", "REPROVADO", "REVISAR_EVIDENCIA", "INCONCLUSIVO", "CANCELADO")
NOME_LOCAL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}\Z")
RESERVADOS_WINDOWS = {"CON", "PRN", "AUX", "NUL"} | {
    prefixo + str(numero) for prefixo in ("COM", "LPT") for numero in range(1, 10)
}
CAMPOS_CASO = (
    "caso_id", "nome", "categoria", "finalidade", "assinatura", "resultado",
    "status_plataforma", "avaliacao_plataforma", "evidencia", "ferramenta_chamada",
    "mock_confirmado", "justificativa", "test_id", "test_run_id", "invocation_id",
    "agent_id", "branch_id", "version_id", "ran_against_draft", "credits_used", "nos_vistos",
)


def _nome_seguro(valor):
    return (isinstance(valor, str) and bool(NOME_LOCAL.fullmatch(valor))
            and valor.upper() not in RESERVADOS_WINDOWS)


def _dentro(raiz, caminho):
    """Resolver antes de ler também bloqueia symlinks que saem da raiz."""
    resolvido = caminho.resolve()
    if not resolvido.is_relative_to(raiz):
        raise ValueError("O caminho aponta para fora da pasta de lotes.")
    return resolvido


def _raiz(base):
    projeto = Path(base).resolve()
    if projeto.name == "lotes":
        return projeto
    # Não seguir uma pasta lotes ligada a uma localização fora do projeto.
    return _dentro(projeto, projeto / "lotes")


def _json(raiz, caminho, tipo, avisos, contexto):
    try:
        seguro = _dentro(raiz, caminho)
        valor = json.loads(seguro.read_text(encoding="utf-8-sig"))
        if not isinstance(valor, tipo):
            avisos.append(f"{contexto}: formato inesperado em {caminho.name}.")
            return None
        return valor
    except FileNotFoundError:
        avisos.append(f"{contexto}: arquivo {caminho.name} ausente.")
    except (OSError, UnicodeError, ValueError, RuntimeError):
        avisos.append(f"{contexto}: não foi possível ler {caminho.name} com segurança; "
                      "o arquivo pode estar incompleto, inválido ou fora da pasta permitida.")
    return None


def _texto(raiz, caminho, avisos, contexto):
    try:
        return _dentro(raiz, caminho).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        avisos.append(f"{contexto}: arquivo {caminho.name} ausente.")
    except (OSError, UnicodeError, ValueError, RuntimeError):
        avisos.append(f"{contexto}: não foi possível ler {caminho.name} com segurança.")
    return ""


def _numero(valor, inteiro=False, taxa=False):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    try:
        if not math.isfinite(valor) or valor < 0:
            return None
    except (ValueError, OverflowError):
        return None
    if inteiro and (not isinstance(valor, int)):
        return None
    if taxa and valor > 1:
        return None
    return valor


def _string(valor):
    return valor if isinstance(valor, str) and valor.strip() else None


def _lista_strings(valor):
    return [item for item in valor if isinstance(item, str)] if isinstance(valor, list) else []


def _lista_dicts(valor):
    return [item for item in valor if isinstance(item, dict)] if isinstance(valor, list) else []


def _visao(resumo, avisos, contexto):
    original = resumo.get("visao_geral")
    if not isinstance(original, dict):
        avisos.append(f"{contexto}: visão geral ausente ou inválida; indicadores desconhecidos.")
        original = {}
    visao = deepcopy(original)
    contagens = original.get("por_resultado")
    contagens = contagens if isinstance(contagens, dict) else {}
    visao["por_resultado"] = {
        chave: _numero(contagens.get(chave), inteiro=True) for chave in RESULTADOS
    }
    for campo in ("planejados", "total_sem_creditos"):
        visao[campo] = _numero(original.get(campo), inteiro=True)
    for campo in ("taxa_aprovacao_decisivos", "cobertura_decisiva"):
        visao[campo] = _numero(original.get(campo), taxa=True)
    visao["creditos_informados"] = _numero(original.get("creditos_informados"))
    visao["alertas"] = _lista_strings(original.get("alertas"))
    if any(visao.get(campo) is None for campo in (
            "planejados", "taxa_aprovacao_decisivos", "cobertura_decisiva",
            "creditos_informados", "total_sem_creditos")):
        avisos.append(f"{contexto}: há indicadores ausentes ou não medidos; exibidos como desconhecidos.")
    return visao


def _casos(resumo, avisos, contexto):
    linhas = resumo.get("casos")
    if not isinstance(linhas, list):
        avisos.append(f"{contexto}: lista de casos ausente ou inválida.")
        return []
    contagens = Counter(linha["caso_id"].casefold() for linha in linhas
                        if isinstance(linha, dict) and _nome_seguro(linha.get("caso_id")))
    casos = []
    repetidos = set()
    for linha in linhas:
        if not isinstance(linha, dict) or not _nome_seguro(linha.get("caso_id")):
            avisos.append(f"{contexto}: uma linha de caso inválida foi ignorada.")
            continue
        identificador = linha["caso_id"]
        if contagens[identificador.casefold()] != 1:
            if identificador.casefold() not in repetidos:
                avisos.append(f"{contexto}: caso {identificador} repetido; associação ambígua, omitido.")
                repetidos.add(identificador.casefold())
            continue
        caso = {campo: None for campo in CAMPOS_CASO}
        caso.update(deepcopy(linha))
        for campo in CAMPOS_CASO:
            if campo not in ("ferramenta_chamada", "mock_confirmado", "ran_against_draft", "credits_used", "nos_vistos"):
                caso[campo] = _string(linha.get(campo))
        caso["credits_used"] = _numero(linha.get("credits_used"))
        for campo in ("ferramenta_chamada", "mock_confirmado", "ran_against_draft"):
            caso[campo] = linha.get(campo) if isinstance(linha.get(campo), bool) else None
        caso["nos_vistos"] = _lista_strings(linha.get("nos_vistos"))
        if caso["resultado"] not in RESULTADOS:
            caso["resultado"] = None
            avisos.append(f"{contexto}: resultado de {identificador} ausente ou desconhecido.")
        casos.append(caso)
    return casos


def _ordem(lote):
    data = lote.get("criado_em_utc")
    try:
        instante = datetime.fromisoformat(data.replace("Z", "+00:00"))
        if instante.tzinfo is None:
            instante = instante.replace(tzinfo=timezone.utc)
        return instante.timestamp(), lote["id_lote"]
    except (AttributeError, TypeError, ValueError, OSError, OverflowError):
        pass
    try:
        instante = datetime.strptime(lote["id_lote"][5:21], "%Y%m%dT%H%M%SZ")
        return instante.replace(tzinfo=timezone.utc).timestamp(), lote["id_lote"]
    except (TypeError, ValueError, OSError, OverflowError):
        return float("-inf"), lote["id_lote"]


def descobrir_lotes(base: Path) -> tuple[list[dict], list[str]]:
    """Descobrir lotes mais novos primeiro, lendo só manifesto e resumo.

    ``rascunho=True`` significa que pelo menos um caso usou rascunho;
    ``False`` exige que todos os casos conhecidos sejam explicitamente False;
    ``None`` significa que não há comprovação suficiente. Misturas são avisadas.
    """
    avisos, lotes = [], []
    try:
        raiz = _raiz(base)
        pastas = list(raiz.iterdir())
    except (OSError, ValueError, RuntimeError):
        return [], ["A pasta de lotes não está disponível ou não é segura para leitura."]
    for pasta in pastas:
        if not pasta.name.startswith("lote_"):
            continue
        contexto = pasta.name
        try:
            if not _nome_seguro(pasta.name):
                raise ValueError("Nome de lote inválido.")
            seguro = _dentro(raiz, pasta)
            if not seguro.is_dir():
                continue
        except (OSError, ValueError, RuntimeError):
            avisos.append(f"{contexto}: pasta insegura ou inacessível; lote ignorado.")
            continue
        manifesto = _json(raiz, pasta / "manifesto.json", dict, avisos, contexto) or {}
        resumo = _json(raiz, pasta / "resumo.json", dict, avisos, contexto) or {}
        casos = _casos(resumo, avisos, contexto)
        rotulo = _string(manifesto.get("rotulo"))
        data = _string(manifesto.get("criado_em_utc"))
        for caso in casos:
            caso.update(lote_id=pasta.name, rotulo_lote=rotulo, data_lote=data)
        estados = [c.get("ran_against_draft") for c in casos]
        rascunho = True if True in estados else (
            False if estados and all(estado is False for estado in estados) else None)
        if True in estados and False in estados:
            avisos.append(f"{contexto}: há resultados de rascunho e publicados no mesmo lote.")
        lote = {
            "id_lote": pasta.name, "lote_id": pasta.name, "pasta": str(seguro),
            "rotulo": rotulo, "criado_em_utc": data,
            "suite_versao": _string(manifesto.get("suite_versao")),
            "assinatura_dataset": _string(manifesto.get("assinatura_dataset")),
            "invocation_id": _string(manifesto.get("invocation_id")),
            "fase": _string(manifesto.get("fase")),
            "agent_id": _string(manifesto.get("agent_id")),
            "branch_id": _string(manifesto.get("branch_id")),
            "visao_geral": _visao(resumo, avisos, contexto), "casos": casos,
            "versoes": sorted({c["version_id"] for c in casos if _string(c.get("version_id"))}),
            "rascunho": rascunho,
        }
        lotes.append(lote)
    lotes.sort(key=_ordem, reverse=True)
    return lotes, avisos


def _run(raw, caso, avisos):
    runs = raw.get("test_runs")
    if not isinstance(runs, list):
        avisos.append("Resultado completo sem lista de execuções válida.")
        return None
    runs = [run for run in runs if isinstance(run, dict)]
    run_id = caso.get("test_run_id")
    if run_id:
        candidatos = [run for run in runs if run.get("test_run_id") == run_id]
    elif caso.get("test_id"):
        candidatos = [run for run in runs if run.get("test_id") == caso["test_id"]]
    else:
        candidatos = runs
    if len(candidatos) != 1:
        avisos.append("Não foi possível associar uma única execução ao caso; mensagens omitidas.")
        return None
    return candidatos[0]


def _modelos(mensagens):
    modelos = set()
    for mensagem in mensagens:
        if mensagem.get("role") != "agent":
            continue
        if _string(mensagem.get("producing_llm")):
            modelos.add(mensagem["producing_llm"])
        uso = mensagem.get("llm_usage")
        if not isinstance(uso, dict):
            continue
        por_modelo = uso.get("model_usage")
        if isinstance(por_modelo, dict):
            modelos.update(nome for nome in por_modelo if _string(nome))
        detalhes = uso.get("detailed_model_usage")
        if isinstance(detalhes, list):
            for detalhe in detalhes:
                config = detalhe.get("config") if isinstance(detalhe, dict) else None
                if isinstance(config, dict) and _string(config.get("model")):
                    modelos.add(config["model"])
    return sorted(modelos)


def _contar_ferramentas(mensagens, avisos):
    # Retornos servem só para confirmar uma chamada antiga sem flag explícita;
    # eles não são contados novamente e seus nested_tools não são percorridos.
    confirmados = {
        (t.get("request_id"), t.get("tool_name"))
        for mensagem in mensagens if mensagem.get("role") == "agent"
        for t in _lista_dicts(mensagem.get("tool_results"))
        if t.get("tool_has_been_called") is True
        and t.get("is_blocked") is not True and _string(t.get("request_id"))
    }
    contagem, vistos, sem_comprovacao = Counter(), set(), 0
    for mensagem in mensagens:
        if mensagem.get("role") != "agent":
            continue
        chamadas = mensagem.get("tool_calls")
        if not isinstance(chamadas, list):
            continue
        for chamada in chamadas:
            if not isinstance(chamada, dict) or not _string(chamada.get("tool_name")):
                continue
            nome = chamada["tool_name"]
            request_id = _string(chamada.get("request_id"))
            flag = chamada.get("tool_has_been_called")
            if flag is False:
                continue
            if flag is not True and (request_id, nome) not in confirmados:
                sem_comprovacao += 1
                continue
            chave = (request_id, nome)
            if request_id and chave in vistos:
                continue
            if request_id:
                vistos.add(chave)
            contagem[nome] += 1
    if sem_comprovacao:
        avisos.append(f"{sem_comprovacao} chamada(s) sem comprovação de execução foram omitidas da contagem.")
    return dict(sorted(contagem.items()))


def ler_detalhe(base: Path, lote_id: str, caso_id: str) -> dict:
    """Abrir um caso salvo, sem relançar testes e sem criar revisão humana."""
    avisos = []
    detalhe = {
        "caso": None, "criterios": [], "roteiro": None, "mensagens": [],
        "conversa": "", "resultado_completo": {}, "modelos": [],
        "contagem_ferramentas": {}, "avisos": avisos, "aviso": avisos,
    }
    if (not _nome_seguro(lote_id) or not lote_id.startswith("lote_")
            or not _nome_seguro(caso_id)):
        avisos.append("Identificador de lote ou caso inválido; nenhum detalhe foi aberto.")
        return detalhe
    try:
        raiz = _raiz(base)
        pasta = _dentro(raiz, raiz / lote_id)
        pasta_caso = _dentro(raiz, pasta / "casos" / caso_id)
    except (OSError, ValueError, RuntimeError):
        avisos.append("O caminho do detalhe está fora da pasta permitida ou é inválido.")
        return detalhe
    resumo = _json(raiz, pasta / "resumo.json", dict, avisos, lote_id) or {}
    casos = [c for c in _casos(resumo, avisos, lote_id) if c["caso_id"] == caso_id]
    if len(casos) != 1:
        avisos.append("O caso não está associado de forma única ao resumo deste lote.")
        return detalhe
    detalhe["caso"] = casos[0]
    entradas = _json(raiz, pasta / "entradas.json", list, avisos, lote_id)
    if entradas is not None:
        correspondentes = [e["caso"] for e in entradas if isinstance(e, dict)
                           and isinstance(e.get("caso"), dict) and e["caso"].get("id") == caso_id]
        if len(correspondentes) == 1:
            entrada = correspondentes[0]
            detalhe["criterios"] = _lista_strings(entrada.get("criterios_sucesso"))
            detalhe["roteiro"] = _string(entrada.get("cenario"))
        else:
            avisos.append("O snapshot não contém uma definição única para este caso.")
    detalhe["conversa"] = _texto(raiz, pasta_caso / "conversa.txt", avisos, caso_id)
    raw = _json(raiz, pasta_caso / "resultado-completo.json", dict, avisos, caso_id)
    if raw is not None:
        detalhe["resultado_completo"] = raw
        run = _run(raw, detalhe["caso"], avisos)
        if run is not None:
            mensagens = run.get("agent_responses")
            if isinstance(mensagens, list):
                detalhe["mensagens"] = [m for m in mensagens if isinstance(m, dict)]
                if len(detalhe["mensagens"]) != len(mensagens):
                    avisos.append("Eventos de conversa inválidos foram ignorados.")
            else:
                avisos.append("A execução não contém uma lista válida de mensagens.")
    detalhe["modelos"] = _modelos(detalhe["mensagens"])
    detalhe["contagem_ferramentas"] = _contar_ferramentas(detalhe["mensagens"], avisos)
    return detalhe
