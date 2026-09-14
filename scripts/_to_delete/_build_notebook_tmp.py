"""
Builds visualization/chart_generation.ipynb by hand as valid nbformat v4 JSON
(the `nbformat` package is not installed in the project's local venv, so we
construct the JSON structure directly with the stdlib `json` module instead).

Run once from anywhere with: python3 build_notebook.py <repo_root>
"""
import json
import sys
from pathlib import Path

REPO_ROOT = Path(sys.argv[1])
OUT_PATH = REPO_ROOT / "visualization" / "chart_generation.ipynb"


def src(text: str):
    text = text.strip("\n")
    lines = text.split("\n")
    return [l + "\n" for l in lines[:-1]] + [lines[-1]]


def md(text: str):
    return {"cell_type": "markdown", "metadata": {}, "source": src(text)}


def code(text: str):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src(text),
    }


cells = []

# ---------------------------------------------------------------------------
cells.append(md("""
# Geração de gráficos — material executivo

Este notebook narra as 7 perguntas de negócio do Tech Challenge (State of Data
Brasil — Fase 3) e gera os gráficos que alimentam o material executivo
(`presentation/`), consumindo **exclusivamente a camada Gold**
(`data/gold/*.csv`), nunca Bronze ou Silver diretamente.

**Pipeline até aqui:**

```
Bronze (CSV bruto, 3 anos)
  -> Silver (limpo / harmonizado cross-year)
  -> Gold (9 tabelas de negócio)
  -> scripts/business_analysis.py   -> data/gold/business_answers/*.csv (16 CSVs, tidy)
  -> scripts/generate_charts.py     -> visualization/figures/*.png (12 gráficos)
  -> ESTE NOTEBOOK                  -> narrativa + gráficos para o material executivo
```

Cada gráfico segue a paleta e as regras de acessibilidade validadas da
dataviz skill (`scripts/chart_style.py`): ordem categórica fixa, uma cor por
ano de pesquisa (nunca recicladas), rampa sequencial de azul para magnitude,
par divergente azul/vermelho para variação positiva/negativa, e legendas
sempre presentes para 2+ séries.

Cada seção segue o padrão de recomendação do prompt mestre do projeto:

```
OBSERVAÇÃO -> EVIDÊNCIA -> INTERPRETAÇÃO -> IMPLICAÇÃO DE NEGÓCIO -> RECOMENDAÇÃO
```

Nenhum valor abaixo é inventado — todos vêm diretamente dos CSVs em
`data/gold/business_answers/`, que por sua vez vêm apenas da camada Gold.
"""))

cells.append(md("""
## Setup

Localiza a raiz do repositório (independente de onde o Jupyter foi iniciado),
adiciona `scripts/` ao `sys.path` para reaproveitar `chart_style.py` e
`generate_charts.py`, e configura pandas para exibição legível.
"""))

cells.append(code("""
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "scripts").is_dir() and (p / "data" / "gold").is_dir():
            return p
    raise FileNotFoundError(
        "Não foi possível localizar a raiz do repositório "
        "(esperado: pastas 'scripts/' e 'data/gold/' como irmãs)."
    )


REPO_ROOT = find_repo_root(Path.cwd())
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import pandas as pd
from IPython.display import Image, display

ANSWERS = REPO_ROOT / "data" / "gold" / "business_answers"
FIGURES = REPO_ROOT / "visualization" / "figures"

pd.set_option("display.max_columns", 50)
pd.set_option("display.width", 140)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

print(f"Repo root: {REPO_ROOT}")
"""))

cells.append(md("""
## Regenerar dados e gráficos (opcional)

Os 16 CSVs em `data/gold/business_answers/` e os 12 PNGs em
`visualization/figures/` já estão versionados no repositório — este notebook
não *precisa* recalculá-los para ser lido. Mas, por reprodutibilidade, a
célula abaixo os regenera a partir da Gold executando os dois scripts
correspondentes (`REGENERATE = False` para pular e apenas ler o que já existe).
"""))

