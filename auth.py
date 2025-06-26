import streamlit as st

def login():
    """Função de login simplificada para testes"""
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.username = ""
        st.session_state.role = ""
    
    if not st.session_state.authenticated:
        st.title("Sistema de Lançamento de Ações Militares")
        
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submitted = st.form_submit_button("Entrar")
            
            if submitted:
                # Para testes, aceitar qualquer credencial
                st.session_state.authenticated = True
                st.session_state.username = username
                st.session_state.role = "admin"  # ou "comcia" se preferir
                st.rerun()
        
        st.info("Para testes, use qualquer usuário e senha.")
        return False
    
    return True

def check_authentication():
    """Verifica se o usuário está autenticado"""
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        login()
        return False
    return True
