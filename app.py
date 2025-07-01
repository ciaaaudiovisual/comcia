import streamlit as st
from auth import check_authentication, check_permission, logout
from database import load_data 
from dashboard import show_dashboard
from alunos import show_alunos
from acoes import show_lancamentos_page
from programacao import show_programacao
# --- MODIFICAÇÃO: Importa a nova função da página ---
from ordens import show_parada_diaria
from relatorios import show_relatorios
from config import show_config
from admin_panel import show_admin_panel
from lancamentos_faia import show_lancamentos_faia

if not check_authentication():
    st.stop()

st.sidebar.title("Sistema de Gestão")
user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
st.sidebar.markdown(f"Usuário: **{user_display_name}**")
if st.sidebar.button("Logout"):
    logout()
    st.rerun()
st.sidebar.divider()

st.sidebar.header("Navegação")
if st.sidebar.button("🔄 Recarregar Dados"):
    load_data.clear()
    st.toast("Os dados foram recarregados com sucesso!", icon="✅")
    st.rerun()

# --- MODIFICAÇÃO: Atualiza o dicionário do menu ---
menu_options = {
    "Dashboard": show_dashboard,
    "Programação": show_programacao,
    "Alunos": show_alunos,
    "Lançamento de Ações": show_lancamentos_page,
    "Parada Diária": show_parada_diaria, # Nome da página atualizado
}

if check_permission('acesso_pagina_lancamentos_faia'):
    menu_options["Lançamentos (FAIA)"] = show_lancamentos_faia
if check_permission('acesso_pagina_relatorios'):
    menu_options["Relatórios"] = show_relatorios
if check_permission('acesso_pagina_configuracoes'):
    menu_options["Configurações"] = show_config
if check_permission('acesso_pagina_painel_admin'):
    menu_options["Painel do Admin"] = show_admin_panel

selected_page = st.sidebar.radio(
    "Ir para:", 
    list(menu_options.keys()), 
    label_visibility="collapsed"
)

if selected_page in menu_options:
    menu_options[selected_page]()
else:
    st.error("Página não encontrada ou você não tem permissão para acessá-la.")
    st.image("https://http.cat/403")
