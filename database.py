import streamlit as st
from supabase import create_client, Client
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- INICIALIZAÇÃO DO CLIENTE SUPABASE ---
# A função é armazenada em cache para criar a conexão apenas uma vez.
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

# --- NOVA FUNÇÃO PARA CARREGAR DADOS ---
# O cache agora é mais curto, pois os dados podem mudar com mais frequência.
@st.cache_data(ttl=60)
def load_data(table_name: str) -> pd.DataFrame:
    """
    Carrega dados de uma tabela específica do Supabase.
    """
    supabase = init_supabase_client()
    if supabase is None:
        return pd.DataFrame()

    logging.info(f"Carregando dados da tabela Supabase: '{table_name}'")
    try:
        response = supabase.table(table_name).select("*").execute()
        df = pd.DataFrame(response.data)
        return df
    except Exception as e:
        logging.error(f"Ocorreu um erro ao carregar dados da tabela '{table_name}': {e}", exc_info=True)
        st.error(f"Erro ao ler a tabela '{table_name}' do Supabase: {e}")
        return pd.DataFrame()

# A função save_data(table_name, df) foi removida.
# As operações de escrita serão feitas diretamente nas páginas do app.