"""Verificações locais dos relatórios: sem SDK, API ou resultados reais."""

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from relatorios_lote import gerar_relatorios


def temporaria():
    # Dentro do projeto para funcionar também em ambientes com TEMP restrito.
    return tempfile.TemporaryDirectory(prefix="relatorios-", dir=Path(__file__).resolve().parent)


def entrada(numero=1, opcional=False, erro=False):
    return {
        "caso": {
            "id": f"{numero:02d}-caso", "nome": f"Caso {numero}", "categoria": "catálogo",
            "finalidade": "Conferir a informação", "max_turnos": 5,
            "ferramenta": "consultar_cursos", "expectativa_ferramenta": "opcional" if opcional else "obrigatoria",
            "mock": {"arquivo": "catalogo.json", "is_error": erro},
        },
        "retorno": {"status": "erro", "codigo": "CATALOGO_INDISPONIVEL"} if erro else {
            "status": "ok", "total": 0, "cursos": []
        },
        "payload": {}, "assinatura": f"hash-{numero}", "test_id": f"test-{numero}",
    }


def run(item, status="passed", grade="success", chamar=True):
    mensagens = [{
        "role": "agent", "message": "Resposta do assistente.",
        "agent_metadata": {"workflow_node_id": "informacoes"},
        "tool_calls": [{"tool_name": "transfer_to_agent", "request_id": "sistema"}],
        "tool_results": [{"tool_name": "transfer_to_agent", "request_id": "sistema", "is_error": False,
                          "result_value": "Transição realizada."}],
    }]
    if chamar:
        mensagens[0]["tool_calls"].append({"tool_name": "consultar_cursos", "request_id": "consulta"})
        mensagens[0]["tool_results"].append({
            "tool_name": "consultar_cursos", "request_id": "consulta",
            "is_error": item["caso"]["mock"]["is_error"],
            "result_value": json.dumps(item["retorno"]),
        })
    return {
        "test_id": item["test_id"], "test_run_id": "run-" + item["test_id"],
        "test_invocation_id": "suite-1", "agent_id": "agent-1", "branch_id": "main",
        "version_id": "v1", "ran_against_draft": False, "status": status,
        "condition_result": {"result": grade, "rationale": {"summary": "Critério avaliado."}},
        "agent_responses": mensagens, "credits_used": 5,
    }


def suite(runs):
    return {"id": "suite-1", "agent_id": "agent-1", "branch_id": "main", "version_id": "v1",
            "ran_against_draft": False, "test_runs": runs}


