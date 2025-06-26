import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, save_data, init_local_db, sync_with_sheets

# Inicializa o banco de dados local na primeira execução
init_local_db()

def show_ordens():
    st.title("Ordens Diárias e Tarefas")
    
    # Botão de sincronização manual
    if st.button("🔄 Sincronizar com Google Sheets"):
        sync_with_sheets()
        st.rerun()

    # Abas para ordens e tarefas
    tab1, tab2 = st.tabs(["📝 Ordens do Dia", "✅ Tarefas"])
    
    with tab1:
        show_ordens_diarias()
    
    with tab2:
        show_tarefas()

def show_ordens_diarias():
    st.subheader("Ordens do Dia")
    
    # Carregar ordens
    ordens_df = load_data("Sistema_Acoes_Militares", "Ordens_Diarias")
    
    # Adicionar nova ordem
    with st.form("nova_ordem"):
        st.write("Registrar Nova Ordem")
        texto = st.text_area("Texto da Ordem")
        col1, col2 = st.columns(2)
        
        with col1:
            submitted = st.form_submit_button("Salvar")
        
        with col2:
            add_as_task = st.form_submit_button("Salvar e Adicionar como Tarefa")
        
        if submitted or add_as_task:
            # Criar novo ID
            novo_id = 1
            if not ordens_df.empty and 'id' in ordens_df.columns:
                novo_id = int(ordens_df['id'].max()) + 1
            
            # Criar nova ordem
            nova_ordem = {
                'id': novo_id,
                'data': datetime.now().strftime('%Y-%m-%d'),
                'texto': texto,
                'autor_id': st.session_state.username
            }
            
            # Adicionar à DataFrame
            if ordens_df.empty:
                ordens_df = pd.DataFrame([nova_ordem])
            else:
                ordens_df = pd.concat([ordens_df, pd.DataFrame([nova_ordem])], ignore_index=True)
            
            # Salvar no Google Sheets
            if save_data("Sistema_Acoes_Militares", "Ordens_Diarias", ordens_df):
                st.success("Ordem registrada com sucesso!")
                
                # Adicionar como tarefa se solicitado
                if add_as_task:
                    adicionar_como_tarefa(texto)
                
                st.rerun()
            else:
                st.error("Erro ao salvar a ordem. Verifique a conexão com o Google Sheets.")
    
    # Exibir ordens
    if not ordens_df.empty:
        # Ordenar por data (mais recentes primeiro)
        ordens_df['data'] = pd.to_datetime(ordens_df['data'], errors='coerce')
        ordens_df = ordens_df.sort_values('data', ascending=False)
        
        for _, ordem in ordens_df.iterrows():
            with st.expander(f"{ordem['data'].strftime('%d/%m/%Y')} - Ordem do Dia", expanded=True):
                st.write(ordem['texto'])
                st.caption(f"Autor: {ordem['autor_id']}")
                
                if st.button("Adicionar como Tarefa", key=f"task_{ordem['id']}"):
                    adicionar_como_tarefa(ordem['texto'])
                    st.success("Adicionado como tarefa!")
                    st.rerun()
    else:
        st.info("Nenhuma ordem registrada.")

