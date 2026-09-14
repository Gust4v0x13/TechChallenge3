"""
Generates the executive-deck chart set (PNG, visualization/figures/) from
the reproducible business-question answers in data/gold/business_answers/
(produced by scripts/business_analysis.py, which reads Gold only).

Plotting is done with matplotlib + seaborn: seaborn draws the marks
(sns.barplot / sns.lineplot) onto axes we size and save ourselves, using
the fixed categorical/sequential/diverging palette from chart_style.py
(the dataviz skill's validated default). Value labels are added with
matplotlib's Axes.bar_label via chart_style.label_bars, one call per
chart instead of a manual per-bar loop.

Each chart function documents the business question it answers, the exact
Gold-derived CSV it reads, and any caveat that must travel with it into
the presentation (per documentation/analytical_domains.md /
data_quality_report.md — sample vs market size, structural NULLs,
DATABASE-only technology scope, Year1 AI N/A, salary-band quantization).

Every function returns its `fig` (does not close it) so it can also be
called directly, inline, from visualization/chart_generation.ipynb — the
notebook's %matplotlib inline backend renders it automatically at the end
of the cell. When run as a script (see __main__ below) each fig is closed
after saving to avoid accumulating open figures.

Run:
    cd state-of-data-tech-challenge/scripts
    source ../.venv/bin/activate
    python3 business_analysis.py   # regenerates data/gold/business_answers/
    python3 generate_charts.py     # regenerates visualization/figures/*.png
"""
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from chart_style import (
    CATEGORICAL, SEQUENTIAL_BLUE, DIVERGING_NEGATIVE, DIVERGING_POSITIVE, DIVERGING_MIDPOINT,
    INK_PRIMARY, INK_SECONDARY, INK_MUTED, apply_style, style_horizontal_bar_axes,
    style_vertical_bar_axes, savefig, label_bars,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
ANSWERS = REPO_ROOT / "data/gold/business_answers"
FIGURES = REPO_ROOT / "visualization/figures"
FIGURES.mkdir(parents=True, exist_ok=True)

apply_style()

YEAR_LABELS = {"year_1": "Pesquisa 1 (2021-22)", "year_2": "Pesquisa 2 (2023-24)", "year_3": "Pesquisa 3 (2025-26)"}
YEAR_COLOR = {"year_1": CATEGORICAL[0], "year_2": CATEGORICAL[2], "year_3": CATEGORICAL[7]}  # blue / aqua / red - fixed, never re-cycled
# same mapping, keyed by the PT-BR display label — seaborn's hue/legend use the display label directly
YEAR_COLOR_LABELED = {YEAR_LABELS[k]: v for k, v in YEAR_COLOR.items()}

GENDER_LABELS = {"MALE": "Masculino", "FEMALE": "Feminino", "OTHER": "Outro", "NOT_INFORMED": "Não informado"}
GENDER_COLOR = {"MALE": CATEGORICAL[0], "FEMALE": CATEGORICAL[4], "OTHER": CATEGORICAL[3], "NOT_INFORMED": CATEGORICAL[6]}
GENDER_COLOR_LABELED = {GENDER_LABELS[k]: v for k, v in GENDER_COLOR.items()}


def pct(ax, axis="x"):
    fmt = plt.FuncFormatter(lambda v, _: f"{v*100:.0f}%")
    (ax.xaxis if axis == "x" else ax.yaxis).set_major_formatter(fmt)


def with_year_label(df, col="survey_year"):
    """Adds a `<col>_label` column mapping year_1/2/3 -> the PT-BR display
    label, so seaborn's hue/legend show the readable label directly
    instead of the raw code (and we never need a manual legend remap)."""
    out = df.copy()
    out[f"{col}_label"] = out[col].map(YEAR_LABELS)
    return out


# ---------------------------------------------------------------------------
# Q1 - Estrutura do mercado
# Source: q1_market_structure_seniority.csv, q1_market_structure_current_work_model.csv
# Caveat: barras representam participação dentro do ano (share_within_year),
# nunca comparar como "crescimento do mercado" - amostras diferentes por ano.
# ---------------------------------------------------------------------------
def chart_q1_seniority_mix():
    df = pd.read_csv(ANSWERS / "q1_market_structure_seniority.csv")
    order = ["JUNIOR", "MID", "SENIOR", "SPECIALIST"]  # UNKNOWN (structural, ~28-30%) excluded - see caption
    df = df[df["dimension_value"].isin(order)]
    years = [c for c in df.columns if c.startswith("year_")]
    labels_pt = {"JUNIOR": "Júnior", "MID": "Pleno", "SENIOR": "Sênior", "SPECIALIST": "Especialista"}
    df["dimension_label"] = df["dimension_value"].map(labels_pt)

    long = df.melt(id_vars="dimension_label", value_vars=years, var_name="survey_year", value_name="value").dropna(subset=["value"])
    long = with_year_label(long)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.barplot(
        data=long, x="dimension_label", y="value", hue="survey_year_label",
        order=[labels_pt[o] for o in order], hue_order=[YEAR_LABELS[y] for y in years],
        palette=YEAR_COLOR_LABELED, ax=ax,
    )
    label_bars(ax, fmt=lambda v: f"{v*100:.0f}%")
    ax.set_xlabel("")
    ax.set_ylabel("")
    pct(ax, "y")
    ax.set_ylim(0, 0.32)  # headroom so the legend never sits on top of the Sênior/Especialista bars
    ax.set_title("Mix de senioridade por edição da pesquisa")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=3, fontsize=9, title=None)
    style_vertical_bar_axes(ax)
    savefig(fig, FIGURES / "q1_seniority_mix.png",
            "Fonte: gold_market_overview. 'Especialista' só existe a partir da Pesquisa 3. "
            "~28-30% dos respondentes/ano ficam em UNKNOWN (não mostrado) - missingness estrutural, não excluída da amostra total.")
    return fig


