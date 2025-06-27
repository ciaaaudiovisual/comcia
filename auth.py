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
        from database import load_data
        # Carrega a lista de usuários
        users_df = load_data("Sistema_Acoes_Militares", "Users")
        if not users_df.empty:
            # Procura pelo usuário
            user_data = users_df[users_df['username'] == username]
            if not user_data.empty:
                # Verifica a senha (em um sistema real, use senhas com hash)
                if user_data.iloc[0]['password'] == password:
                    st.session_state.authenticated = True
                    st.session_state.username = user_data.iloc[0]['username']
                    st.session_state.role = user_data.iloc[0]['role']
                    st.rerun()
                else:
                    st.error("Senha incorreta.")
            else:
                st.error("Usuário não encontrado.")
        else:
            st.error("Nenhum usuário cadastrado no sistema.")
        
        st.info("Para testes, use qualquer usuário e senha.")
        return False
    
    return True

def check_authentication():
    """Verifica se o usuário está autenticado"""
    if 'authenticated' not in st.session_state or not st.session_state.authenticated:
        login()
        return False
    return True
