# Data Quality Report — fact_respondent (v1)

Status: primeiro corte validado (vertical slice Bronze → Silver → Gold), executado localmente via `scripts/run_local_pipeline.py`. Pipeline execution date: 2026-09-02.

## 1. Volumetria (Bronze → Silver, sem perda de linhas)

| survey_year | rows raw (Bronze) | rows fact_respondent (Silver) | perda |
|---|---:|---:|---:|
| year_1 | 2.645 | 2.645 | 0 |
| year_2 | 5.293 | 5.293 | 0 |
| year_3 | 3.495 | 3.495 | 0 |
| **total** | **11.433** | **11.433** | **0** |

`respondent_id` (surrogate `{survey_year}_{index:06d}`) não apresentou nenhuma duplicata nas 11.433 linhas combinadas.

## 2. Missingness — estrutural vs. não-estrutural

Taxa de `UNKNOWN` (mapeado explicitamente a partir de nulo — nunca descartado silenciosamente) por campo harmonizado:

| Campo | year_1 | year_2 | year_3 | Leitura |
|---|---:|---:|---:|---|
| `gender` | 0,0% | 0,0% | 0,0% | Pergunta obrigatória em P1, sempre respondida quando o respondente chega até essa seção |
| `employment_status` | 0,0% | 0,0% | 0,0% | idem |
| `seniority` | 29,8% | 27,1% | 28,4% | **Estrutural**: bate quase exatamente com o volume de respondentes que não passam pelo bloco `P2_f`/`P2_g` (gestores respondem `P2_e` em vez disso, ou o respondente não está no bloco de emprego formal). Não interpretar como dado ausente por qualidade ruim. |
| `current_work_model` | 10,6% | 10,2% | 7,6% | Estrutural — mesmo bloco condicional de `P2_a`/`2.a` (situação de trabalho) |

Nenhum campo obrigatório de identificação (`gender`, `employment_status`) apresentou missingness — o que é evidência de que a extração de coluna está correta (se estivesse pegando a coluna errada, veríamos nulos onde não deveria haver).

## 3. Faixa salarial — parsing e anomalias

`documentation/mappings/mapping_salary_band.csv` contém o parsing determinístico de cada rótulo de faixa salarial observado nos 3 anos (16 rótulos distintos únicos), com `salary_lower_bound`, `salary_upper_bound`, `salary_midpoint`, `open_ended` e `anomaly_flag`.

- **Faixas abertas (open-ended), tratadas sem inventar limite** (regra da seção 26 do prompt mestre): `salary_midpoint` fica `NULL` para essas linhas.
  - year_1: 66 respondentes
  - year_2: 102 respondentes
  - year_3: 137 respondentes
- **Anomalia de digitação confirmada**: o rótulo `"de R$ 25.001/mês a R$ 3000/mês"` aparece 1 vez em year_3 (limite superior menor que o inferior — provável erro de captura do formulário, possivelmente deveria ser R$ 30.000). Foi marcado com `anomaly_flag=True` e `salary_midpoint=NULL` em vez de corrigido silenciosamente. **Decisão**: excluir da métrica de midpoint até confirmação; manter no `respondent_count`.
- **Variantes de pontuação equivalentes**, harmonizadas para o mesmo bound (ex.: `"R$ 2.001/mês a R$ 3000/mês"` vs `"R$ 2.001/mês a R$ 3.000/mês"`): tratadas como a mesma faixa.

## 4. Anomalia confirmada em `company_size`

O rótulo `"de 501 a 100"` aparece nos dados brutos de year_2 e year_3 (1 linha cada) — limite superior (100) menor que o inferior (501), claramente uma inversão de dígitos do formulário (provavelmente deveria ser "de 501 a 1000"). Mapeado para `INVALID` em `mapping_company_size.csv` em vez de corrigido por suposição.

## 5. Comparabilidade de `current_role` entre anos (ver `mapping_role.csv`)

Nem todo cargo é diretamente comparável entre os 3 anos:

- Year 1 combina "Analista de BI" e "Analytics Engineer" em uma única opção; Year 2/3 os separam. Comparação válida apenas no nível agregado `BI_ANALYTICS_ENGINEER_GROUP`.
- Year 1 separa "Engenheiro de Dados" de "Arquiteto de Dados"; Year 2 funde os dois em uma opção. Comparação válida apenas no nível agregado `DATA_ENGINEER_GROUP`.
- Year 1 separa "Desenvolvedor/Engenheiro de Software" de "Analista de Sistemas/TI"; Year 2/3 fundem em uma opção. Comparação válida apenas no nível agregado `SOFTWARE_IT_GROUP`.

Qualquer gráfico de evolução de cargo por ano deve usar os `comparability_group` da mapping table, não o `canonical_role` isolado, quando a comparação cruzar esses grupos.

## 6. Duplicate rows (Bronze, herdado do profiling original)