def chart_q1_work_model_mix():
    df = pd.read_csv(ANSWERS / "q1_market_structure_current_work_model.csv")
    order = ["REMOTE", "HYBRID_FLEXIBLE", "HYBRID_FIXED", "ON_SITE"]
    labels_pt = {"REMOTE": "100% remoto", "HYBRID_FLEXIBLE": "Híbrido flexível", "HYBRID_FIXED": "Híbrido fixo", "ON_SITE": "100% presencial"}
    df = df[df["dimension_value"].isin(order)]
    df["dimension_label"] = df["dimension_value"].map(labels_pt)
    years = [c for c in df.columns if c.startswith("year_")]

    long = df.melt(id_vars="dimension_label", value_vars=years, var_name="survey_year", value_name="value").dropna(subset=["value"])
    long = with_year_label(long)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.barplot(
        data=long, x="dimension_label", y="value", hue="survey_year_label",
        order=[labels_pt[o] for o in order], hue_order=[YEAR_LABELS[y] for y in years],
        palette=YEAR_COLOR_LABELED, ax=ax,
    )
    label_bars(ax, fmt=lambda v: f"{v*100:.0f}%")
    ax.set_xlabel("")
    ax.set_ylabel("")
    pct(ax, "y")
    ax.set_title("Modelo de trabalho: retorno gradual ao presencial")
    ax.legend(loc="upper right", title=None)
    style_vertical_bar_axes(ax)
    savefig(fig, FIGURES / "q1_work_model_mix.png", "Fonte: gold_market_overview.")
    return fig


