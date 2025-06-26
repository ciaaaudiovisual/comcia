import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import sqlite3
import os

print("DEBUG: database.py - Início do script")

# Caminho para o banco de dados SQLite
DB_PATH = 'sistema_militar.db'

def init_local_db():
    print("DEBUG: database.py - init_local_db() chamada")
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
    print("DEBUG: database.py - init_local_db() concluída")

def save_local_data(table_name, data_df):
    print(f"DEBUG: database.py - save_local_data() chamada para {table_name}")
    conn = sqlite3.connect(DB_PATH)
    data_df.to_sql(table_name.lower(), conn, if_exists='replace', index=False)
    conn.close()
    print(f"DEBUG: database.py - Dados de {table_name} salvos localmente.")
    return True

def load_local_data(table_name):
    print(f"DEBUG: database.py - load_local_data() chamada para {table_name}")
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name.lower()}", conn)
        print(f"DEBUG: database.py - Dados de {table_name} carregados do SQLite local: {len(df)} linhas")
    except pd.io.sql.DatabaseError as e:
        print(f"ERROR: database.py - Erro ao carregar dados de {table_name} do SQLite: {e}. Retornando DataFrame vazio.")
        df = pd.DataFrame() # Retorna DataFrame vazio se a tabela não existir
    conn.close()
    return df

def sync_with_sheets():
    print("DEBUG: database.py - sync_with_sheets() chamada")
    # Exemplo de sincronização para 'tarefas' e 'ordens_diarias'
    # Você precisará adaptar isso para todas as suas tabelas

    # Sincronizar Tarefas
    tarefas_local = load_local_data("Tarefas")
    if not tarefas_local.empty:
        try:
            print("DEBUG: database.py - Tentando sincronizar Tarefas com Google Sheets")
            # Carregar dados atuais do Google Sheets
            tarefas_sheets = _load_data_from_sheets("Sistema_Acoes_Militares", "Tarefas")
            
            # Comparar e atualizar (lógica simplificada: sobrescreve tudo)
            # Para uma sincronização mais robusta, você precisaria de timestamps ou IDs de versão
            if _save_data_to_sheets("Sistema_Acoes_Militares", "Tarefas", tarefas_local):
                st.success("Tarefas sincronizadas com Google Sheets!")
                print("DEBUG: database.py - Tarefas sincronizadas com Google Sheets com sucesso.")
        except Exception as e:
            st.error(f"Erro ao sincronizar tarefas com Google Sheets: {e}")
            print(f"ERROR: database.py - Erro ao sincronizar tarefas com Google Sheets: {e}")

    # Sincronizar Ordens Diarias
    ordens_local = load_local_data("Ordens_Diarias")
    if not ordens_local.empty:
        try:
            print("DEBUG: database.py - Tentando sincronizar Ordens Diárias com Google Sheets")
            ordens_sheets = _load_data_from_sheets("Sistema_Acoes_Militares", "Ordens_Diarias")
            if _save_data_to_sheets("Sistema_Acoes_Militares", "Ordens_Diarias", ordens_local):
                st.success("Ordens Diárias sincronizadas com Google Sheets!")
                print("DEBUG: database.py - Ordens Diárias sincronizadas com Google Sheets com sucesso.")
        except Exception as e:
            st.error(f"Erro ao sincronizar ordens diárias com Google Sheets: {e}")
            print(f"ERROR: database.py - Erro ao sincronizar ordens diárias com Google Sheets: {e}")

    # Sincronizar Acoes (já existente)
    conn = sqlite3.connect(DB_PATH)
    acoes_nao_sincronizadas = pd.read_sql("SELECT * FROM acoes WHERE sincronizado = 0", conn)
    
    if not acoes_nao_sincronizadas.empty:
        print("DEBUG: database.py - Tentando sincronizar Ações não sincronizadas com Google Sheets")
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
            print("DEBUG: database.py - Ações sincronizadas com Google Sheets e marcadas como sincronizadas.")
    
    conn.close()
    print("DEBUG: database.py - sync_with_sheets() concluída")
    return True


# Configurar escopo e credenciais
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Função para conectar ao Google Sheets
@st.cache_resource
def connect_to_sheets():
    print("DEBUG: database.py - connect_to_sheets() chamada")
    try:
        # Lendo credenciais do st.secrets
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES)
        client = gspread.authorize(credentials)
        print("DEBUG: database.py - Conexão com Sheets bem-sucedida")
        return client
    except Exception as e:
        st.error(f"Erro ao conectar com Google Sheets: {e}")
        print(f"ERROR: database.py - Erro ao conectar com Google Sheets: {e}")
        return None