def show_tarefas():
    st.subheader("Tarefas")
    
    # Carregar tarefas
    tarefas_df = load_data("Sistema_Acoes_Militares", "Tarefas")
    usuarios_df = load_data("Sistema_Acoes_Militares", "Usuarios")
    
    # Garantir que tarefas_df tenha as colunas esperadas, mesmo que vazio
    expected_cols = ['id', 'texto', 'status', 'responsavel', 'data_criacao', 'data_conclusao', 'concluida_por']
    if tarefas_df.empty or not all(col in tarefas_df.columns for col in expected_cols):
        tarefas_df = pd.DataFrame(columns=expected_cols)

    # Adicionar nova tarefa
    with st.form("nova_tarefa"):
        st.write("Adicionar Nova Tarefa")
        texto = st.text_input("Descrição da Tarefa")
        
        # Obter lista de usuários para atribuição
        usuarios = ["Não atribuído"]
        if not usuarios_df.empty and 'username' in usuarios_df.columns:
            usuarios.extend(usuarios_df['username'].tolist())
        
        responsavel = st.selectbox("Atribuir a:", usuarios)
        
        submitted = st.form_submit_button("Adicionar")
        
        if submitted:
            # Criar novo ID
            novo_id = 1
            if not tarefas_df.empty and 'id' in tarefas_df.columns:
                novo_id = int(tarefas_df['id'].max()) + 1
            
            # Criar nova tarefa
            nova_tarefa = {
                'id': novo_id,
                'texto': texto,
                'status': 'Pendente',  # Status inicial: Pendente
                'responsavel': "" if responsavel == "Não atribuído" else responsavel,
                'data_criacao': datetime.now().strftime('%Y-%m-%d'),
                'data_conclusao': '',
                'concluida_por': '' # Adicionando a coluna concluida_por
            }
            
            # Adicionar à DataFrame
            if tarefas_df.empty:
                tarefas_df = pd.DataFrame([nova_tarefa])
            else:
                tarefas_df = pd.concat([tarefas_df, pd.DataFrame([nova_tarefa])], ignore_index=True)
            
            # Salvar no Google Sheets
            if save_data("Sistema_Acoes_Militares", "Tarefas", tarefas_df):
                st.success("Tarefa adicionada com sucesso!")
                st.rerun()
            else:
                st.error("Erro ao salvar a tarefa. Verifique a conexão com o Google Sheets.")
    
    # Exibir tarefas
    if not tarefas_df.empty:
        # Filtros
        col1, col2 = st.columns(2)
        
        with col1:
            filtro_status = st.multiselect(
                "Filtrar por Status:",
                ["Pendente", "Em Andamento", "Concluída"],
                default=["Pendente", "Em Andamento", "Concluída"]
            )
        
        with col2:
            filtro_responsavel = st.multiselect(
                "Filtrar por Responsável:",
                ["Não atribuído"] + ([] if usuarios_df.empty else usuarios_df['username'].tolist()),
                default=[]
            )
        
        # Aplicar filtros
        filtered_df = tarefas_df
        
        if filtro_status:
            filtered_df = filtered_df[filtered_df['status'].isin(filtro_status)]
        
        if filtro_responsavel:
            # Tratar "Não atribuído"
            if "Não atribuído" in filtro_responsavel:
                mask = (filtered_df['responsavel'] == "") | (filtered_df['responsavel'].isin([r for r in filtro_responsavel if r != "Não atribuído"]))
                filtered_df = filtered_df[mask]
            else:
                filtered_df = filtered_df[filtered_df['responsavel'].isin(filtro_responsavel)]
        
        # Ordenar por status e data
        filtered_df['data_criacao'] = pd.to_datetime(filtered_df['data_criacao'], errors='coerce')
        filtered_df = filtered_df.sort_values(['status', 'data_criacao'], ascending=[True, False])
        
        # Exibir tarefas
        for _, tarefa in filtered_df.iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([5, 3, 2])
                
                with col1:
                    st.write(tarefa['texto'])
                    st.caption(f"Criada em: {tarefa['data_criacao']}")
                
                with col2:
                    responsavel = tarefa['responsavel'] if tarefa['responsavel'] else "Não atribuído"
                    st.write(f"Responsável: {responsavel}")
                    
                    # Exibir quem concluiu, se houver
                    if tarefa['status'] == 'Concluída' and tarefa['concluida_por']:
                        st.caption(f"Concluída por: {tarefa['concluida_por']} em {tarefa['data_conclusao']}")
                
                with col3:
                    # Status com radio buttons
                    status = st.radio(
                        "Status:",
                        ["Pendente", "Em Andamento", "Concluída"],
                        index=["Pendente", "Em Andamento", "Concluída"].index(tarefa['status']),
                        key=f"status_{tarefa['id']}"
                    )
                    
                    # Seleção de quem concluiu, se o status for Concluída
                    concluida_por_options = ["Não informado"] + ([] if usuarios_df.empty else usuarios_df['username'].tolist())
                    current_concluida_by_index = concluida_por_options.index(tarefa['concluida_por']) if tarefa['concluida_por'] in concluida_por_options else 0

                    concluida_por = st.selectbox(
                        "Concluída por:",
                        concluida_por_options,
                        index=current_concluida_by_index,
                        key=f"concluida_por_{tarefa['id']}"
                    )

                    # Atualizar status e concluida_por se alterado
                    if status != tarefa['status'] or (status == 'Concluída' and concluida_por != tarefa['concluida_por']):
                        tarefas_df.loc[tarefas_df['id'] == tarefa['id'], 'status'] = status
                        
                        # Se marcada como concluída, registrar quem concluiu e quando
                        if status == 'Concluída':
                            tarefas_df.loc[tarefas_df['id'] == tarefa['id'], 'data_conclusao'] = datetime.now().strftime('%Y-%m-%d')
                            tarefas_df.loc[tarefas_df['id'] == tarefa['id'], 'concluida_por'] = concluida_por if concluida_por != "Não informado" else ""
                        else:
                            tarefas_df.loc[tarefas_df['id'] == tarefa['id'], 'data_conclusao'] = ''
                            tarefas_df.loc[tarefas_df['id'] == tarefa['id'], 'concluida_por'] = ''
                        
                        # Salvar no Google Sheets
                        if save_data("Sistema_Acoes_Militares", "Tarefas", tarefas_df):
                            st.success("Status atualizado!")
                            st.rerun()
                        else:
                            st.error("Erro ao atualizar status.")
    else:
        st.info("Nenhuma tarefa registrada.")