class RelatoriosLoteTest(unittest.TestCase):
    def gerar(self, pasta, runs, entradas):
        return gerar_relatorios(Path(pasta), suite(runs), entradas)

    def test_associacao_por_id_ordem_invertida_e_arquivos(self):
        itens = [entrada(1), entrada(2)]
        runs = [run(itens[1]), run(itens[0])]
        runs[0]["condition_result"]["rationale"]["summary"] = "Segunda resposta."
        with temporaria() as pasta:
            resumo = self.gerar(pasta, runs, itens)
            self.assertEqual([c["test_id"] for c in resumo["casos"]], ["test-1", "test-2"])
            self.assertIn("Segunda resposta", resumo["casos"][1]["justificativa"])
            self.assertEqual(resumo["visao_geral"]["por_resultado"]["APROVADO"], 2)
            self.assertEqual(resumo["visao_geral"]["creditos_informados"], 10)
            self.assertEqual(resumo["casos"][0]["nos_vistos"], ["informacoes"])
            csv_path = Path(pasta) / "resumo.csv"
            self.assertTrue(csv_path.read_bytes().startswith(b"\xef\xbb\xbf"))
            with csv_path.open(encoding="utf-8-sig", newline="") as arquivo:
                self.assertEqual(len(list(csv.DictReader(arquivo, delimiter=";"))), 2)
            per_caso = json.loads((Path(pasta) / "casos/01-caso/resultado-completo.json").read_text("utf-8"))
            self.assertEqual(per_caso["test_runs"][0]["test_id"], "test-1")
            self.assertIn("Resposta do assistente", (Path(pasta) / "casos/01-caso/conversa.txt").read_text("utf-8"))

    def test_erro_esperado_da_ferramenta_tambem_comprova_mock(self):
        item = entrada(erro=True)
        with temporaria() as pasta:
            caso = self.gerar(pasta, [run(item)], [item])["casos"][0]
            self.assertEqual(caso["resultado"], "APROVADO")
            self.assertTrue(caso["mock_confirmado"])

    def test_vinte_casos_geram_vinte_linhas_e_pastas(self):
        itens = [entrada(i) for i in range(1, 21)]
        with temporaria() as pasta:
            resumo = self.gerar(pasta, [run(item) for item in reversed(itens)], itens)
            self.assertEqual(resumo["visao_geral"]["planejados"], 20)
            self.assertEqual(resumo["visao_geral"]["por_resultado"]["APROVADO"], 20)
            with (Path(pasta) / "resumo.csv").open(encoding="utf-8-sig", newline="") as arquivo:
                self.assertEqual(len(list(csv.DictReader(arquivo, delimiter=";"))), 20)
            self.assertEqual(len(list((Path(pasta) / "casos").iterdir())), 20)

    def test_ferramenta_opcional_nao_chamada_e_eventos_sistema(self):
        item = entrada(opcional=True)
        with temporaria() as pasta:
            caso = self.gerar(pasta, [run(item, chamar=False)], [item])["casos"][0]
            self.assertEqual(caso["resultado"], "APROVADO")
            self.assertEqual(caso["evidencia"], "NA")
            self.assertIsNone(caso["mock_confirmado"])

    def test_chamada_marcada_como_nao_executada_nao_comprova_mock(self):
        for opcional in (False, True):
            item = entrada(opcional=opcional)
            resposta = run(item)
            resposta["agent_responses"][0]["tool_calls"][-1]["tool_has_been_called"] = False
            with self.subTest(opcional=opcional), temporaria() as pasta:
                caso = self.gerar(pasta, [resposta], [item])["casos"][0]
                self.assertFalse(caso["ferramenta_chamada"])
                self.assertEqual(caso["resultado"], "APROVADO" if opcional else "REVISAR_EVIDENCIA")
                self.assertEqual(caso["evidencia"], "NA" if opcional else "INSUFICIENTE")

    def test_retorno_bloqueado_nao_comprova_mock_mesmo_com_json_igual(self):
        for opcional in (False, True):
            for chamada in (False, True):
                item = entrada(opcional=opcional)
                resposta = run(item)
                resposta["agent_responses"][0]["tool_calls"][-1]["tool_has_been_called"] = chamada
                resposta["agent_responses"][0]["tool_results"][-1]["is_blocked"] = True
                with self.subTest(opcional=opcional, chamada=chamada), temporaria() as pasta:
                    caso = self.gerar(pasta, [resposta], [item])["casos"][0]
                    self.assertEqual(caso["resultado"], "REVISAR_EVIDENCIA")
                    self.assertEqual(caso["ferramenta_chamada"], chamada)
                    self.assertFalse(caso["mock_confirmado"])

    def test_execucao_ausente_ou_duplicada_e_inconclusiva(self):
        item = entrada()
        for runs in ([], [run(item), run(item)]):
            with self.subTest(quantidade=len(runs)), temporaria() as pasta:
                resumo = self.gerar(pasta, runs, [item])
                self.assertEqual(resumo["casos"][0]["resultado"], "INCONCLUSIVO")
                self.assertEqual(resumo["visao_geral"]["cobertura_decisiva"], 0)
                self.assertIsNone(resumo["visao_geral"]["taxa_aprovacao_decisivos"])

    def test_lote_cancelado_so_classifica_ausentes_como_cancelados(self):
        item = entrada()
        for runs, esperado in (([], "CANCELADO"), ([run(item), run(item)], "INCONCLUSIVO"),
                               ([run(item)], "APROVADO")):
            dados = {**suite(runs), "cancelled": True}
            with self.subTest(quantidade=len(runs)), temporaria() as pasta:
                caso = gerar_relatorios(Path(pasta), dados, [item])["casos"][0]
                self.assertEqual(caso["resultado"], esperado)

    def test_mock_incorreto_requer_revisao_mesmo_com_grade_positivo(self):
        for opcional in (False, True):
            item = entrada(opcional=opcional)
            resposta = run(item)
            resposta["agent_responses"][0]["tool_results"][-1]["result_value"] = '{"outro":"valor"}'
            with self.subTest(opcional=opcional), temporaria() as pasta:
                caso = self.gerar(pasta, [resposta], [item])["casos"][0]
                self.assertEqual(caso["resultado"], "REVISAR_EVIDENCIA")
                self.assertFalse(caso["mock_confirmado"])

    def test_reprovacao_cancelamento_e_pendente(self):
        item = entrada()
        for status, grade, esperado in (("failed", "failure", "REPROVADO"),
                                        ("cancelled", "unknown", "CANCELADO"),
                                        ("pending", "unknown", "INCONCLUSIVO")):
            with self.subTest(status=status), temporaria() as pasta:
                caso = self.gerar(pasta, [run(item, status, grade)], [item])["casos"][0]
                self.assertEqual(caso["resultado"], esperado)

    def test_metadata_nova_versao_rascunho_e_ids_inesperados(self):
        item = entrada()
        principal = run(item)
        principal.update({"version_id": "v2", "ran_against_draft": True, "campo_futuro": {"novo": True}})
        extra = run(entrada(2))
        del extra["credits_used"]
        with temporaria() as pasta:
            resumo = self.gerar(pasta, [principal, extra], [item])
            alertas = " ".join(resumo["visao_geral"]["alertas"])
            self.assertIn("versão", alertas)
            self.assertIn("rascunho", alertas)
            self.assertIn("inesperados", alertas)
            self.assertEqual(resumo["visao_geral"]["total_sem_creditos"], 1)
            raw = json.loads((Path(pasta) / "resultado-completo.json").read_text("utf-8"))
            self.assertTrue(raw["test_runs"][0]["campo_futuro"]["novo"])
            self.assertEqual(resumo["casos"][0]["version_id"], "v2")

    def test_chamada_sem_retorno_nao_fica_aprovada(self):
        item = entrada()
        resposta = run(item)
        resposta["agent_responses"][0]["tool_results"] = []
        with temporaria() as pasta:
            caso = self.gerar(pasta, [resposta], [item])["casos"][0]
            self.assertEqual(caso["resultado"], "REVISAR_EVIDENCIA")

    def test_caminhos_invalidos_sao_rejeitados_antes_de_escrever(self):
        for identificador in ("../fora", "/absoluto", "C:\\fora", "CON", "..", "caso/"):
            item = entrada()
            item["caso"]["id"] = identificador
            with self.subTest(identificador=identificador), temporaria() as pasta:
                with self.assertRaises(ValueError):
                    self.gerar(pasta, [], [item])
                self.assertEqual(list(Path(pasta).iterdir()), [])
        itens = [entrada(1), entrada(2)]
        itens[0]["caso"]["id"], itens[1]["caso"]["id"] = "CASO", "caso"
        with temporaria() as pasta:
            with self.assertRaises(ValueError):
                self.gerar(pasta, [], itens)
            self.assertEqual(list(Path(pasta).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
