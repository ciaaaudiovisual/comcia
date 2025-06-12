import streamlit as st
import pandas as pd
from datetime import datetime
import os

# Importar módulos do projeto
from database import load_data, save_data
from auth import login, check_authentication
from acoes import show_lancamentos_page
from alunos import show_alunos
from dashboard import show_dashboard
from relatorios import show_relatorios
from ordens import show_ordens
from config import show_config

# Configuração da página
st.set_page_config(
    page_title="Sistema de Ações Militares",
    page_icon="🎖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar estado da sessão
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None

# Verificar autenticação
if not st.session_state.authenticated:
    login()
else:
    # Menu lateral
    st.sidebar.title(f"Bem-vindo, {st.session_state.username}")
    
    menu = st.sidebar.radio(
        "Navegação",
        ["Dashboard", "Alunos", "Relatórios", "Ordens Diárias", "Configurações"]
    )
    
    # Botão de logout
    if st.sidebar.button("Sair"):
        st.session_state.authenticated = False
        st.session_state.username = None
        st.session_state.role = None
        st.rerun()
    
    # Exibir página selecionada
    if menu == "Dashboard":
        show_dashboard()
    elif menu == "Alunos":
        show_alunos()
    elif menu == "Relatórios":
        show_relatorios()
    elif menu == "Ordens Diárias":
        show_ordens()
    elif menu == "Configurações":
        if st.session_state.role == "admin":
            show_config()
        else:
            st.error("Acesso negado. Apenas administradores podem acessar esta página.")
