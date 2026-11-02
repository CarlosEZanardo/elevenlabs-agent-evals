"""Painel local, somente de leitura, dos lotes já executados.

Não importa o SDK nem carrega credenciais. A avaliação automática é preservada;
uma conversa exibida no painel não recebe uma nota humana por inferência.
"""

from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import streamlit as st

from dashboard_dados import descobrir_lotes, ler_detalhe


BASE = Path(__file__).resolve().parent
STATUS = {
    "APROVADO": "Aprovado", "REPROVADO": "Reprovado",
    "REVISAR_EVIDENCIA": "Revisar evidência", "INCONCLUSIVO": "Inconclusivo",
    "CANCELADO": "Cancelado",
}
CORES = {
    "Aprovado": "#148579", "Reprovado": "#D05D5D", "Revisar evidência": "#D59A33",
    "Inconclusivo": "#78889B", "Cancelado": "#B5BFCA", "Não informado": "#78889B",
}


def numero(valor, casas=0):
    """Não transforma informação ausente em zero."""
    if not isinstance(valor, (int, float)) or isinstance(valor, bool) or not math.isfinite(valor):
        return "—"
    return f"{valor:,.{casas}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def data_local(valor):
    try:
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        if data.tzinfo is None:
            return data.strftime("%d/%m/%Y · %H:%M") + " (fuso não informado)"
        return data.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y · %H:%M")
    except (ValueError, TypeError):
        return "Data não informada"


def nome_caso(caso):
    nome = str(caso.get("nome") or caso.get("caso_id") or "Cenário")
    partes = nome.split(" | ", 2)
    return partes[-1]


def identificador(lote):
    return lote["id_lote"]


def rotulo_lote(lote):
    return f"{lote.get('rotulo') or 'Sem rótulo'} · {data_local(lote.get('criado_em_utc'))}"


def resultado(caso):
    return STATUS.get(caso.get("resultado"), "Não informado")


def tabela_casos(casos):
    return pd.DataFrame([{
        "Caso": c.get("caso_id", "—")[:2],
        "Cenário": nome_caso(c),
        "Resultado automático": resultado(c),
        "Créditos": c.get("credits_used"),
        "Evidência da ferramenta": {"CONFIRMADA": "Confirmada", "NA": "Não exigida"}.get(c.get("evidencia"), c.get("evidencia") or "Não informada"),
        "Categoria": str(c.get("categoria") or "Não informada").replace("_", " "),
    } for c in casos])


def estilo():
    st.markdown("""<style>
    .stApp { background:#F6F8FA; }
    [data-testid="stSidebar"] { background:#EAF0F3; border-right:1px solid #DCE4EA; }
    .block-container { max-width:1500px; padding-top:4.2rem; padding-bottom:3rem; }
    h1 { font-weight:750!important; letter-spacing:-.045em!important; font-size:2.55rem!important; }
    h2 { letter-spacing:-.025em; }
    h3 { font-size:1.15rem!important; letter-spacing:-.015em; }
    .eyebrow { color:#0F766E; font-size:.76rem; font-weight:750; letter-spacing:.16em; margin-bottom:.35rem; }
    [data-testid="stMetric"] { background:white; border:1px solid #DFE7ED; border-radius:12px; padding:17px 19px; }
    [data-testid="stMetricLabel"] { color:#65758A; min-height:2.5rem; }
    [data-testid="stMetricLabel"] p { white-space:normal!important; overflow:visible!important; text-overflow:clip!important; }
    [data-testid="stMetricValue"] { font-size:1.85rem; font-weight:700; letter-spacing:-.035em; }
    [data-testid="stVerticalBlockBorderWrapper"] { border-radius:12px; }
    [data-testid="stChatMessage"] { border:1px solid #E4EAF0; border-radius:12px; background:#FFF; }
    [data-testid="stText"] { font-family:inherit; font-size:.95rem; line-height:1.6; white-space:pre-wrap; }
    @media (max-width:1050px) {
      [data-testid="stHorizontalBlock"] { flex-wrap:wrap; }
      [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex:1 1 220px!important; min-width:min(100%,220px)!important;
      }
    }
    </style>""", unsafe_allow_html=True)