cells.append(code("""
import subprocess

REGENERATE = True  # False para apenas ler os CSVs/PNGs já versionados

if REGENERATE:
    subprocess.run(
        [sys.executable, "business_analysis.py"],
        cwd=REPO_ROOT / "scripts", check=True,
    )
    subprocess.run(
        [sys.executable, "generate_charts.py"],
        cwd=REPO_ROOT / "scripts", check=True,
    )
    print("\\nGold -> business_answers -> figures regenerado com sucesso.")
else:
    print("Regeneração pulada — lendo CSVs/PNGs já versionados.")
"""))

# ---------------------------------------------------------------------------
# Q1
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 1 — Como está estruturado o mercado brasileiro de Dados?

**Fonte:** `gold_market_overview` via `q1_market_structure_seniority.csv` e
`q1_market_structure_current_work_model.csv`.

**OBSERVAÇÃO**
A participação de "100% remoto" caiu de forma consistente nas três edições,
enquanto presencial e híbrido fixo cresceram — um movimento de retorno
gradual ao escritório.

**EVIDÊNCIA**
- 100% remoto: 50,5% (P1) → 41,6% (P2) → 36,7% (P3)
- 100% presencial: 12,4% → 14,9% → 19,2%
- Híbrido fixo: 9,1% → 14,9% → 18,5%
- Híbrido flexível: praticamente estável (17,4% → 18,4% → 18,1%)

**INTERPRETAÇÃO**
Mesmo perdendo participação a cada edição, o trabalho remoto ainda é a
modalidade isolada mais comum — mas a tendência de três pontos no tempo
aponta para convergência com modelos híbridos/presenciais.

**IMPLICAÇÃO DE NEGÓCIO**
Políticas de atração de talento ancoradas exclusivamente em "100% remoto"
perdem peso relativo frente ao mercado; risco de atrito com o segmento de
profissionais que ainda prioriza remoto (aprofundado na Pergunta 6).

**RECOMENDAÇÃO**
Monitorar a atitude de RTO (*return-to-office*) e o gap entre modelo atual e
modelo ideal dos profissionais ao desenhar a política de atração/retenção;
usar o híbrido flexível como meio-termo já validado pelo mercado.

*Nota de qualidade:* ~28–30% dos respondentes/ano ficam em `UNKNOWN` para
senioridade — missingness estrutural do questionário, não exclusão de
amostra; "Especialista" só existe como categoria a partir da Pesquisa 3.
"""))

cells.append(code("""
seniority = pd.read_csv(ANSWERS / "q1_market_structure_seniority.csv")
work_model = pd.read_csv(ANSWERS / "q1_market_structure_current_work_model.csv")

display(seniority)
display(work_model)

display(Image(filename=FIGURES / "q1_seniority_mix.png"))
display(Image(filename=FIGURES / "q1_work_model_mix.png"))
"""))

# ---------------------------------------------------------------------------
# Q2
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 2 — Quais perfis profissionais são mais valorizados pelo mercado?

**Fonte:** `gold_compensation_by_role`, `gold_compensation_by_seniority` via
`q2_compensation_by_role_latest_year.csv` e
`q2_compensation_by_seniority_all_years.csv`.

**OBSERVAÇÃO**
A mediana salarial por senioridade ficou estável para Júnior e Pleno nas três
pesquisas, mas subiu de forma marcada para Sênior na Pesquisa 3 — e
Especialista (categoria nova) já nasce acima de Sênior.

**EVIDÊNCIA**
- Júnior: R$ 3.500,5 nas 3 pesquisas (estável)
- Pleno: R$ 7.000,5 nas 3 pesquisas (estável)
- Sênior: R$ 10.000,5 (P1) = R$ 10.000,5 (P2) → **R$ 14.000,5 (P3)**
- Especialista (só P3): R$ 18.000,5
- Cargos no topo da mediana (Pesquisa 3): Analytics Engineer, ML Engineer e
  Data Product Manager em R$ 14.000,5 (Data Architect empata, mas com
  amostra pequena, n=28)

**INTERPRETAÇÃO**
Como júnior e pleno não se moveram, o salto do sênior não é inflação
uniforme — é valorização real e recente da senioridade avançada,
provavelmente puxada pela mesma frente (IA/plataformas de dados) vista nas
Perguntas 4 e 5.

**IMPLICAÇÃO DE NEGÓCIO**
A compressão salarial entre pleno e sênior diminuiu: profissionais
sênior/especialista tornaram-se desproporcionalmente mais caros de reter e
contratar em relação ao restante da pirâmide.

**RECOMENDAÇÃO**
Priorizar orçamento de retenção e trilha de carreira para sênior/especialista
— justamente o segmento cuja mediana quase dobrou frente ao pleno — em vez de
distribuir o mesmo reajuste percentual por toda a pirâmide.

*Nota de qualidade:* medianas empatadas entre cargos/anos podem refletir a
baixa granularidade das faixas salariais da pesquisa (poucos valores
possíveis de mediana), não necessariamente igualdade real — por isso os
gráficos e a tabela sempre trazem o IQR/amostra junto com a mediana; cargos
com `low_sample_flag=True` (n<30, ex.: Data Architect, Academic) estão
marcados com asterisco e não devem ser lidos como conclusivos isoladamente.
"""))