Mantido do profiling anterior, ainda não reavaliado excluindo timestamp/IDs técnicos (ver seção 39 do prompt mestre — próximo passo):

| Dataset | Duplicated rows (raw) |
|---|---:|
| year_1 | 4 |
| year_2 | 0 |
| year_3 | 1 |

## 7. Próximos passos de qualidade

1. Reavaliar duplicatas de year_1/year_3 excluindo timestamp e IDs técnicos para distinguir "linha duplicada" de "respondente duplicado" (seção 39 do prompt mestre).
2. Formalizar `dim_survey_question` (disponibilidade de pergunta por ano) como tabela, hoje documentada apenas em texto.
3. Modelar a distinção fina NOT_ASKED / NOT_ELIGIBLE / NOT_ANSWERED / INVALID para os campos com missingness estrutural, hoje colapsados em `UNKNOWN`.
4. Validar `education_level`, `sector`, `data_experience_band` com mapping tables próprias (hoje entram no Silver como categoria bruta, sem harmonização de rótulo).

## 8. Addendum — Gold tables de domínios 2–9 (primeiro corte), 2026-09-02

Implementadas nesta rodada: `gold_compensation_by_role`, `gold_compensation_by_seniority`, `gold_compensation_by_region`, `gold_compensation_by_work_model`, `gold_gender_representation`, `gold_technology_adoption_by_year`, `gold_ai_adoption_overview`, `gold_skill_priority_score`. Scripts: `scripts/build_compensation_gender_gold.py`, `scripts/build_technology_gold.py`, `scripts/build_ai_gold.py`, `scripts/build_skill_priority_gold.py` (validados localmente) + equivalentes Glue em `glue/silver_2_gold_compensation_gender.py` e `glue/silver_2_gold_technology_ai_skills.py` (a parte de tecnologia foi portada para PySpark nativo; a parte de AI/skill-score ainda não, documentado no próprio arquivo — precisa de acesso real ao Glue para validar antes de portar às cegas).

### 8.1 Correção de denominador — `personal_genai_use` (bug pego antes de publicar)

Primeira implementação de `gold_ai_adoption_overview` usava `len(sub)` (toda a população do ano) como denominador para as taxas de uso pessoal de GenAI. Isso é exatamente o erro que a seção 28 do prompt mestre pede para evitar: o bloco `P4_m`/`4.j` é condicional (28,7% dos respondentes de year_2 têm as 5 colunas do bloco totalmente nulas — não elegíveis, não "não usam IA"). Corrigido para usar `eligible_respondents` (quem respondeu pelo menos uma opção do bloco) como denominador. Resultado após a correção: `personal_genai_usage_rate` sobe de 85,9% para 80,3% em year_2 (o número errado estava *inflado*, não subestimado, porque não-elegíveis viravam "não usei" ao inv​és de saírem do denominador) — e o `eligible_respondents` resultante (3.772 em year_2) bate exatamente com o `eligible_respondents` do bloco de tecnologia de banco de dados do mesmo ano, o que é uma verificação de consistência forte de que ambos os blocos são gateados pela mesma condição de branching do questionário.

### 8.2 Limitação conhecida — granularidade de `salary_association` no skill score

`salary_midpoint` tem apenas ~14 valores distintos possíveis (definidos pelas faixas salariais). Isso faz com que a mediana de vários subgrupos coincida exatamente com a mediana geral, zerando `salary_association` para essas tecnologias por empate, não porque a tecnologia realmente não tenha associação salarial. Interpretar `salary_association = 0` como "empatado no valor central da distribuição", não como "nenhuma associação".

### 8.3 Escopo explicitamente não coberto neste corte

- `gold_technology_adoption_by_year` cobre apenas a família **DATABASE** (33–34 tecnologias). Linguagens, cloud, BI, ETL e stack de Data Science/ML ainda não foram convertidos para bridge — ver `documentation/analytical_domains.md`, domínio 3.
- `gold_ai_adoption_overview` cobre `enterprise_ai_priority` e `personal_genai_use`. Use cases específicos de IA (`bridge_ai_use_case`) e blockers (`bridge_ai_blocker`) ainda não implementados.
- `gold_skill_priority_score` roda só sobre a família DATABASE pelo mesmo motivo, e usa apenas year_3 para as métricas de papel/senioridade/salário (year_1/year_2 entram somente no cálculo de `adoption_growth_pp`). O componente `future_interest` não é medido (nenhuma pergunta da pesquisa cobre isso) — peso redistribuído proporcionalmente entre os outros 4 componentes, documentado no cabeçalho de `scripts/build_skill_priority_gold.py`.
- `gold_compensation_by_role` inclui os cargos como aparecem em `mapping_role.csv` (`canonical_role`), não os `comparability_group` agregados — comparar contagem de um cargo específico entre anos ainda exige checar se ele pertence a um grupo que foi fundido/dividido entre edições da pesquisa.
