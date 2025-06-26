import streamlit as st
from auth import check_authentication, login
from database import init_local_db, sync_with_sheets
from dashboard import show_dashboard
from alunos import show_alunos
from acoes import show_lancamentos_page
from ordens import show_ordens as show_ordens_e_tarefas # Renomeado para evitar conflito
from relatorios import show_relatorios
from config import show_config

print("DEBUG: app.py - Início do script principal")
st.write("DEBUG: app.py - Iniciando o aplicativo...")

# Inicializa o banco de dados local na primeira execução
init_local_db()
print("DEBUG: app.py - init_local_db() chamado")
st.write("DEBUG: app.py - Banco de dados local inicializado.")

# Verifica autenticação
if not check_authentication():
    print("DEBUG: app.py - Usuário não autenticado, exibindo tela de login.")
    st.stop() # Para a execução se não autenticado

print(f"DEBUG: app.py - Usuário autenticado: {st.session_state.username}, Role: {st.session_state.role}")
st.write(f"DEBUG: app.py - Bem-vindo, {st.session_state.username}!")

# Layout da barra lateral para navegação
st.sidebar.title("Navegação")

# Adicionar botão de sincronização na sidebar
if st.sidebar.button("🔄 Sincronizar com Google Sheets"):
    print("DEBUG: app.py - Botão Sincronizar clicado na sidebar")
    sync_with_sheets()
    st.rerun()

menu_options = {
    "Dashboard": show_dashboard,
    "Alunos": show_alunos,
    "Lançamento de Ações": show_lancamentos_page,
    "Ordens e Tarefas": show_ordens_e_tarefas,
    "Relatórios": show_relatorios,
}

# Adicionar Configurações apenas para admin
if st.session_state.role == "admin":
    menu_options["Configurações"] = show_config

# Seleção de página na barra lateral
selected_page = st.sidebar.radio("Ir para:", list(menu_options.keys()))

# Exibir a página selecionada
print(f"DEBUG: app.py - Página selecionada: {selected_page}")
menu_options[selected_page]()

print("DEBUG: app.py - Fim do script principal")
st.write("DEBUG: app.py - Aplicativo carregado completamente.")


