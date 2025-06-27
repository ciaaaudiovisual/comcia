import streamlit as st
import pandas as pd
import sqlite3
import gspread
from google.oauth2.service_account import Credentials
import logging

# Configuração do logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Funções de Conexão com Base de Dados Local (SQLite) ---

def connect_to_local_db():
    """Conecta à base de dados SQLite local."""
    try:
        conn = sqlite3.connect('local_database.db', check_same_thread=False)
        logging.info("Conexão com a base de dados local SQLite estabelecida.")
        return conn
    except sqlite3.Error as e:
        logging.error(f"Erro ao conectar à base de dados SQLite: {e}")
        return None

def init_local_db():
    """Inicializa a base de dados local e cria as tabelas se não existirem."""
    logging.info("init_local_db() chamado.")
    conn = connect_to_local_db()
    if conn is None:
        return

    tables_schema = {
        "Alunos": ["id", "numero_interno", "nome_guerra", "nome_completo", "pelotao", "especialidade", "data_nascimento", "pontuacao", "foto_url", "nip", "antiguidade", "graduacao"],
        "Acoes": ["id", "aluno_id", "tipo_acao_id", "tipo", "descricao", "data", "usuario", "pontuacao", "pontuacao_efetiva"],
        "Users": ["id", "username", "password", "nome", "permissao"],
        "Tipos_Acao": ["id", "nome", "descricao", "pontuacao", "codigo"],
        "Programacao": ["id", "data", "horario", "descricao", "local", "responsavel", "obs", "concluida"] # Nome da aba corrigido para 'Programacao' se for o caso
    }
    
    try:
        cursor = conn.cursor()
        for table_name, columns in tables_schema.items():
            columns_sql = ", ".join([f'"{col}" TEXT' for col in columns])
            cursor.execute(f'CREATE TABLE IF NOT EXISTS {table_name} ({columns_sql})')
        conn.commit()
        logging.info("Tabelas locais verificadas/criadas com sucesso.")
    except sqlite3.Error as e:
        logging.error(f"Erro ao criar tabelas no SQLite: {e}")
    finally:
        if conn:
            conn.close()

# --- Funções de Conexão e Dados com Google Sheets ---

@st.cache_resource(ttl=600)
def connect_to_google_sheets():
    """Conecta ao Google Sheets usando as credenciais do Streamlit secrets e armazena o cliente em cache."""
    logging.info("Tentando conectar ao Google Sheets...")
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        client = gspread.authorize(creds)
        logging.info("Conexão com Google Sheets estabelecida com sucesso.")
        return client
    except Exception as e:
        logging.error(f"Falha na conexão com Google Sheets: {e}", exc_info=True)
        st.error(f"Erro de conexão com o Google Sheets. Verifique as credenciais em st.secrets. Detalhe: {e}")
        return None

@st.cache_data(ttl=300)
def load_data(sheet_name, table_name):
    """
    Carrega dados de uma aba específica do Google Sheets.
    Esta função é armazenada em cache e é a única forma de carregar dados do Sheets.
    """
    logging.info(f"Carregando dados do Sheets: Aba '{table_name}'")
    client = connect_to_google_sheets()
    if client is None: 
        st.error("Não foi possível carregar dados pois a conexão com o Google Sheets falhou.")
        return pd.DataFrame() # Retorna DataFrame vazio se a conexão falhar
    
    try:
        worksheet = client.open(sheet_name).worksheet(table_name)
        # numericise_ignore=['all'] garante que todos os dados, como 'id', venham como strings
        data = worksheet.get_all_records(numericise_ignore=['all'])
        
        # Se a planilha estiver vazia, mas tiver cabeçalho
        if not data:
            headers = worksheet.row_values(1)
            return pd.DataFrame(columns=headers) if headers else pd.DataFrame()
            
        return pd.DataFrame(data)

    except gspread.exceptions.WorksheetNotFound:
        logging.warning(f"Aba '{table_name}' não encontrada na planilha '{sheet_name}'.")
        st.warning(f"Aba '{table_name}' não foi encontrada na planilha. Verifique o nome.")
        return pd.DataFrame()
    except Exception as e:
        logging.error(f"Erro ao carregar dados da aba '{table_name}': {e}", exc_info=True)
        st.error(f"Ocorreu um erro ao carregar dados da aba '{table_name}'. Detalhe: {e}")
        return pd.DataFrame()

def save_data(sheet_name, worksheet_name, df_to_save):
    """
    Salva um DataFrame numa aba específica do Google Sheets usando a conexão em cache.
    """
    logging.info(f"Salvando dados no Sheets: Aba '{worksheet_name}'")
    client = connect_to_google_sheets()
    if client is None:
        st.error("Não foi possível salvar os dados pois a conexão com o Google Sheets falhou.")
        return False

    try:
        sheet = client.open(sheet_name)
        try:
            worksheet = sheet.worksheet(worksheet_name)
            worksheet.clear() # Limpa a aba antes de escrever
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existe, cria uma nova
            worksheet = sheet.add_worksheet(title=worksheet_name, rows="100", cols="20")

        # Converte o DataFrame para uma lista de listas para o gspread
        df_to_save = df_to_save.fillna('') # Substitui NaN por strings vazias para evitar erros
        worksheet.update([df_to_save.columns.values.tolist()] + df_to_save.values.tolist())
        logging.info(f"Dados salvos com sucesso na aba '{worksheet_name}'.")
        
        # Limpa o cache para que a próxima leitura puxe os dados atualizados
        st.cache_data.clear()
        
        return True
    except Exception as e:
        logging.error(f"Falha ao salvar os dados no Google Sheets: {e}", exc_info=True)
        st.error(f"Falha ao salvar os dados no Google Sheets. Detalhe: {e}")
        return False

# --- Funções de Sincronização e Base de Dados Local ---

def save_data_locally(df, table_name):
    """Salva um DataFrame na base de dados SQLite local."""
    if df is None or df.empty: return
    conn = connect_to_local_db()
    if conn is None: return
    
    try:
        df.to_sql(table_name, conn, if_exists='replace', index=False)
        conn.commit()
    finally:
        if conn: conn.close()

def sync_with_sheets():
    """Sincroniza todos os dados locais PARA o Google Sheets (Upload)."""
    logging.info("Iniciando sincronização local -> Sheets...")
    sheet_name = st.secrets.get("gcp_service_account", {}).get("sheet_name", "Sistema_Acoes_Militares")
    
    conn = connect_to_local_db()
    if conn is None: return
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        local_tables = [t[0] for t in cursor.fetchall()]

        for table_name in local_tables:
            local_df = pd.read_sql(f'SELECT * FROM {table_name}', conn)
            if not local_df.empty:
                logging.info(f"Sincronizando tabela '{table_name}' para o Sheets.")
                save_data(sheet_name, table_name, local_df)
    finally:
        conn.close()
    
    st.success("Sincronização de dados locais para o Google Sheets concluída!")

