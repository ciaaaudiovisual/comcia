# No arquivo database.py

import streamlit as st
from supabase import create_client, Client
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@st.cache_resource
def init_supabase_client() -> Client:
    """Inicializa e retorna o cliente Supabase usando as credenciais do Streamlit Secrets."""
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        st.error(f"Erro ao conectar com o Supabase. Verifique seu arquivo 'secrets.toml'. Detalhe: {e}")
        return None

# --- FUNÇÃO load_data ATUALIZADA COM PAGINAÇÃO ---
@st.cache_data(ttl=60)
def load_data(table_name: str) -> pd.DataFrame:
    """
    Carrega TODOS os dados de uma tabela específica do Supabase,
    usando paginação para superar o limite de 1000 linhas.
    """
    supabase = init_supabase_client()
    if supabase is None:
        return pd.DataFrame()

    logging.info(f"Carregando TODOS os dados da tabela Supabase: '{table_name}'")
    try:
        all_data = []
        page = 0
        page_size = 1000  # O tamanho da página padrão do Supabase

        while True:
            # Calcula o range (intervalo) da página atual
            start_index = page * page_size
            end_index = start_index + page_size - 1
            
            # Busca a página atual de dados usando .range()
            response = supabase.table(table_name).select("*").range(start_index, end_index).execute()
            
            current_page_data = response.data
            if not current_page_data:
                # Se não houver mais dados, para o loop
                break
            
            # Adiciona os dados da página à nossa lista completa
            all_data.extend(current_page_data)
            
            # Se a página retornou menos dados que o tamanho máximo,
            # significa que chegamos ao fim.
            if len(current_page_data) < page_size:
                break
            
            # Prepara para buscar a próxima página na próxima iteração
            page += 1

        df = pd.DataFrame(all_data)
        logging.info(f"Carregamento concluído. Total de {len(df)} linhas da tabela '{table_name}'.")
        return df
        
    except Exception as e:
        logging.error(f"Ocorreu um erro ao carregar dados da tabela '{table_name}': {e}", exc_info=True)
        st.error(f"Erro ao ler a tabela '{table_name}' do Supabase: {e}")
        return pd.DataFrame()