def adicionar_como_tarefa(texto):
    # Carregar tarefas existentes
    tarefas_df = load_data("Sistema_Acoes_Militares", "Tarefas")
    usuarios_df = load_data("Sistema_Acoes_Militares", "Usuarios")
    
    # Garantir que tarefas_df tenha as colunas esperadas, mesmo que vazio
    expected_cols = ['id', 'texto', 'status', 'responsavel', 'data_criacao', 'data_conclusao', 'concluida_por']
    if tarefas_df.empty or not all(col in tarefas_df.columns for col in expected_cols):
        tarefas_df = pd.DataFrame(columns=expected_cols)

    # Criar novo ID
    novo_id = 1
    if not tarefas_df.empty and 'id' in tarefas_df.columns:
        novo_id = int(tarefas_df['id'].max()) + 1
    
    # Obter lista de usuários para atribuição
    usuarios = ["Não atribuído"]
    if not usuarios_df.empty:
        usuarios.extend(usuarios_df['username'].tolist())
    
    # Interface para adicionar tarefa
    st.subheader("Adicionar Nova Tarefa")
    responsavel = st.selectbox("Atribuir a:", usuarios)
    
    # Criar nova tarefa
    nova_tarefa = {
        'id': novo_id,
        'texto': texto,
        'status': 'Pendente',  # Status inicial: Pendente
        'responsavel': "" if responsavel == "Não atribuído" else responsavel,
        'data_criacao': datetime.now().strftime('%Y-%m-%d'),
        'data_conclusao': '',
        'concluida_por': '' # Adicionando a coluna concluida_por
    }
    
    # Adicionar à DataFrame
    if tarefas_df.empty:
        tarefas_df = pd.DataFrame([nova_tarefa])
    else:
        tarefas_df = pd.concat([tarefas_df, pd.DataFrame([nova_tarefa])], ignore_index=True)
    
    # Salvar no Google Sheets
    if save_data("Sistema_Acoes_Militares", "Tarefas", tarefas_df):
        st.success("Tarefa adicionada com sucesso!")
        st.rerun()
    else:
        st.error("Erro ao salvar a tarefa. Verifique a conexão com o Google Sheets.")


