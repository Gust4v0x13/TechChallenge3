# State of Data Brasil — Tech Challenge Fase 3 (Engenharia de Dados)

Plataforma analítica que integra e harmoniza as três edições mais recentes da pesquisa **State of Data Brasil** (Data Hackers + Bain) para responder, com evidências, como está o mercado brasileiro de Dados, Analytics e IA — para orientar decisões de contratação, remuneração, capacitação e investimento de uma instituição financeira fictícia (cenário do Tech Challenge da Fase 3 da Pós Tech / FIAP).

## Sumário

1. [Problema de negócio](#1-problema-de-negócio)
2. [Objetivo](#2-objetivo)
3. [Datasets](#3-datasets)
4. [Arquitetura](#4-arquitetura)
5. [Estrutura do repositório](#5-estrutura-do-repositório)
6. [Camadas Bronze / Silver / Gold](#6-camadas-bronze--silver--gold)
7. [Processamento](#7-processamento)
8. [Execução](#8-execução)
9. [Análises](#9-análises)
10. [Principais resultados](#10-principais-resultados)
11. [Limitações](#11-limitações)
12. [Próximos passos](#12-próximos-passos)

---

## 1. Problema de negócio

Uma empresa de consultoria estratégica em dados foi contratada por uma grande instituição financeira que pretende expandir suas áreas de Dados, Analytics e Inteligência Artificial. Antes de investir em contratação, capacitação e tecnologia, a instituição precisa entender o mercado brasileiro de profissionais de Dados: quem são, quanto custam, quais tecnologias dominam, como a remuneração varia por senioridade/região/modelo de trabalho, como está a diversidade de gênero e qual o estágio real de adoção de IA.

## 2. Objetivo

Construir uma plataforma analítica em nuvem (AWS) capaz de integrar e harmonizar as três pesquisas State of Data Brasil mais recentes, transformando dados brutos e heterogêneos (questionários diferentes a cada edição) em um modelo analítico único e confiável — e a partir dele, produzir indicadores, gráficos e um material executivo com recomendações de negócio rastreáveis até a evidência que as sustenta.

## 3. Datasets

Fonte: pesquisa **State of Data Brasil**, três edições mais recentes.

| Edição | Período | Linhas (raw) | Colunas (raw) | Linhas duplicadas |
|---|---|---:|---:|---:|
| Pesquisa 1 | 2021-2022 | 2.645 | 356 | 4 |
| Pesquisa 2 | 2023-2024 | 5.293 | 399 | 0 |
| Pesquisa 3 | 2025-2026 | 3.495 | 388 | 1 |

Os arquivos brutos ficam em `data/raw/survey_year_N/`. Um ponto de atenção documentado logo no início do projeto: os inventários de colunas de Pesquisa 1 e 2 (`raw_columns_year1.txt`, `raw_columns_year2.txt`) foram originalmente exportados como `set()` do Python, que não preserva ordem nem duplicatas — isso mascarava campos críticos (gênero, cargo, senioridade, faixa salarial) como se estivessem ausentes. O schema real foi recuperado posicionalmente (`df.iloc[:, position]`, nunca por nome/posição do `set`) antes de qualquer harmonização — ver `documentation/methodology.md`, seção 3.

O alto percentual de valores ausentes nos brutos (~55–62%) **não é, por padrão, um problema de qualidade**: os questionários têm seções condicionais (só gestores, só quem está empregado, blocos específicos por cargo), então grande parte do missing é **estrutural** (`UNKNOWN` esperado pelo desenho do questionário), não um gap de coleta — ver `documentation/data_quality_report.md`, seção 2.

## 4. Arquitetura

```
State of Data Brasil (3 pesquisas)
        │
        ▼
Amazon S3 — Bronze (CSV bruto, nunca alterado)
        │
        ▼
AWS Glue Crawler → AWS Glue Data Catalog
        │
        ▼
AWS Glue Job (PySpark) — limpeza, harmonização cross-year
        │
        ▼
Amazon S3 — Silver (Parquet limpo/harmonizado) → Glue Data Catalog
        │
   ┌────┴────┐
   ▼         ▼
Amazon    AWS Glue/Spark
Athena    (agregações de negócio)
   │         │
   └────┬────┘
        ▼
Amazon S3 — Gold (9 datasets de negócio)
        │
        ▼
Analytics / Charts (PySpark, matplotlib + seaborn)
        │
        ▼
Storytelling executivo (apresentação)
```

Diagrama fonte (editável): [`architecture/aws_architecture.drawio`](architecture/aws_architecture.drawio) — abrir em [diagrams.net](https://app.diagrams.net) ou na extensão Draw.io do VS Code. Export estático: `architecture/aws_architecture.jpg`.

**Importante sobre o estágio atual**: este ambiente de desenvolvimento não tem acesso ao AWS Academy Lab, então o pipeline foi validado **localmente**, com pandas, contra os três CSVs reais (`scripts/`), e os **jobs PySpark equivalentes para o Glue real já estão escritos** em `glue/`, prontos para apontar para os buckets S3 quando o Lab estiver disponível. As duas implementações são mantidas em espelho — qualquer mudança de regra de harmonização precisa ser replicada nas duas (documentado no topo de `scripts/run_local_pipeline.py` e `documentation/methodology.md`).

## 5. Estrutura do repositório

```text
state-of-data-tech-challenge/
│
├── README.md                          — este arquivo
│
├── architecture/
│   ├── aws_architecture.drawio        — diagrama de arquitetura (fonte editável)
│   └── aws_architecture.jpg           — export estático do diagrama
│
├── data/
│   ├── raw/survey_year_{1,2,3}/       — CSVs originais da pesquisa (nunca alterados) + inventário de colunas
│   ├── profiling/                     — schema_profile_year_{1,2,3}.csv (schema posicional recuperado)
│   ├── samples/                       — (reservado para amostras; ainda vazio)
│   ├── bronze/year_{1,2,3}/           — espelho local do S3 Bronze (saída de scripts/run_local_pipeline.py)
│   ├── silver/                        — espelho local do S3 Silver: fact_respondent (particionado por survey_year),
│   │                                     bridge_respondent_technology, fact_ai_adoption
│   └── gold/                          — espelho local do S3 Gold: 9 datasets de negócio + business_answers/
│       ├── market_overview/, gold_compensation_by_role/, gold_compensation_by_seniority/,
│       │   gold_compensation_by_region/, gold_compensation_by_work_model/, gold_gender_representation/,
│       │   gold_technology_adoption_by_year/, gold_ai_adoption_overview/, gold_skill_priority_score/
│       └── business_answers/          — 16 CSVs tidy, um por pergunta de negócio (saída de scripts/business_analysis.py)
│
├── glue/                              — AWS Glue Jobs em PySpark (produção, para rodar no AWS Academy Lab)
│   ├── ingest_raw_to_bronze.py
│   ├── bronze_2_silver.py
│   ├── silver_2_gold.py
│   ├── silver_2_gold_compensation_gender.py
│   ├── silver_2_gold_technology_ai_skills.py
│   └── utils/field_maps.py            — mapeamento campo canônico → código da pergunta, por ano
│
├── scripts/                           — pipeline de referência em pandas (roda localmente, espelha glue/)
│   ├── run_local_pipeline.py          — Bronze → Silver → Gold (gold_market_overview)
│   ├── build_compensation_gender_gold.py
│   ├── build_technology_gold.py
│   ├── build_ai_gold.py
│   ├── build_skill_priority_gold.py
│   ├── business_analysis.py           — as 7 perguntas de negócio, lê só a Gold, grava data/gold/business_answers/
│   ├── chart_style.py                 — paleta e estilo compartilhado (matplotlib + seaborn)
│   ├── generate_charts.py             — os 12 gráficos do material executivo, lê business_answers/
│   └── field_maps.py                  — espelho de glue/utils/field_maps.py
│
├── sql/                                — consultas Athena (esqueleto criado; consultas ainda não escritas — ver seção 11)
│   ├── market_overview.sql
│   ├── salary_analysis.sql
│   ├── technology_adoption.sql
│   ├── gender_diversity.sql
│   └── ai_adoption.sql
│
├── documentation/
│   ├── data_dictionary.md             — dicionário de dados (rascunho inicial; versão completa por ano está
│   │                                     em elaboração — ver seção 11)
│   ├── business_questions.md          — placeholder (as perguntas estão documentadas nesta seção 9 do README
│   │                                     e no código de scripts/business_analysis.py; ainda não migradas para cá)
│   ├── data_quality_report.md         — volumetria, missingness estrutural, anomalias encontradas e corrigidas
│   ├── methodology.md                 — decisões de harmonização, parsing de salário, resolução de coluna por código
│   └── mappings/                      — 8 mapping tables versionadas (gender, seniority, work_model,
│                                         employment_status, company_size, role, salary_band, ai_priority)
│
├── visualization/
│   ├── chart_generation.ipynb         — narrativa das 7 perguntas de negócio + geração ao vivo dos 12 gráficos
│   │                                     (matplotlib + seaborn), consumindo só a Gold
│   └── figures/                       — os 12 PNGs gerados, prontos para o material executivo
│
```

## 6. Camadas Bronze / Silver / Gold

**Bronze** (`data/bronze/` local / `s3://.../bronze/` na AWS): réplica fiel dos CSVs originais, com metadados de ingestão adicionados (`survey_year`, `source_file`, `ingestion_timestamp`) — nunca modifica categorias, remove colunas ou corrige respostas.

**Silver** (`data/silver/` local / `s3://.../silver/` na AWS): limpeza, tipagem e harmonização cross-year via mapping tables versionadas (nunca `if/else` espalhado pelo código). Modelo implementado neste corte:
- `fact_respondent` — grão 1 respondente × 1 pesquisa, com `gender`, `seniority`, `employment_status`, `current_work_model`, `ideal_work_model` e `salary_band` (com `salary_lower_bound`/`upper_bound`/`midpoint`) já harmonizados; `current_role`, `sector`, `education_level`, entre outros, ainda em formato bruto (harmonização pendente — seção 11).
- `bridge_respondent_technology` — formato long (`respondent_id × survey_year × technology`), evitando manter centenas de colunas booleanas.
- `fact_ai_adoption` — métricas de adoção de IA por respondente/pesquisa.

**Gold** (`data/gold/` local / `s3://.../gold/` na AWS): 9 datasets desenhados para responder diretamente às perguntas de negócio (nunca uma cópia genérica do Silver) — `gold_market_overview`, `gold_compensation_by_role`, `gold_compensation_by_seniority`, `gold_compensation_by_region`, `gold_compensation_by_work_model`, `gold_gender_representation`, `gold_technology_adoption_by_year`, `gold_ai_adoption_overview`, `gold_skill_priority_score`. Os gráficos e o material executivo consomem exclusivamente esta camada.

## 7. Processamento

Duas implementações espelhadas, mantidas em sincronia:

| | Local (validado) | AWS Glue (produção) |
|---|---|---|
| Linguagem | pandas | PySpark |
| Local | `scripts/` | `glue/` |
| Formato de saída | CSV (sem `pyarrow` disponível localmente) | Parquet particionado por `survey_year` |
| Execução | `python3 scripts/run_local_pipeline.py` | Glue Job no AWS Academy Lab |

Regras aplicadas nas duas implementações: resolução de coluna sempre pelo **código exato da pergunta** (nunca por posição ou rótulo — o mesmo código pode significar perguntas diferentes entre anos); um valor bruto sem entrada na mapping table **falha o pipeline explicitamente** em vez de virar `UNKNOWN` silenciosamente; faixas salariais abertas (`"Acima de R$ 40.000"`) nunca recebem um limite superior inventado.

## 8. Execução

```bash
# 1. Ambiente
cd state-of-data-tech-challenge
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy matplotlib seaborn

# 2. Pipeline Bronze -> Silver -> Gold (referência local)
cd scripts
python3 run_local_pipeline.py
python3 build_compensation_gender_gold.py
python3 build_technology_gold.py
python3 build_ai_gold.py
python3 build_skill_priority_gold.py

# 3. Perguntas de negócio (lê só a Gold, grava data/gold/business_answers/)
python3 business_analysis.py

# 4. Gráficos do material executivo (lê business_answers/, grava visualization/figures/)
python3 generate_charts.py
```

Para a narrativa completa com os gráficos gerados ao vivo, abrir `visualization/chart_generation.ipynb` (a primeira célula localiza a raiz do repositório automaticamente e pode regenerar os dados a partir da Gold).

## 9. Análises

O projeto responde 7 perguntas de negócio, cada uma com uma função dedicada em `scripts/business_analysis.py` e uma seção correspondente em `visualization/chart_generation.ipynb`:

1. Como está estruturado o mercado brasileiro de Dados?
2. Quais perfis profissionais são mais valorizados pelo mercado?
3. Qual é o cenário de diversidade de gênero nas carreiras de Dados?
4. Quais tecnologias apresentam maior adoção entre os profissionais?
5. Qual é o índice de adoção de Inteligência Artificial e seu impacto?
6. Existem diferenças relevantes entre regiões, senioridades ou modelos de trabalho?
7. Quais oportunidades e desafios podem ser identificados para empresas que desejam investir em Dados e IA?

Cada resposta segue o padrão: **Observação → Evidência → Interpretação → Implicação de negócio → Recomendação**, nunca apresentando uma conclusão sem o número que a sustenta.

## 10. Principais resultados

- **Modelo de trabalho**: participação de "100% remoto" caiu de forma consistente (50,5% → 41,6% → 36,7%), com presencial e híbrido fixo em alta — sinal de retorno gradual ao escritório.
- **Remuneração por senioridade**: mediana estável para Júnior/Pleno nas 3 pesquisas, mas salto real para Sênior na última edição (R$ 10.000,5 → R$ 14.000,5); Especialista (categoria nova) já nasce acima de Sênior (R$ 18.000,5).
- **Diversidade de gênero**: participação feminina geral cresceu (18,6% → 24,4% → 22,0%), mas um funil de gênero persiste dentro de cada edição — a proporção de mulheres cai a cada nível de senioridade, nas três pesquisas.
- **Tecnologia**: Databricks lidera o crescimento de adoção (+11,5pp vs. edição anterior) entre as tecnologias de dados; PostgreSQL segue como a mais adotada em termos absolutos (36,8%).
- **IA**: uso pessoal de alguma solução de GenAI já é quase universal na última edição (97,9%), mas o investimento formal da empresa (ferramenta paga) ainda cobre menos da metade dos respondentes (42,4%).
- **Região**: mediana salarial idêntica entre as 5 regiões na última edição — leitura que exige cautela, pois pode refletir a baixa granularidade das faixas salariais da pesquisa, não igualdade real (ver seção 11).

Detalhamento completo, com os números e o raciocínio Observação → Recomendação de cada pergunta, em `visualization/chart_generation.ipynb`.

## 11. Limitações

- **Execução AWS ainda não realizada**: o pipeline Bronze → Silver → Gold foi validado localmente (pandas); os Glue Jobs em PySpark existem e estão prontos, mas ainda não rodaram contra S3/Glue reais no AWS Academy Lab.
- **Faixas salariais discretas (quantização)**: a mediana usa o ponto médio de faixas pré-definidas (não salário contínuo) — medianas empatadas entre cargos, anos ou regiões podem refletir a granularidade da faixa, não igualdade real; sempre olhar o IQR junto.
- **Escopo de tecnologia parcial**: `gold_technology_adoption_by_year` e `gold_skill_priority_score` cobrem hoje só a família **DATABASE** (33 tecnologias); linguagens, cloud, BI, ETL e ferramentas de ML/Data Science ainda não estão modeladas na Gold.
- **IA — Pesquisa 1 sem dados**: as perguntas de IA não existiam na primeira edição; tratado explicitamente como ausência de pergunta (nunca como 0% de adoção).
- **Amostras pequenas**: a região Norte, por exemplo, tem n=48 na última edição — qualquer comparação regional deve vir acompanhada do tamanho de amostra.
- **`gold_skill_priority_score`**: o componente `future_interest` (peso original 0,10) não é medido — não existe pergunta equivalente nas três pesquisas; o peso foi redistribuído proporcionalmente entre os outros 4 componentes. O score nunca deve ser lido sem seus componentes.
- **Documentação incompleta**: `documentation/business_questions.md` e as 5 queries em `sql/` estão como esqueleto/vazias; `documentation/data_dictionary.md` é um rascunho inicial — uma versão mais completa, por ano, está em elaboração fora deste repositório.
- **`fact_respondent` parcialmente harmonizado**: `current_role`, `sector`, `education_level`, `education_area`, `rto_attitude`, entre outros campos, ainda estão em formato bruto no Silver.
- **Material executivo ainda não montado**: `presentation/` está vazio — os 12 gráficos e os textos Observação → Recomendação já existem em `visualization/chart_generation.ipynb`, prontos para virar slides.