# Funções internas para acesso direto ao Sheets (não usar diretamente no app)
def _load_data_from_sheets(sheet_name, worksheet_name):
    print(f"DEBUG: database.py - _load_data_from_sheets() chamada para {worksheet_name}")
    client = connect_to_sheets()
    if not client:
        print("DEBUG: database.py - Cliente Sheets não disponível, retornando DataFrame vazio.")
        return pd.DataFrame()
    
    try:
        sheet = client.open(sheet_name)
        worksheet = sheet.worksheet(worksheet_name)
        data = worksheet.get_all_records()
        print(f"DEBUG: database.py - Dados de {worksheet_name} carregados do Sheets: {len(data)} registros")
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao carregar dados do Sheets ({worksheet_name}): {e}")
        print(f"ERROR: database.py - Erro ao carregar dados do Sheets ({worksheet_name}): {e}")
        return pd.DataFrame()

def _save_data_to_sheets(sheet_name, worksheet_name, data_df):
    print(f"DEBUG: database.py - _save_data_to_sheets() chamada para {worksheet_name}")
    client = connect_to_sheets()
    if not client:
        print("DEBUG: database.py - Cliente Sheets não disponível, não é possível salvar.")
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
        values = data_df[headers].values.tolist()
        
        # Inserir dados
        if values:
            worksheet.append_rows(values)
        
        print(f"DEBUG: database.py - Dados de {worksheet_name} salvos no Sheets com sucesso.")
        return True
    except Exception as e:
        st.error(f"Erro ao salvar dados no Sheets ({worksheet_name}): {e}")
        print(f"ERROR: database.py - Erro ao salvar dados no Sheets ({worksheet_name}): {e}")
        return False


# Função principal para carregar dados (com cache e prioridade local)
@st.cache_data(ttl=300) # Cache por 5 minutos para leituras do Sheets
def load_data(sheet_name, worksheet_name):
    print(f"DEBUG: database.py - load_data() chamada para {worksheet_name}")
    # Tentar carregar do SQLite local
    local_df = load_local_data(worksheet_name)
    
    # Se o DataFrame local estiver vazio, carregar do Google Sheets e atualizar o SQLite local.
    if local_df.empty:
        st.info(f"Carregando {worksheet_name} do Google Sheets (local vazio ou desatualizado)...")
        print(f"DEBUG: database.py - Local vazio para {worksheet_name}, tentando carregar do Sheets.")
        sheets_df = _load_data_from_sheets(sheet_name, worksheet_name)
        if not sheets_df.empty:
            save_local_data(worksheet_name, sheets_df) # Salva no SQLite
            print(f"DEBUG: database.py - Dados de {worksheet_name} carregados do Sheets e salvos localmente.")
            return sheets_df
        else:
            print(f"DEBUG: database.py - Não foi possível carregar {worksheet_name} do Sheets, retornando DataFrame vazio.")
            return pd.DataFrame() # Retorna DataFrame vazio se não conseguir carregar de nenhum lugar
    else:
        st.info(f"Carregando {worksheet_name} do SQLite local...")
        print(f"DEBUG: database.py - Carregando {worksheet_name} do SQLite local.")
        return local_df

# Função para salvar dados
def save_data(sheet_name, worksheet_name, data_df):
    print(f"DEBUG: database.py - save_data() chamada para {worksheet_name}")
    # Salvar no SQLite local imediatamente
    if save_local_data(worksheet_name, data_df):
        st.success(f"Dados de {worksheet_name} salvos localmente.")
        print(f"DEBUG: database.py - Dados de {worksheet_name} salvos localmente com sucesso.")
        # Tentar sincronizar com o Google Sheets em segundo plano (ou em lote)
        # Para este exemplo, faremos a chamada direta, mas idealmente seria assíncrona
        try:
            print(f"DEBUG: database.py - Tentando sincronizar {worksheet_name} com Google Sheets.")
            if _save_data_to_sheets(sheet_name, worksheet_name, data_df):
                st.success(f"Dados de {worksheet_name} sincronizados com Google Sheets.")
                print(f"DEBUG: database.py - Dados de {worksheet_name} sincronizados com Google Sheets com sucesso.")
            else:
                st.warning(f"Falha ao sincronizar {worksheet_name} com Google Sheets. Verifique o log.")
                print(f"WARNING: database.py - Falha ao sincronizar {worksheet_name} com Google Sheets.")
        except Exception as e:
            st.error(f"Erro durante a sincronização de {worksheet_name} com Google Sheets: {e}")
            st.warning(f"Dados de {worksheet_name} salvos localmente, mas não sincronizados com Google Sheets.")
            print(f"ERROR: database.py - Erro durante a sincronização de {worksheet_name} com Google Sheets: {e}")

        # Limpar cache do Streamlit para garantir que a próxima leitura seja fresca
        load_data.clear()
        return True
    else:
        st.error(f"Erro ao salvar dados de {worksheet_name} localmente.")
        print(f"ERROR: database.py - Erro ao salvar dados de {worksheet_name} localmente.")
        return False

print("DEBUG: database.py - Fim do script")