cells.append(code("""
comp_role = pd.read_csv(ANSWERS / "q2_compensation_by_role_latest_year.csv")
comp_seniority = pd.read_csv(ANSWERS / "q2_compensation_by_seniority_all_years.csv")

display(comp_role.sort_values("median_salary_midpoint", ascending=False))
display(comp_seniority)

display(Image(filename=FIGURES / "q2_salary_by_role.png"))
display(Image(filename=FIGURES / "q2_salary_by_seniority.png"))
"""))

# ---------------------------------------------------------------------------
# Q3
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 3 — Qual é o cenário de diversidade de gênero nas carreiras de Dados?

**Fonte:** `gold_gender_representation` via `q3_gender_overall_by_year.csv` e
`q3_gender_share_by_seniority.csv`.

**OBSERVAÇÃO**
A participação feminina geral cresceu entre as pesquisas, mas dentro de cada
edição a proporção de mulheres cai de forma consistente à medida que a
senioridade aumenta — um funil de gênero que persiste apesar do crescimento
na entrada de carreira.

**EVIDÊNCIA**
- Participação feminina geral: 18,6% (P1) → 24,4% (P2) → 22,0% (P3)
- Funil por senioridade — Pesquisa 3: Júnior 28,2% → Pleno 22,4% →
  Sênior 20,7% → Especialista 20,1%
- Mesmo padrão na Pesquisa 1: Júnior 23,2% → Pleno 19,9% → Sênior 16,3%

**INTERPRETAÇÃO**
O funil (queda de representação com a progressão de carreira) se repete em
ambas as pontas da série histórica — não é um efeito de uma pesquisa
isolada. Isso indica um problema de retenção/promoção, e não apenas de
atração de mulheres para a área.

**IMPLICAÇÃO DE NEGÓCIO**
Sem intervenção direcionada, o ganho de diversidade observado na entrada de
carreira tende a não se traduzir em paridade em posições sênior/liderança no
médio prazo.

**RECOMENDAÇÃO**
Investir em mentoria e trilhas de promoção com foco na transição
pleno → sênior, ponto em que o funil mais se estreita, e acompanhar a
retenção diferenciada por gênero e senioridade a cada nova edição da
pesquisa.

*Nota de qualidade:* o questionário possui categorias de gênero além de
masculino/feminino (`OTHER`, `NOT_INFORMED`); elas permanecem na modelagem
(`fact_respondent`), mas têm amostra muito pequena para leitura executiva
própria — o recorte binário acima é o que a pergunta de negócio pede, sem
apagar as demais categorias do modelo.
"""))

cells.append(code("""
gender_year = pd.read_csv(ANSWERS / "q3_gender_overall_by_year.csv")
gender_seniority = pd.read_csv(ANSWERS / "q3_gender_share_by_seniority.csv")

display(gender_year)
display(gender_seniority)

