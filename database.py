import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import os

# Caminho para o banco de dados SQLite
DB_PATH = 'sistema_militar.db'

def init_local_db():
    """Inicializa o banco de dados local"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Criar tabelas se não existirem
    c.execute("""
    CREATE TABLE IF NOT EXISTS alunos (
        id INTEGER PRIMARY KEY,
        numero_interno TEXT,
        nome_guerra TEXT,
        nome_completo TEXT,
        pelotao TEXT,
        especialidade TEXT,
        data_nascimento TEXT,
        pontuacao REAL,
        foto_path TEXT
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS acoes (
        id INTEGER PRIMARY KEY,
        aluno_id INTEGER,
        tipo_acao_id INTEGER,
        tipo TEXT,
        descricao TEXT,
        data TEXT,
        usuario TEXT,
        pontuacao REAL,
        pontuacao_efetiva REAL,
        sincronizado INTEGER DEFAULT 0
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS tarefas (
        id INTEGER PRIMARY KEY,
        texto TEXT,
        status TEXT,
        responsavel TEXT,
        data_criacao TEXT,
        data_conclusao TEXT,
        concluida_por TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS ordens_diarias (
        id INTEGER PRIMARY KEY,
        data TEXT,
        texto TEXT,
        autor_id TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        username TEXT PRIMARY KEY
    )
    """)

    conn.commit()
    conn.close()

def save_local_data(table_name, data_df):
    """Salva dados localmente"""
    conn = sqlite3.connect(DB_PATH)
    data_df.to_sql(table_name.lower(), conn, if_exists='replace', index=False)
    conn.close()
    return True

def load_local_data(table_name):
    """Carrega dados locais"""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
    except pd.io.sql.DatabaseError:
        df = pd.DataFrame() # Retorna DataFrame vazio se a tabela não existir
    conn.close()
    return df

def sync_with_sheets():
    """Sincroniza dados locais com Google Sheets"""
    st.info("DEBUG: Sincronizando dados com Google Sheets...")
    
    # Sincronizar Tarefas
    tarefas_local = load_local_data("Tarefas")
    if not tarefas_local.empty:
        try:
            st.info("DEBUG: Sincronizando Tarefas...")
            if _save_data_to_sheets("Sistema_Acoes_Militares", "Tarefas", tarefas_local):
                st.success("Tarefas sincronizadas com Google Sheets!")
        except Exception as e:
            st.error(f"Erro ao sincronizar tarefas com Google Sheets: {e}")

    # Sincronizar Ordens Diarias
    ordens_local = load_local_data("Ordens_Diarias")
    if not ordens_local.empty:
        try:
            st.info("DEBUG: Sincronizando Ordens Diárias...")
            if _save_data_to_sheets("Sistema_Acoes_Militares", "Ordens_Diarias", ordens_local):
                st.success("Ordens Diárias sincronizadas com Google Sheets!")
        except Exception as e:
            st.error(f"Erro ao sincronizar ordens diárias com Google Sheets: {e}")

    # Sincronizar Acoes
    conn = sqlite3.connect(DB_PATH)
    try:
        acoes_nao_sincronizadas = pd.read_sql("SELECT * FROM acoes WHERE sincronizado = 0", conn)
    except pd.io.sql.DatabaseError:
        st.warning("DEBUG: Tabela 'acoes' ou coluna 'sincronizado' não encontrada no SQLite. Pulando sincronização de ações.")
        acoes_nao_sincronizadas = pd.DataFrame()
    
    if not acoes_nao_sincronizadas.empty:
        st.info("DEBUG: Sincronizando Ações não sincronizadas...")
        try:
            # Carregar dados atuais do Google Sheets
            acoes_sheets = _load_data_from_sheets("Sistema_Acoes_Militares", "Acoes")
            
            # Mesclar dados
            if acoes_sheets.empty:
                acoes_sheets = acoes_nao_sincronizadas
            else:
                acoes_sheets = pd.concat([acoes_sheets, acoes_nao_sincronizadas], ignore_index=True)
            
            # Salvar no Google Sheets
            if _save_data_to_sheets("Sistema_Acoes_Militares", "Acoes", acoes_sheets):
                # Marcar como sincronizado
                c = conn.cursor()
                c.execute("UPDATE acoes SET sincronizado = 1 WHERE sincronizado = 0")
                conn.commit()
                st.success("Ações sincronizadas com Google Sheets!")
            else:
                st.warning("Falha ao sincronizar Ações com Google Sheets.")
        except Exception as e:
            st.error(f"Erro ao sincronizar ações com Google Sheets: {e}")
    
    conn.close()
    st.info("DEBUG: Sincronização concluída.")


# Configurar escopo e credenciais
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Função para conectar ao Google Sheets
@st.cache_resource
def connect_to_sheets():
    try:
        # Lendo credenciais do st.secrets
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES)
        client = gspread.authorize(credentials)
        st.info("DEBUG: Conexão com Google Sheets estabelecida.")
        return client
    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        st.warning("DEBUG: Falha na conexão com Google Sheets.")
        return None

# Funções internas para acesso direto ao Sheets (não usar diretamente no app)
def _load_data_from_sheets(sheet_name, worksheet_name):
    st.info(f"DEBUG: _load_data_from_sheets() chamada para {worksheet_name}")
    client = connect_to_sheets()
    if not client:
        st.warning("DEBUG: Cliente Sheets não disponível para carregamento.")
        return pd.DataFrame()
    
    try:
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        st.info(f"DEBUG: Dados de {worksheet_name} carregados do Sheets.")
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Sheets ({worksheet_name}): {e}")
        st.warning(f"DEBUG: Falha ao carregar dados de {worksheet_name} do Sheets.")
        return pd.DataFrame()

def _save_data_to_sheets(sheet_name, worksheet_name, data_df):
    st.info(f"DEBUG: _save_data_to_sheets() chamada para {worksheet_name}")
    client = connect_to_sheets()
    if not client:
        st.warning("DEBUG: Cliente Sheets não disponível para salvamento.")
        return False
    
    try:
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        
        # Limpar planilha (exceto cabeçalho)
        if worksheet.row_count > 1:
            worksheet.delete_rows(2, worksheet.row_count)
        
        # Obter cabeçalhos
        headers = worksheet.row_values(1)
        
        # Preparar dados para inserção
        # Garantir que o DataFrame tenha as colunas na ordem correta dos cabeçalhos do Sheets
        # Adicionado tratamento para colunas que podem não existir no DataFrame mas existem no Sheets
        df_to_save = data_df.reindex(columns=headers, fill_value='')
        values = df_to_save.values.tolist()
        
        # Inserir dados
        if values:
            worksheet.append_rows(values)
        
        st.info(f"DEBUG: Dados de {worksheet_name} salvos no Sheets.")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar dados no Sheets ({worksheet_name}): {e}")
        st.warning(f"DEBUG: Falha ao salvar dados de {worksheet_name} no Sheets.")
        return False


# Função principal para carregar dados (com cache e prioridade local)
@st.cache_data(ttl=300) # Cache por 5 minutos para leituras do Sheets
def load_data(sheet_name, worksheet_name):
    st.info(f"DEBUG: load_data() chamada para {worksheet_name}")
    # Tentar carregar do SQLite local
    local_df = load_local_data(worksheet_name)
    
    # Se o DataFrame local estiver vazio, carregar do Google Sheets e atualizar o SQLite local.
    if local_df.empty:
        st.info(f"Carregando {worksheet_name} do Google Sheets (local vazio ou desatualizado)...")
        sheets_df = _load_data_from_sheets(sheet_name, worksheet_name)
        if not sheets_df.empty:
            save_local_data(worksheet_name, sheets_df) # Salva no SQLite
            st.info(f"DEBUG: Dados de {worksheet_name} salvos localmente após carregar do Sheets.")
            return sheets_df
        else:
            st.warning(f"DEBUG: Não foi possível carregar {worksheet_name} de nenhum lugar.")
            return pd.DataFrame() # Retorna DataFrame vazio se não conseguir carregar de nenhum lugar
    else:
        st.info(f"Carregando {worksheet_name} do SQLite local...")
        return local_df

# Função para salvar dados
def save_data(sheet_name, worksheet_name, data_df):
    st.info(f"DEBUG: save_data() chamada para {worksheet_name}")
    # Salvar no SQLite local imediatamente
    if save_local_data(worksheet_name, data_df):
        st.success(f"Dados de {worksheet_name} salvos localmente.")
        st.info(f"DEBUG: Dados de {worksheet_name} salvos localmente.")
        # Tentar sincronizar com o Google Sheets em segundo plano (ou em lote)
        # Para este exemplo, faremos a chamada direta, mas idealmente seria assíncrona
        try:
            if _save_data_to_sheets(sheet_name, worksheet_name, data_df):
                st.success(f"Dados de {worksheet_name} sincronizados com Google Sheets.")
                st.info(f"DEBUG: Dados de {worksheet_name} sincronizados com Google Sheets.")
            else:
                st.warning(f"Falha ao sincronizar {worksheet_name} com Google Sheets. Verifique o log.")
        except Exception as e:
            st.error(f"Erro durante a sincronização de {worksheet_name} com Google Sheets: {e}")
            st.warning(f"DEBUG: Dados de {worksheet_name} salvos localmente, mas não sincronizados com Google Sheets.")

        # Limpar cache do Streamlit para garantir que a próxima leitura seja fresca
        load_data.clear()
        return True
    else:
        st.error(f"Erro ao salvar dados de {worksheet_name} localmente.")
        st.warning(f"DEBUG: Falha ao salvar dados de {worksheet_name} localmente.")
        return False


