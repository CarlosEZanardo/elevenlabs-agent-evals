"""Read-only dashboard for completed evaluation batches.

Does not import the SDK or load credentials. Automated outcomes are preserved;
displaying a conversation does not create an inferred human-review grade.
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

from dashboard_data import discover_batches, read_detail


BASE = Path(__file__).resolve().parent
STATUS = {
    "PASSED": "Passed", "FAILED": "Failed",
    "REVIEW_EVIDENCE": "Review evidence", "INCONCLUSIVE": "Inconclusive",
    "CANCELLED": "Cancelled",
}
COLORS = {
    "Passed": "#148579", "Failed": "#D05D5D", "Review evidence": "#D59A33",
    "Inconclusive": "#78889B", "Cancelled": "#B5BFCA", "Not reported": "#78889B",
}


def number(value, decimals=0):
    """Keep missing measurements distinct from zero."""
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        return "—"
    return f"{value:,.{decimals}f}"


def local_date(value):
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return timestamp.strftime("%b %d, %Y · %H:%M") + " (time zone not specified)"
        return timestamp.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%b %d, %Y · %H:%M")
    except (ValueError, TypeError):
        return "Date not provided"


def case_name(case):
    name = str(case.get("name") or case.get("case_id") or "Scenario")
    parts = name.split(" | ", 2)
    return parts[-1]


def identifier(batch):
    return batch["batch_id"]


def batch_label(batch):
    return f"{batch.get('label') or 'Unlabeled'} · {local_date(batch.get('created_at_utc'))}"


def outcome(case):
    return STATUS.get(case.get("outcome"), "Not reported")


def case_table(cases):
    return pd.DataFrame([{
        "Case": c.get("case_id", "—")[:2],
        "Scenario": case_name(c),
        "Automated outcome": outcome(c),
        "Credits": c.get("credits_used"),
        "Tool evidence": {"CONFIRMED": "Confirmed", "NA": "Not required"}.get(c.get("evidence"), c.get("evidence") or "Not reported"),
        "Category": str(c.get("category") or "Not reported").replace("_", " "),
    } for c in cases])


def style():
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


def show_metrics(batch):
    cases = batch.get("cases", [])
    overview = batch.get("overview") or {}
    passed = sum(c.get("outcome") == "PASSED" for c in cases)
    decisive = sum(c.get("outcome") in {"PASSED", "FAILED"} for c in cases)
    planned = overview.get("planned")
    pass_rate = f"{passed / decisive:.0%}" if decisive else "—"
    coverage = f"{decisive / planned:.0%}" if isinstance(planned, int) and planned > 0 else "—"
    cols = st.columns(4)
    cols[0].metric("Planned scenarios", number(planned))
    cols[1].metric("Automated pass rate", pass_rate, help=f"{passed} passed out of {decisive} decisive outcomes. Inconclusive, cancelled and evidence-review outcomes are excluded from this denominator.")
    cols[2].metric("Decisive coverage", coverage, help="Passed or failed outcomes / planned scenarios. A high pass rate with low coverage needs review.")
    cols[3].metric("Credits reported", number(overview.get("reported_credits")), help="Usage reported in the results. This is not the account balance or a cost in BRL.")
    if overview.get("total_without_credits"):
        st.caption(f"Partial usage: {overview['total_without_credits']} run(s) have no reported credit usage.")


def charts(cases):
    left, right = st.columns([.8, 1.4], gap="large")
    with left, st.container(border=True):
        st.subheader("Automated outcomes")
        counts = Counter(outcome(c) for c in cases)
        data = pd.DataFrame([{"Outcome": name, "Scenarios": n} for name, n in counts.items()])
        chart = alt.Chart(data).mark_arc(innerRadius=70, outerRadius=105).encode(
            theta=alt.Theta("Scenarios:Q"),
            color=alt.Color("Outcome:N", scale=alt.Scale(domain=list(COLORS), range=list(COLORS.values())), legend=alt.Legend(orient="bottom", title=None)),
            tooltip=["Outcome:N", "Scenarios:Q"],
        )
        center = alt.Chart(pd.DataFrame([{"total": str(len(cases))}])).mark_text(fontSize=33, fontWeight=700, color="#182535").encode(text="total:N")
        st.altair_chart((chart + center).properties(height=260), width="stretch")
        st.caption("Review automated outcomes alongside the conversation and criteria.")
    with right, st.container(border=True):
        st.subheader("Where credits were used")
        costs = case_table(cases).dropna(subset=["Credits"])
        if costs.empty:
            st.info("No credit usage is reported for this selection.")
            return
        costs = costs.sort_values("Credits", ascending=False).head(8).copy()
        costs["Scenario label"] = costs["Case"] + " · " + costs["Scenario"].str.slice(0, 35)
        bars = alt.Chart(costs).mark_bar(cornerRadiusEnd=4, color="#217F8E").encode(
            x=alt.X("Credits:Q", title="Credits reported"),
            y=alt.Y("Scenario label:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)),
            tooltip=["Case:N", "Scenario:N", "Credits:Q", "Automated outcome:N"],
        ).properties(height=260)
        st.altair_chart(bars, width="stretch")
        st.caption("Up to eight highest-usage scenarios in the selection. A passing outcome can still be expensive.")


def show_conversation(detail, key):
    """Separate tool events from dialogue, using the same verified counts as the metrics."""
    messages = detail.get("messages") or []
    show = st.toggle("Show tool summary", value=False, key=f"tools_{key}")
    if show:
        counts = detail.get("tool_counts") or {}
        if counts:
            st.dataframe(pd.DataFrame([{"Tool": name, "Executed calls": n} for name, n in counts.items()]), hide_index=True, width="stretch")
        else:
            st.caption("No executed calls are confirmed by the available events.")
    if not messages:
        st.text(detail.get("conversation") or "Conversation unavailable in this report.")
        return
    for m in messages:
        if not isinstance(m, dict):
            continue
        text = m.get("message")
        if text:
            role = "user" if m.get("role") == "user" else "assistant"
            with st.chat_message(role):
                st.text(str(text))


def case_detail(batch, cases):
    if not cases:
        return
    st.subheader("Open a scenario")
    lookup = {c["case_id"]: c for c in cases}
    case_id = st.selectbox("Scenario", list(lookup), format_func=lambda k: f"{k[:2]} · {case_name(lookup[k])}", key=f"detail_{identifier(batch)}")
    detail = read_detail(BASE, identifier(batch), case_id)
    case = detail.get("case") or lookup[case_id]
    for warning in detail.get("warnings", []):
        st.warning(warning)
    c1, c2, c3 = st.columns(3)
    c1.metric("Automated outcome", outcome(case))
    c2.metric("Credits for this scenario", number(case.get("credits_used")))
    calls = detail.get("tool_counts") or {}
    transitions = (sum(n for name, n in calls.items() if name.startswith("notify_condition_"))
                  if detail.get("messages") else None)
    c3.metric("Transition calls", number(transitions), help="Transition tool calls recorded in the events. This is not a count of unique nodes.")
    st.caption("Human review: no structured review record is stored in this project.")
    if transitions is not None and transitions > 10:
        st.info(f"This scenario records {transitions} transition calls. Check whether the conversation progressed despite the automated pass.")
    conversation, evaluation, source = st.tabs(["Conversation", "Criteria and evaluation", "Run data"])
    with conversation:
        show_conversation(detail, f"{identifier(batch)}_{case_id}")
        st.download_button("Download conversation", detail.get("conversation") or "", file_name=f"{case_id}.txt", mime="text/plain", key=f"txt_{identifier(batch)}_{case_id}")
    with evaluation:
        st.markdown("**Criteria submitted for this run**")
        if detail.get("criteria"):
            for i, criterion in enumerate(detail["criteria"], 1):
                st.write(f"{i}. {criterion}")
        else:
            st.info("The criteria snapshot is unavailable.")
        st.markdown("**Automated rationale**")
        st.text(case.get("rationale_text") or "Not reported.")
        with st.expander("Simulated customer instructions"):
            st.text(detail.get("script") or "Not available.")
    with source:
        st.write("**Recorded model(s):** " + (", ".join(detail.get("models") or []) or "Not reported"))
        st.write("**Agent version:** " + str(case.get("version_id") or "Not reported"))
        st.write("**Run against draft:** " + ("Yes" if case.get("ran_against_draft") is True else "No" if case.get("ran_against_draft") is False else "Not reported"))
        st.write("**Test definition:** " + str(case.get("signature") or "Not reported"))
        st.json({"batch": identifier(batch), "label": batch.get("label"), "invocation_id": case.get("invocation_id"), "test_id": case.get("test_id"), "test_run_id": case.get("test_run_id"), "evidence": case.get("evidence"), "tool_calls_detail": calls}, expanded=False)
        st.download_button("Download sanitized run JSON", json.dumps(detail.get("full_result") or {}, ensure_ascii=False, indent=2), file_name=f"{case_id}-outcome.json", mime="application/json", key=f"json_{identifier(batch)}_{case_id}")


def batch_overview(batch):
    st.subheader(batch.get("label") or "Unlabeled batch")
    st.caption(f"{local_date(batch.get('created_at_utc'))} · São Paulo time · Scenario suite {batch.get('suite_version') or 'not reported'}")
    if batch.get("translation_note"):
        st.info(batch["translation_note"])
    show_metrics(batch)
    for alert in (batch.get("overview") or {}).get("alerts", []):
        st.warning(alert)
    all_cases = batch.get("cases") or []
    if not all_cases:
        st.info("No results are available for this batch yet.")
        return
    st.write("")
    charts(all_cases)
    st.subheader("Batch scenarios")
    outcome_filter, search_filter = st.columns(2)
    options = list(dict.fromkeys(outcome(c) for c in all_cases))
    selected_outcomes = outcome_filter.multiselect("Automated outcome", options, placeholder="All outcomes", key=f"status_{identifier(batch)}")
    search = search_filter.text_input("Search scenarios", placeholder="Name, number or category", key=f"search_{identifier(batch)}").casefold().strip()
    cases = [c for c in all_cases if (not selected_outcomes or outcome(c) in selected_outcomes) and (not search or search in f"{c.get('case_id','')} {case_name(c)} {c.get('category','')}".casefold())]
    if not cases:
        st.info("No scenarios match the filters. Clear the search or selected outcome.")
        return
    table = case_table(cases)
    st.dataframe(table, hide_index=True, width="stretch", column_config={"Credits": st.column_config.NumberColumn(format="%.0f"), "Scenario": st.column_config.TextColumn(width="large")})
    st.caption(f"Showing {len(cases)} of {len(all_cases)} scenarios. The metrics and charts above represent the entire batch.")
    st.download_button("Download filtered table CSV", table.to_csv(index=False).encode("utf-8-sig"), file_name=f"{identifier(batch)}-scenarios.csv", mime="text/csv", key=f"csv_{identifier(batch)}")
    st.divider()
    case_detail(batch, cases)


def compare_batches(batches):
    st.subheader("Compare batches in context")
    st.caption("A scenario can have different criteria over time. This comparison identifies changes to the test definition.")
    lookup = {identifier(l): l for l in batches}
    ids = list(lookup)
    a, b = st.columns(2)
    id_a = a.selectbox("Batch A", ids, format_func=lambda k: batch_label(lookup[k]), key="compare_a")
    id_b = b.selectbox("Batch B", ids, index=min(1, len(ids)-1), format_func=lambda k: batch_label(lookup[k]), key="compare_b")
    if id_a == id_b:
        st.info("Select two different batches to compare.")
        return
    batch_a, batch_b = lookup[id_a], lookup[id_b]
    ca = {c["case_id"]: c for c in batch_a.get("cases", [])}
    cb = {c["case_id"]: c for c in batch_b.get("cases", [])}
    shared = sorted(set(ca) & set(cb))
    identical = [i for i in shared if ca[i].get("signature") and ca[i].get("signature") == cb[i].get("signature")]
    st.write(f"**{len(shared)} shared scenarios · {len(identical)} with identical definitions.**")
    if len(identical) < len(shared):
        st.info("Some test definitions differ or are unavailable. Interpret these results using the criteria from each run.")
    if len(ca) != len(cb) or set(ca) != set(cb):
        st.caption(f"Coverage differs: A contains {len(ca)} scenarios; B contains {len(cb)}. Whole-batch rates use different denominators.")
    rows = []
    for i in sorted(set(ca) | set(cb)):
        case_a, case_b = ca.get(i), cb.get(i)
        same_definition = bool(case_a and case_b and case_a.get("signature") and case_a.get("signature") == case_b.get("signature"))
        definition = ("Present in one batch" if not case_a or not case_b else "Not reported"
                     if not case_a.get("signature") or not case_b.get("signature")
                     else "Identical" if same_definition else "Changed")
        rows.append({"Case": i[:2], "Scenario": case_name(case_a or case_b), "Outcome A": outcome(case_a) if case_a else "Missing", "Outcome B": outcome(case_b) if case_b else "Missing", "Credits A": case_a.get("credits_used") if case_a else None, "Credits B": case_b.get("credits_used") if case_b else None, "Definition": definition})
    table = pd.DataFrame(rows)
    shared_only = st.checkbox("Show shared scenarios only", value=True, key="shared_only")
    if shared_only:
        table = table[table["Case"].isin([i[:2] for i in shared])]
    st.dataframe(table, hide_index=True, width="stretch")
    st.download_button("Download comparison CSV", table.to_csv(index=False).encode("utf-8-sig"), file_name="batch-comparison.csv", mime="text/csv", key="csv_comparison")
    if not shared:
        return
    st.markdown("**Side-by-side conversation**")
    selected_case = st.selectbox("Scenario to compare", shared, format_func=lambda k: f"{k[:2]} · {case_name(ca[k])}", key=f"compare_case_{id_a}_{id_b}")
    for column, batch, case in zip(st.columns(2, gap="large"), [batch_a, batch_b], [ca[selected_case], cb[selected_case]]):
        with column, st.container(border=True):
            st.write("**" + batch_label(batch) + "**")
            if batch.get("translation_note"):
                st.caption(batch["translation_note"])
            st.caption(f"{outcome(case)} · {number(case.get('credits_used'))} credits · Version {case.get('version_id') or 'not reported'}")
            detail = read_detail(BASE, identifier(batch), selected_case)
            st.text(detail.get("conversation") or "Conversation unavailable.")
            with st.expander("Criteria for this run"):
                for i, criterion in enumerate(detail.get("criteria") or [], 1):
                    st.write(f"{i}. {criterion}")


def main():
    st.set_page_config(page_title="Ponte Idiomas · Evals", page_icon="📊", layout="wide")
    style()
    with st.sidebar:
        st.markdown("### PONTE / EVALS")
        st.caption("Evaluation workflow demonstration")
        st.button("Refresh reports", width="stretch", help="Reloads local files without running tests.")
    batches, warnings = discover_batches(BASE)
    with st.sidebar:
        st.caption(f"{len(batches)} batches found")
        if not batches:
            st.info("Batches will appear here after a run.")
        else:
            lookup = {identifier(l): l for l in batches}
            selected_batch = st.selectbox("Selected batch", list(lookup), format_func=lambda k: batch_label(lookup[k]), key="selected_batch")
            st.divider()
            st.caption("Refresh reloads this demonstration’s batches. New local runs appear here after their files are reviewed and published.")
    st.markdown('<div class="eyebrow">PONTE IDIOMAS · EVALS</div>', unsafe_allow_html=True)
    st.title("From outcome to conversation")
    st.write("Explore batches, compare scenarios and investigate the agent’s evidence.")
    st.info("Read-only evaluation reports. Opening this dashboard does not start tests. Review automated outcomes alongside their evidence.")
    for warning in warnings:
        st.warning(warning)
    if not batches:
        st.info("No batch reports are available yet. Run scenarios through your evaluation workflow, then refresh this page.")
        return
    overview_tab, comparison_tab = st.tabs(["Batch overview", "Compare batches"])
    with overview_tab:
        batch_overview(lookup[selected_batch])
    with comparison_tab:
        compare_batches(batches)
    st.divider()
    st.caption("Source: local text-test reports. This dashboard does not start simulations or query the ElevenLabs API.")


if __name__ == "__main__":
    main()