# ---------------------------------------------------------------------------
# Q2 - Perfis mais valorizados (remuneração)
# Source: q2_compensation_by_role_latest_year.csv, q2_compensation_by_seniority_all_years.csv
# Caveat: cargos com low_sample_flag=True marcados com asterisco - não
# publicar como comparável sem essa marca (n < 30).
# ---------------------------------------------------------------------------
ROLE_LABELS = {
    "DATA_ANALYST": "Analista de Dados", "DATA_SCIENTIST": "Cientista de Dados",
    "DATA_ENGINEER_OR_ARCHITECT": "Eng. de Dados / Arquiteto", "DATA_ARCHITECT": "Arquiteto de Dados",
    "BI_ANALYST": "Analista de BI", "ANALYTICS_ENGINEER": "Analytics Engineer",
    "BUSINESS_ANALYST": "Analista de Negócios", "ML_ENGINEER": "ML Engineer",
    "SOFTWARE_ENGINEER_OR_IT_ANALYST": "Eng. Software / Analista TI", "SUPPORT_ANALYST": "Analista de Suporte",
    "DATA_PRODUCT_MANAGER": "Data Product Manager", "OTHER_ENGINEERING": "Outras Engenharias",
    "ACADEMIC": "Acadêmico/Pesquisador", "STATISTICIAN": "Estatístico", "DBA": "DBA",
    "MARKET_INTELLIGENCE_ANALYST": "Market Intelligence", "OTHER": "Outro",
}


def chart_q2_salary_by_role():
    df = pd.read_csv(ANSWERS / "q2_compensation_by_role_latest_year.csv").sort_values("median_salary_midpoint")
    df = df.tail(10).copy()
    df["role_label"] = [f"{ROLE_LABELS.get(r, r)}{'*' if flag else ''}" for r, flag in zip(df["current_role"], df["low_sample_flag"])]
    order = df["role_label"].tolist()  # ascending -> largest last -> plotted at the top (seaborn: first `order` item at top)
    order = list(reversed(order))

    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(data=df, y="role_label", x="median_salary_midpoint", order=order, color=SEQUENTIAL_BLUE[-2], ax=ax)
    label_bars(ax, fmt=lambda v: f"R$ {v:,.0f}".replace(",", "."), padding=5, fontsize=9, color=INK_PRIMARY)
    ax.set_ylabel("")
    ax.set_title("Mediana salarial por cargo — Pesquisa 3 (2025-26)")
    ax.set_xlabel("Salário mediano (R$/mês, ponto médio da faixa)", labelpad=10)
    style_horizontal_bar_axes(ax)
    fig.subplots_adjust(bottom=0.2)  # keep the xlabel clear of the source caption below it
    savefig(fig, FIGURES / "q2_salary_by_role.png",
            "Fonte: gold_compensation_by_role. * amostra pequena (n<30) - ver salary_iqr antes de comparar.")
    return fig


def chart_q2_salary_by_seniority():
    df = pd.read_csv(ANSWERS / "q2_compensation_by_seniority_all_years.csv")
    order = ["JUNIOR", "MID", "SENIOR", "SPECIALIST"]
    labels_pt = {"JUNIOR": "Júnior", "MID": "Pleno", "SENIOR": "Sênior", "SPECIALIST": "Especialista"}
    df["seniority_label"] = df["seniority"].map(labels_pt)
    years = df["survey_year"].unique().tolist()
    df = with_year_label(df)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.barplot(
        data=df, x="seniority_label", y="median_salary_midpoint", hue="survey_year_label",
        order=[labels_pt[o] for o in order], hue_order=[YEAR_LABELS[y] for y in years],
        palette=YEAR_COLOR_LABELED, ax=ax,
    )
    label_bars(ax, fmt=lambda v: f"{v/1000:.1f}k", padding=3)
    ax.set_xlabel("")
    ax.set_ylabel("Salário mediano (R$/mês)")
    ax.set_title("Remuneração mediana por senioridade")
    ax.legend(loc="upper left", title=None)
    style_vertical_bar_axes(ax)
    savefig(fig, FIGURES / "q2_salary_by_seniority.png",
            "Fonte: gold_compensation_by_seniority. 'Especialista' só medido a partir da Pesquisa 3.")
    return fig


