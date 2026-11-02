"""Suíte de avaliações por texto. Prévia por padrão; execução só com --executar.

Mantém o exemplo individual avaliar.py e seus relatórios intactos. O SDK cadastra
as definições e envia os casos selecionados em UMA solicitação run_tests.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.conversational_ai.tests.types.tests_create_request_body import TestsCreateRequestBody_Simulation

from avaliar import OPCOES, TERMINAIS, aguardar, ler_json, para_dict, salvar_json
from relatorios_lote import gerar_relatorios


BASE = Path(__file__).resolve().parent
REJEICOES = {400, 401, 402, 403, 404, 422, 429}
REFERENCIA_CREDITOS = 251  # Consumo informado pela execução individual de 20/10/2026.


def assinatura(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def montar_teste(caso, retorno, tool_id):
    """Aceita um objeto JSON de qualquer negócio como resposta controlada da tool."""
    if not isinstance(retorno, dict):
        raise ValueError(f"{caso['id']}: o mock precisa ser um objeto JSON.")
    # Esta verificação pertence ao catálogo de exemplo, não ao contrato do runner.
    if retorno.get("status") == "ok" and "cursos" in retorno:
        if not isinstance(retorno["cursos"], list):
            raise ValueError(f"{caso['id']}: cursos precisa ser uma lista.")
        if retorno.get("total") != len(retorno["cursos"]):
            raise ValueError(f"{caso['id']}: total não corresponde à lista de cursos.")
    return {
        "type": "simulation",
        "name": caso["nome"],
        "simulation_scenario": caso["cenario"],
        "simulation_max_turns": caso["max_turnos"],
        "success_conditions": caso["criterios_sucesso"],
        "tool_mock_config": {
            "mocking_strategy": "selected", "fallback_strategy": "raise_error",
            "mocked_tool_ids": [tool_id],
        },
        "tool_mock_overrides": {tool_id: [{
            "parameter_conditions": [],
            "mock_result": json.dumps(retorno, ensure_ascii=False),
            "is_error": caso["mock"]["is_error"],
        }]},
    }


def carregar_entradas(base, tool_id, casos_selecionados=None, limite=None, suite_path=None):
    base = Path(base)
    raiz_cenarios = (base / "cenarios").resolve()
    caminho_suite = Path(suite_path) if suite_path is not None else Path("cenarios/suite-20.json")
    caminho_suite = (base / caminho_suite).resolve()
    if not caminho_suite.is_relative_to(raiz_cenarios) or caminho_suite.suffix.lower() != ".json":
        raise ValueError("A suíte deve ser um arquivo .json dentro de cenarios.")
    suite = ler_json(caminho_suite)
    casos = suite.get("casos") if isinstance(suite, dict) else None
    if not isinstance(casos, list) or not casos:
        raise ValueError("A suíte precisa ter uma lista não vazia de casos.")
    for caso in casos:
        if (not isinstance(caso, dict) or not isinstance(caso.get("id"), str)
                or not re.fullmatch(r"(?:0[1-9]|[1-9][0-9])-[a-z0-9-]+", caso["id"])):
            raise ValueError("ID de cenário inválido: use um número de 01 a 99 seguido de hífen e nome.")
        if not isinstance(caso.get("nome"), str) or not caso["nome"].strip():
            raise ValueError("Cada definição da suíte deve ter um nome não vazio.")
    if len({c["id"] for c in casos}) != len(casos):
        raise ValueError("Cada definição da suíte deve ter um ID distinto.")
    if len({c["nome"] for c in casos}) != len(casos):
        raise ValueError("Cada definição da suíte deve ter um nome distinto.")
    # Valida a suíte toda antes de selecionar ou enviar qualquer caso.
    entradas = []
    raiz_fixtures = (base / "fixtures").resolve()
    for caso in casos:
        if tipo := caso.get("expectativa_ferramenta"):
            if tipo not in {"obrigatoria", "opcional"}:
                raise ValueError(f"{caso['id']}: expectativa de ferramenta inválida.")
        else:
            raise ValueError(f"{caso['id']}: falta expectativa de ferramenta.")
        if type(caso["max_turnos"]) is not int or not 1 <= caso["max_turnos"] <= 50:
            raise ValueError(f"{caso['id']}: max_turnos inválido.")
        if not caso.get("cenario") or not caso.get("criterios_sucesso"):
            raise ValueError(f"{caso['id']}: roteiro e critérios são obrigatórios.")
        if not all(isinstance(c, str) and c.strip() for c in caso["criterios_sucesso"]):
            raise ValueError(f"{caso['id']}: critérios precisam ser textos não vazios.")
        if type(caso["mock"]["is_error"]) is not bool:
            raise ValueError(f"{caso['id']}: is_error precisa ser booleano.")
        caminho = (raiz_fixtures / caso["mock"]["arquivo"]).resolve()
        if not caminho.is_relative_to(raiz_fixtures):
            raise ValueError("O arquivo de mock deve ficar dentro de fixtures.")
        retorno = ler_json(caminho)
        payload = montar_teste(caso, retorno, tool_id)
        entradas.append({"caso": caso, "retorno": retorno, "payload": payload,
                         "assinatura": assinatura(payload)})
    if casos_selecionados is not None:
        tokens = [c.strip() for c in casos_selecionados.split(",") if c.strip()]
        if not tokens:
            raise ValueError("Informe os números dos casos separados por vírgula.")
        # O número do caso pode ser escrito como 1 ou 01; o ID salvo não muda.
        tokens = [c.zfill(2) if re.fullmatch(r"[0-9]{1,2}", c) else c for c in tokens]
        selecionados = [e for e in entradas if e["caso"]["id"] in tokens or e["caso"]["id"][:2] in tokens]
        conhecidos = {e["caso"]["id"] for e in entradas} | {e["caso"]["id"][:2] for e in entradas}
        if desconhecidos := set(tokens) - conhecidos:
            raise ValueError(
                f"Cenários não encontrados: {', '.join(repr(c) for c in sorted(desconhecidos))}. "
                "IDs disponíveis: " + ", ".join(e["caso"]["id"] for e in entradas) + ". "
                "Números disponíveis: " + ", ".join(sorted({e["caso"]["id"][:2] for e in entradas})) + "."
            )
        entradas = selecionados
    elif limite is not None:
        if not 1 <= limite <= len(casos):
            raise ValueError(f"O limite deve estar entre 1 e {len(casos)} nesta suíte.")
        entradas = entradas[:limite]
    return suite, entradas


def estado_atual(base):
    caminho = base / ".estado-lotes.json"
    estado = ler_json(caminho) if caminho.exists() else {"cadastros": {}}
    # O primeiro caso preserva o payload original; podemos reutilizar seu cadastro.
    antigo = base / ".estado.json"
    if antigo.exists():
        for chave, test_id in ler_json(antigo).get("cadastros", {}).items():
            estado.setdefault("cadastros", {}).setdefault(chave, test_id)
    return estado


def pasta_salva(base, nome):
    caminho = (base / nome).resolve()
    if not caminho.is_relative_to((base / "lotes").resolve()):
        raise ValueError("O lote salvo precisa estar dentro da pasta lotes.")
    return caminho


def cadastrar(client, entradas, estado, caminho_estado):
    """Salva cada ID recebido; não repete automaticamente cadastro ou execução."""
    for entrada in entradas:
        chave = entrada["assinatura"]
        test_id = estado.setdefault("cadastros", {}).get(chave)
        if not test_id:
            teste = client.conversational_ai.tests.create(
                request=TestsCreateRequestBody_Simulation(**entrada["payload"]), request_options=OPCOES
            )
            test_id = teste.id
            estado["cadastros"][chave] = test_id
            salvar_json(caminho_estado, estado)
        entrada["test_id"] = test_id
    ids = [e["test_id"] for e in entradas]
    if len(ids) != len(set(ids)):
        raise ValueError("Dois cenários apontam para o mesmo cadastro; confira a suíte antes de enviar.")


def iniciar_lote(client, base, suite, entradas, agent_id, branch_id, rotulo):
    estado = estado_atual(base)
    if estado.get("pendente"):
        raise ValueError("Há um lote pendente. Use --consultar antes de enviar outro.")
    nome = "lote_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ_") + uuid4().hex[:6]
    pasta = base / "lotes" / nome
    estado_path = base / ".estado-lotes.json"
    manifesto = {
        "rotulo": rotulo, "criado_em_utc": datetime.now(timezone.utc).isoformat(),
        "suite_versao": suite["versao"], "sdk_versao": version("elevenlabs"),
        "agent_id": agent_id, "branch_id": branch_id, "repeat_count": 1,
        "casos": [e["caso"]["id"] for e in entradas], "fase": "cadastrando",
        "assinatura_dataset": assinatura([e["assinatura"] for e in entradas]),
    }
    salvar_json(pasta / "manifesto.json", manifesto)
    salvar_json(pasta / "entradas.json", entradas)
    cadastrar(client, entradas, estado, estado_path)
    # Snapshot completo, com os IDs, ANTES do POST que inicia as simulações.
    salvar_json(pasta / "entradas.json", entradas)
    manifesto["fase"] = "envio_iniciado"
    salvar_json(pasta / "manifesto.json", manifesto)
    estado["ultima_pasta"] = str(pasta.relative_to(base))
    estado["pendente"] = {"pasta": estado["ultima_pasta"], "invocation_id": None}
    salvar_json(estado_path, estado)
    try:
        resposta = client.conversational_ai.agents.run_tests(
            agent_id=agent_id, branch_id=branch_id,
            tests=[{"test_id": e["test_id"]} for e in entradas], repeat_count=1,
            request_options=OPCOES,
        )
    except ApiError as exc:
        if exc.status_code in REJEICOES:
            estado["pendente"] = None
            manifesto["fase"] = "envio_rejeitado"
            salvar_json(estado_path, estado)
            salvar_json(pasta / "manifesto.json", manifesto)
        raise
    estado["pendente"]["invocation_id"] = resposta.id
    manifesto.update({"invocation_id": resposta.id, "fase": "em_andamento"})
    salvar_json(estado_path, estado)
    salvar_json(pasta / "manifesto.json", manifesto)
    salvar_json(pasta / "resultado-completo.json", para_dict(resposta))
    return pasta, resposta


def recuperar(client, base, identificador):
    estado = estado_atual(base)
    nome = (estado.get("pendente") or {}).get("pasta") or estado.get("ultima_pasta")
    if not nome:
        raise ValueError("Não há lote salvo para consultar.")
    pasta = pasta_salva(base, nome)
    manifesto = ler_json(pasta / "manifesto.json")
    entradas = ler_json(pasta / "entradas.json")
    invocation_id = manifesto.get("invocation_id") if identificador == "ultima" else identificador
    if not invocation_id:
        raise ValueError("Confira Tests na ElevenLabs e use --consultar ID_DA_EXECUCAO cujo envio perdeu a resposta.")
    resposta = client.conversational_ai.tests.invocations.get(
        test_invocation_id=invocation_id, request_options=OPCOES
    )
    # Não associe o snapshot a uma execução de outro teste ou agente.
    esperados = {e["test_id"] for e in entradas}
    if any(r.test_id not in esperados for r in resposta.test_runs):
        raise ValueError("O ID informado inclui testes que não pertencem a este lote.")
    if resposta.agent_id and resposta.agent_id != manifesto["agent_id"]:
        raise ValueError("O ID informado pertence a outro agente.")
    manifesto["invocation_id"] = resposta.id
    salvar_json(pasta / "manifesto.json", manifesto)
    estado["pendente"] = {"pasta": nome, "invocation_id": resposta.id}
    salvar_json(base / ".estado-lotes.json", estado)
    return pasta, resposta


def finalizar(client, base, pasta, resposta):
    print("Execução:", resposta.id)
    dados = aguardar(client, resposta)
    entradas = ler_json(pasta / "entradas.json")
    resumo = gerar_relatorios(pasta, dados, entradas)
    runs = dados.get("test_runs", [])
    esperados = {e["test_id"] for e in entradas}
    terminou = bool(dados.get("cancelled")) or (
        len(runs) == len(entradas) and {r.get("test_id") for r in runs} == esperados
        and all(r.get("status") in TERMINAIS for r in runs)
    )
    manifesto = ler_json(pasta / "manifesto.json")
    manifesto["fase"] = "finalizado" if terminou else "em_andamento"
    salvar_json(pasta / "manifesto.json", manifesto)
    estado = estado_atual(base)
    estado["pendente"] = None if terminou else {"pasta": str(pasta.relative_to(base)), "invocation_id": resposta.id}
    salvar_json(base / ".estado-lotes.json", estado)
    geral = resumo["visao_geral"]
    print("\nResultados:", json.dumps(geral["por_resultado"], ensure_ascii=False))
    print("Créditos informados:", geral["creditos_informados"])
    print("Relatórios:", pasta)
    for alerta in geral.get("alertas", []):
        print("Observação:", alerta)
    if not terminou:
        print("Há resultados pendentes/incompletos. Use --consultar; não inicia outro lote.")
    return 0 if resumo["casos"] and all(c["resultado"] == "APROVADO" for c in resumo["casos"]) else 1


def previa(base, suite, entradas, agent_id, branch_id):
    plano = {
        "tipo": "previa_local_sem_execucao", "suite_versao": suite["versao"],
        "agent_id": agent_id, "branch_id": branch_id, "quantidade": len(entradas),
        "repeat_count": 1, "referencia_creditos_por_caso": REFERENCIA_CREDITOS,
        "referencia_linear_creditos": REFERENCIA_CREDITOS * len(entradas),
        "nota_custo": "Referência baseada em uma execução anterior; não é previsão ou teto de consumo.",
        "entradas": entradas,
    }
    salvar_json(base / "plano-lote.json", plano)
    print("PRÉVIA LOCAL — sem requisição à API e sem iniciar simulações.")
    print("Casos selecionados:", len(entradas), "| repetições por caso: 1")
    for e in entradas:
        c = e["caso"]
        print(f"{c['id']}: {c['nome']} | {c['max_turnos']} turnos | tool {c['expectativa_ferramenta']} | {c['mock']['arquivo']} / is_error={c['mock']['is_error']}")
    print("Referência linear de créditos:", plano["referencia_linear_creditos"], "(o consumo real varia).")
    print("Plano salvo em:", base / "plano-lote.json")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--preview", action="store_true")
    modo.add_argument("--executar", action="store_true", help="Inicia as simulações selecionadas; consome recursos.")
    modo.add_argument("--consultar", nargs="?", const="ultima", metavar="ID", help="Recupera o último lote; não inicia simulações.")
    filtro = parser.add_mutually_exclusive_group()
    filtro.add_argument("--casos", help='Números ou IDs separados por vírgula. Exemplo: --casos "01,11,17". Aceita 1 ou 01.')
    filtro.add_argument("--limite", type=int, help="Seleciona os primeiros N casos da suíte escolhida.")
    parser.add_argument("--suite", metavar="ARQUIVO", help="Arquivo .json dentro de cenarios. Padrão: cenarios/suite-20.json.")
    parser.add_argument("--rotulo", default="baseline", help="Descrição desta rodada para comparação posterior.")
    args = parser.parse_args(argv)
    load_dotenv(BASE / ".env")
    try:
        if args.consultar and (args.casos is not None or args.limite is not None or args.suite is not None):
            raise ValueError("--consultar usa o snapshot já salvo. Não combine com --suite ou filtros de casos.")
        chave = os.getenv("ELEVENLABS_API_KEY", "").strip()
        agent_id = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
        branch_id = os.getenv("ELEVENLABS_BRANCH_ID", "").strip()
        tool_id = os.getenv("ELEVENLABS_TOOL_ID", "").strip()
        if args.consultar:
            if not chave:
                raise ValueError("Preencha a chave no .env local antes de consultar.")
            client = ElevenLabs(api_key=chave, timeout=30)
            pasta, resposta = recuperar(client, BASE, args.consultar)
            return finalizar(client, BASE, pasta, resposta)
        suite, entradas = carregar_entradas(BASE, tool_id or "tool_exemplo", args.casos, args.limite, args.suite)
        if not args.executar:
            return previa(BASE, suite, entradas, agent_id, branch_id)
        if not all([chave, agent_id, branch_id, tool_id]):
            raise ValueError("Preencha a chave e os identificadores no .env local.")
        print(f"Enviando {len(entradas)} cenários, uma repetição cada. Essa ação usa créditos da ElevenLabs.")
        client = ElevenLabs(api_key=chave, timeout=30)
        pasta, resposta = iniciar_lote(client, BASE, suite, entradas, agent_id, branch_id, args.rotulo)
        return finalizar(client, BASE, pasta, resposta)
    except ApiError as exc:
        print(f"A API devolveu HTTP {exc.status_code}. Confira chave, permissões, cota e identificadores.")
        print("Sem tentativa automática. Se o envio ficou incerto, consulte Tests e recupere a MESMA execução.")
        return 2
    except (ValueError, KeyError, OSError) as exc:
        print("Não foi possível concluir:", str(exc))
        return 2
    except Exception as exc:
        print(f"Não foi possível concluir ({type(exc).__name__}). Use --consultar se já houve envio.")
        return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
