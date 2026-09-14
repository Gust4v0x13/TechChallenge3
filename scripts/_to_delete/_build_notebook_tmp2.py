"""
Rebuilds visualization/chart_generation.ipynb (nbformat v4, hand-built JSON —
`nbformat` package unavailable locally) so the notebook's code cells call the
matplotlib+seaborn chart functions in generate_charts.py directly (inline,
live-rendered figures via the %matplotlib inline backend) instead of just
displaying the pre-saved PNGs.
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(sys.argv[1])
OUT_PATH = REPO_ROOT / "visualization" / "chart_generation.ipynb"

EXISTING = json.loads(OUT_PATH.read_text(encoding="utf-8"))


def src(text: str):
    text = text.strip("\n")
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]]


def md(text: str):
    return {"cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(text: str):
    return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": src(text)}


old_cells = EXISTING["cells"]

# Map each old "read CSV(s) + display Image(...)" code cell (by the CSV(s) it
# reads) to its replacement, which instead imports and calls the seaborn
# chart function(s) directly — matplotlib's inline backend renders the
# returned (still-open) figure automatically at the end of the cell.
REPLACEMENTS = {
    'seniority = pd.read_csv(ANSWERS / "q1_market_structure_seniority.csv")': '''
from generate_charts import chart_q1_seniority_mix, chart_q1_work_model_mix

seniority = pd.read_csv(ANSWERS / "q1_market_structure_seniority.csv")
work_model = pd.read_csv(ANSWERS / "q1_market_structure_current_work_model.csv")

display(seniority)
display(work_model)

chart_q1_seniority_mix()
chart_q1_work_model_mix()
''',
    'comp_role = pd.read_csv(ANSWERS / "q2_compensation_by_role_latest_year.csv")': '''
from generate_charts import chart_q2_salary_by_role, chart_q2_salary_by_seniority

comp_role = pd.read_csv(ANSWERS / "q2_compensation_by_role_latest_year.csv")
comp_seniority = pd.read_csv(ANSWERS / "q2_compensation_by_seniority_all_years.csv")

display(comp_role.sort_values("median_salary_midpoint", ascending=False))
display(comp_seniority)

chart_q2_salary_by_role()
chart_q2_salary_by_seniority()
''',
    'gender_year = pd.read_csv(ANSWERS / "q3_gender_overall_by_year.csv")': '''
from generate_charts import chart_q3_gender_share_by_year, chart_q3_gender_funnel

gender_year = pd.read_csv(ANSWERS / "q3_gender_overall_by_year.csv")
gender_seniority = pd.read_csv(ANSWERS / "q3_gender_share_by_seniority.csv")

display(gender_year)
display(gender_seniority)

chart_q3_gender_share_by_year()
chart_q3_gender_funnel()
''',
    'tech_adoption = pd.read_csv(ANSWERS / "q4_technology_adoption_latest_year.csv")': '''
from generate_charts import chart_q4_top_technologies, chart_q4_yoy_change

tech_adoption = pd.read_csv(ANSWERS / "q4_technology_adoption_latest_year.csv")
tech_yoy = pd.read_csv(ANSWERS / "q4_technology_yoy_change_latest_year.csv")

display(tech_adoption.sort_values("adoption_rate", ascending=False).head(10))
display(tech_yoy.sort_values("yoy_pp_change_vs_prev_survey", ascending=False).head(10))

chart_q4_top_technologies()
chart_q4_yoy_change()
''',
    'ai_overview = pd.read_csv(ANSWERS / "q5_ai_adoption_overview.csv")': '''
from generate_charts import chart_q5_ai_adoption

ai_overview = pd.read_csv(ANSWERS / "q5_ai_adoption_overview.csv")

display(ai_overview)

chart_q5_ai_adoption()
''',
    'comp_region = pd.read_csv(ANSWERS / "q6_compensation_by_region_latest_year.csv")': '''
from generate_charts import chart_q6_salary_by_region, chart_q6_salary_by_work_model

comp_region = pd.read_csv(ANSWERS / "q6_compensation_by_region_latest_year.csv")
comp_work_model = pd.read_csv(ANSWERS / "q6_compensation_by_work_model_all_years.csv")

display(comp_region.sort_values("median_salary_midpoint", ascending=False))
display(comp_work_model)

chart_q6_salary_by_region()
chart_q6_salary_by_work_model()
''',
    'skill_priority = pd.read_csv(ANSWERS / "q7_skill_priority_ranking.csv")': '''
from generate_charts import chart_q7_skill_priority

skill_priority = pd.read_csv(ANSWERS / "q7_skill_priority_ranking.csv")

display(skill_priority.head(10))

chart_q7_skill_priority()
''',
}

SETUP_OLD_MARKER = 'ANSWERS = REPO_ROOT / "data" / "gold" / "business_answers"'
SETUP_NEW_TAIL = '''
import matplotlib.pyplot as plt
import seaborn as sns

ANSWERS = REPO_ROOT / "data" / "gold" / "business_answers"
FIGURES = REPO_ROOT / "visualization" / "figures"

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 140)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

print(f"Repo root: {REPO_ROOT}")
print(f"matplotlib {plt.matplotlib.__version__} / seaborn {sns.__version__}")
'''

INTRO_OLD_SNIPPET = "Cada gráfico segue a paleta e as regras de acessibilidade validadas da"
INTRO_NEW_PARAGRAPH = """Os gráficos são desenhados com **matplotlib + seaborn**
(`scripts/chart_style.py` + `scripts/generate_charts.py`): seaborn
(`sns.barplot` / `sns.lineplot`) desenha as marcas sobre eixos que
dimensionamos e salvamos nós mesmos, o que mantém controle total sobre
tamanho de figura, legendas e as correções de sobreposição de rótulo já
validadas. Cada `chart_q*_...()` chamado abaixo grava o PNG em
`visualization/figures/` (para o material executivo) **e** renderiza a
figura aqui mesmo no notebook, via `%matplotlib inline`."""

new_cells = []
for cell in old_cells:
    text = "".join(cell["source"])

    if cell["cell_type"] == "code" and SETUP_OLD_MARKER in text:
        head = text.split(SETUP_OLD_MARKER)[0]
        new_cells.append(code(head + SETUP_NEW_TAIL))
        continue

    if cell["cell_type"] == "code":
        matched = False
        for marker, replacement in REPLACEMENTS.items():
            if marker in text:
                new_cells.append(code(replacement))
                matched = True
                break
        if matched:
            continue

    if cell["cell_type"] == "markdown" and INTRO_OLD_SNIPPET in text:
        text = text.replace(
            "Cada gráfico segue a paleta e as regras de acessibilidade validadas da\n"
            "dataviz skill (`scripts/chart_style.py`): ordem categórica fixa, uma cor por\n"
            "ano de pesquisa (nunca recicladas), rampa sequencial de azul para magnitude,\n"
            "par divergente azul/vermelho para variação positiva/negativa, e legendas\n"
            "sempre presentes para 2+ séries.",
            "Cada gráfico segue a paleta e as regras de acessibilidade validadas da\n"
            "dataviz skill: ordem categórica fixa, uma cor por ano de pesquisa (nunca\n"
            "recicladas), rampa sequencial de azul para magnitude, par divergente\n"
            "azul/vermelho para variação positiva/negativa, e legendas sempre presentes\n"
            "para 2+ séries.\n\n" + INTRO_NEW_PARAGRAPH,
        )
        new_cells.append(md(text))
        continue

    new_cells.append(cell)

EXISTING["cells"] = new_cells

with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(EXISTING, f, ensure_ascii=False, indent=1)

kinds = [c["cell_type"] for c in new_cells]
print(f"Wrote {OUT_PATH} ({len(new_cells)} cells: {kinds.count('code')} code, {kinds.count('markdown')} markdown)")
