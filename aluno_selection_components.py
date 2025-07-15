# aluno_selection_components.py

import streamlit as st
import pandas as pd
from database import load_data # Assumindo que database.py está disponível

def render_alunos_filter_and_selection(key_suffix: str = "", include_full_name_search: bool = True) -> pd.DataFrame:
    """
    Renderiza um componente padronizado para filtrar e selecionar alunos.
    Retorna um DataFrame dos alunos selecionados.

    Args:
        key_suffix (str): Sufixo para as chaves dos widgets Streamlit para evitar colisões.
        include_full_name_search (bool): Se True, inclui um campo de busca por nome completo.
    """
    alunos_df = load_data("Alunos")
    
    if alunos_df.empty:
        st.info("Nenhum aluno cadastrado para seleção.")
        return pd.DataFrame()

    st.subheader("Filtro de Alunos")

    # Garante que 'pelotao' e 'nome_guerra' não têm NaN para opções
    alunos_df['pelotao'] = alunos_df['pelotao'].fillna('Não Definido')
    alunos_df['nome_guerra'] = alunos_df['nome_guerra'].fillna('Nome Desconhecido')

    col1, col2 = st.columns([1, 2])

    with col1:
        opcoes_pelotao = ["Todos"] + sorted(alunos_df['pelotao'].unique().tolist())
        pelotao_selecionado = st.selectbox(
            "Filtrar por Pelotão:", 
            options=opcoes_pelotao, 
            key=f"pelotao_filter_{key_suffix}"
        )

    df_alunos_filtrados_pelo_pelotao = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        df_alunos_filtrados_pelo_pelotao = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]

    # Campo de busca por nome de guerra
    with col2:
        busca_nome_guerra = st.text_input(
            "Buscar por Nome de Guerra:", 
            help="Digite parte do nome de guerra para filtrar.",
            key=f"nome_guerra_search_{key_suffix}"
        )
        if busca_nome_guerra:
            df_alunos_filtrados_pelo_pelotao = df_alunos_filtrados_pelo_pelotao[
                df_alunos_filtrados_pelo_pelotao['nome_guerra'].str.contains(busca_nome_guerra, case=False, na=False)
            ]

    # Campo de busca por nome completo (opcional)
    if include_full_name_search:
        busca_nome_completo = st.text_input(
            "Buscar por Nome Completo:",
            help="Digite parte do nome completo para filtrar.",
            key=f"nome_completo_search_{key_suffix}"
        )
        if busca_nome_completo:
            # Certifique-se de que a coluna 'nome_completo' existe e é string
            if 'nome_completo' in df_alunos_filtrados_pelo_pelotao.columns:
                df_alunos_filtrados_pelo_pelotao = df_alunos_filtrados_pelo_pelotao[
                    df_alunos_filtrados_pelo_pelotao['nome_completo'].astype(str).str.contains(busca_nome_completo, case=False, na=False)
                ]
            else:
                st.warning("A coluna 'nome_completo' não está disponível para busca.")

    # Opções para o multiselect de alunos (baseado nos filtros aplicados)
    opcoes_alunos_para_selecao = sorted(df_alunos_filtrados_pelo_pelotao['nome_guerra'].unique().tolist())
    
    # Adiciona uma opção para selecionar todos os alunos visíveis
    if "Selecionar Todos os Visíveis" not in opcoes_alunos_para_selecao and not df_alunos_filtrados_pelo_pelotao.empty:
        opcoes_alunos_para_selecao.insert(0, "Selecionar Todos os Visíveis")

    selected_nomes_guerra = st.multiselect(
        "Selecione Aluno(s):",
        options=opcoes_alunos_para_selecao,
        key=f"alunos_multiselect_{key_suffix}"
    )

    # Lógica para "Selecionar Todos os Visíveis"
    if "Selecionar Todos os Visíveis" in selected_nomes_guerra:
        # Se "Selecionar Todos os Visíveis" for escolhido, retorne todos os alunos no df_alunos_filtrados_pelo_pelotao
        return df_alunos_filtrados_pelo_pelotao
    elif selected_nomes_guerra:
        # Retorna apenas os alunos explicitamente selecionados
        return df_alunos_filtrados_pelo_pelotao[df_alunos_filtrados_pelo_pelotao['nome_guerra'].isin(selected_nomes_guerra)]
    else:
        # Se nada for selecionado (e "Selecionar Todos" não foi clicado), retorne um DataFrame vazio ou todos os filtrados, dependendo da sua regra.
        # Por padrão, vamos retornar um DataFrame vazio se nada for selecionado explicitamente.
        return pd.DataFrame()
