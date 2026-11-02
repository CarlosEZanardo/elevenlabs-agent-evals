"""Testes locais do lote: SDK real, HTTP simulado e arquivos temporários."""

import copy
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import httpx
from elevenlabs.client import ElevenLabs
from elevenlabs.core.api_error import ApiError

import avaliar
import avaliar_lote as lote


class LoteTests(unittest.TestCase):
    def copiar_inputs(self, destino):
        shutil.copytree(lote.BASE / "cenarios", destino / "cenarios")
        shutil.copytree(lote.BASE / "fixtures", destino / "fixtures")

    def client(self, handler):
        return ElevenLabs(api_key="chave-local-do-teste", httpx_client=httpx.Client(
            transport=httpx.MockTransport(handler)))

    def test_suite_20_e_primeiro_payload_compativel_com_cadastro_original(self):
        suite, entradas = lote.carregar_entradas(lote.BASE, "tool_local")
        self.assertEqual(len(entradas), 20)
        self.assertEqual(sum(e["caso"]["finalidade"] == "validacao" for e in entradas), 4)
        cenario = avaliar.ler_json(lote.BASE / "cenarios" / "01-duvida-ingles.json")
        esperado = avaliar.preparar(cenario, entradas[0]["retorno"], "tool_local")
        self.assertEqual(entradas[0]["payload"], esperado)
        self.assertEqual(lote.assinatura(esperado), entradas[0]["assinatura"])
        _, escolha = lote.carregar_entradas(lote.BASE, "tool_local", "01,11,17")
        self.assertEqual([e["caso"]["id"][:2] for e in escolha], ["01", "11", "17"])

    def test_preview_sem_cliente_e_sem_chave(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copiar_inputs(base)
            with patch.object(lote, "BASE", base), patch.object(lote, "load_dotenv"), \
                    patch.dict("os.environ", {}, clear=True), \
                    patch.object(lote, "ElevenLabs", side_effect=AssertionError("Não criar cliente")), \
                    redirect_stdout(StringIO()):
                self.assertEqual(lote.main(["--preview"]), 0)
            plano = avaliar.ler_json(base / "plano-lote.json")
            self.assertEqual(plano["quantidade"], 20)
            self.assertEqual(plano["repeat_count"], 1)
            self.assertFalse((base / "lotes").exists())

    def test_suite_minima_preserva_definicoes_e_suite_personalizada_tem_limite_proprio(self):
        completa, _ = lote.carregar_entradas(lote.BASE, "tool_local")
        minima, entradas = lote.carregar_entradas(
            lote.BASE, "tool_local", suite_path="cenarios/suite-minima.json")
        self.assertEqual(minima["versao"], "1.1-minima")
        self.assertEqual([e["caso"]["id"][:2] for e in entradas], ["01", "11", "17"])
        self.assertEqual(minima["casos"], [c for c in completa["casos"] if c["id"][:2] in {"01", "11", "17"}])
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copiar_inputs(base)
            arquivo = base / "cenarios" / "dupla.json"
            avaliar.salvar_json(arquivo, {"versao": "propria", "casos": copy.deepcopy(minima["casos"][:2])})
            suite, dupla = lote.carregar_entradas(base, "tool_local", limite=2, suite_path=arquivo)
            self.assertEqual(suite["versao"], "propria")
            self.assertEqual(len(dupla), 2)
            _, selecao = lote.carregar_entradas(base, "tool_local", "11", suite_path="cenarios/dupla.json")
            self.assertEqual(len(selecao), 1)
            self.assertTrue(selecao[0]["caso"]["id"].startswith("11-"))
            with self.assertRaisesRegex(ValueError, "entre 1 e 2 nesta suíte"):
                lote.carregar_entradas(base, "tool_local", limite=3, suite_path=arquivo)
            with self.assertRaises(ValueError) as erro:
                lote.carregar_entradas(base, "tool_local", "17", suite_path=arquivo)
            self.assertIn("IDs disponíveis: 01-duvida-ingles, 11-secretaria-matricula", str(erro.exception))
            self.assertIn("Números disponíveis: 01, 11", str(erro.exception))

    def test_suite_personalizada_bloqueia_escape_extensao_e_link_resolvido_fora(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copiar_inputs(base)
            for caminho in ("../fora.json", "cenarios/../../fora.json", ".env", "cenarios/.env"):
                with self.subTest(caminho=caminho), patch.object(lote, "ler_json") as ler:
                    with self.assertRaisesRegex(ValueError, "arquivo .json dentro de cenarios"):
                        lote.carregar_entradas(base, "tool_local", suite_path=caminho)
                    ler.assert_not_called()
            # Simula a resolução de um link; não depende do privilégio de symlink no Windows.
            link = base / "cenarios" / "atalho.json"
            fora = base / "fora.json"
            resolver = Path.resolve
            def resolver_link(caminho, *args, **kwargs):
                return fora if caminho == link else resolver(caminho, *args, **kwargs)
            with patch.object(Path, "resolve", autospec=True, side_effect=resolver_link), \
                    patch.object(lote, "ler_json") as ler:
                with self.assertRaisesRegex(ValueError, "dentro de cenarios"):
                    lote.carregar_entradas(base, "tool_local", suite_path="cenarios/atalho.json")
                ler.assert_not_called()

    def test_suite_vazia_ids_duplicados_nomes_duplicados_e_numero_zero_rejeitados(self):
        original = avaliar.ler_json(lote.BASE / "cenarios" / "suite-minima.json")
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copiar_inputs(base)
            for alteracao, mensagem in (("vazia", "lista não vazia"), ("id", "ID distinto"),
                                       ("nome", "nome distinto"), ("zero", "01 a 99")):
                suite = copy.deepcopy(original)
                if alteracao == "vazia":
                    suite["casos"] = []
                elif alteracao == "zero":
                    suite["casos"][0]["id"] = "00-invalido"
                else:
                    suite["casos"][1][alteracao] = suite["casos"][0][alteracao]
                avaliar.salvar_json(base / "cenarios" / "propria.json", suite)
                with self.subTest(alteracao=alteracao), self.assertRaisesRegex(ValueError, mensagem):
                    lote.carregar_entradas(base, "tool_local", suite_path="cenarios/propria.json")

    def test_preview_suite_propria_le_apenas_env_local_sem_cliente(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copiar_inputs(base)
            (base / ".env").write_text(
                "ELEVENLABS_API_KEY=chave-local-do-teste\nELEVENLABS_AGENT_ID=agent_local\n"
                "ELEVENLABS_BRANCH_ID=branch_local\nELEVENLABS_TOOL_ID=tool_local\n", encoding="utf-8")
            with patch.object(lote, "BASE", base), patch.dict("os.environ", {}, clear=True), \
                    patch.object(lote, "ElevenLabs", side_effect=AssertionError("Não criar cliente")), \
                    redirect_stdout(StringIO()):
                self.assertEqual(lote.main(["--preview", "--suite", "cenarios/suite-minima.json"]), 0)
            plano = avaliar.ler_json(base / "plano-lote.json")
            self.assertEqual(plano["quantidade"], 3)
            self.assertEqual(plano["agent_id"], "agent_local")
            self.assertEqual(plano["suite_versao"], "1.1-minima")
            self.assertNotIn("chave-local-do-teste", (base / "plano-lote.json").read_text(encoding="utf-8"))
            self.assertFalse((base / "lotes").exists())

    def test_consulta_rejeita_suite_explicita_antes_de_criar_cliente(self):
        saida = StringIO()
        with patch.object(lote, "load_dotenv"), \
                patch.object(lote, "ElevenLabs", side_effect=AssertionError("Não criar cliente")), \
                patch.object(lote, "carregar_entradas", side_effect=AssertionError("Usar snapshot")), \
                redirect_stdout(saida):
            self.assertEqual(lote.main(["--consultar", "--suite", "cenarios/suite-minima.json"]), 2)
        self.assertIn("snapshot já salvo", saida.getvalue())

    def test_mock_objeto_generico_e_serializado_pelo_sdk_e_comprovado_no_relatorio(self):
        _, entradas = lote.carregar_entradas(lote.BASE, "tool_local", "01")
        entrada = copy.deepcopy(entradas[0])
        retorno = {"status": "confirmada", "reserva": {"protocolo": "LOCAL-001", "servicos": ["alinhamento"]}}
        entrada["retorno"] = retorno
        entrada["caso"]["ferramenta"] = "consultar_reserva"
        entrada["payload"] = lote.montar_teste(entrada["caso"], retorno, "tool_local")
        entrada["assinatura"] = lote.assinatura(entrada["payload"])
        cadastros = []
        def handler(req):
            cadastros.append(json.loads(req.content))
            return httpx.Response(200, json={"id": "test_local"})
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            lote.cadastrar(self.client(handler), [entrada], {"cadastros": {}}, base / "estado.json")
            mock = cadastros[0]["tool_mock_overrides"]["tool_local"][0]
            self.assertEqual(json.loads(mock["mock_result"]), retorno)
            dados = {"id": "suite_local", "test_runs": [{
                "test_id": "test_local", "test_run_id": "run_local", "status": "passed",
                "condition_result": {"result": "success"}, "credits_used": 0,
                "agent_responses": [{"role": "agent", "message": "Reserva localizada.",
                    "tool_calls": [{"tool_name": "consultar_reserva", "request_id": "req_local"}],
                    "tool_results": [{"tool_name": "consultar_reserva", "request_id": "req_local",
                        "is_error": False, "result_value": json.dumps(retorno)}]}],
            }]}
            resumo = lote.gerar_relatorios(base / "relatorio", dados, [entrada])
            self.assertEqual(resumo["casos"][0]["resultado"], "APROVADO")
            self.assertTrue(resumo["casos"][0]["mock_confirmado"])

    def test_mock_generico_nao_exige_status_e_catalogo_mantem_validacao(self):
        _, entradas = lote.carregar_entradas(lote.BASE, "tool_local", "01")
        caso = entradas[0]["caso"]
        for retorno in ({"cliente": {"nome": "Pessoa de teste"}}, {"status": "pendente"},
                        {"status": "ok", "total": 9, "itens": []}):
            with self.subTest(retorno=retorno):
                payload = lote.montar_teste(caso, retorno, "tool_local")
                self.assertEqual(json.loads(payload["tool_mock_overrides"]["tool_local"][0]["mock_result"]), retorno)
        for retorno in ([], None, "texto", 42):
            with self.subTest(retorno=retorno), self.assertRaisesRegex(ValueError, "objeto JSON"):
                lote.montar_teste(caso, retorno, "tool_local")
        with self.assertRaisesRegex(ValueError, "total não corresponde"):
            lote.montar_teste(caso, {"status": "ok", "total": 2, "cursos": []}, "tool_local")
        with self.assertRaisesRegex(ValueError, "cursos precisa ser uma lista"):
            lote.montar_teste(caso, {"status": "ok", "total": 0, "cursos": None}, "tool_local")

    def test_selecao_aceita_numero_sem_zero_e_mostra_valor_desconhecido(self):
        _, entradas = lote.carregar_entradas(lote.BASE, "tool_local", "1, 11,17")
        self.assertEqual([e["caso"]["id"][:2] for e in entradas], ["01", "11", "17"])
        _, entradas = lote.carregar_entradas(lote.BASE, "tool_local", "01-duvida-ingles,11,17")
        self.assertEqual([e["caso"]["id"][:2] for e in entradas], ["01", "11", "17"])
        with self.assertRaisesRegex(ValueError, "Cenários não encontrados: '99'"):
            lote.carregar_entradas(lote.BASE, "tool_local", "01,11,99")

    def test_selecao_vazia_nao_vira_lote_completo(self):
        for selecao in ("", " ", ",,"):
            with self.subTest(selecao=selecao), self.assertRaisesRegex(ValueError, "Informe os números"):
                lote.carregar_entradas(lote.BASE, "tool_local", selecao)

    def test_mocks_distintos_e_validacao_de_selecao(self):
        _, entradas = lote.carregar_entradas(lote.BASE, "tool_local", "16,17,18")
        mocks = [e["payload"]["tool_mock_overrides"]["tool_local"][0] for e in entradas]
        self.assertEqual([m["is_error"] for m in mocks], [False, False, True])
        self.assertEqual([json.loads(m["mock_result"])["status"] for m in mocks], ["ok", "erro", "erro"])
        with self.assertRaises(ValueError):
            lote.carregar_entradas(lote.BASE, "tool_local", "99")
        with self.assertRaises(ValueError):
            lote.carregar_entradas(lote.BASE, "tool_local", limite=0)

    def test_caminho_mock_nao_pode_sair_de_fixtures(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
            base = Path(tmp)
            self.copiar_inputs(base)
            arquivo = base / "cenarios" / "suite-20.json"
            suite = avaliar.ler_json(arquivo)
            suite["casos"][0]["mock"]["arquivo"] = "../.env"
            avaliar.salvar_json(arquivo, suite)
            with self.assertRaisesRegex(ValueError, "dentro de fixtures"):
                lote.carregar_entradas(base, "tool_local")

    def test_lote_com_sdk_snapshot_reuso_e_consulta_sem_nova_execucao(self):
        _, originais = lote.carregar_entradas(lote.BASE, "tool_local", "01,11")
        entradas = copy.deepcopy(originais)
        suite = {"versao": "teste"}
        chamadas, cadastros, execucoes = [], {}, []
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
            base = Path(tmp)
            def handler(req):
                chamadas.append((req.method, req.url.path))
                if req.url.path.endswith("/create"):
                    body = json.loads(req.content)
                    test_id = "test_" + str(len(cadastros) + 1)
                    cadastros[test_id] = body
                    return httpx.Response(200, json={"id": test_id})
                if req.method == "POST":
                    body = json.loads(req.content)
                    self.assertEqual(body["repeat_count"], 1)
                    self.assertEqual(len(body["tests"]), 2)
                    estado = avaliar.ler_json(base / ".estado-lotes.json")
                    pasta = lote.pasta_salva(base, estado["pendente"]["pasta"])
                    snapshot = avaliar.ler_json(pasta / "entradas.json")
                    self.assertTrue(all(e.get("test_id") for e in snapshot))
                    self.assertNotIn("chave-local-do-teste", (pasta / "entradas.json").read_text())
                    suite_id = f"suite_local_{len(execucoes) + 1}"
                    runs = []
                    for i, e in enumerate(reversed(snapshot)):
                        chamadas_tool, retornos_tool = [], []
                        if e["caso"]["expectativa_ferramenta"] == "obrigatoria":
                            chamadas_tool = [{"tool_name": e["caso"]["ferramenta"], "request_id": "req_local",
                                              "params_as_json": "{}", "tool_has_been_called": True}]
                            retornos_tool = [{"tool_name": e["caso"]["ferramenta"], "request_id": "req_local",
                                             "tool_has_been_called": True, "is_error": e["caso"]["mock"]["is_error"],
                                             "result_value": json.dumps(e["retorno"])}]
                        runs.append({"test_run_id": f"run_{i}", "test_invocation_id": suite_id,
                                     "agent_id": "agent_local", "branch_id": "branch_local", "version_id": "v_local",
                                     "ran_against_draft": False, "test_id": e["test_id"], "status": "passed",
                                     "condition_result": {"result": "success", "rationale": {"summary": "Correto no teste local"}},
                                     "credits_used": 10, "agent_responses": [{"role": "agent", "time_in_call_secs": 0,
                                         "message": "Resposta preparada para testar o código.",
                                         "tool_calls": chamadas_tool, "tool_results": retornos_tool}]})
                    completo = {"id": suite_id, "agent_id": "agent_local", "branch_id": "branch_local",
                                "version_id": "v_local", "ran_against_draft": False, "test_runs": runs}
                    execucoes.append(completo)
                    pendente = copy.deepcopy(completo)
                    for run in pendente["test_runs"]:
                        run["status"] = "pending"
                    return httpx.Response(200, json=pendente)
                return httpx.Response(200, json=execucoes[-1])
            client = self.client(handler)
            rapidez = lambda c, r: avaliar.aguardar(c, r, segundos=1, intervalo=0)
            with patch.object(lote, "aguardar", side_effect=rapidez):
                pasta, resposta = lote.iniciar_lote(client, base, suite, entradas, "agent_local", "branch_local", "baseline")
                self.assertEqual(lote.finalizar(client, base, pasta, resposta), 0)
                resumo = avaliar.ler_json(pasta / "resumo.json")
                self.assertEqual(len(resumo["casos"]), 2)
                self.assertEqual(resumo["visao_geral"]["por_resultado"]["APROVADO"], 2)
                self.assertIsNone(avaliar.ler_json(base / ".estado-lotes.json")["pendente"])
                posts_antes = sum(m == "POST" for m, _ in chamadas)
                recuperada, resposta = lote.recuperar(client, base, "ultima")
                self.assertEqual(lote.finalizar(client, base, recuperada, resposta), 0)
                self.assertEqual(sum(m == "POST" for m, _ in chamadas), posts_antes)
                pasta2, resposta2 = lote.iniciar_lote(client, base, suite, copy.deepcopy(originais), "agent_local", "branch_local", "repeticao")
                self.assertEqual(lote.finalizar(client, base, pasta2, resposta2), 0)
                self.assertEqual(len(cadastros), 2)
                self.assertEqual(len(execucoes), 2)
                self.assertNotEqual(pasta, pasta2)

    def test_post_rejeitado_e_incerto_sem_repeticao(self):
        suite, entradas_originais = lote.carregar_entradas(lote.BASE, "tool_local", "01")
        for status, pendente in [(401, False), (500, True)]:
            with self.subTest(status=status), tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp, redirect_stdout(StringIO()):
                base = Path(tmp)
                entradas = copy.deepcopy(entradas_originais)
                avaliar.salvar_json(base / ".estado-lotes.json", {"cadastros": {entradas[0]["assinatura"]: "test_local"}})
                chamadas = []
                def handler(req):
                    chamadas.append(req)
                    return httpx.Response(status, json={"detail": "Erro preparado para teste"})
                client = self.client(handler)
                with self.assertRaises(ApiError):
                    lote.iniciar_lote(client, base, suite, entradas, "agent_local", "branch_local", "erro")
                self.assertEqual(len(chamadas), 1)
                self.assertEqual(bool(avaliar.ler_json(base / ".estado-lotes.json")["pendente"]), pendente)
                if pendente:
                    with self.assertRaisesRegex(ValueError, "pendente"):
                        lote.iniciar_lote(client, base, suite, entradas, "agent_local", "branch_local", "erro")
                    self.assertEqual(len(chamadas), 1)


if __name__ == "__main__":
    unittest.main()
