# Methodology — Bronze → Silver → Gold (v1)

## 1. Escopo deste corte (vertical slice)

Seguindo a seção 41 do prompt mestre, este corte implementa uma fatia vertical completa antes de expandir para todos os domínios analíticos:

```
Raw CSV (data/raw/) → Bronze → Silver (fact_respondent) → Gold (gold_market_overview)
```

Domínios cobertos: 1 (evolução do mercado) parcialmente, mais a base para os domínios 2, 4, 5, 6 e 7 (que dependem de `fact_respondent`). Domínios 3, 8 e 9 (tecnologia, IA, skills) dependem de bridge tables ainda não implementadas.

## 2. Execução local vs. AWS Glue

Não há acesso a AWS Glue/Athena nesta sessão (ambiente local apenas). Por isso:

- `scripts/run_local_pipeline.py` — implementação de referência em pandas, executada e validada localmente contra os 3 CSVs brutos reais. Escreve `data/bronze/`, `data/silver/respondents/`, `data/gold/market_overview/` (CSV, não Parquet — sem `pyarrow` disponível neste ambiente sem acesso à internet).
- `glue/ingest_raw_to_bronze.py`, `glue/bronze_2_silver.py`, `glue/silver_2_gold.py` — implementação equivalente em PySpark real, pronta para rodar como AWS Glue Jobs quando o AWS Academy Lab estiver disponível. Escrevem Parquet particionado por `survey_year`, como especificado na arquitetura (seção 17 do prompt mestre).

**Regra de manutenção**: qualquer mudança de regra de harmonização (mapping table, parsing de salário, resolução de coluna por código) deve ser aplicada nos dois lugares. Os comentários de cabeçalho de cada script Glue apontam para o script pandas equivalente e vice-versa.

## 3. Resolução de coluna por código, nunca por posição ou label

Year 1 e Year 2: os headers do CSV bruto são strings literais de tupla Python, ex.: `"('P1_b ', 'Genero')"`. Year 3: os headers já são strings `código_label`, ex.: `1.b_genero`.

`scripts/field_maps.py` (espelhado em `glue/utils/field_maps.py`) mapeia `campo_canonico -> código_da_pergunta` por ano, e a resolução de coluna sempre casa pelo **código exato**, nunca pela posição (frágil a mudanças de ordem) nem pelo texto do label (o mesmo código pode significar perguntas diferentes entre anos — ver o caso `P2_q` documentado em `documentation/schema_audit_cross_year.md`: significa "modelo de trabalho atual" em Year 1 e "empresa teve layoff" em Year 2).

## 4. Harmonização via mapping tables versionadas

Implementadas em `documentation/mappings/` (todas com coluna `mapping_version`):

| Arquivo | Campo(s) | Observação |
|---|---|---|
| `mapping_gender.csv` | `gender` | `MALE`, `FEMALE`, `OTHER`, `NOT_INFORMED`, `UNKNOWN` |
| `mapping_seniority.csv` | `seniority` | `JUNIOR`, `MID`, `SENIOR`, `SPECIALIST` (só Year 3), `UNKNOWN` |
| `mapping_work_model.csv` | `current_work_model`, `ideal_work_model` | `REMOTE`, `ON_SITE`, `HYBRID_FLEXIBLE`, `HYBRID_FIXED`, `UNKNOWN` |
| `mapping_employment_status.csv` | `employment_status` | inclui variante textual Year 1 com sufixo "(PJ)" mapeada ao mesmo canônico de Year 2/3 |
| `mapping_company_size.csv` | `company_size` (ordinal) | inclui a anomalia `"de 501 a 100"` mapeada para `INVALID` |
| `mapping_role.csv` | `current_role` | inclui coluna `comparability_group` para casos de fusão/divisão de opções entre anos (ver seção 5 do `data_quality_report.md`) |
| `mapping_salary_band.csv` | `salary_band` | gerado programaticamente por parsing de regex (seção 5 abaixo), não digitado manualmente |

Regra de validação (implementada tanto no pipeline local quanto no job Glue): um valor bruto presente nos dados mas ausente da mapping table **falha o pipeline explicitamente**, em vez de virar `UNKNOWN` silenciosamente. Isso garante que uma nova categoria introduzida em uma edição futura da pesquisa seja detectada, não mascarada.

## 5. Parsing de faixa salarial

Bounds nunca foram digitados manualmente. `salary_lower_bound`/`salary_upper_bound`/`salary_midpoint` são extraídos por regex a partir do rótulo original (`de R$ X/mês a R$ Y/mês`, `Acima de R$ X/mês`, `Menos de R$ X/mês`), com três categorias de `open_ended`:

- `CLOSED`: ambos os limites conhecidos → midpoint = média.
- `UPPER_OPEN` / `LOWER_OPEN`: apenas um limite conhecido → midpoint fica `NULL` (nenhum limite é inventado, conforme seção 26 do prompt mestre).

Uma linha onde o limite superior é menor que o inferior é marcada `anomaly_flag=True` e também recebe `salary_midpoint=NULL`.

## 6. `fact_respondent` — o que está e o que não está harmonizado neste corte

Harmonizados (mapping table aplicada): `gender`, `seniority`, `employment_status`, `current_work_model`, `ideal_work_model`, `salary_band` (parsing numérico).

Ainda em formato bruto/raw no Silver (harmonização pendente): `current_role_raw`, `sector`, `company_size_raw` (mapping table já existe mas ainda não aplicada ao pipeline), `education_level`, `education_area`, `data_experience_band`, `it_experience_band`, `rto_attitude_raw`, `ethnicity_raw`, `pcd_flag_raw`.

## 7. Gold — `gold_market_overview`

Primeira Gold table, respondendo ao domínio 1 (evolução do mercado). Grão: `survey_year × dimension × dimension_value`, dimensões `seniority`, `gender`, `current_work_model`, `region`, `employment_status`. Métrica principal: `respondent_share_within_year` — deliberadamente **não** uma métrica de "crescimento do mercado", porque as três pesquisas são amostras independentes de tamanhos diferentes, não uma população rastreada ao longo do tempo (seção 24 do prompt mestre). Comparações de tendência devem usar a participação percentual dentro de cada ano, nunca a contagem absoluta de respondentes.

## 8. Reprodutibilidade

Toda linha do Silver carrega `source_file`, `ingestion_timestamp`, `pipeline_version` (`v1`) e `processing_timestamp`, permitindo rastrear qualquer registro de volta ao arquivo bruto e à versão do pipeline que o gerou.
