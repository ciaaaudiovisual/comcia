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

    # Garante que as colunas principais não têm valores nulos para os filtros
    alunos_df['pelotao'] = alunos_df['pelotao'].fillna('Não Definido')
    alunos_df['nome_guerra'] = alunos_df['nome_guerra'].fillna('Nome Desconhecido')
    alunos_df['numero_interno'] = alunos_df['numero_interno'].fillna('S/N') # Garante que numero_interno não é nulo

    col1, col2 = st.columns([1, 2])

    with col1:
        opcoes_pelotao = ["Todos"] + sorted(alunos_df['pelotao'].unique().tolist())
        pelotao_selecionado = st.selectbox(
            "Filtrar por Pelotão:", 
            options=opcoes_pelotao, 
            key=f"pelotao_filter_{key_suffix}"
        )

    df_alunos_filtrados = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        df_alunos_filtrados = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]

    with col2:
        busca_nome_guerra = st.text_input(
            "Buscar por Nome de Guerra:", 
            help="Digite parte do nome de guerra para filtrar.",
            key=f"nome_guerra_search_{key_suffix}"
        )
        if busca_nome_guerra:
            df_alunos_filtrados = df_alunos_filtrados[
                df_alunos_filtrados['nome_guerra'].str.contains(busca_nome_guerra, case=False, na=False)
            ]

    if include_full_name_search:
        busca_nome_completo = st.text_input(
            "Buscar por Nome Completo:",
            help="Digite parte do nome completo para filtrar.",
            key=f"nome_completo_search_{key_suffix}"
        )
        if busca_nome_completo:
            if 'nome_completo' in df_alunos_filtrados.columns:
                df_alunos_filtrados = df_alunos_filtrados[
                    df_alunos_filtrados['nome_completo'].astype(str).str.contains(busca_nome_completo, case=False, na=False)
                ]

    # --- ALTERAÇÃO AQUI: Formata as opções para incluir o número interno ---
    # Garante que não há alunos duplicados nas opções
    df_opcoes = df_alunos_filtrados.drop_duplicates(subset=['id'])
    
    # Cria os rótulos no formato "Numero Interno - Nome de Guerra"
    opcoes_formatadas = df_opcoes.apply(
        lambda row: f"{row.get('numero_interno', 'S/N')} - {row.get('nome_guerra', 'N/A')}",
        axis=1
    ).tolist()

    # Ordena a lista de opções
    opcoes_formatadas = sorted(opcoes_formatadas)
    # --- FIM DA ALTERAÇÃO ---

    if "Selecionar Todos os Visíveis" not in opcoes_formatadas and not df_alunos_filtrados.empty:
        opcoes_formatadas.insert(0, "Selecionar Todos os Visíveis")

    # O widget multiselect agora usa as opções formatadas
    selected_options = st.multiselect(
        "Selecione Aluno(s):",
        options=opcoes_formatadas,
        key=f"alunos_multiselect_{key_suffix}"
    )

    # --- ALTERAÇÃO AQUI: Lógica para retornar os alunos selecionados com base na opção formatada ---
    if "Selecionar Todos os Visíveis" in selected_options:
        # Retorna todos os alunos que estão visíveis após os filtros
        return df_alunos_filtrados
    elif selected_options:
        # Extrai os números internos das opções selecionadas (ex: "101 - JOÃO" -> "101")
        numeros_internos_selecionados = [option.split(' - ')[0] for option in selected_options]
        # Filtra o DataFrame original com base nesses números internos
        return df_alunos_filtrados[df_alunos_filtrados['numero_interno'].isin(numeros_internos_selecionados)]
    else:
        # Se nada for selecionado, retorna um DataFrame vazio
        return pd.DataFrame()
    # --- FIM DA ALTERAÇÃO ---
