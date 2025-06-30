import streamlit as st
import pandas as pd
from database import init_supabase_client, load_data

# --- FUNÇÕES DE AUTENTICAÇÃO (LOGIN) ATUALIZADAS ---

# --- NOVO DIÁLOGO DE SOLICITAÇÃO DE CADASTRO ---
@st.dialog("Solicitação de Acesso")
def show_registration_dialog():
    """Exibe um formulário para um novo usuário solicitar acesso."""
    supabase = init_supabase_client()
    st.write("Por favor, preencha seus dados. Um administrador irá revisar e aprovar seu acesso.")
    
    with st.form("registration_form", clear_on_submit=True):
        email = st.text_input("Seu E-mail (será seu login)*")
        password = st.text_input("Crie uma Senha*", type="password")
        nome_completo = st.text_input("Nome Completo*")
        nome_guerra = st.text_input("Nome de Guerra*")
        
        if st.form_submit_button("Enviar Solicitação"):
            if not all([email, password, nome_completo, nome_guerra]):
                st.warning("Todos os campos são obrigatórios.")
            else:
                try:
                    # 1. Cria o usuário no sistema de autenticação do Supabase. Ele ficará aguardando.
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    
                    if res.user:
                        # 2. Insere a solicitação na nossa tabela de aprovação pendente.
                        supabase.table("RegistrationRequests").insert({
                            "id": res.user.id,
                            "email": email,
                            "nome_completo": nome_completo,
                            "nome_guerra": nome_guerra,
                            "status": "pending"
                        }).execute()
                        st.success("Solicitação enviada com sucesso! Aguarde a aprovação do administrador.")
                    else:
                        st.error("Não foi possível registrar o usuário no sistema de autenticação.")

                except Exception as e:
                    st.error(f"Erro ao enviar solicitação: {e}")


def logout():
    """Limpa o estado da sessão para deslogar o usuário."""
    keys_to_clear = ['authenticated', 'username', 'role', 'full_name', 'user_id', 'email']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Opcional: Tenta deslogar do Supabase, mas a limpeza da sessão já protege o app
    try:
        supabase = init_supabase_client()
        if supabase:
            supabase.auth.sign_out()
    except Exception:
        pass # Ignora erros se a conexão falhar aqui
    
    st.toast("Você saiu com segurança.", icon="👋")


# --- FUNÇÕES DE AUTENTICAÇÃO (LOGIN) ---


# --- FUNÇÃO DE LOGIN ATUALIZADA ---
def login(supabase):
    """Exibe o formulário de login e o link para solicitar acesso."""
    st.title("Sistema de Gestão")
    st.subheader("Por favor, faça o login para continuar")

    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar")

        if submitted:
            try:
                user_session = supabase.auth.sign_in_with_password({"email": email, "password": password})
                user_id = user_session.user.id
                users_df = load_data("Users")
                user_profile = users_df[users_df['id'] == user_id]

                if not user_profile.empty:
                    user_row = user_profile.iloc[0]
                    st.session_state.authenticated = True
                    st.session_state.username = user_row['username']
                    st.session_state.full_name = user_row.get('nome', user_row['username'])
                    st.session_state.role = user_row.get('role', 'compel')
                    st.session_state.user_id = user_id
                    st.rerun()
                else:
                    st.error("Autenticação bem-sucedida, mas o perfil de usuário não foi encontrado ou aprovado. Contate um administrador.")
                    supabase.auth.sign_out()
            
            except Exception:
                st.error("Falha no login. Verifique seu email e senha.")

    st.divider()
    if st.button("Não tem uma conta? Solicite seu acesso aqui"):
        show_registration_dialog()

def check_authentication():
    """Verifica se o usuário está autenticado. Se não, exibe a tela de login."""
    supabase = init_supabase_client()
    if not supabase:
        st.error("Falha na conexão com o banco de dados. Verifique as configurações 'secrets.toml'.")
        st.stop()
        
    if not st.session_state.get('authenticated'):
        try:
            user_session = supabase.auth.get_session()
            if user_session and user_session.user:
                user_id = user_session.user.id
                users_df = load_data("Users")
                user_profile = users_df[users_df['id'] == user_id]
                
                if not user_profile.empty:
                    user_row = user_profile.iloc[0]
                    st.session_state.authenticated = True
                    st.session_state.username = user_row['username']
                    st.session_state.full_name = user_row.get('nome', user_row['username'])
                    st.session_state.role = user_row.get('role', 'compel')
                    st.session_state.user_id = user_id
                else:
                    supabase.auth.sign_out()
            else:
                 st.session_state.authenticated = False
        except Exception:
            st.session_state.authenticated = False

    if not st.session_state.get('authenticated'):
        login(supabase)
        st.stop()
    
    return True





# --- FUNÇÕES DE PERMISSÃO (PERMANECEM AS MESMAS) ---

@st.cache_data(ttl=300)
def get_permissions_rules():
    return load_data("Permissions")

def check_permission(feature_key: str) -> bool:
    try:
        user_role = st.session_state.get('role')
        if not user_role: return False
        if user_role == 'admin': return True
        
        permission_rules_df = get_permissions_rules()
        if permission_rules_df.empty: return False
        
        rule = permission_rules_df[permission_rules_df['feature_key'] == feature_key]
        if rule.empty: return False
        
        allowed_roles_str = rule.iloc[0].get('allowed_roles')
        if pd.isna(allowed_roles_str) or not allowed_roles_str: return False
        
        return user_role in [role.strip() for role in allowed_roles_str.split(',')]
    except Exception:
        return False