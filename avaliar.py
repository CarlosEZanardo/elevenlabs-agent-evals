"""Primeira avaliação da Ponte Idiomas: cenário -> SDK -> resultado.

Sem argumentos, apenas mostra uma prévia local. --executar inicia UM teste
na ElevenLabs. --consultar apenas recupera a última execução, sem iniciar outra.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.conversational_ai.tests.types.tests_create_request_body import (
    TestsCreateRequestBody_Simulation,
)


BASE = Path(__file__).resolve().parent
# Sem repetição automática de POST: uma resposta perdida não deve gerar outra cobrança.
OPCOES = {"max_retries": 0, "timeout_in_seconds": 30}
TERMINAIS = {"passed", "failed", "cancelled"}


def ler_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def salvar_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def preparar(cenario, catalogo, tool_id):
    """Monta o cadastro do teste. O mock usa o ID da ferramenta, não seu nome."""
    if not 1 <= cenario["max_turnos"] <= 50:
        raise ValueError("max_turnos deve estar entre 1 e 50.")
    if catalogo.get("status") != "ok" or catalogo.get("total") != len(catalogo.get("cursos", [])):
        raise ValueError("Catálogo de teste inválido.")
    return {
        "type": "simulation",
        "name": cenario["nome"],
        "simulation_scenario": cenario["cenario"],
        "simulation_max_turns": cenario["max_turnos"],
        "success_conditions": cenario["criterios_sucesso"],
        "tool_mock_config": {
            "mocking_strategy": "selected",
            "fallback_strategy": "raise_error",
            "mocked_tool_ids": [tool_id],
        },
        "tool_mock_overrides": {
            tool_id: [{
                "parameter_conditions": [],
                "mock_result": json.dumps(catalogo, ensure_ascii=False),
                "is_error": False,
            }]
        },
    }


def para_dict(modelo):
    return modelo.model_dump(mode="json", exclude_none=True)


def iniciar(client, agent_id, branch_id, payload, estado_path, entradas):
    """Reutiliza o cadastro se o cenário/mock não mudaram; inicia uma execução."""
    estado = ler_json(estado_path) if estado_path.exists() else {}
    # Se houve interrupção, primeiro consulte a execução anterior. Não a repita às cegas.
    if estado.get("aguardando"):
        raise ValueError("Há uma execução pendente. Use --consultar antes de executar outra.")
    assinatura = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    cadastro = estado.get("cadastros", {}).get(assinatura)
    if not cadastro:
        teste = client.conversational_ai.tests.create(
            request=TestsCreateRequestBody_Simulation(**payload), request_options=OPCOES
        )
        cadastro = teste.id
        estado.setdefault("cadastros", {})[assinatura] = cadastro
        salvar_json(estado_path, estado)
        print("Teste cadastrado:", cadastro)
    else:
        print("Reutilizando teste cadastrado:", cadastro)

    # O sinal de envio é salvo antes do POST. Se a resposta se perder, não repetimos.
    estado["aguardando"] = True
    estado["ultima_execucao"] = None
    estado["ultimo_test_id"] = cadastro
    estado["entradas"] = entradas
    salvar_json(estado_path, estado)
    try:
        resposta = client.conversational_ai.agents.run_tests(
            agent_id=agent_id,
            branch_id=branch_id,
            tests=[{"test_id": cadastro}],
            repeat_count=1,
            request_options=OPCOES,
        )
    except ApiError as exc:
        # Rejeições inequívocas não iniciaram o teste. Erros de rede/5xx são
        # incertos: mantenha o bloqueio até conferir o histórico na plataforma.
        if exc.status_code in (400, 401, 402, 403, 404, 422, 429):
            estado["aguardando"] = False
            salvar_json(estado_path, estado)
        raise
    estado["ultima_execucao"] = resposta.id
    salvar_json(estado_path, estado)
    return resposta


def aguardar(client, resposta, segundos=180, intervalo=3):
    """Consultar o resultado não inicia simulações adicionais."""
    limite = time.monotonic() + segundos
    while True:
        dados = para_dict(resposta)
        runs = dados.get("test_runs", [])
        if dados.get("cancelled") or (runs and all(r.get("status") in TERMINAIS for r in runs)):
            return dados
        if time.monotonic() >= limite:
            return dados  # Pendente continua pendente; nunca vira aprovação por timeout.
        time.sleep(intervalo)
        resposta = client.conversational_ai.tests.invocations.get(
            test_invocation_id=resposta.id, request_options=OPCOES
        )


def resumir(dados, cenario, catalogo):
    """Separa a avaliação do LLM da evidência determinística da ferramenta."""
    runs = dados.get("test_runs", [])
    if len(runs) != 1:
        return {"resultado": "INCONCLUSIVO", "motivo": "Esperada exatamente uma execução."}
    run = runs[0]
    condicao = run.get("condition_result") or {}
    razao = condicao.get("rationale") or {}
    motivo = " | ".join(filter(None, [razao.get("summary"), *(razao.get("messages") or [])]))
    mensagens = run.get("agent_responses") or []
    chamadas = [t for m in mensagens for t in (m.get("tool_calls") or [])]
    retornos = [t for m in mensagens for t in (m.get("tool_results") or [])]
    chamada = any(t.get("tool_name") == cenario["ferramenta"] for t in chamadas)
    mock_confirmado = False
    for t in retornos:
        if t.get("tool_name") != cenario["ferramenta"] or t.get("is_error"):
            continue
        try:
            mock_confirmado |= json.loads(t.get("result_value", "")) == catalogo
        except (ValueError, TypeError):
            pass

    status, grade = run.get("status"), condicao.get("result")
    if status == "passed" and grade == "success":
        resultado = "APROVADO" if chamada and mock_confirmado else "REVISAR_EVIDENCIA"
    elif status == "failed" and grade == "failure":
        resultado = "REPROVADO"
    elif status == "cancelled" or dados.get("cancelled"):
        resultado = "CANCELADO"
    else:
        resultado = "INCONCLUSIVO"
    return {
        "cenario": cenario["id"],
        "resultado": resultado,
        "status_plataforma": status,
        "avaliacao_plataforma": grade or "não informada",
        "ferramenta_chamada": chamada,
        "mock_confirmado": mock_confirmado,
        "motivo": motivo or "Sem justificativa disponível; confira o resultado completo.",
        "invocation_id": dados["id"],
        "test_id": run.get("test_id"),
        "agent_id": run.get("agent_id") or dados.get("agent_id"),
        "branch_id": run.get("branch_id") or dados.get("branch_id"),
        "version_id": run.get("version_id") or dados.get("version_id") or "não informada",
        "ran_against_draft": run.get("ran_against_draft", dados.get("ran_against_draft")),
        "credits_used": run.get("credits_used", "não informado"),
    }


def registrar(base, dados, cenario, catalogo, payload):
    """Salva entradas, retorno completo, CSV e transcrição legível, sem a chave."""
    pasta = base / "resultados" / dados["id"]
    resumo = resumir(dados, cenario, catalogo)
    salvar_json(pasta / "entradas.json", {"cenario": cenario, "catalogo": catalogo, "cadastro": payload})
    salvar_json(pasta / "resultado-completo.json", dados)
    salvar_json(pasta / "resumo.json", resumo)
    with (pasta / "resumo.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(resumo), delimiter=";")
        writer.writeheader()
        writer.writerow(resumo)
    linhas = ["Ponte Idiomas — avaliação por texto", f"Execução: {dados['id']}", ""]
    for run in dados.get("test_runs", []):
        for m in run.get("agent_responses") or []:
            if m.get("message"):
                linhas.append(f"{m.get('role', '?')}: {m['message']}")
            for t in m.get("tool_calls") or []:
                linhas.append(f"  [chamada: {t.get('tool_name', '?')}]")
            for t in m.get("tool_results") or []:
                linhas.append(f"  [retorno: {t.get('tool_name', '?')}; erro={t.get('is_error')}]")
    (pasta / "conversa.txt").write_text("\n".join(linhas), encoding="utf-8")
    return resumo, pasta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    acao = parser.add_mutually_exclusive_group()
    acao.add_argument("--preview", action="store_true", help="Prévia local, sem API (padrão).")
    acao.add_argument("--executar", action="store_true", help="Cadastra/reutiliza o teste e inicia UMA simulação.")
    acao.add_argument("--consultar", nargs="?", const="ultima", metavar="ID", help="Consulta a última execução ou o ID indicado, sem iniciar outra.")
    args = parser.parse_args(argv)
    load_dotenv(BASE / ".env")
    cenario = ler_json(BASE / "cenarios" / "01-duvida-ingles.json")
    catalogo = ler_json(BASE / "fixtures" / "catalogo.json")
    tool_id = os.getenv("ELEVENLABS_TOOL_ID", "")
    payload = preparar(cenario, catalogo, tool_id or "tool_exemplo")

    if not (args.executar or args.consultar):
        print("PRÉVIA LOCAL — nenhuma chamada à API; nenhuma simulação iniciada.\n")
        print("Cenário:", cenario["nome"])
        print("Máximo de turnos:", cenario["max_turnos"])
        print("Ferramenta com resposta fixa:", cenario["ferramenta"])
        for i, criterio in enumerate(cenario["criterios_sucesso"], 1):
            print(f"Critério {i}: {criterio}")
        print("\nVerificações locais extras: chamada da ferramenta e retorno igual ao catálogo fixo.")
        print("Próximo passo: preencher .env e usar --executar (consome recursos da ElevenLabs).")
        return 0

    chave = os.getenv("ELEVENLABS_API_KEY", "").strip()
    agent_id = os.getenv("ELEVENLABS_AGENT_ID", "").strip()
    branch_id = os.getenv("ELEVENLABS_BRANCH_ID", "").strip()
    if not chave or not agent_id or not branch_id or not tool_id:
        print("Preencha ELEVENLABS_API_KEY e os identificadores no arquivo local .env. Não envie a chave no chat.")
        return 2
    estado_path = BASE / ".estado.json"
    # O SDK usa a chave em memória; nunca a imprimimos ou salvamos nos relatórios.
    client = ElevenLabs(api_key=chave, timeout=30)
    try:
        if args.executar:
            print("Iniciando UMA simulação por texto, até cinco turnos, no agente e branch configurados.")
            resposta = iniciar(client, agent_id, branch_id, payload, estado_path, {
                "cenario": cenario, "catalogo": catalogo, "cadastro": payload,
            })
            # Guarda as entradas desta execução para que --consultar use as mesmas,
            # mesmo se o usuário editar o cenário ou o catálogo depois.
            salvar_json(BASE / "resultados" / resposta.id / "entradas.json", {
                "cenario": cenario, "catalogo": catalogo, "cadastro": payload,
            })
        else:
            estado = ler_json(estado_path) if estado_path.exists() else {}
            identificador = estado.get("ultima_execucao") if args.consultar == "ultima" else args.consultar
            if not identificador:
                print("Sem ID de execução salvo. Se o envio anterior falhou, confira Tests na ElevenLabs antes de repetir.")
                return 2
            entradas = estado.get("entradas")
            if not entradas:
                print("Não há entradas salvas para recuperar esta execução.")
                return 2
            cenario, catalogo, payload = entradas["cenario"], entradas["catalogo"], entradas["cadastro"]
            resposta = client.conversational_ai.tests.invocations.get(
                test_invocation_id=identificador, request_options=OPCOES
            )
            if any(r.test_id != estado.get("ultimo_test_id") for r in resposta.test_runs):
                print("Esse ID pertence a outro teste. Use o ID da execução enviada por este projeto.")
                return 2
            estado["ultima_execucao"] = resposta.id
            salvar_json(estado_path, estado)
        print("Execução:", resposta.id)
        dados = aguardar(client, resposta)
        resumo, pasta = registrar(BASE, dados, cenario, catalogo, payload)
        runs = dados.get("test_runs", [])
        terminou = dados.get("cancelled") or (runs and all(r.get("status") in TERMINAIS for r in runs))
        estado = ler_json(estado_path)
        estado["aguardando"] = not bool(terminou)
        salvar_json(estado_path, estado)
        print("\nResultado:", resumo["resultado"])
        print("Justificativa:", resumo.get("motivo", ""))
        print("Ferramenta chamada:", resumo.get("ferramenta_chamada", False))
        print("Catálogo fixo confirmado:", resumo.get("mock_confirmado", False))
        print("Relatórios:", pasta)
        if not terminou:
            print("Ainda pendente. Use --consultar; isso não inicia outra simulação.")
        return 0 if resumo["resultado"] == "APROVADO" else 1
    except ApiError as exc:
        # Não imprime headers/body de erro, que podem conter informações da conta.
        print(f"A API retornou HTTP {exc.status_code}. Confira chave, permissões e IDs.")
        if exc.status_code in (401, 403):
            print("A chave precisa permitir acesso ao agente, criação e execução de testes.")
        print("Não houve nova tentativa automática. Confira Tests antes de repetir um envio incerto.")
        return 2
    except ValueError as exc:
        print(str(exc))
        return 2
    except Exception as exc:
        print(f"Não foi possível concluir ({type(exc).__name__}). Não houve nova tentativa automática.")
        print("Se houver ID de execução, use --consultar. Caso contrário, confira Tests na ElevenLabs.")
        return 2


if __name__ == "__main__":
    # Garante acentos no terminal do Windows, quando houver suporte.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
