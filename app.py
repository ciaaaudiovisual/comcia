import streamlit as st
from auth import check_authentication, check_permission
from database import load_data 
from dashboard import show_dashboard
from alunos import show_alunos
from acoes import show_lancamentos_page
from programacao import show_programacao
from ordens import show_ordens_e_tarefas
from relatorios import show_relatorios
from config import show_config
from admin_panel import show_admin_panel
from lancamentos_faia import show_lancamentos_faia

# A chamada a init_local_db() foi removida pois não é mais necessária.

if not check_authentication():
    st.stop()

# --- BARRA LATERAL E NAVEGAÇÃO ATUALIZADA ---
st.sidebar.title("Sistema de Gestão")

# --- CORREÇÃO APLICADA AQUI ---
# Acesso seguro ao nome do usuário para exibição
user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
st.sidebar.markdown(f"Usuário: **{user_display_name}**")
st.sidebar.divider()

st.sidebar.header("Navegação")
if st.sidebar.button("🔄 Recarregar Dados"):
    load_data.clear() # Limpa o cache da função load_data
    st.toast("Os dados foram recarregados com sucesso!", icon="✅")
    st.rerun()

# --- CONSTRUÇÃO DINÂMICA DO MENU COM O NOVO SISTEMA DE PERMISSÕES ---
# 1. Começamos com as páginas que todos os usuários logados podem ver
menu_options = {
    "Dashboard": show_dashboard,
    "Programação": show_programacao,
    "Alunos": show_alunos,
    "Lançamento de Ações": show_lancamentos_page,
    "Ordens e Tarefas": show_ordens_e_tarefas,
}

# 2. Adicionamos as páginas restritas uma a uma, verificando a permissão
if check_permission('acesso_pagina_lancamentos_faia'):
    menu_options["Lançamentos (FAIA)"] = show_lancamentos_faia

if check_permission('acesso_pagina_relatorios'):
    menu_options["Relatórios"] = show_relatorios

if check_permission('acesso_pagina_configuracoes'):
    menu_options["Configurações"] = show_config
    
if check_permission('acesso_pagina_painel_admin'):
    menu_options["Painel do Admin"] = show_admin_panel

# 3. O menu é exibido para o usuário com as opções permitidas para ele
selected_page = st.sidebar.radio(
    "Ir para:", 
    list(menu_options.keys()), 
    label_visibility="collapsed"
)

# 4. A página selecionada é executada
if selected_page in menu_options:
    menu_options[selected_page]()
else:
    st.error("Página não encontrada ou você não tem permissão para acessá-la.")
    st.image("https://http.cat/403") # Imagem de "Acesso Proibido"