def exibir_metricas(lote):
    casos = lote.get("casos", [])
    geral = lote.get("visao_geral") or {}
    aprovados = sum(c.get("resultado") == "APROVADO" for c in casos)
    decisivos = sum(c.get("resultado") in {"APROVADO", "REPROVADO"} for c in casos)
    planejados = geral.get("planejados")
    taxa = f"{aprovados / decisivos:.0%}" if decisivos else "—"
    cobertura = f"{decisivos / planejados:.0%}" if isinstance(planejados, int) and planejados > 0 else "—"
    cols = st.columns(4)
    cols[0].metric("Cenários planejados", numero(planejados))
    cols[1].metric("Aprovação automática", taxa, help=f"{aprovados} aprovados entre {decisivos} resultados decisivos. Inconclusivos, cancelados e evidências pendentes ficam fora desse denominador.")
    cols[2].metric("Cobertura decisiva", cobertura, help="Resultados aprovados ou reprovados / cenários planejados. Uma taxa de aprovação alta com baixa cobertura merece atenção.")
    cols[3].metric("Créditos informados", numero(geral.get("creditos_informados")), help="Consumo retornado nos relatórios. Não representa saldo da conta nem custo em reais.")
    if geral.get("total_sem_creditos"):
        st.caption(f"Consumo parcial: {geral['total_sem_creditos']} execução(ões) sem créditos informados.")