# ---------------------------------------------------------------------------
# Q3 - Diversidade de gênero
# Source: q3_gender_overall_by_year.csv, q3_gender_share_by_seniority.csv
# Caveat: campo de gênero recuperado do CSV bruto para os 3 anos (não é
# gap real) - comparável nos 3 anos. Amostras diferentes por ano.
# ---------------------------------------------------------------------------
def chart_q3_gender_share_by_year():
    df = pd.read_csv(ANSWERS / "q3_gender_overall_by_year.csv")
    genders = ["MALE", "FEMALE", "OTHER", "NOT_INFORMED"]
    df = df[df["gender"].isin(genders)].copy()
    df["gender_label"] = df["gender"].map(GENDER_LABELS)
    years = df["survey_year"].unique().tolist()
    df = with_year_label(df)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.barplot(
        data=df, x="survey_year_label", y="share_within_bucket", hue="gender_label",
        order=[YEAR_LABELS[y] for y in years], hue_order=[GENDER_LABELS[g] for g in genders],
        palette=GENDER_COLOR_LABELED, ax=ax,
    )
    label_bars(ax, fmt=lambda v: f"{v*100:.0f}%", min_value=0.005)  # suppress the misleading "0%" label on truthfully-nonzero (~0.2-0.4%) OTHER/NOT_INFORMED slivers
    ax.set_xlabel("")
    ax.set_ylabel("")
    pct(ax, "y")
    ax.set_ylim(0, 0.97)  # headroom above the tallest bar (81%) so the legend never overlaps a data label
    ax.set_title("Representação de gênero por edição da pesquisa")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, 1.16), ncol=4, fontsize=9, title=None)
    style_vertical_bar_axes(ax)
    savefig(fig, FIGURES / "q3_gender_share_by_year.png", "Fonte: gold_gender_representation.")
    return fig


def chart_q3_gender_funnel():
    df = pd.read_csv(ANSWERS / "q3_gender_share_by_seniority.csv")
    order = ["JUNIOR", "MID", "SENIOR", "SPECIALIST"]
    labels_pt = {"JUNIOR": "Júnior", "MID": "Pleno", "SENIOR": "Sênior", "SPECIALIST": "Especialista"}
    df = df[df["survey_year"].isin(["year_1", "year_3"])].copy()
    df["seniority_label"] = pd.Categorical(df["seniority"].map(labels_pt), categories=[labels_pt[o] for o in order], ordered=True)
    df = with_year_label(df)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.lineplot(
        data=df.sort_values("seniority_label"), x="seniority_label", y="share_within_bucket", hue="survey_year_label",
        hue_order=[YEAR_LABELS["year_1"], YEAR_LABELS["year_3"]],
        palette={YEAR_LABELS["year_1"]: YEAR_COLOR["year_1"], YEAR_LABELS["year_3"]: YEAR_COLOR["year_3"]},
        marker="o", markersize=8, linewidth=2, ax=ax,
    )
    for _, row in df.iterrows():
        ax.text(row["seniority_label"], row["share_within_bucket"] + 0.008, f"{row['share_within_bucket']*100:.0f}%",
                ha="center", fontsize=8.5, color=INK_SECONDARY)
    ax.set_xlabel("")
    pct(ax, "y")
    ax.set_ylim(0, max(0.35, df["share_within_bucket"].max() * 1.25))
    ax.set_title("Participação feminina cai ao longo da progressão de carreira")
    ax.legend(loc="upper right", title=None)
    style_vertical_bar_axes(ax)
    ax.grid(axis="x", visible=False)
    savefig(fig, FIGURES / "q3_gender_funnel_by_seniority.png",
            "Fonte: gold_gender_representation. % de mulheres dentro de cada nível de senioridade (representação), não distribuição interna de gênero.")
    return fig


