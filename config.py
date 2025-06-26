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
            # Preparar novas configurações
            novas_configs = [
                {'chave': 'pontuacao_inicial', 'valor': str(nova_pontuacao_inicial), 'descricao': 'Pontuação inicial dos alunos'},
                {'chave': 'periodo_adaptacao_inicio', 'valor': novo_periodo_inicio.strftime('%Y-%m-%d'), 'descricao': 'Data de início do período de adaptação'},
                {'chave': 'periodo_adaptacao_fim', 'valor': novo_periodo_fim.strftime('%Y-%m-%d'), 'descricao': 'Data de fim do período de adaptação'},
                {'chave': 'fator_adaptacao', 'valor': str(novo_fator), 'descricao': 'Fator de multiplicação para pontuação no período de adaptação'}
            ]
            
            # Criar ou atualizar DataFrame
            if config_df.empty:
                config_df = pd.DataFrame(novas_configs)
            else:
                # Atualizar valores existentes
                for config in novas_configs:
                    if config['chave'] in config_df['chave'].values:
                        idx = config_df[config_df['chave'] == config['chave']].index
                        config_df.loc[idx, 'valor'] = config['valor']
                    else:
                        config_df = pd.concat([config_df, pd.DataFrame([config])], ignore_index=True)
            
            # Salvar no Google Sheets
            if save_data("Sistema_Acoes_Militares", "Config", config_df):
                st.success("Configurações salvas com sucesso!")
            else:
                st.error("Erro ao salvar configurações. Verifique a conexão com o Google Sheets.")

def show_config_usuarios():
    st.subheader("Gestão de Usuários")
    
    # Carregar usuários existentes
    usuarios_df = load_data("Sistema_Acoes_Militares", "Usuarios")
    
    # Formulário para novo usuário
    with st.form("novo_usuario"):
        st.write("Adicionar Novo Usuário")
        
        username = st.text_input("Nome de Usuário")
        password = st.text_input("Senha", type="password")
        nome = st.text_input("Nome Completo")
        role = st.selectbox("Tipo", ["admin", "comcia"])
        
        submitted = st.form_submit_button("Adicionar Usuário")
        
        if submitted:
            if not username or not password or not nome:
                st.error("Todos os campos são obrigatórios.")
            else:
                # Verificar se usuário já existe
                if not usuarios_df.empty and username in usuarios_df['username'].values:
                    st.error("Este nome de usuário já existe.")
                else:
                    # Criar novo ID
                    novo_id = 1
                    if not usuarios_df.empty and 'id' in usuarios_df.columns:
                        novo_id = int(usuarios_df['id'].max()) + 1
                    
                    # Criar novo usuário
                    novo_usuario = {
                        'id': novo_id,
                        'username': username,
                        'password': password,
                        'nome': nome,
                        'role': role
                    }
                    
                    # Adicionar à DataFrame
                    if usuarios_df.empty:
                        usuarios_df = pd.DataFrame([novo_usuario])
                    else:
                        usuarios_df = pd.concat([usuarios_df, pd.DataFrame([novo_usuario])], ignore_index=True)
                    
                    # Salvar no Google Sheets
                    if save_data("Sistema_Acoes_Militares", "Usuarios", usuarios_df):
                        st.success("Usuário adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar usuário. Verifique a conexão com o Google Sheets.")
    
    # Exibir usuários existentes
    st.subheader("Usuários Cadastrados")
    
    if usuarios_df.empty:
        st.info("Nenhum usuário cadastrado ainda.")
    else:
        # Ocultar senhas na exibição
        usuarios_display = usuarios_df.copy()
        if 'password' in usuarios_display.columns:
            usuarios_display['password'] = '********'
        
        # Exibir usuários
        for _, usuario in usuarios_display.iterrows():
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.write(f"**{usuario['nome']}**")
                st.write(f"Username: {usuario['username']}")
            
            with col2:
                st.write(f"Tipo: {usuario['role']}")
            
            with col3:
                if st.button(f"Excluir #{usuario['id']}"):
                    # Confirmar exclusão
                    if 'confirmar_exclusao' not in st.session_state:
                        st.session_state.confirmar_exclusao = usuario['id']
                        st.warning(f"Tem certeza que deseja excluir o usuário {usuario['nome']}?")
                        st.button(f"Confirmar Exclusão #{usuario['id']}", key=f"confirm_{usuario['id']}")
                    elif st.session_state.confirmar_exclusao == usuario['id']:
                        # Excluir usuário
                        usuarios_df = usuarios_df[usuarios_df['id'] != usuario['id']]
                        
                        # Salvar no Google Sheets
                        if save_data("Sistema_Acoes_Militares", "Usuarios", usuarios_df):
                            st.success("Usuário excluído com sucesso!")
                            del st.session_state.confirmar_exclusao
                            st.rerun()
                        else:
                            st.error("Erro ao excluir usuário. Verifique a conexão com o Google Sheets.")
            
            st.divider()

