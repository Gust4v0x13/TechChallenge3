"""
Cross-year source field maps for the State of Data Brasil surveys.

Codes recovered directly from the raw CSV headers (data/raw/survey_year_N/*.csv),
NOT from the earlier set()-based raw_columns_yearN.txt exports (see
documentation/schema_audit_cross_year.md for why those undercounted columns).

Year 1 / Year 2 headers are serialized as "(code, label)" tuple strings.
Year 3 headers are "code_label" dot-notation strings.
"""

YEAR1_FIELD_CODES = {
    "age_band": "P1_a_a ",
    "gender": "P1_b ",
    "state": "P1_e_a ",
    "region": "P1_e_b ",
    "education_level": "P1_h ",
    "education_area": "P1_i ",
    "employment_status": "P2_a ",
    "sector": "P2_b ",
    "company_size": "P2_c ",
    "manager_flag": "P2_d ",
    "current_role": "P2_f ",
    "seniority": "P2_g ",
    "salary_band": "P2_h ",
    "data_experience_band": "P2_i ",
    "it_experience_band": "P2_j ",
    "current_work_model": "P2_q ",
    "ideal_work_model": "P2_r ",
    "rto_attitude": "P2_s ",
    # not present in Year 1 raw export (confirmed absent, not a parsing artifact)
    "ethnicity": None,
    "pcd_flag": None,
}

YEAR2_FIELD_CODES = {
    "age_band": "P1_a_1 ",
    "gender": "P1_b ",
    "ethnicity": "P1_c ",
    "pcd_flag": "P1_d ",
    "state": "P1_i_1 ",
    "region": "P1_i_2 ",
    "education_level": "P1_l ",
    "education_area": "P1_m ",
    "employment_status": "P2_a ",
    "sector": "P2_b ",
    "company_size": "P2_c ",
    "manager_flag": "P2_d ",
    "current_role": "P2_f ",
    "seniority": "P2_g ",
    "salary_band": "P2_h ",
    "data_experience_band": "P2_i ",
    "it_experience_band": "P2_j ",
    "current_work_model": "P2_r ",
    "ideal_work_model": "P2_s ",
    "rto_attitude": "P2_t ",
}

YEAR3_FIELD_CODES = {
    "age_band": "1.a.1_faixa_idade",
    "gender": "1.b_genero",
    "ethnicity": "1.c_cor/raca/etnia",
    "pcd_flag": "1.d_pcd",
    "state": "1.i.1_uf_onde_mora",
    "region": "1.i.2_regiao_onde_mora",
    "education_level": "1.l_nivel_de_ensino",
    "education_area": "1.m_área_de_formação",
    "employment_status": "2.a_situação_de_trabalho",
    "sector": "2.b_setor",
    "company_size": "2.c_numero_de_funcionarios",
    "manager_flag": "2.d_atua_como_gestor",
    "current_role": "2.f_cargo_atual",
    "seniority": "2.g_nivel",
    "salary_band": "2.h_faixa_salarial",
    "data_experience_band": "2.i_tempo_de_experiencia_em_dados",
    "it_experience_band": "2.j_tempo_de_experiencia_em_ti",
    "current_work_model": "2.q_modelo_de_trabalho_atual",
    "ideal_work_model": "2.r_modelo_de_trabalho_ideal",
    "rto_attitude": "2.s_atitude_em_caso_de_retorno_presencial",
}

FIELD_CODES_BY_YEAR = {
    "year_1": YEAR1_FIELD_CODES,
    "year_2": YEAR2_FIELD_CODES,
    "year_3": YEAR3_FIELD_CODES,
}