# ---------------------------------------------------------------------------
# Q4 - Adoção de tecnologia (família DATABASE)
# Source: q4_technology_adoption_latest_year.csv, q4_technology_yoy_change_latest_year.csv
# Caveat: escopo limitado à família de bancos de dados/fontes de dados;
# denominador = respondentes elegíveis (não a amostra total do ano).
# ---------------------------------------------------------------------------
def chart_q4_top_technologies():
    df = pd.read_csv(ANSWERS / "q4_technology_adoption_latest_year.csv").sort_values("adoption_rate").tail(10)
    order = list(reversed(df["technology"].tolist()))

    fig, ax = plt.subplots(figsize=(7.5, 5))
    sns.barplot(data=df, y="technology", x="adoption_rate", order=order, color=SEQUENTIAL_BLUE[-2], ax=ax)
    label_bars(ax, fmt=lambda v: f"{v*100:.0f}%", padding=5, fontsize=9, color=INK_PRIMARY)
    ax.set_ylabel("")
    ax.set_title("Tecnologias de dados mais adotadas — Pesquisa 3 (2025-26)")
    ax.set_xlabel("Taxa de adoção (entre respondentes elegíveis para a pergunta)", labelpad=10)
    pct(ax, "x")
    style_horizontal_bar_axes(ax)
    fig.subplots_adjust(bottom=0.2)  # keep the xlabel clear of the source caption below it
    savefig(fig, FIGURES / "q4_top_technologies.png",
            "Fonte: gold_technology_adoption_by_year. Escopo: família DATABASE apenas (33 tecnologias avaliadas).")
    return fig


def chart_q4_yoy_change():
    df = pd.read_csv(ANSWERS / "q4_technology_yoy_change_latest_year.csv").dropna(subset=["yoy_pp_change_vs_prev_survey"])
    top_gains = df.sort_values("yoy_pp_change_vs_prev_survey", ascending=False).head(6)
    top_drops = df.sort_values("yoy_pp_change_vs_prev_survey", ascending=True).head(6)
    plot_df = pd.concat([top_drops, top_gains]).drop_duplicates("technology").sort_values("yoy_pp_change_vs_prev_survey").copy()
    plot_df["sign"] = np.where(plot_df["yoy_pp_change_vs_prev_survey"] > 0, "Alta", "Queda")
    order = list(reversed(plot_df["technology"].tolist()))  # largest gain at the top, consistent with every other horizontal-bar chart here

    fig, ax = plt.subplots(figsize=(8, 5.5))
    sns.barplot(
        data=plot_df, y="technology", x="yoy_pp_change_vs_prev_survey", hue="sign",
        order=order, palette={"Alta": DIVERGING_POSITIVE, "Queda": DIVERGING_NEGATIVE},
        dodge=False, legend=False, ax=ax,
    )
    ax.axvline(0, color=INK_MUTED, linewidth=1)
    label_bars(ax, fmt=lambda v: f"{v:+.1f}pp", padding=5, fontsize=8.5, color=INK_PRIMARY)
    vmax = plot_df["yoy_pp_change_vs_prev_survey"].abs().max()
    ax.set_xlim(-vmax * 1.35, vmax * 1.35)
    ax.set_ylabel("")
    ax.set_title("Maiores altas e quedas de adoção (Pesquisa 2 -> Pesquisa 3)")
    ax.set_xlabel("Variação em pontos percentuais de adoção")
    style_horizontal_bar_axes(ax)
    ax.grid(axis="x", visible=True)
    savefig(fig, FIGURES / "q4_technology_yoy_change.png",
            "Fonte: gold_technology_adoption_by_year. Azul = queda, vermelho = alta. Escopo: família DATABASE.")
    return fig


