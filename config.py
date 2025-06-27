import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, save_data

def show_config():
    st.title("Configurações do Sistema")
    
    # Verificar se é administrador
    if st.session_state.role != "admin":
        st.error("Acesso negado. Apenas administradores podem acessar esta página.")
        return
    
    # Criar abas para diferentes configurações
    tab1, tab2, tab3 = st.tabs(["⚙️ Configurações Gerais", "👥 Usuários", "🏆 Tipos de Ação"])
    
    with tab1:
        show_config_gerais()
    
    with tab2:
        show_config_usuarios()
    
    with tab3:
        show_config_tipos_acao()

def show_config_gerais():
    st.subheader("Configurações Gerais")
    
    # Carregar configurações existentes
    config_df = load_data("Sistema_Acoes_Militares", "Config")
    
    # Valores padrão
    pontuacao_inicial = 10.0
    periodo_adaptacao_inicio = datetime.now().date()
    periodo_adaptacao_fim = datetime.now().date()
    fator_adaptacao = 0.25
    
    # Obter valores atuais
    if not config_df.empty:
        if 'pontuacao_inicial' in config_df['chave'].values:
            pontuacao_inicial = float(config_df[config_df['chave'] == 'pontuacao_inicial']['valor'].iloc[0])
        
        if 'periodo_adaptacao_inicio' in config_df['chave'].values:
            try:
                periodo_adaptacao_inicio = pd.to_datetime(config_df[config_df['chave'] == 'periodo_adaptacao_inicio']['valor'].iloc[0]).date()
            except:
                pass
        
        if 'periodo_adaptacao_fim' in config_df['chave'].values:
            try:
                periodo_adaptacao_fim = pd.to_datetime(config_df[config_df['chave'] == 'periodo_adaptacao_fim']['valor'].iloc[0]).date()
            except:
                pass
        
        if 'fator_adaptacao' in config_df['chave'].values:
            fator_adaptacao = float(config_df[config_df['chave'] == 'fator_adaptacao']['valor'].iloc[0])
    
    # Formulário para editar configurações
    with st.form("editar_config"):
        st.write("Configurações do Sistema")
        
        nova_pontuacao_inicial = st.number_input("Pontuação Inicial dos Alunos", value=pontuacao_inicial, min_value=0.0)
        
        col1, col2 = st.columns(2)
        with col1:
            novo_periodo_inicio = st.date_input("Início do Período de Adaptação", value=periodo_adaptacao_inicio)
        with col2:
            novo_periodo_fim = st.date_input("Fim do Período de Adaptação", value=periodo_adaptacao_fim)
        
        novo_fator = st.slider("Fator de Adaptação (multiplicador da pontuação)", min_value=0.0, max_value=1.0, value=fator_adaptacao, step=0.05)
        
        submitted = st.form_submit_button("Salvar Configurações")
        
        if submitted:
            novas_configs_df = pd.DataFrame([
                {'chave': 'pontuacao_inicial', 'valor': str(nova_pontuacao_inicial), 'descricao': 'Pontuação inicial dos alunos'},
                {'chave': 'periodo_adaptacao_inicio', 'valor': novo_periodo_inicio.strftime('%Y-%m-%d'), 'descricao': 'Data de início do período de adaptação'},
                {'chave': 'periodo_adaptacao_fim', 'valor': novo_periodo_fim.strftime('%Y-%m-%d'), 'descricao': 'Data de fim do período de adaptação'},
                {'chave': 'fator_adaptacao', 'valor': str(novo_fator), 'descricao': 'Fator de multiplicação para pontuação no período de adaptação'}
            ])
            
            if save_data("Sistema_Acoes_Militares", "Config", novas_configs_df):
                st.success("Configurações salvas com sucesso!")
            else:
                st.error("Erro ao salvar configurações.")

def show_config_usuarios():
    st.subheader("Gestão de Usuários")
    
    # Carregar usuários existentes
    usuarios_df = load_data("Sistema_Acoes_Militares", "Users") # CORRIGIDO PARA 'Users'
    
    # Formulário para novo usuário
    with st.form("novo_usuario", clear_on_submit=True):
        st.write("Adicionar Novo Usuário")
        
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type="password")
        nome = st.text_input("Nome Completo")
        role = st.selectbox("Tipo", ["admin", "comcia"])
        
        submitted = st.form_submit_button("Adicionar Usuário")
        
        if submitted:
            if not all([username, password, nome]):
                st.error("Todos os campos são obrigatórios.")
            elif not usuarios_df.empty and username in usuarios_df['username'].values:
                st.error("Este nome de usuário já existe.")
            else:
                novo_id = 1
                if not usuarios_df.empty and 'id' in usuarios_df.columns:
                    novo_id = int(pd.to_numeric(usuarios_df['id'], errors='coerce').max()) + 1
                
                novo_usuario = {
                    'id': novo_id,
                    'username': username,
                    'password': password, # Idealmente, esta senha deveria ser "hashed"
                    'nome': nome,
                    'role': role
                }
                
                novo_usuario_df = pd.DataFrame([novo_usuario])

                if save_data("Sistema_Acoes_Militares", "Users", novo_usuario_df):
                    st.success("Usuário adicionado com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar usuário.")
    
    st.subheader("Usuários Cadastrados")
    
    if usuarios_df.empty:
        st.info("Nenhum usuário cadastrado ainda.")
    else:
        usuarios_display = usuarios_df.copy()
        if 'password' in usuarios_display.columns:
            usuarios_display['password'] = '********'
        
        for _, usuario in usuarios_display.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            with col1:
                st.write(f"**{usuario['nome']}** (`{usuario['username']}`)")
            with col2:
                st.write(f"Permissão: {usuario.get('role', 'N/A')}")
            with col3:
                # CORREÇÃO: Adicionada uma chave única ao botão
                if st.button("Excluir", key=f"delete_user_{usuario['id']}"):
                    usuarios_df_updated = usuarios_df[usuarios_df['id'] != usuario['id']]
                    if save_data("Sistema_Acoes_Militares", "Users", usuarios_df_updated):
                        st.success(f"Usuário {usuario['nome']} excluído.")
                        st.rerun()
                    else:
                        st.error("Erro ao excluir usuário.")
            st.divider()