display(Image(filename=FIGURES / "q3_gender_share_by_year.png"))
display(Image(filename=FIGURES / "q3_gender_funnel_by_seniority.png"))
"""))

# ---------------------------------------------------------------------------
# Q4
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 4 — Quais tecnologias apresentam maior adoção entre os profissionais?

**Fonte:** `gold_technology_adoption_by_year` via
`q4_technology_adoption_latest_year.csv` e
`q4_technology_yoy_change_latest_year.csv` (escopo: família **DATABASE**, 33
tecnologias avaliadas — linguagens, cloud, BI e ETL ainda não estão
modeladas em Gold).

**OBSERVAÇÃO**
Databricks lidera folgadamente o crescimento de adoção entre a Pesquisa 2 e
a Pesquisa 3, enquanto PostgreSQL segue como a tecnologia de dados mais
adotada em termos absolutos.

**EVIDÊNCIA**
- PostgreSQL: 36,8% de adoção (a maior da família), +8,5pp vs. pesquisa
  anterior
- Databricks: 32,9% de adoção, **+11,5pp** (maior crescimento da família)
- S3: 28,8% (+7,9pp); SQLite: 12,3% (+7,6pp)
- Denominador: 2.096 respondentes elegíveis para a pergunta na Pesquisa 3
  (não a amostra total do ano)

**INTERPRETAÇÃO**
A combinação de alta adoção absoluta (PostgreSQL) com alto crescimento
relativo (Databricks) sugere duas frentes distintas se consolidando ao mesmo
tempo: banco relacional tradicional como padrão de mercado, e plataformas de
lakehouse/dados unificados ganhando espaço rapidamente.

**IMPLICAÇÃO DE NEGÓCIO**
Equipes de engenharia de dados precisarão dominar tanto a base
(SQL/PostgreSQL) quanto a plataforma emergente (Databricks/Spark) para
permanecer competitivas nos próximos ciclos de contratação.

**RECOMENDAÇÃO**
Priorizar treinamento interno em Databricks/Spark para os times de
engenharia de dados, sem abandonar a solidez em SQL/PostgreSQL como
competência de base — ver também o score combinado da Pergunta 7.
"""))

cells.append(code("""
tech_adoption = pd.read_csv(ANSWERS / "q4_technology_adoption_latest_year.csv")
tech_yoy = pd.read_csv(ANSWERS / "q4_technology_yoy_change_latest_year.csv")

display(tech_adoption.sort_values("adoption_rate", ascending=False).head(10))
display(tech_yoy.sort_values("yoy_pp_change_vs_prev_survey", ascending=False).head(10))

display(Image(filename=FIGURES / "q4_top_technologies.png"))
display(Image(filename=FIGURES / "q4_technology_yoy_change.png"))
"""))

# ---------------------------------------------------------------------------
# Q5
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 5 — Qual é o índice de adoção de Inteligência Artificial e seu impacto?

**Fonte:** `gold_ai_adoption_overview` via `q5_ai_adoption_overview.csv`.

**OBSERVAÇÃO**
O uso pessoal de alguma solução de IA generativa já é quase universal entre
os respondentes elegíveis na Pesquisa 3, e a proporção de empresas que pagam
formalmente pela ferramenta deu um salto muito maior do que o uso em si.

**EVIDÊNCIA**
- `personal_genai_usage_rate`: 80,3% (P2, n=3.772 elegíveis) →
  **97,9%** (P3, n=2.106 elegíveis)
- `personal_genai_company_paid_rate`: 6,4% (P2) → **42,4%** (P3)
- `enterprise_ai_priority_rate`: 36,2% (P2) → 60,6% (P3)

**INTERPRETAÇÃO**
A curva de adoção pessoal já está próxima da saturação; o salto real está
migrando de "uso pessoal informal" para "investimento institucional formal"
— empresa priorizando e pagando pela ferramenta.

**IMPLICAÇÃO DE NEGÓCIO**
Mesmo na Pesquisa 3, 58% dos respondentes ainda não têm a ferramenta de IA
paga pela empresa — ou seja, a maioria do uso de IA no mercado ainda ocorre
fora de um investimento formal, o que é um risco de governança
(*shadow IT* de IA) para quem ainda não formalizou.

**RECOMENDAÇÃO**
Formalizar investimento em ferramentas de GenAI corporativas com governança
definida, em vez de depender do uso individual não custeado — o mercado já
está migrando nessa direção e quem não acompanhar fica exposto a um uso não
governado de IA com dados sensíveis.

