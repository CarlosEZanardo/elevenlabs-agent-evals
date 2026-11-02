"""Testes sintéticos de publicação; não usam credenciais nem a ElevenLabs."""

from collections import Counter
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


MODULO = Path(__file__).resolve().parents[1] / "scripts" / "exportar_demo.py"
spec = importlib.util.spec_from_file_location("exportar_demo", MODULO)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def fixture_raw():
    chamada = {"request_id": "request_original_abc123", "tool_id": "tool_original_abc123", "tool_name": "notify_condition_1", "tool_has_been_called": True,
               "params_as_json": '{"email":"pessoa@example.test","api_key":"segredo-sintetico"}', "campo_futuro": "nao-publicar"}
    retorno = {"request_id": chamada["request_id"], "tool_name": chamada["tool_name"], "tool_has_been_called": True,
               "is_blocked": False, "result_value": '{"workspace_id":"workspace_original_abc123","token":"segredo-sintetico"}',
               "result": {"steps": [{"requests": [chamada]}]}}
    return {"invocation_id": "suite_original_abc123", "test_id": "test_original_abc123", "desconhecido": "nao-publicar", "test_runs": [{
        "test_run_id": "run_original_abc123", "test_id": "test_original_abc123", "agent_id": "agent_original_abc123",
        "branch_id": "agtbrch_original_abc123", "version_id": "agtvrsn_original_abc123", "ran_against_draft": False,
        "status": "success", "credits_used": 42,
        "metadata": {"ran_by_user_email": "pessoa@example.test", "workspace_id": "workspace_original_abc123", "authorization": "segredo-sintetico"},
        "test_info": {"tool_mock_overrides": {"tool_original_abc123": [{"mock_result": '{"token":"segredo-sintetico"}'}]}},
        "condition_result": {"result": "success", "rationale": {"summary": "Critérios atendidos.", "messages": [], "campo_futuro": "nao-publicar"}},
        "charging": {"llm_charge": 39, "platform_charge": 3, "campo_futuro": "nao-publicar"},
        "agent_responses": [
            {"role": "user", "message": "Qual o preço?", "user_identifier": "pessoa@example.test"},
            {"role": "agent", "message": "A mensalidade é R$ 220.", "time_in_call_secs": 2.5, "producing_llm": "modelo-teste",
             "agent_metadata": {"agent_id": "agent_original_abc123"}, "tool_calls": [chamada, chamada], "tool_results": [retorno],
             "llm_usage": {"model_usage": {"modelo-teste": {"input": {"tokens": 20}}}}},
            {"role": "agent", "message": "Mais alguma dúvida?", "tool_calls": [{**chamada, "request_id": "request_second_abc123"}]},
        ],
    }]}


def criar_origem(raiz):
    origem = raiz / "local"
    pasta = origem / "lotes" / "lote_20260101T000000Z_exemplo"
    caso = {"caso_id": "01-preco", "nome": "Preço", "categoria": "Informações", "finalidade": "desenvolvimento", "assinatura": "a" * 64,
            "resultado": "APROVADO", "status_plataforma": "success", "justificativa": "Critérios atendidos.",
            "test_id": "test_original_abc123", "test_run_id": "run_original_abc123", "agent_id": "agent_original_abc123", "credits_used": 42,
            "ran_against_draft": False, "nos_vistos": ["node_original_abc123"], "campo_futuro": "nao-publicar"}
    geral = {"planejados": 1, "por_resultado": {k: int(k == "APROVADO") for k in demo.RESULTADOS}, "taxa_aprovacao_decisivos": 1,
             "cobertura_decisiva": 1, "creditos_informados": 42, "total_sem_creditos": 0, "alertas": [], "campo_futuro": "nao-publicar"}
    demo.escrever_json(pasta / "manifesto.json", {"rotulo": "Exemplo", "criado_em_utc": "2026-01-01T00:00:00Z", "agent_id": caso["agent_id"], "casos": [caso["caso_id"]], "campo_futuro": "nao-publicar"})
    demo.escrever_json(pasta / "resumo.json", {"visao_geral": geral, "casos": [caso]})
    demo.escrever_json(pasta / "entradas.json", [{"caso": {"id": caso["caso_id"], "cenario": "Pergunte o preço.", "criterios_sucesso": ["Informa R$ 220."], "campo_futuro": "nao-publicar"},
         "retorno": {"status": "ok", "total": 0, "cursos": [], "authorization": "segredo-sintetico"}, "payload": {"token": "segredo-sintetico"}}])
    pasta_caso = pasta / "casos" / caso["caso_id"]
    demo.escrever_json(pasta_caso / "resultado-completo.json", fixture_raw())
    (pasta_caso / "conversa.txt").write_text("USER: Qual o preço?\nAGENT: A mensalidade é R$ 220.\n", encoding="utf-8")
    (origem / ".env").write_text("NAO_DEVE_SER_LIDO=segredo-sintetico\n", encoding="utf-8")
    return origem, pasta