def graficos(casos):
    left, right = st.columns([.8, 1.4], gap="large")
    with left, st.container(border=True):
        st.subheader("Resultados automáticos")
        contagem = Counter(resultado(c) for c in casos)
        dados = pd.DataFrame([{"Resultado": nome, "Cenários": n} for nome, n in contagem.items()])
        chart = alt.Chart(dados).mark_arc(innerRadius=70, outerRadius=105).encode(
            theta=alt.Theta("Cenários:Q"),
            color=alt.Color("Resultado:N", scale=alt.Scale(domain=list(CORES), range=list(CORES.values())), legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Resultado:N", "Cenários:Q"],
        )
        centro = alt.Chart(pd.DataFrame([{"total": str(len(casos))}])).mark_text(fontSize=33, fontWeight=700, color="#182535").encode(text="total:N")
        st.altair_chart((chart + centro).properties(height=260), width="stretch")
        st.caption("A aprovação automática deve ser interpretada junto com a conversa e os critérios.")
    with right, st.container(border=True):
        st.subheader("Onde os créditos foram usados")
        custo = tabela_casos(casos).dropna(subset=["Créditos"])
        if custo.empty:
            st.info("Não há consumo informado para esta seleção.")
            return
        custo = custo.sort_values("Créditos", ascending=False).head(8).copy()
        custo["Identificação"] = custo["Caso"] + " · " + custo["Cenário"].str.slice(0, 35)
        barras = alt.Chart(custo).mark_bar(cornerRadiusEnd=4, color="#217F8E").encode(
            x=alt.X("Créditos:Q", title="Créditos informados"),
            y=alt.Y("Identificação:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)),
            tooltip=["Caso:N", "Cenário:N", "Créditos:Q", "Resultado automático:N"],
        ).properties(height=260)
        st.altair_chart(barras, width="stretch")
        st.caption("Até oito maiores consumos da seleção. Uma aprovação também pode ter custo elevado.")


def exibir_conversa(detalhe, chave):
    """Separa ferramentas das falas e usa a mesma contagem comprovada dos cartões."""
    mensagens = detalhe.get("mensagens") or []
    mostrar = st.toggle("Mostrar resumo das ferramentas", value=False, key=f"tools_{chave}")
    if mostrar:
        contagem = detalhe.get("contagem_ferramentas") or {}
        if contagem:
            st.dataframe(pd.DataFrame([{"Ferramenta": nome, "Chamadas executadas": n} for nome, n in contagem.items()]), hide_index=True, width="stretch")
        else:
            st.caption("Nenhuma chamada executada comprovada nos eventos disponíveis.")
    if not mensagens:
        st.text(detalhe.get("conversa") or "Conversa não disponível neste relatório.")
        return
    for m in mensagens:
        if not isinstance(m, dict):
            continue
        texto = m.get("message")
        if texto:
            role = "user" if m.get("role") == "user" else "assistant"
            with st.chat_message(role):
                st.text(str(texto))


def detalhe_caso(lote, casos):
    if not casos:
        return
    st.subheader("Abrir um cenário")
    mapa = {c["caso_id"]: c for c in casos}
    caso_id = st.selectbox("Cenário", list(mapa), format_func=lambda k: f"{k[:2]} · {nome_caso(mapa[k])}", key=f"detalhe_{identificador(lote)}")
    detalhe = ler_detalhe(BASE, identificador(lote), caso_id)
    caso = detalhe.get("caso") or mapa[caso_id]
    for aviso in detalhe.get("avisos", []):
        st.warning(aviso)
    c1, c2, c3 = st.columns(3)
    c1.metric("Resultado automático", resultado(caso))
    c2.metric("Créditos deste cenário", numero(caso.get("credits_used")))
    chamadas = detalhe.get("contagem_ferramentas") or {}
    transicoes = (sum(n for nome, n in chamadas.items() if nome.startswith("notify_condition_"))
                  if detalhe.get("mensagens") else None)
    c3.metric("Chamadas de transição", numero(transicoes), help="Chamadas de ferramentas de transição registradas nos eventos. Não é a contagem de nós únicos.")
    st.caption("Revisão humana: sem registro nos arquivos deste projeto.")
    if transicoes is not None and transicoes > 10:
        st.info(f"Este cenário registra {transicoes} chamadas de transição. Confira se a conversa avançou, mesmo com aprovação automática.")
    conversa, avaliacao, origem = st.tabs(["Conversa", "Critérios e avaliação", "Dados da execução"])
    with conversa:
        exibir_conversa(detalhe, f"{identificador(lote)}_{caso_id}")
        st.download_button("Baixar conversa", detalhe.get("conversa") or "", file_name=f"{caso_id}.txt", mime="text/plain", key=f"txt_{identificador(lote)}_{caso_id}")
    with avaliacao:
        st.markdown("**Critérios enviados nesta execução**")
        if detalhe.get("criterios"):
            for i, criterio in enumerate(detalhe["criterios"], 1):
                st.write(f"{i}. {criterio}")
        else:
            st.info("O snapshot dos critérios não está disponível.")
        st.markdown("**Justificativa automática**")
        st.text(caso.get("justificativa") or "Não informada.")
        with st.expander("Instruções do cliente simulado"):
            st.text(detalhe.get("roteiro") or "Não disponíveis.")
    with origem:
        st.write("**Modelo(s) registrado(s):** " + (", ".join(detalhe.get("modelos") or []) or "Não informados"))
        st.write("**Versão do agente:** " + str(caso.get("version_id") or "Não informada"))
        st.write("**Execução sobre rascunho:** " + ("Sim" if caso.get("ran_against_draft") is True else "Não" if caso.get("ran_against_draft") is False else "Não informado"))
        st.write("**Definição do teste:** " + str(caso.get("assinatura") or "Não informada"))
        st.json({"lote": identificador(lote), "rotulo": lote.get("rotulo"), "invocation_id": caso.get("invocation_id"), "test_id": caso.get("test_id"), "test_run_id": caso.get("test_run_id"), "evidencia": caso.get("evidencia"), "chamadas_ferramentas": chamadas}, expanded=False)
        st.download_button("Baixar execução sanitizada JSON", json.dumps(detalhe.get("resultado_completo") or {}, ensure_ascii=False, indent=2), file_name=f"{caso_id}-resultado.json", mime="application/json", key=f"json_{identificador(lote)}_{caso_id}")


def visao_lote(lote):
    st.subheader(lote.get("rotulo") or "Lote sem rótulo")
    st.caption(f"{data_local(lote.get('criado_em_utc'))} · Horário de Brasília · Conjunto de cenários {lote.get('suite_versao') or 'não informado'}")
    exibir_metricas(lote)
    for alerta in (lote.get("visao_geral") or {}).get("alertas", []):
        st.warning(alerta)
    todos = lote.get("casos") or []
    if not todos:
        st.info("Este lote ainda não tem resultados disponíveis.")
        return
    st.write("")
    graficos(todos)
    st.subheader("Cenários do lote")
    filtro1, filtro2 = st.columns(2)
    opcoes = list(dict.fromkeys(resultado(c) for c in todos))
    filtro = filtro1.multiselect("Resultado automático", opcoes, placeholder="Todos os resultados", key=f"status_{identificador(lote)}")
    busca = filtro2.text_input("Buscar cenário", placeholder="Nome, número ou categoria", key=f"busca_{identificador(lote)}").casefold().strip()
    casos = [c for c in todos if (not filtro or resultado(c) in filtro) and (not busca or busca in f"{c.get('caso_id','')} {nome_caso(c)} {c.get('categoria','')}".casefold())]
    if not casos:
        st.info("Nenhum cenário corresponde aos filtros. Limpe a busca ou o resultado selecionado.")
        return
    tabela = tabela_casos(casos)
    st.dataframe(tabela, hide_index=True, width="stretch", column_config={"Créditos": st.column_config.NumberColumn(format="localized"), "Cenário": st.column_config.TextColumn(width="large")})
    st.caption(f"Exibindo {len(casos)} de {len(todos)} cenários. Os cartões e gráficos acima representam o lote inteiro.")
    st.download_button("Baixar tabela filtrada CSV", tabela.to_csv(index=False, sep=";").encode("utf-8-sig"), file_name=f"{identificador(lote)}-cenarios.csv", mime="text/csv", key=f"csv_{identificador(lote)}")
    st.divider()
    detalhe_caso(lote, casos)


def comparar_lotes(lotes):
    st.subheader("Compare rodadas, preservando o contexto")
    st.caption("Um mesmo cenário pode ter critérios diferentes ao longo do tempo. A comparação indica quando a definição mudou.")
    mapa = {identificador(l): l for l in lotes}
    ids = list(mapa)
    a, b = st.columns(2)
    id_a = a.selectbox("Lote A", ids, format_func=lambda k: rotulo_lote(mapa[k]), key="comparar_a")
    id_b = b.selectbox("Lote B", ids, index=min(1, len(ids)-1), format_func=lambda k: rotulo_lote(mapa[k]), key="comparar_b")
    if id_a == id_b:
        st.info("Selecione dois lotes diferentes para comparar.")
        return
    lote_a, lote_b = mapa[id_a], mapa[id_b]
    ca = {c["caso_id"]: c for c in lote_a.get("casos", [])}
    cb = {c["caso_id"]: c for c in lote_b.get("casos", [])}
    comuns = sorted(set(ca) & set(cb))
    mesmos = [i for i in comuns if ca[i].get("assinatura") and ca[i].get("assinatura") == cb[i].get("assinatura")]
    st.write(f"**{len(comuns)} cenários em comum · {len(mesmos)} com definição idêntica.**")
    if len(mesmos) < len(comuns):
        st.info("Algumas definições dos testes são diferentes ou não foram informadas. Compare esses resultados considerando os critérios de cada execução.")
    if len(ca) != len(cb) or set(ca) != set(cb):
        st.caption(f"Cobertura diferente: A contém {len(ca)} cenários; B contém {len(cb)}. Taxas dos lotes inteiros usam bases diferentes.")
    linhas = []
    for i in sorted(set(ca) | set(cb)):
        aa, bb = ca.get(i), cb.get(i)
        mesma = bool(aa and bb and aa.get("assinatura") and aa.get("assinatura") == bb.get("assinatura"))
        definicao = ("Presente em um lote" if not aa or not bb else "Não informada"
                     if not aa.get("assinatura") or not bb.get("assinatura")
                     else "Idêntica" if mesma else "Alterada")
        linhas.append({"Caso": i[:2], "Cenário": nome_caso(aa or bb), "Resultado A": resultado(aa) if aa else "Ausente", "Resultado B": resultado(bb) if bb else "Ausente", "Créditos A": aa.get("credits_used") if aa else None, "Créditos B": bb.get("credits_used") if bb else None, "Definição": definicao})
    tabela = pd.DataFrame(linhas)
    somente_comuns = st.checkbox("Mostrar somente cenários em comum", value=True, key="somente_comuns")
    if somente_comuns:
        tabela = tabela[tabela["Caso"].isin([i[:2] for i in comuns])]
    st.dataframe(tabela, hide_index=True, width="stretch")
    st.download_button("Baixar comparação CSV", tabela.to_csv(index=False, sep=";").encode("utf-8-sig"), file_name="comparacao-lotes.csv", mime="text/csv", key="csv_comparacao")
    if not comuns:
        return
    st.markdown("**Conversa lado a lado**")
    escolhido = st.selectbox("Cenário para comparar", comuns, format_func=lambda k: f"{k[:2]} · {nome_caso(ca[k])}", key=f"comparar_caso_{id_a}_{id_b}")
    for coluna, lote, caso in zip(st.columns(2, gap="large"), [lote_a, lote_b], [ca[escolhido], cb[escolhido]]):
        with coluna, st.container(border=True):
            st.write("**" + rotulo_lote(lote) + "**")
            st.caption(f"{resultado(caso)} · {numero(caso.get('credits_used'))} créditos · Versão {caso.get('version_id') or 'não informada'}")
            detalhe = ler_detalhe(BASE, identificador(lote), escolhido)
            st.text(detalhe.get("conversa") or "Conversa não disponível.")
            with st.expander("Critérios desta execução"):
                for i, criterio in enumerate(detalhe.get("criterios") or [], 1):
                    st.write(f"{i}. {criterio}")


def main():
    st.set_page_config(page_title="Ponte Idiomas · Avaliações", page_icon="📊", layout="wide")
    estilo()
    with st.sidebar:
        st.markdown("### PONTE / EVALS")
        st.caption("Demonstração de um workflow de avaliação")
        st.button("Atualizar relatórios", width="stretch", help="Relê os arquivos locais. Não executa testes.")
    lotes, avisos = descobrir_lotes(BASE)
    with st.sidebar:
        st.caption(f"{len(lotes)} lotes encontrados")
        if not lotes:
            st.info("Os lotes aparecerão aqui depois de uma execução.")
        else:
            mapa = {identificador(l): l for l in lotes}
            selecionado = st.selectbox("Lote em foco", list(mapa), format_func=lambda k: rotulo_lote(mapa[k]), key="lote_foco")
            st.divider()
            st.caption("A atualização relê os lotes desta demonstração. Novas rodadas locais só aparecem aqui após revisão e publicação dos arquivos.")
    st.markdown('<div class="eyebrow">PONTE IDIOMAS · AVALIAÇÕES</div>', unsafe_allow_html=True)
    st.title("Do resultado à conversa")
    st.write("Explore as rodadas, compare os cenários e investigue as evidências do agente.")
    st.info("Case de estudo · resultados históricos sanitizados. Identificadores foram substituídos; avaliações, créditos e falas foram preservados, com remoção de dados pessoais. Este painel não inicia testes.")
    for aviso in avisos:
        st.warning(aviso)
    if not lotes:
        st.info("Ainda não há relatórios de lote para exibir. Execute os cenários pelo seu fluxo de avaliação e depois atualize esta página.")
        return
    visao, comparacao = st.tabs(["Visão do lote", "Comparar lotes"])
    with visao:
        visao_lote(mapa[selecionado])
    with comparacao:
        comparar_lotes(lotes)
    st.divider()
    st.caption("Fonte: relatórios locais dos testes por texto. Este painel não inicia simulações nem consulta a API da ElevenLabs.")


if __name__ == "__main__":
    main()
