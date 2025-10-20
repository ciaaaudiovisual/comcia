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
from saude import show_saude
from assistente_ia import show_assistente_ia
from revisao_geral import show_revisao_geral
from geracao_documentos import show_geracao_documentos
from controle_pernoite import show_controle_pernoite
from previa_rancho import show_previa_rancho
from auxilio_transporte import show_auxilio_transporte
from conselho_avaliacao import show_conselho_avaliacao
from conselho_avaliacao import show_conselho_avaliacao
from relatorio_geral import show_relatorio_geral # <-- NOVA IMPORTAÇÃO


if not check_authentication():
    st.stop()

st.set_page_config(
    page_title="SisCOMCA",
    page_icon="🎖️",
    layout="wide"
)

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

menu_options = {
    "Dashboard": show_dashboard,
    "Assistente IA": show_assistente_ia,
    "Programação": show_programacao,
    "Cadastro de Alunos": show_alunos,
    "Lançamento de Ações": show_gestao_acoes,
    "Saúde": show_saude,
    "Parada Diária": show_parada_diaria,
}

if check_permission('acesso_pagina_geracao_documentos'):
    menu_options["Geração de Documentos"] = show_geracao_documentos

if check_permission('acesso_pagina_revisao_geral'):
    menu_options["Revisão Geral"] = show_revisao_geral

    # A linha abaixo parece estar no lugar errado na sua versão,
    # mas mantive a lógica de permissão
    menu_options["Conselho de Avaliação"] = show_conselho_avaliacao
    
if check_permission('acesso_pagina_relatorios'):
    menu_options["Relatórios"] = show_relatorios
    menu_options["Relatório Geral"] = show_relatorio_geral # <-- NOVA PÁGINA ADICIONADA

if check_permission('acesso_pagina_configuracoes'):
    menu_options["Configurações"] = show_config
    
if check_permission('acesso_pagina_geracao_documentos'):
    menu_options["Geração de Documentos"] = show_geracao_documentos


    menu_options["Conselho de Avaliação"] = show_conselho_avaliacao
    
if check_permission('acesso_pagina_relatorios'):
    menu_options["Relatórios"] = show_relatorios

if check_permission('acesso_pagina_configuracoes'):
    menu_options["Configurações"] = show_config

if check_permission('acesso_pagina_painel_admin'):
    menu_options["Painel do Admin"] = show_admin_panel

if check_permission('acesso_pagina_pernoite'):
    menu_options["Controle de Pernoite"] = show_controle_pernoite

if check_permission('acesso_pagina_rancho_pernoite'):
    menu_options["Prévia de Rancho (Sheets)"] = show_previa_rancho

if check_permission('acesso_pagina_auxilio_transporte'):
    menu_options["Auxílio Transporte"] = show_auxilio_transporte

selected_page = st.sidebar.radio(
    "Ir para:", 
    list(menu_options.keys()), 
    label_visibility="collapsed"
)

if selected_page in menu_options:
    menu_options[selected_page]()
else:
    st.error("Página não encontrada ou você não tem permissão para acessá-la.")

