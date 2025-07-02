import streamlit as st
from auth import check_authentication, check_permission, logout
from database import load_data 
from dashboard import show_dashboard
from alunos import show_alunos
from programacao import show_programacao
from ordens import show_parada_diaria
from relatorios import show_relatorios
from config import show_config
from admin_panel import show_admin_panel
from gestao_acoes import show_gestao_acoes

if not check_authentication():
    st.stop()

st.sidebar.title("Sistema de Gestão de Alunos")
user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
st.sidebar.markdown(f"Usuário: **{user_display_name}**")
if st.sidebar.button("Logout"):
    logout()
    st.rerun()
st.sidebar.divider()

st.sidebar.header("Menu de Navegação")
if st.sidebar.button("🔄 Recarregar Dados"):
    load_data.clear()
    st.toast("Os dados foram recarregados com sucesso!", icon="✅")
    st.rerun()

# --- MODIFICAÇÃO: Menu atualizado com a página unificada ---
menu_options = {
    "Dashboard": show_dashboard,
    "Programação": show_programacao,
    "Alunos": show_alunos,
    "Lançamento de Ações": show_gestao_acoes, # Nova página unificada
    "Parada Diária": show_parada_diaria,
}

# As permissões agora controlam o acesso à página unificada.
# A permissão 'acesso_pagina_lancamentos_faia' ainda é útil para controlar quem pode lançar.
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