*Nota de qualidade:* a Pesquisa 1 não tinha essas perguntas
(`question_available=False`) — **nunca tratada como 0% de adoção**, apenas
omitida do gráfico. O denominador é o número de respondentes elegíveis por
métrica (varia por pergunta), não a amostra total do ano.
"""))

cells.append(code("""
ai_overview = pd.read_csv(ANSWERS / "q5_ai_adoption_overview.csv")

display(ai_overview)

display(Image(filename=FIGURES / "q5_ai_adoption.png"))
"""))

# ---------------------------------------------------------------------------
# Q6
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 6 — Existem diferenças relevantes entre regiões, senioridades ou modelos de trabalho?

**Fonte:** `gold_compensation_by_region`, `gold_compensation_by_work_model`
via `q6_compensation_by_region_latest_year.csv` e
`q6_compensation_by_work_model_all_years.csv` (senioridade já coberta em
detalhe na Pergunta 2).

**OBSERVAÇÃO**
Na Pesquisa 3, a mediana salarial é **idêntica** (R$ 10.000,5) entre as 5
regiões do Brasil — mas a dispersão (IQR) varia bastante, com destaque para
a região Norte, que tem a menor amostra e o maior IQR.

**EVIDÊNCIA**
- Mediana igual a R$ 10.000,5 em Centro-oeste, Nordeste, Norte, Sudeste e Sul
- IQR: Sudeste R$ 11.000 (n=2.171) · Norte R$ 13.000 (**n=48**) ·
  demais regiões R$ 9.000
- Por modelo de trabalho (P3): Presencial R$ 7.000,5 vs. Remoto/Híbrido
  R$ 10.000,5 — padrão que se repete nas 3 pesquisas

**INTERPRETAÇÃO**
A igualdade de mediana entre regiões provavelmente reflete a baixa
granularidade das faixas salariais da pesquisa (poucos valores discretos
possíveis), não necessariamente ausência de desigualdade regional real. A
região Norte, com n=48, exige cautela adicional — comparar um n pequeno como
esse com o Sudeste (n=2.171) sem essa ressalva seria enganoso.

Quanto ao modelo de trabalho, o presencial aparece consistentemente com
mediana mais baixa que remoto/híbrido nas três pesquisas — mas isso é
**correlação, não causalidade**: perfis mais seniores tendem a ter mais
poder de negociação para trabalho remoto, então parte do efeito pode vir da
senioridade, não do modelo em si.

**IMPLICAÇÃO DE NEGÓCIO**
Não é possível afirmar, com esta metodologia, que não há diferença salarial
regional real, nem que "trabalho remoto aumenta salário" — ambas as leituras
precisam de controle estatístico adicional (por cargo/senioridade) antes de
virarem política.

**RECOMENDAÇÃO**
Comunicar o achado de forma calibrada: *"profissionais remotos apresentaram
remuneração mediana X% maior na amostra"*, nunca como causalidade direta;
tratar a comparação regional como limitação metodológica explícita
(faixas salariais discretas) no material executivo, e priorizar dados de
salário contínuo em pesquisas futuras se a comparação regional for
estratégica.
"""))

cells.append(code("""
comp_region = pd.read_csv(ANSWERS / "q6_compensation_by_region_latest_year.csv")
comp_work_model = pd.read_csv(ANSWERS / "q6_compensation_by_work_model_all_years.csv")

display(comp_region.sort_values("median_salary_midpoint", ascending=False))
display(comp_work_model)

display(Image(filename=FIGURES / "q6_salary_by_region.png"))
display(Image(filename=FIGURES / "q6_salary_by_work_model.png"))
"""))