# ---------------------------------------------------------------------------
# Q5 - Adoção de IA
# Source: q5_ai_adoption_overview.csv
# Caveat: Pesquisa 1 não tinha essas perguntas - nunca tratada como 0%,
# simplesmente omitida do gráfico.
# ---------------------------------------------------------------------------
def chart_q5_ai_adoption():
    df = pd.read_csv(ANSWERS / "q5_ai_adoption_overview.csv")
    metrics = ["enterprise_ai_priority_rate", "personal_genai_usage_rate", "personal_genai_company_paid_rate"]
    metric_labels = {
        "enterprise_ai_priority_rate": "IA é prioridade\nna empresa",
        "personal_genai_usage_rate": "Usa alguma\nsolução de GenAI",
        "personal_genai_company_paid_rate": "Empresa paga\npela ferramenta",
    }
    years = ["year_2", "year_3"]  # year_1: question_available=False, omitted (never shown as 0%)
    df = df[df["survey_year"].isin(years) & df["metric"].isin(metrics)].copy()
    df["metric_label"] = df["metric"].map(metric_labels)
    df = with_year_label(df)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.barplot(
        data=df, x="metric_label", y="rate", hue="survey_year_label",
        order=[metric_labels[m] for m in metrics], hue_order=[YEAR_LABELS[y] for y in years],
        palette=YEAR_COLOR_LABELED, ax=ax,
    )
    label_bars(ax, fmt=lambda v: f"{v*100:.0f}%", padding=4, fontsize=9)
    ax.set_xlabel("")
    ax.set_ylabel("")
    pct(ax, "y")
    ax.set_ylim(0, 1.08)
    ax.set_title("Adoção de IA generativa — Pesquisa 1 sem esses dados (pergunta não existia)")
    ax.legend(loc="upper left", title=None)
    style_vertical_bar_axes(ax)
    fig.subplots_adjust(bottom=0.22)  # x tick labels are two lines tall — keep them clear of the caption below
    savefig(fig, FIGURES / "q5_ai_adoption.png", "Fonte: gold_ai_adoption_overview. Denominador: respondentes elegíveis para cada pergunta.")
    return fig


# ---------------------------------------------------------------------------
# Q6 - Diferenças por região / senioridade / modelo de trabalho
# Source: q6_compensation_by_region_latest_year.csv, q6_compensation_by_work_model_all_years.csv
# Caveat: faixas salariais têm baixa granularidade (~14 valores possíveis
# de mediana) - medianas empatadas podem refletir quantização, não
# igualdade real; por isso mostramos o IQR (p25-p75) junto com a mediana.
# ---------------------------------------------------------------------------
def chart_q6_salary_by_region():
    df = pd.read_csv(ANSWERS / "q6_compensation_by_region_latest_year.csv").sort_values("median_salary_midpoint")
    order = list(reversed(df["region"].tolist()))
    err = df.set_index("region")["salary_iqr"] / 2  # p25/p75 not saved in this answer file - iqr shown as symmetric spread proxy

    fig, ax = plt.subplots(figsize=(8, 4.5))
    sns.barplot(data=df, y="region", x="median_salary_midpoint", order=order, color=SEQUENTIAL_BLUE[-2], ax=ax)

    xmax = (df["median_salary_midpoint"] + err.values).max()
    ax.set_xlim(0, xmax * 1.28)
    for i, region in enumerate(order):
        row = df[df["region"] == region].iloc[0]
        e = err[region]
        ax.errorbar(row["median_salary_midpoint"], i, xerr=e, ecolor=INK_MUTED, capsize=3, linewidth=1, fmt="none")
        ax.text(row["median_salary_midpoint"] + e + xmax * 0.02, i,
                f"R$ {row['median_salary_midpoint']/1000:.1f}k (n={row['respondent_count']})",
                va="center", fontsize=8.5, color=INK_SECONDARY)
    ax.set_ylabel("")
    ax.set_title("Mediana salarial por região — Pesquisa 3 (barra de erro = IQR)")
    ax.set_xlabel("Salário mediano (R$/mês)", labelpad=10)
    style_horizontal_bar_axes(ax)
    fig.subplots_adjust(bottom=0.18)  # keep the xlabel clear of the source caption below it
    savefig(fig, FIGURES / "q6_salary_by_region.png",
            "Fonte: gold_compensation_by_region. Medianas próximas podem refletir quantização das faixas salariais, não igualdade real - ver IQR.")
    return fig


