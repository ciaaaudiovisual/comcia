import streamlit as st
from auth import check_authentication
from database import init_local_db
from dashboard import show_dashboard
from alunos import show_alunos
from acoes import show_lancamentos_page
from programacao import show_programacao
from ordens import show_ordens_e_tarefas 
from relatorios import show_relatorios
from config import show_config

# Inicializa o banco de dados local (se houver)
init_local_db()

# Verifica autenticação
if not check_authentication():
    st.stop()

st.sidebar.title("Navegação")

# --- NOVO BOTÃO DE RECARREGAMENTO MANUAL ---
# Este botão permite que o usuário force a busca por dados atualizados
# da planilha, sem precisar salvar nada. É útil se múltiplos
# usuários estiverem a editar a planilha diretamente.
if st.sidebar.button("🔄 Recarregar Dados do Sheets"):
    st.cache_data.clear()
    st.toast("Os dados foram recarregados com sucesso a partir da planilha!", icon="✅")
    st.rerun()
# --- FIM DA ADIÇÃO ---


# Dicionário com as opções do menu de navegação
menu_options = {
    "Dashboard": show_dashboard,
    "Programação": show_programacao,
    "Alunos": show_alunos,
    "Lançamento de Ações": show_lancamentos_page,
    "Ordens e Tarefas": show_ordens_e_tarefas,
    "Relatórios": show_relatorios,
}

# Adicionar a página de Configurações apenas para administradores
if st.session_state.get('role') == "admin":
    menu_options["Configurações"] = show_config

# Seleção de página na barra lateral
selected_page = st.sidebar.radio("Ir para:", list(menu_options.keys()))

# Exibir a página selecionada
menu_options[selected_page]()