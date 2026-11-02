"""Leitura local do dashboard: associação, dados ausentes e limites de arquivos."""

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard_dados import descobrir_lotes, ler_detalhe


def temporaria():
    return tempfile.TemporaryDirectory(prefix="dashboard-", dir=Path(__file__).resolve().parent)


def salvar(caminho, valor):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(valor, ensure_ascii=False), encoding="utf-8")


def exemplo():
    return {
        "caso_id": "01-caso", "nome": "Caso de catálogo", "categoria": "informação",
        "assinatura": "hash1", "resultado": "APROVADO", "credits_used": 12,
        "test_id": "test-1", "test_run_id": "run-1", "version_id": "versao-1",
        "ran_against_draft": False, "nos_vistos": ["informacoes"],
    }


def criar_lote(base, nome="lote_20261030T000627Z_abc", data="2026-10-30T00:06:27+00:00", casos=None):
    pasta = base / "lotes" / nome
    linhas = [exemplo()] if casos is None else casos
    salvar(pasta / "manifesto.json", {
        "rotulo": "Rodada controlada", "criado_em_utc": data,
        "suite_versao": "1.1", "assinatura_dataset": "dataset-1",
        "invocation_id": "suite-1", "fase": "finalizado",
    })
    salvar(pasta / "resumo.json", {
        "visao_geral": {
            "planejados": len(linhas), "por_resultado": {
                "APROVADO": len(linhas), "REPROVADO": 0, "REVISAR_EVIDENCIA": 0,
                "INCONCLUSIVO": 0, "CANCELADO": 0,
            },
            "taxa_aprovacao_decisivos": 1.0, "cobertura_decisiva": 1.0,
            "creditos_informados": sum(linha.get("credits_used", 0) for linha in linhas
                                       if isinstance(linha.get("credits_used"), (int, float))),
            "total_sem_creditos": 0, "alertas": [],
        }, "casos": linhas,
    })
    return pasta


def criar_detalhe(pasta, mensagens=None, runs=None):
    salvar(pasta / "entradas.json", [{"caso": {
        "id": "01-caso", "cenario": "Pergunte o preço e aceite a explicação.",
        "criterios_sucesso": ["Informar o preço correto.", "Não garantir vaga."],
    }}])
    caso = pasta / "casos" / "01-caso"
    caso.mkdir(parents=True, exist_ok=True)
    (caso / "conversa.txt").write_text("agent: Resposta pública.\n", encoding="utf-8")
    if runs is None:
        runs = [{"test_run_id": "run-1", "test_id": "test-1",
                 "agent_responses": mensagens or [],
                 "charging": {"llm_usage": {"model_usage": {"modelo-avaliador": {}}}}}]
    salvar(caso / "resultado-completo.json", {"invocation_id": "suite-1", "test_runs": runs})
    return caso