class ExportacaoDemoTests(unittest.TestCase):
    def test_projecao_omite_metadata_e_jsons_livres_aninhados(self):
        raw = fixture_raw()
        saida = demo.projetar_resultado(raw)
        serializado = json.dumps(saida)
        for proibido in ("ran_by_user_email", "workspace_id", "pessoa@example.test", "segredo-sintetico", "nao-publicar", "params_as_json", "tool_mock_overrides", "agent_metadata"):
            self.assertNotIn(proibido, serializado)
        self.assertEqual(saida["test_runs"][0]["credits_used"], 42)
        self.assertEqual(saida["test_runs"][0]["condition_result"]["result"], "success")
        self.assertEqual(saida["test_runs"][0]["charging"]["llm_charge"], 39)

    def test_aliases_deterministicos_preservam_associacoes(self):
        raw = fixture_raw()
        saida = demo.projetar_resultado(raw)
        self.assertEqual(saida["test_id"], saida["test_runs"][0]["test_id"])
        chamada = saida["test_runs"][0]["agent_responses"][1]["tool_calls"][0]
        retorno = saida["test_runs"][0]["agent_responses"][1]["tool_results"][0]
        self.assertEqual(chamada["request_id"], retorno["request_id"])
        self.assertEqual(demo.alias_id(raw["test_id"]), saida["test_id"])
        self.assertNotEqual(demo.alias_id("a"), demo.alias_id("b"))

    def test_execucao_trun_no_cabecalho_usa_o_mesmo_alias_do_json(self):
        identificador = "trun_0123456789abcdefghijklmnop"
        raw = fixture_raw()
        raw["test_runs"][0]["test_run_id"] = identificador
        esperado = demo.projetar_resultado(raw)["test_runs"][0]["test_run_id"]
        cabecalho = demo.texto(f"Execução: {identificador}\n")
        self.assertEqual(cabecalho, f"Execução: {esperado}\n")
        self.assertNotIn(identificador, cabecalho)

    def test_dedupe_e_contagem_ignoram_nested_tools(self):
        raw = fixture_raw()
        esperado = Counter({"notify_condition_1": 2})
        self.assertEqual(demo.contagem_chamadas(raw), esperado)
        self.assertEqual(demo.contagem_chamadas(demo.projetar_resultado(raw)), esperado)

    def test_confirmacao_por_retorno_preservada(self):
        raw = fixture_raw()
        m = raw["test_runs"][0]["agent_responses"][1]
        for chamada in m["tool_calls"]:
            chamada.pop("tool_has_been_called", None)
        self.assertEqual(demo.contagem_chamadas(raw), demo.contagem_chamadas(demo.projetar_resultado(raw)))

    def test_texto_redige_email_credencial_url_caminhos_e_ids(self):
        original = r"Contato pessoa@example.test, sk_0123456789abcdefghijkl C:\Users\pessoa\teste.txt /home/pessoa/teste https://example.test/token=segredo agent_original_abc123 123e4567-e89b-12d3-a456-426614174000"
        limpo = demo.texto(original)
        for proibido in ("pessoa@example.test", "0123456789", "C:\\Users", "/home/", "https://", "agent_original_abc123", "123e4567-e89b"):
            self.assertNotIn(proibido, limpo)
        self.assertIn("demo_", limpo)

    def test_exportacao_preserva_notas_criterios_e_transcricoes(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            origem, pasta = criar_origem(raiz)
            destino = raiz / "publicavel"
            self.assertEqual(demo.exportar(origem, destino), {"lotes": 1, "casos": 1})
            publicavel = destino / "lotes" / pasta.name
            resumo = json.loads((publicavel / "resumo.json").read_text(encoding="utf-8"))
            self.assertEqual(resumo["visao_geral"]["por_resultado"]["APROVADO"], 1)
            self.assertEqual(resumo["visao_geral"]["creditos_informados"], 42)
            self.assertEqual(resumo["casos"][0]["assinatura"], "a" * 64)
            entrada = json.loads((publicavel / "entradas.json").read_text(encoding="utf-8"))[0]
            self.assertEqual(entrada["caso"]["criterios_sucesso"], ["Informa R$ 220."])
            self.assertEqual((publicavel / "casos/01-preco/conversa.txt").read_text(encoding="utf-8"), "USER: Qual o preço?\nAGENT: A mensalidade é R$ 220.\n")
            todos = "\n".join(p.read_text(encoding="utf-8") for p in publicavel.rglob("*") if p.is_file())
            for proibido in ("segredo-sintetico", "nao-publicar", "pessoa@example.test", "test_original_abc123"):
                self.assertNotIn(proibido, todos)
            self.assertFalse((destino / ".env").exists())
            self.assertTrue((origem / ".env").exists())

    def test_recusa_sobreposicao_e_destino_existente_sem_alterar_origem(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            origem, pasta = criar_origem(raiz)
            original = (pasta / "resumo.json").read_bytes()
            for destino in (origem, origem / "filho", raiz):
                with self.assertRaises(ValueError):
                    demo.exportar(origem, destino)
            destino = raiz / "publicavel"
            demo.exportar(origem, destino)
            with self.assertRaises(ValueError):
                demo.exportar(origem, destino)
            self.assertEqual(original, (pasta / "resumo.json").read_bytes())

    def test_recusa_caso_com_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            origem, pasta = criar_origem(raiz)
            p = pasta / "resumo.json"
            resumo = json.loads(p.read_text(encoding="utf-8"))
            resumo["casos"][0]["caso_id"] = "../fora"
            demo.escrever_json(p, resumo)
            with self.assertRaises(ValueError):
                demo.exportar(origem, raiz / "publicavel")
            self.assertFalse((raiz / "publicavel/lotes").exists())


if __name__ == "__main__":
    unittest.main()