def chart_q6_salary_by_work_model():
    df = pd.read_csv(ANSWERS / "q6_compensation_by_work_model_all_years.csv")
    order = ["ON_SITE", "HYBRID_FIXED", "HYBRID_FLEXIBLE", "REMOTE"]
    labels_pt = {"ON_SITE": "Presencial", "HYBRID_FIXED": "Híbrido fixo", "HYBRID_FLEXIBLE": "Híbrido flexível", "REMOTE": "Remoto"}
    df["work_model_label"] = df["current_work_model"].map(labels_pt)
    years = df["survey_year"].unique().tolist()
    df = with_year_label(df)

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    sns.barplot(
        data=df, x="work_model_label", y="median_salary_midpoint", hue="survey_year_label",
        order=[labels_pt[o] for o in order], hue_order=[YEAR_LABELS[y] for y in years],
        palette=YEAR_COLOR_LABELED, ax=ax,
    )
    label_bars(ax, fmt=lambda v: f"{v/1000:.1f}k", padding=3)
    ax.set_xlabel("")
    ax.set_ylabel("Salário mediano (R$/mês)")
    ax.set_ylim(0, df["median_salary_midpoint"].max() * 1.18)  # headroom for value labels above the tallest bars
    ax.set_title("Remuneração mediana por modelo de trabalho")
    ax.legend(loc="upper left", title=None)
    style_vertical_bar_axes(ax)
    savefig(fig, FIGURES / "q6_salary_by_work_model.png", "Fonte: gold_compensation_by_work_model.")
    return fig


# ---------------------------------------------------------------------------
# Q7 - Skills prioritárias (síntese)
# Source: q7_skill_priority_ranking.csv
# Caveat: componente future_interest NÃO medido (sem pergunta na pesquisa)
# - peso redistribuído entre os outros 4; nunca apresentar o score sozinho.
# ---------------------------------------------------------------------------
def chart_q7_skill_priority():
    df = pd.read_csv(ANSWERS / "q7_skill_priority_ranking.csv").sort_values("priority_score").tail(10)
    order = list(reversed(df["technology"].tolist()))

    fig, ax = plt.subplots(figsize=(7.5, 5))
    sns.barplot(data=df, y="technology", x="priority_score", order=order, color=SEQUENTIAL_BLUE[-2], ax=ax)
    label_bars(ax, fmt=lambda v: f"{v:.2f}", padding=5, fontsize=9, color=INK_PRIMARY)
    ax.set_ylabel("")
    ax.set_title("Score de priorização de skills — família DATABASE")
    ax.set_xlabel("priority_score (crescimento + presença cross-role + associação salarial + presença sênior)",
                   fontsize=9.5, labelpad=10)
    style_horizontal_bar_axes(ax)
    fig.subplots_adjust(bottom=0.22)  # keep the (long) xlabel clear of the source caption below it
    savefig(fig, FIGURES / "q7_skill_priority_score.png",
            "Fonte: gold_skill_priority_score. Componente 'interesse futuro' não medido (sem pergunta na pesquisa); score nunca deve ser lido sem os componentes.")
    return fig


if __name__ == "__main__":
    for fn in [
        chart_q1_seniority_mix, chart_q1_work_model_mix,
        chart_q2_salary_by_role, chart_q2_salary_by_seniority,
        chart_q3_gender_share_by_year, chart_q3_gender_funnel,
        chart_q4_top_technologies, chart_q4_yoy_change,
        chart_q5_ai_adoption,
        chart_q6_salary_by_region, chart_q6_salary_by_work_model,
        chart_q7_skill_priority,
    ]:
        fig = fn()
        plt.close(fig)
    print(f"\nAll figures saved under {FIGURES.relative_to(REPO_ROOT)}/")
