# components.py
import streamlit as st
import pandas as pd
from database import load_data # Assumindo que database.py está no mesmo nível

@st.cache_data(ttl=3600) # Cache para os dados dos alunos
def get_alunos_data():
    """Carrega os dados dos alunos do banco de dados."""
    return load_data("Alunos")

def select_alunos_component(key_suffix=""):
    """
    Renderiza os componentes de busca e seleção múltipla de alunos.

    Args:
        key_suffix (str): Sufixo para as chaves dos widgets Streamlit para evitar conflitos.

    Returns:
        pd.DataFrame: DataFrame dos alunos selecionados.
    """
    df_alunos = get_alunos_data()

    if df_alunos is None or df_alunos.empty:
        st.warning("Não foi possível carregar os dados dos alunos.")
        return pd.DataFrame()

    st.subheader("Seleção de Alunos")

    # Campo de busca por nome
    search_query = st.text_input(
        "Buscar aluno por nome:",
        key=f"search_input_{key_suffix}",
        placeholder="Digite o nome do aluno..."
    )

    filtered_alunos = df_alunos.copy()
    if search_query:
        filtered_alunos = filtered_alunos[
            filtered_alunos['nome'].str.contains(search_query, case=False, na=False)
        ]

    # Multi-seleção de alunos
    # Usamos o 'nome' do aluno como opção visível e o 'id_aluno' como valor para seleção,
    # ou apenas o nome se id_aluno não for um campo único ou preferível.
    options_for_multiselect = filtered_alunos['nome'].tolist()
    
    # Se você tiver um ID único para cada aluno, é melhor usar uma tupla (nome, id)
    # para garantir que a seleção seja precisa, especialmente se houver nomes duplicados.
    # Ex: options_for_multiselect = filtered_alunos.apply(lambda row: f"{row['nome']} (ID: {row['id_aluno']})", axis=1).tolist()
    # E depois você precisaria extrair o ID de volta.
    
    # Por simplicidade, vamos usar o nome por enquanto, assumindo nomes únicos o suficiente
    # ou que a filtragem posterior será feita pelo nome.
    
    selected_names = st.multiselect(
        "Selecione os alunos:",
        options=options_for_multiselect,
        default=options_for_multiselect, # Por padrão, todos selecionados inicialmente
        key=f"multiselect_alunos_{key_suffix}"
    )

    # Filtrar o DataFrame original pelos nomes selecionados
    selected_alunos_df = filtered_alunos[filtered_alunos['nome'].isin(selected_names)]

    if selected_alunos_df.empty:
        st.info("Nenhum aluno selecionado ou encontrado com os critérios de busca.")
    
    return selected_alunos_df