# ---------------------------------------------------------------------------
# Q7
# ---------------------------------------------------------------------------
cells.append(md("""
---

## Pergunta 7 — Quais oportunidades e desafios para empresas que desejam investir em Dados e IA?

**Fonte:** `gold_skill_priority_score` via `q7_skill_priority_ranking.csv`,
lido em conjunto com os achados das Perguntas 1–6.

**OBSERVAÇÃO**
Databricks lidera folgadamente o score combinado de priorização de skills,
puxado por altíssimo crescimento de adoção e presença máxima entre papéis
distintos (cross-role) — mas o score também mostra que "prioridade" não é
sinônimo de "maior salário associado".

**EVIDÊNCIA**
- `priority_score`: Databricks 0,76 vs. 2º colocado (S3) 0,55 — diferença de
  +0,21
- Componentes de Databricks: crescimento de adoção 20,4pp · presença
  cross-role 100% · associação salarial 0,0 · presença em papéis sênior 64,7%
- Top 5 do ranking: Databricks, S3, Amazon Aurora/RDS, SQLite, Redis

**INTERPRETAÇÃO**
O placar é dominado pelos componentes de crescimento (peso 0,30) e presença
cross-role (peso 0,25); Databricks ter `salary_association=0` mostra que
"tecnologia em alta" e "tecnologia associada a salários mais altos" são
dimensões independentes nesta base — investir apenas em tecnologias "mais
pagas" perderia o sinal de tecnologias emergentes e amplamente adotadas como
Databricks.

**Síntese de oportunidades e desafios (Perguntas 1–7):**

| Oportunidade | Desafio associado |
|---|---|
| Databricks/lakehouse em forte crescimento cross-role | Escopo de tecnologia modelado em Gold ainda cobre só a família DATABASE |
| Adoção pessoal de GenAI já quase universal (97,9% na P3) | 58% das empresas ainda não pagam formalmente pela ferramenta — risco de shadow IT de IA |
| Sênior/Especialista com mediana salarial em forte alta | Compressão salarial menor = maior custo de retenção nesse segmento |
| Participação feminina geral em crescimento | Funil de gênero (queda com a senioridade) persiste em todas as edições |
| Modelo híbrido flexível estável e aceito pelo mercado | Retorno ao presencial em curso — risco de atrito com quem prioriza remoto |

**IMPLICAÇÃO DE NEGÓCIO**
As maiores oportunidades de investimento (Databricks, GenAI corporativa,
retenção sênior) vêm acompanhadas de desafios estruturais específicos
(governança de IA, funil de gênero, cobertura ainda parcial da modelagem de
tecnologia) que precisam entrar no mesmo plano, não ser tratados
separadamente.

**RECOMENDAÇÃO**
1. Priorizar capacitação interna em Databricks e no ecossistema de
   armazenamento/lakehouse (S3, Aurora/RDS) como frente nº 1 de upskilling.
2. Formalizar investimento e governança em ferramentas de GenAI corporativas.
3. Direcionar programas de mentoria e promoção para a transição
   pleno → sênior entre mulheres, onde o funil mais se estreita.
4. Nunca apresentar o `priority_score` sozinho — sempre com seus componentes
   visíveis, para a liderança entender o que está sendo otimizado.

*Nota de qualidade:* o componente `future_interest` (peso original 0,10) não
é medido — não existe pergunta equivalente nas três pesquisas; o peso foi
redistribuído proporcionalmente entre os outros 4 componentes (documentado
em `documentation/methodology.md`). Escopo do score limitado à família
DATABASE.
"""))

cells.append(code("""
skill_priority = pd.read_csv(ANSWERS / "q7_skill_priority_ranking.csv")

display(skill_priority.head(10))

display(Image(filename=FIGURES / "q7_skill_priority_score.png"))
"""))

# ---------------------------------------------------------------------------
cells.append(md("""
---

## Próximos passos

- Estes 12 gráficos (`visualization/figures/*.png`) alimentam diretamente o
  Capítulo 1–6 da narrativa executiva descrita em
  `documentation/methodology.md` / prompt mestre do projeto.
- Próxima etapa natural: montar `presentation/tech_challenge.pptx` /
  `.pdf` reutilizando estas imagens e os textos OBSERVAÇÃO → EVIDÊNCIA →
  INTERPRETAÇÃO → IMPLICAÇÃO → RECOMENDAÇÃO já redigidos acima.
- Limitações que devem viajar para o material executivo: escopo de
  tecnologia restrito à família DATABASE; quantização das faixas salariais;
  amostra pequena na região Norte; componente `future_interest` não medido
  no score de skills.
"""))

notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
            "pygments_lexer": "ipython3",
            "version": "3",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with open(OUT_PATH, "w", encoding="utf-8") as f:
    json.dump(notebook, f, ensure_ascii=False, indent=1)

print(f"Wrote {OUT_PATH} ({len(cells)} cells)")