class DashboardDadosTest(unittest.TestCase):
    def test_inventario_de_varios_lotes_sem_reclassificacao(self):
        with temporaria() as temp:
            base = Path(temp)
            criar_lote(base, "lote_20261001T000000Z_a", "2026-10-01T00:00:00Z")
            segunda = exemplo()
            segunda.update(caso_id="02-caso", credits_used=24)
            criar_lote(base, "lote_20261002T000000Z_b", "2026-10-02T00:00:00Z", [exemplo(), segunda])
            lotes, avisos = descobrir_lotes(base)
            self.assertEqual(len(lotes), 2)
            self.assertEqual(sum(len(lote["casos"]) for lote in lotes), 3)
            self.assertEqual(sum(lote["visao_geral"]["creditos_informados"] for lote in lotes), 48)
            self.assertFalse(avisos)
            self.assertEqual(lotes[0]["id_lote"], "lote_20261002T000000Z_b")
            self.assertEqual(lotes[0]["visao_geral"]["por_resultado"]["APROVADO"], 2)
            self.assertNotIn("revisao_humana", lotes[0])
            self.assertNotIn("avaliacao_humana", lotes[0]["casos"][0])

    def test_descoberta_le_so_manifesto_e_resumo_e_copia_linhas(self):
        with temporaria() as temp:
            base = Path(temp)
            criar_lote(base)
            original = Path.read_text

            def leitura(caminho, *args, **kwargs):
                self.assertIn(caminho.name, {"manifesto.json", "resumo.json"})
                return original(caminho, *args, **kwargs)

            with patch.object(Path, "read_text", autospec=True, side_effect=leitura):
                lotes, avisos = descobrir_lotes(base)
            self.assertFalse(avisos)
            linha = lotes[0]["casos"][0]
            self.assertEqual(linha["lote_id"], lotes[0]["id_lote"])
            self.assertEqual(linha["rotulo_lote"], "Rodada controlada")
            self.assertEqual(lotes[0]["versoes"], ["versao-1"])
            self.assertIs(lotes[0]["rascunho"], False)
            linha["nos_vistos"].append("mutação-apenas-em-memória")
            novamente, _ = descobrir_lotes(base / "lotes")
            self.assertEqual(novamente[0]["casos"][0]["nos_vistos"], ["informacoes"])

    def test_ordenacao_usa_data_manifesto_e_nome_como_fallback(self):
        with temporaria() as temp:
            base = Path(temp)
            criar_lote(base, "lote_20260101T000000Z_a", "2026-12-01T00:00:00Z")
            criar_lote(base, "lote_20261101T000000Z_b", "data-inválida")
            criar_lote(base, "lote_20261001T000000Z_c", "2026-01-01T00:00:00Z")
            lotes, _ = descobrir_lotes(base)
            self.assertEqual([l["id_lote"] for l in lotes], [
                "lote_20260101T000000Z_a", "lote_20261101T000000Z_b", "lote_20261001T000000Z_c",
            ])

    def test_arquivos_parciais_e_dados_ausentes_nao_viram_zero(self):
        with temporaria() as temp:
            base = Path(temp)
            pasta = criar_lote(base)
            (pasta / "manifesto.json").write_text('{"rotulo":', encoding="utf-8")
            salvar(pasta / "resumo.json", {"casos": [{"caso_id": "01-caso"}]})
            lotes, avisos = descobrir_lotes(base)
            self.assertTrue(avisos)
            lote = lotes[0]
            self.assertIsNone(lote["rotulo"])
            self.assertIsNone(lote["visao_geral"]["taxa_aprovacao_decisivos"])
            self.assertIsNone(lote["visao_geral"]["por_resultado"]["APROVADO"])
            self.assertIsNone(lote["visao_geral"]["creditos_informados"])
            self.assertIsNone(lote["casos"][0]["resultado"])
            self.assertIsNone(lote["casos"][0]["credits_used"])
            self.assertIsNone(lote["rascunho"])
            (pasta / "resumo.json").unlink()
            novamente, avisos = descobrir_lotes(base)
            self.assertTrue(avisos)
            self.assertEqual(novamente[0]["casos"], [])

    def test_zero_medido_e_desconhecido_continuam_diferentes(self):
        with temporaria() as temp:
            base = Path(temp)
            pasta = criar_lote(base)
            salvar(pasta / "resumo.json", {
                "visao_geral": {"planejados": 1, "por_resultado": {"APROVADO": 0},
                               "taxa_aprovacao_decisivos": 0, "cobertura_decisiva": 0,
                               "creditos_informados": 0, "total_sem_creditos": 1},
                "casos": [{"caso_id": "01-caso", "resultado": "INCONCLUSIVO", "credits_used": None}],
            })
            lotes, _ = descobrir_lotes(base)
            v = lotes[0]["visao_geral"]
            self.assertEqual(v["taxa_aprovacao_decisivos"], 0)
            self.assertEqual(v["por_resultado"]["APROVADO"], 0)
            self.assertIsNone(v["por_resultado"]["REPROVADO"])
            self.assertEqual(v["creditos_informados"], 0)
            self.assertIsNone(lotes[0]["casos"][0]["credits_used"])

    def test_detalhe_associa_run_modelos_so_agente_e_conta_top_level(self):
        with temporaria() as temp:
            base = Path(temp)
            pasta = criar_lote(base)
            mensagens = [
                {"role": "agent", "message": "Resposta pública.", "producing_llm": "modelo-gerador",
                 "tool_calls": [
                     {"tool_name": "consultar_cursos", "request_id": "q", "tool_has_been_called": True},
                     {"tool_name": "notify_condition_1_met", "request_id": "e", "tool_has_been_called": True},
                     {"tool_name": "bloqueada", "request_id": "b", "tool_has_been_called": False},
                     {"tool_name": "antiga", "request_id": "a"},
                     {"tool_name": "sem-prova", "request_id": "x"}],
                 "tool_results": [
                     {"tool_name": "antiga", "request_id": "a", "tool_has_been_called": True},
                     {"tool_name": "notify_condition_1_met", "request_id": "e", "tool_has_been_called": True,
                      "result": {"steps": [{"nested_tools": {"requests": [
                          {"tool_name": "transfer_to_agent", "tool_has_been_called": True}]}}]}}]},
                {"role": "user", "message": "Pergunta.", "producing_llm": "modelo-usuario",
                 "llm_usage": {"model_usage": {"modelo-usuario-uso": {}}},
                 "tool_calls": [{"tool_name": "falsa-do-usuario", "tool_has_been_called": True}]},
                {"role": "agent", "message": "Continuação.", "tool_results": 42,
                 "llm_usage": {"model_usage": {"modelo-uso": {}},
                               "detailed_model_usage": [{"config": {"model": "modelo-config"}}]},
                 "tool_calls": [
                     {"tool_name": "consultar_cursos", "request_id": "q", "tool_has_been_called": True},
                     {"tool_name": "sem-id", "tool_has_been_called": True},
                     {"tool_name": "sem-id", "tool_has_been_called": True}]},
            ]
            criar_detalhe(pasta, runs=[
                {"test_run_id": "outro-run", "agent_responses": [{"role": "agent", "message": "Errado."}]},
                {"test_run_id": "run-1", "test_id": "test-1", "agent_responses": mensagens,
                 "charging": {"model_usage": {"modelo-avaliador": {}}}},
            ])
            detalhe = ler_detalhe(base, pasta.name, "01-caso")
            self.assertEqual(detalhe["mensagens"], mensagens)
            self.assertEqual(detalhe["modelos"], ["modelo-config", "modelo-gerador", "modelo-uso"])
            self.assertEqual(detalhe["contagem_ferramentas"], {
                "antiga": 1, "consultar_cursos": 1, "notify_condition_1_met": 1, "sem-id": 2,
            })
            self.assertIn("preço", detalhe["criterios"][0])
            self.assertIn("Pergunte", detalhe["roteiro"])
            self.assertIn("Resposta pública", detalhe["conversa"])
            self.assertIs(detalhe["aviso"], detalhe["avisos"])
            self.assertTrue(any("sem comprovação" in a for a in detalhe["avisos"]))

    def test_transicoes_repetidas_contadas_sem_reclassificar_resultado(self):
        with temporaria() as temp:
            base = Path(temp)
            pasta = criar_lote(base)
            mensagens = [
                {"role": "agent", "producing_llm": "modelo-gerador", "tool_calls": [{
                    "tool_name": "notify_condition_1_met", "request_id": "primeira",
                    "tool_has_been_called": True}]},
                {"role": "agent", "producing_llm": "modelo-gerador", "tool_calls": [{
                    "tool_name": "notify_condition_1_met", "request_id": "segunda",
                    "tool_has_been_called": True}]},
                {"role": "agent", "producing_llm": "modelo-gerador", "message": "Resposta correta."},
            ]
            criar_detalhe(pasta, mensagens=mensagens)
            detalhe = ler_detalhe(base, pasta.name, "01-caso")
            self.assertFalse(detalhe["avisos"])
            self.assertEqual(detalhe["caso"]["resultado"], "APROVADO")
            self.assertEqual(detalhe["contagem_ferramentas"]["notify_condition_1_met"], 2)
            self.assertEqual(detalhe["modelos"], ["modelo-gerador"])
            self.assertNotIn("modelo-avaliador", detalhe["modelos"])

    def test_travessia_identificadores_reservados_e_caso_nao_autorizado(self):
        with temporaria() as temp:
            base = Path(temp)
            pasta = criar_lote(base)
            criar_detalhe(pasta)
            for lote_id, caso_id in [("../fora", "01-caso"), (pasta.name, "../01-caso"),
                                     (pasta.name, "C:\\fora"), (pasta.name, "CON"),
                                     (pasta.name, "02-nao-listado")]:
                with self.subTest(lote=lote_id, caso=caso_id):
                    detalhe = ler_detalhe(base, lote_id, caso_id)
                    self.assertTrue(detalhe["avisos"])
                    self.assertIsNone(detalhe["caso"])
                    self.assertEqual(detalhe["resultado_completo"], {})

    def test_symlink_para_fora_nao_e_lido(self):
        with temporaria() as temp:
            base = Path(temp) / "projeto"
            pasta = criar_lote(base)
            criar_detalhe(pasta)
            fora = Path(temp) / "nao-permitido.json"
            salvar(fora, {"segredo": "valor-que-nao-deve-ser-lido"})
            alvo = pasta / "casos" / "01-caso" / "resultado-completo.json"
            alvo.unlink()
            try:
                alvo.symlink_to(fora)
            except OSError as exc:
                self.skipTest(f"Criação de symlink indisponível neste Windows: {exc}")
            detalhe = ler_detalhe(base, pasta.name, "01-caso")
            self.assertEqual(detalhe["resultado_completo"], {})
            self.assertTrue(detalhe["avisos"])
            # A descoberta também não segue uma pasta de lote fora da raiz.
            externo = Path(temp) / "lote_externo"
            externo.mkdir()
            (base / "lotes" / "lote_symlink").symlink_to(externo, target_is_directory=True)
            lotes, avisos = descobrir_lotes(base)
            self.assertEqual(len(lotes), 1)
            self.assertTrue(any("lote_symlink" in a for a in avisos))

    def test_destino_resolvido_fora_da_raiz_e_bloqueado_sem_privilegio_de_symlink(self):
        # Simula só o destino que o Windows devolveria para o link. Assim o
        # controle de resolução é exercitado mesmo sem privilégio de symlink.
        with temporaria() as temp:
            base = Path(temp) / "projeto"
            pasta = criar_lote(base)
            caso = criar_detalhe(pasta)
            alvo = caso / "resultado-completo.json"
            fora = Path(temp) / "fora.json"
            salvar(fora, {"segredo": "não deve ser aberto"})
            original_resolve, original_read = Path.resolve, Path.read_text

            def resolver(caminho, *args, **kwargs):
                if caminho == alvo:
                    return original_resolve(fora)
                return original_resolve(caminho, *args, **kwargs)

            def ler(caminho, *args, **kwargs):
                self.assertNotEqual(caminho, original_resolve(fora))
                return original_read(caminho, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=resolver), \
                    patch.object(Path, "read_text", autospec=True, side_effect=ler):
                detalhe = ler_detalhe(base, pasta.name, "01-caso")
            self.assertEqual(detalhe["resultado_completo"], {})
            self.assertTrue(detalhe["avisos"])

    def test_jsons_corrompidos_e_estruturas_inesperadas_nao_derrubam_detalhe(self):
        with temporaria() as temp:
            base = Path(temp)
            pasta = criar_lote(base)
            caso = criar_detalhe(pasta)
            (pasta / "entradas.json").write_text("incompleto", encoding="utf-8")
            (caso / "resultado-completo.json").write_text("{", encoding="utf-8")
            detalhe = ler_detalhe(base, pasta.name, "01-caso")
            self.assertEqual(detalhe["caso"]["resultado"], "APROVADO")
            self.assertTrue(detalhe["avisos"])
            self.assertEqual(detalhe["mensagens"], [])
            salvar(caso / "resultado-completo.json", {"test_runs": {"errado": True}})
            self.assertTrue(ler_detalhe(base, pasta.name, "01-caso")["avisos"])

    def test_duplicatas_e_colisao_de_pastas_nao_associam_caso_ambiguo(self):
        with temporaria() as temp:
            base = Path(temp)
            primeira, segunda = exemplo(), exemplo()
            segunda["caso_id"] = "01-CASO"
            pasta = criar_lote(base, casos=[primeira, segunda])
            lotes, avisos = descobrir_lotes(base)
            self.assertEqual(lotes[0]["casos"], [])
            self.assertTrue(avisos)
            detalhe = ler_detalhe(base, pasta.name, "01-caso")
            self.assertIsNone(detalhe["caso"])

    def test_rascunho_misto_e_valores_invalidos_ficam_explicitos(self):
        with temporaria() as temp:
            base = Path(temp)
            primeira, segunda = exemplo(), exemplo()
            segunda.update(caso_id="02-caso", ran_against_draft=True, version_id="versao-2",
                           credits_used="não medido", categoria={"invalido": True})
            criar_lote(base, casos=[primeira, segunda])
            lotes, avisos = descobrir_lotes(base)
            self.assertIs(lotes[0]["rascunho"], True)
            self.assertEqual(lotes[0]["versoes"], ["versao-1", "versao-2"])
            self.assertIsNone(lotes[0]["casos"][1]["credits_used"])
            self.assertIsNone(lotes[0]["casos"][1]["categoria"])
            self.assertTrue(any("rascunho e publicados" in a for a in avisos))


if __name__ == "__main__":
    unittest.main()