def show_config_tipos_acao():
    st.subheader("Tipos de Ação")
    
    tipos_acao_df = load_data("Sistema_Acoes_Militares", "Tipos_Acao")
    
    with st.form("novo_tipo_acao", clear_on_submit=True):
        st.write("Adicionar Novo Tipo de Ação")
        
        nome = st.text_input("Nome")
        descricao = st.text_input("Descrição")
        pontuacao = st.number_input("Pontuação", value=0.0, step=0.5)
        codigo = st.text_input("Código (abreviação)")
        
        submitted = st.form_submit_button("Adicionar")
        
        if submitted:
            if not nome or not codigo:
                st.error("Nome e Código são obrigatórios.")
            else:
                novo_id = 1
                if not tipos_acao_df.empty and 'id' in tipos_acao_df.columns:
                    novo_id = int(pd.to_numeric(tipos_acao_df['id'], errors='coerce').max()) + 1
                
                novo_tipo = {
                    'id': novo_id,
                    'nome': nome,
                    'descricao': descricao,
                    'pontuacao': str(pontuacao),
                    'codigo': codigo
                }
                
                novo_tipo_df = pd.DataFrame([novo_tipo])
                
                if save_data("Sistema_Acoes_Militares", "Tipos_Acao", novo_tipo_df):
                    st.success("Tipo de ação adicionado com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar tipo de ação.")
    
    st.subheader("Tipos de Ação Cadastrados")
    
    if tipos_acao_df.empty:
        st.info("Nenhum tipo de ação cadastrado ainda.")
    else:
        for _, tipo in tipos_acao_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 2])
                
                with col1:
                    st.write(f"**{tipo['nome']}** (`{tipo['codigo']}`)")
                    st.caption(tipo['descricao'])
                
                with col2:
                    pontuacao_val = float(tipo.get('pontuacao', 0))
                    cor = "green" if pontuacao_val > 0 else "red" if pontuacao_val < 0 else "gray"
                    st.markdown(f"Pontuação: <span style='color:{cor};font-weight:bold'>{pontuacao_val:+.1f}</span>", unsafe_allow_html=True)
                
                with col3:
                    # CORREÇÃO: Adicionadas chaves únicas aos botões
                    if st.button("Editar", key=f"edit_tipo_{tipo['id']}"):
                        st.session_state.editar_tipo_id = tipo['id']
                    
                    if st.button("Excluir", key=f"delete_tipo_{tipo['id']}"):
                        tipos_acao_df_updated = tipos_acao_df[tipos_acao_df['id'] != tipo['id']]
                        if save_data("Sistema_Acoes_Militares", "Tipos_Acao", tipos_acao_df_updated):
                            st.success(f"Tipo '{tipo['nome']}' excluído.")
                            st.rerun()
                        else:
                            st.error("Erro ao excluir tipo de ação.")
            
            # Formulário de edição (aparece abaixo do item)
            if 'editar_tipo_id' in st.session_state and st.session_state.editar_tipo_id == tipo['id']:
                with st.form(f"edit_form_tipo_{tipo['id']}", clear_on_submit=True):
                    st.write(f"Editando: **{tipo['nome']}**")
                    novo_nome = st.text_input("Nome", value=tipo['nome'])
                    nova_descricao = st.text_input("Descrição", value=tipo['descricao'])
                    nova_pontuacao = st.number_input("Pontuação", value=float(tipo['pontuacao']), step=0.5)
                    novo_codigo = st.text_input("Código", value=tipo['codigo'])
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.form_submit_button("Salvar Alterações"):
                            dados_atualizados = {
                                'id': tipo['id'],
                                'nome': novo_nome,
                                'descricao': nova_descricao,
                                'pontuacao': str(nova_pontuacao),
                                'codigo': novo_codigo
                            }
                            df_atualizado = pd.DataFrame([dados_atualizados])
                            if save_data("Sistema_Acoes_Militares", "Tipos_Acao", df_atualizado):
                                del st.session_state.editar_tipo_id
                                st.rerun()
                    with c2:
                        if st.form_submit_button("Cancelar"):
                            del st.session_state.editar_tipo_id
                            st.rerun()

