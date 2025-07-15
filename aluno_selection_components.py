# aluno_selection_components.py
import streamlit as st
import pandas as pd
from database import load_data # Assumindo que database.py está no mesmo nível

@st.cache_data(ttl=3600) # Cache para os dados dos alunos por 1 hora
def get_all_alunos_data():
    """
    Carrega todos os dados dos alunos do banco de dados e aplica o preenchimento de N/A.
    """
    df = load_data("Alunos")
    if df is not None and not df.empty:
        # Garante que colunas essenciais para busca e exibição não sejam NaN
        df['nome_guerra'] = df['nome_guerra'].fillna('N/A')
        df['numero_interno'] = df['numero_interno'].fillna('S/N')
        df['nip'] = df['nip'].fillna('N/A')
        df['nome_completo'] = df['nome_completo'].fillna('N/A')
        
        # --- CORREÇÃO DO KeyError: VERIFICAR SE A COLUNA EXISTE ANTES DE PREENCHER ---
        if 'turma' in df.columns: # 
            df['turma'] = df['turma'].fillna('N/A') # 
        else:
            df['turma'] = 'N/A' #  # Se a coluna 'turma' não existe, cria ela com um valor padrão

        # Garante que 'id' é string para consistência nos merges
        df['id'] = df['id'].astype(str)

    return df

def render_alunos_filter_and_selection(key_suffix="", include_full_name_search=False):
    """
    Renderiza os componentes de busca e seleção múltipla de alunos.

    Args:
        key_suffix (str): Sufixo para as chaves dos widgets Streamlit para evitar conflitos.
        include_full_name_search (bool): Se True, inclui um campo de busca por nome completo.

    Returns:
        pd.DataFrame: DataFrame dos alunos selecionados.
    """
    st.subheader("Filtro e Seleção de Alunos")

    df_alunos = get_all_alunos_data()

    if df_alunos is None or df_alunos.empty:
        st.warning("Não foi possível carregar os dados dos alunos. Verifique a tabela 'Alunos'.")
        return pd.DataFrame()

    # --- Campos de Busca ---
    col_search1, col_search2 = st.columns(2)
    with col_search1:
        search_nome_guerra = st.text_input(
            "Buscar por Nome de Guerra:",
            key=f"search_nome_guerra_{key_suffix}",
            placeholder="Ex: JOKER",
            help="Busca insensível a maiúsculas/minúsculas."
        )
    with col_search2:
        search_numero_interno = st.text_input(
            "Buscar por Nº Interno:",
            key=f"search_numero_interno_{key_suffix}",
            placeholder="Ex: 101"
        )
    
    if include_full_name_search:
        col_search3, col_search4 = st.columns(2)
        with col_search3:
            search_nip = st.text_input(
                "Buscar por NIP:",
                key=f"search_nip_{key_suffix}",
                placeholder="Ex: 12345678"
            )
        with col_search4:
            search_nome_completo = st.text_input(
                "Buscar por Nome Completo:",
                key=f"search_nome_completo_{key_suffix}",
                placeholder="Ex: Jack Napier",
                help="Busca insensível a maiúsculas/minúsculas."
            )

    # --- Filtro por Turma ---
    #  Garante que 'turma' é uma coluna, mesmo que 'N/A'
    turmas_unicas = sorted([t for t in df_alunos['turma'].unique() if pd.notna(t) and t != 'N/A'])
    selected_turma = st.selectbox(
        "Filtrar por Turma:",
        options=["Todas as Turmas"] + turmas_unicas,
        key=f"filter_turma_{key_suffix}"
    )

    # --- Aplica os Filtros ---
    filtered_alunos = df_alunos.copy()

    if search_nome_guerra:
        filtered_alunos = filtered_alunos[
            filtered_alunos['nome_guerra'].str.contains(search_nome_guerra, case=False, na=False)
        ]
    if search_numero_interno:
        filtered_alunos = filtered_alunos[
            filtered_alunos['numero_interno'].astype(str).str.contains(search_numero_interno, case=False, na=False)
        ]
    if include_full_name_search:
        if search_nip:
            filtered_alunos = filtered_alunos[
                filtered_alunos['nip'].astype(str).str.contains(search_nip, case=False, na=False)
            ]
        if search_nome_completo:
            filtered_alunos = filtered_alunos[
                filtered_alunos['nome_completo'].str.contains(search_nome_completo, case=False, na=False)
            ]
    
    if selected_turma != "Todas as Turmas":
        filtered_alunos = filtered_alunos[filtered_alunos['turma'] == selected_turma]


    # Prepara as opções para o multiselect
    options_for_multiselect = filtered_alunos.apply(
        lambda row: f"{row['numero_interno']} - {row['nome_guerra']} ({row.get('pelotao', 'N/A')})", axis=1
    ).tolist()
    options_for_multiselect.sort() # Garante que as opções estejam ordenadas

    # Mantém os IDs dos alunos para fácil acesso após a seleção
    label_to_id_map = filtered_alunos.set_index(
        filtered_alunos.apply(lambda row: f"{row['numero_interno']} - {row['nome_guerra']} ({row.get('pelotao', 'N/A')})", axis=1)
    )['id'].to_dict()

    # --- Checkbox para Selecionar Todos os Alunos Filtrados ---
    select_all_filtered = st.checkbox(
        "Selecionar todos os alunos filtrados",
        key=f"select_all_filtered_{key_suffix}"
    )

    default_selection = options_for_multiselect if select_all_filtered else []

    selected_labels = st.multiselect(
        "Selecione os alunos (os que correspondem à busca):",
        options=options_for_multiselect,
        default=default_selection, # Agora o default depende do checkbox
        key=f"multiselect_alunos_{key_suffix}"
    )

    # Converte os labels selecionados de volta para IDs de alunos
    selected_ids = [label_to_id_map[label] for label in selected_labels if label in label_to_id_map]
    
    # Filtra o DataFrame original de alunos pelos IDs selecionados
    selected_alunos_df = df_alunos[df_alunos['id'].isin(selected_ids)].copy()

    if selected_alunos_df.empty and (search_nome_guerra or search_numero_interno or (include_full_name_search and (search_nip or search_nome_completo)) or selected_turma != "Todas as Turmas"):
        st.info("Nenhum aluno encontrado com os critérios de busca/filtro.")
    elif selected_alunos_df.empty:
        st.info("Nenhum aluno selecionado.")
    
    return selected_alunos_df