def show_config_tipos_acao():
    st.subheader("Tipos de Ação")
    
    # Carregar tipos de ação existentes
    tipos_acao_df = load_data("Sistema_Acoes_Militares", "Tipos_Acao")
    
    # Formulário para novo tipo de ação
    with st.form("novo_tipo_acao"):
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
                # Criar novo ID
                novo_id = 1
                if not tipos_acao_df.empty and 'id' in tipos_acao_df.columns:
                    novo_id = int(tipos_acao_df['id'].max()) + 1
                
                # Criar novo tipo de ação
                novo_tipo = {
                    'id': novo_id,
                    'nome': nome,
                    'descricao': descricao,
                    'pontuacao': str(pontuacao),
                    'codigo': codigo
                }
                
                # Adicionar à DataFrame
                if tipos_acao_df.empty:
                    tipos_acao_df = pd.DataFrame([novo_tipo])
                else:
                    tipos_acao_df = pd.concat([tipos_acao_df, pd.DataFrame([novo_tipo])], ignore_index=True)
                
                # Salvar no Google Sheets
                if save_data("Sistema_Acoes_Militares", "Tipos_Acao", tipos_acao_df):
                    st.success("Tipo de ação adicionado com sucesso!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar tipo de ação. Verifique a conexão com o Google Sheets.")
    
    # Exibir tipos de ação existentes
    st.subheader("Tipos de Ação Cadastrados")
    
    if tipos_acao_df.empty:
        st.info("Nenhum tipo de ação cadastrado ainda.")
    else:
        # Exibir tipos de ação
        for _, tipo in tipos_acao_df.iterrows():
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.write(f"**{tipo['nome']} ({tipo['codigo']})**")
                st.write(tipo['descricao'])
            
            with col2:
                pontuacao = float(tipo['pontuacao'])
                cor = "green" if pontuacao > 0 else "red" if pontuacao < 0 else "gray"
                st.markdown(f"Pontuação: <span style='color:{cor};font-weight:bold'>{pontuacao:+g}</span>", unsafe_allow_html=True)
            
            with col3:
                if st.button(f"Editar #{tipo['id']}"):
                    st.session_state.editar_tipo = tipo['id']
                
                if st.button(f"Excluir #{tipo['id']}"):
                    # Confirmar exclusão
                    if 'confirmar_exclusao_tipo' not in st.session_state:
                        st.session_state.confirmar_exclusao_tipo = tipo['id']
                        st.warning(f"Tem certeza que deseja excluir o tipo de ação {tipo['nome']}?")
                        st.button(f"Confirmar Exclusão Tipo #{tipo['id']}", key=f"confirm_tipo_{tipo['id']}")
                    elif st.session_state.confirmar_exclusao_tipo == tipo['id']:
                        # Excluir tipo de ação
                        tipos_acao_df = tipos_acao_df[tipos_acao_df['id'] != tipo['id']]
                        
                        # Salvar no Google Sheets
                        if save_data("Sistema_Acoes_Militares", "Tipos_Acao", tipos_acao_df):
                            st.success("Tipo de ação excluído com sucesso!")
                            del st.session_state.confirmar_exclusao_tipo
                            st.rerun()
                        else:
                            st.error("Erro ao excluir tipo de ação. Verifique a conexão com o Google Sheets.")
            
            # Formulário para editar tipo de ação
            if 'editar_tipo' in st.session_state and st.session_state.editar_tipo == tipo['id']:
                with st.form(f"editar_tipo_{tipo['id']}"):
                    st.write(f"Editar Tipo de Ação #{tipo['id']}")
                    
                    novo_nome = st.text_input("Nome", value=tipo['nome'])
                    nova_descricao = st.text_input("Descrição", value=tipo['descricao'])
                    nova_pontuacao = st.number_input("Pontuação", value=float(tipo['pontuacao']), step=0.5)
                    novo_codigo = st.text_input("Código", value=tipo['codigo'])
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        submitted = st.form_submit_button("Salvar")
                    with col2:
                        cancelar = st.form_submit_button("Cancelar")
                    
                    if submitted:
                        if not novo_nome or not novo_codigo:
                            st.error("Nome e Código são obrigatórios.")
                        else:
                            # Atualizar tipo de ação
                            idx = tipos_acao_df[tipos_acao_df['id'] == tipo['id']].index
                            tipos_acao_df.loc[idx, 'nome'] = novo_nome
                            tipos_acao_df.loc[idx, 'descricao'] = nova_descricao
                            tipos_acao_df.loc[idx, 'pontuacao'] = str(nova_pontuacao)
                            tipos_acao_df.loc[idx, 'codigo'] = novo_codigo
                            
                            # Salvar no Google Sheets
                            if save_data("Sistema_Acoes_Militares", "Tipos_Acao", tipos_acao_df):
                                st.success("Tipo de ação atualizado com sucesso!")
                                del st.session_state.editar_tipo
                                st.rerun()
                            else:
                                st.error("Erro ao atualizar tipo de ação. Verifique a conexão com o Google Sheets.")
                    
                    if cancelar:
                        del st.session_state.editar_tipo
                        st.rerun()
            
            st.divider()
