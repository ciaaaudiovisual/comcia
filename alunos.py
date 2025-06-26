import streamlit as st
import pandas as pd
import os
from datetime import datetime
from database import load_data, save_data
from acoes import registrar_acao

def show_alunos():
    st.title("Gestão de Alunos")
    
    # Carregar dados
    alunos_df = load_data("Sistema_Acoes_Militares", "Alunos")
    acoes_df = load_data("Sistema_Acoes_Militares", "Acoes")
    
    # Adicionar novo aluno
    if st.button("➕ Adicionar Novo Aluno"):
        st.session_state.show_add_aluno = True
        if 'show_edit_aluno' in st.session_state:
            del st.session_state.show_edit_aluno
            del st.session_state.edit_aluno_id
    
    # Formulário para adicionar novo aluno
    if 'show_add_aluno' in st.session_state and st.session_state.show_add_aluno:
        with st.form("novo_aluno"):
            st.subheader("Novo Aluno")
            
            col1, col2 = st.columns(2)
            
            with col1:
                numero_interno = st.text_input("Número Interno")
                nome_guerra = st.text_input("Nome de Guerra")
                nome_completo = st.text_input("Nome Completo")
                
            with col2:
                pelotao = st.text_input("Pelotão")
                especialidade = st.text_input("Especialidade")
                data_nascimento = st.date_input("Data de Nascimento")
            
            # Upload de foto
            foto = st.file_uploader("Foto do Aluno", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("Salvar")
            cancel = st.form_submit_button("Cancelar")
            
            if submitted:
                # Criar novo ID
                novo_id = 1
                if not alunos_df.empty and 'id' in alunos_df.columns:
                    novo_id = int(alunos_df['id'].max()) + 1
                
                # Criar novo aluno
                novo_aluno = {
                    'id': novo_id,
                    'numero_interno': numero_interno,
                    'nome_guerra': nome_guerra,
                    'nome_completo': nome_completo,
                    'pelotao': pelotao,
                    'especialidade': especialidade,
                    'data_nascimento': data_nascimento.strftime('%Y-%m-%d'),
                    'pontuacao': 10  # Pontuação inicial
                }
                
                # Salvar foto se fornecida
                if foto is not None:
                    # Criar pasta para fotos se não existir
                    if not os.path.exists("fotos"):
                        os.makedirs("fotos")
                    
                    # Salvar foto
                    foto_path = f"fotos/{novo_id}.jpg"
                    with open(foto_path, "wb") as f:
                        f.write(foto.getbuffer())
                    
                    # Adicionar caminho da foto ao registro do aluno
                    novo_aluno['foto_path'] = foto_path
                
                # Adicionar à DataFrame
                if alunos_df.empty:
                    alunos_df = pd.DataFrame([novo_aluno])
                else:
                    alunos_df = pd.concat([alunos_df, pd.DataFrame([novo_aluno])], ignore_index=True)
                
                # Salvar no Google Sheets
                if save_data("Sistema_Acoes_Militares", "Alunos", alunos_df):
                    st.success("Aluno adicionado com sucesso!")
                    st.session_state.show_add_aluno = False
                    st.rerun()
                else:
                    st.error("Erro ao salvar o aluno. Verifique a conexão com o Google Sheets.")
            
            if cancel:
                st.session_state.show_add_aluno = False
                st.rerun()
    
    # Formulário para editar aluno
    if 'show_edit_aluno' in st.session_state and st.session_state.show_edit_aluno:
        aluno_id = st.session_state.edit_aluno_id
        aluno = alunos_df[alunos_df['id'] == aluno_id].iloc[0]
        
        with st.form("editar_aluno"):
            st.subheader(f"Editar Aluno: {aluno['nome_guerra']}")
            
            col1, col2 = st.columns(2)
            
            with col1:
                numero_interno = st.text_input("Número Interno", value=aluno['numero_interno'])
                nome_guerra = st.text_input("Nome de Guerra", value=aluno['nome_guerra'])
                nome_completo = st.text_input("Nome Completo", value=aluno['nome_completo'])
                
            with col2:
                pelotao = st.text_input("Pelotão", value=aluno['pelotao'])
                especialidade = st.text_input("Especialidade", value=aluno['especialidade'])
                
                # Converter data de nascimento para datetime
                data_nascimento_str = aluno.get('data_nascimento', datetime.now().strftime('%Y-%m-%d'))
                try:
                    data_nascimento_dt = datetime.strptime(data_nascimento_str, '%Y-%m-%d')
                except:
                    data_nascimento_dt = datetime.now()
                
                data_nascimento = st.date_input("Data de Nascimento", value=data_nascimento_dt)
            
            # Mostrar foto atual se existir
            if 'foto_path' in aluno and os.path.exists(aluno['foto_path']):
                st.image(aluno['foto_path'], width=150, caption="Foto atual")
            
            # Upload de nova foto
            foto = st.file_uploader("Nova Foto (deixe em branco para manter a atual)", type=["jpg", "jpeg", "png"])
            
            submitted = st.form_submit_button("Salvar")
            cancel = st.form_submit_button("Cancelar")
            
            if submitted:
                # Atualizar dados do aluno
                alunos_df.loc[alunos_df['id'] == aluno_id, 'numero_interno'] = numero_interno
                alunos_df.loc[alunos_df['id'] == aluno_id, 'nome_guerra'] = nome_guerra
                alunos_df.loc[alunos_df['id'] == aluno_id, 'nome_completo'] = nome_completo
                alunos_df.loc[alunos_df['id'] == aluno_id, 'pelotao'] = pelotao
                alunos_df.loc[alunos_df['id'] == aluno_id, 'especialidade'] = especialidade
                alunos_df.loc[alunos_df['id'] == aluno_id, 'data_nascimento'] = data_nascimento.strftime('%Y-%m-%d')
                
                # Salvar nova foto se fornecida
                if foto is not None:
                    # Criar pasta para fotos se não existir
                    if not os.path.exists("fotos"):
                        os.makedirs("fotos")
                    
                    # Salvar foto
                    foto_path = f"fotos/{aluno_id}.jpg"
                    with open(foto_path, "wb") as f:
                        f.write(foto.getbuffer())
                    
                    # Atualizar caminho da foto
                    alunos_df.loc[alunos_df['id'] == aluno_id, 'foto_path'] = foto_path
                
                # Salvar no Google Sheets
                if save_data("Sistema_Acoes_Militares", "Alunos", alunos_df):
                    st.success("Aluno atualizado com sucesso!")
                    del st.session_state.show_edit_aluno
                    del st.session_state.edit_aluno_id
                    st.rerun()
                else:
                    st.error("Erro ao atualizar o aluno. Verifique a conexão com o Google Sheets.")
            
            if cancel:
                del st.session_state.show_edit_aluno
                del st.session_state.edit_aluno_id
                st.rerun()
    
    # Exibir lista de alunos
    if not alunos_df.empty:
        # Filtro de busca
        search = st.text_input("🔍 Buscar aluno (nome, número, pelotão...)")
        
        # Filtrar alunos
        filtered_df = alunos_df
        if search:
            search_lower = search.lower()
            mask = (
                alunos_df['nome_guerra'].str.lower().str.contains(search_lower, na=False) |
                alunos_df['nome_completo'].str.lower().str.contains(search_lower, na=False) |
                alunos_df['numero_interno'].str.lower().str.contains(search_lower, na=False) |
                alunos_df['pelotao'].str.lower().str.contains(search_lower, na=False)
            )
            filtered_df = alunos_df[mask]
        
        # Exibir alunos em cards
        st.subheader(f"Alunos ({len(filtered_df)} encontrados)")
        
        # Dividir em colunas
        cols = st.columns(3)
        
        for i, (_, aluno) in enumerate(filtered_df.iterrows()):
            with cols[i % 3]:
                with st.container(border=True):
                    # Exibir foto se disponível
                    if 'foto_path' in aluno and os.path.exists(aluno['foto_path']):
                        st.image(aluno['foto_path'], width=100)
                    else:
                        st.markdown("📷")
                    
                    st.markdown(f"**{aluno['nome_guerra']}**")
                    st.write(f"Nº: {aluno['numero_interno']}")
                    st.write(f"Pelotão: {aluno['pelotao']}")
                    
                    # Calcular pontuação atual
                    pontuacao = 10
                    if not acoes_df.empty and 'aluno_id' in acoes_df.columns and 'pontuacao_efetiva' in acoes_df.columns:
                        acoes_aluno = acoes_df[acoes_df['aluno_id'] == aluno['id']]
                        if not acoes_aluno.empty:
                            pontuacao += acoes_aluno['pontuacao_efetiva'].sum()
                    
                    # Exibir pontuação com cor
                    cor = "green" if pontuacao >= 10 else "red"
                    st.markdown(f"<h4 style='color:{cor}'>{pontuacao:.1f} pts</h4>", unsafe_allow_html=True)
                    
                    # Botões de ação
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("👁️ Ver", key=f"ver_{aluno['id']}"):
                            st.session_state.aluno_selecionado = aluno['id']
                            st.rerun()
                    
                    with col2:
                        if st.button("✏️ Editar", key=f"editar_{aluno['id']}"):
                            st.session_state.show_edit_aluno = True
                            st.session_state.edit_aluno_id = aluno['id']
                            st.rerun()
                    
                    with col3:
                        if st.button("➕ Ação", key=f"acao_{aluno['id']}"):
                            st.session_state.registrar_acao = True
                            st.session_state.aluno_acao = aluno['id']
                            st.rerun()
    else:
        st.info("Nenhum aluno cadastrado. Clique em 'Adicionar Novo Aluno' para começar.")
    
    # Exibir detalhes do aluno selecionado
    if 'aluno_selecionado' in st.session_state:
        show_detalhes_aluno(st.session_state.aluno_selecionado, alunos_df, acoes_df)
    
    # Registrar ação para aluno
    if 'registrar_acao' in st.session_state and st.session_state.registrar_acao:
        aluno_id = st.session_state.aluno_acao
        aluno = alunos_df[alunos_df['id'] == aluno_id].iloc[0]
        registrar_acao(aluno_id, aluno['nome_guerra'])

def show_detalhes_aluno(aluno_id, alunos_df, acoes_df):
    # Encontrar aluno
    aluno = alunos_df[alunos_df['id'] == aluno_id].iloc[0]
    
    # Filtrar ações do aluno
    acoes_aluno = pd.DataFrame()
    if not acoes_df.empty and 'aluno_id' in acoes_df.columns:
        acoes_aluno = acoes_df[acoes_df['aluno_id'] == aluno_id].sort_values('data', ascending=False)
    
    # Calcular pontuação atual
    pontuacao_atual = 10
    if not acoes_aluno.empty and 'pontuacao_efetiva' in acoes_aluno.columns:
        pontuacao_atual += acoes_aluno['pontuacao_efetiva'].sum()
    
    # Exibir detalhes
    st.subheader(f"Detalhes do Aluno: {aluno['nome_guerra']}")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Exibir foto do aluno se disponível
        import os
        if 'foto_path' in aluno and os.path.exists(aluno['foto_path']):
            st.image(aluno['foto_path'], width=150)
        else:
            st.image("https://via.placeholder.com/150?text=Sem+Foto", width=150 )
            
        st.markdown(f"""
        ### {aluno['nome_guerra']}
        **Nome Completo:** {aluno['nome_completo']}  
        **Número Interno:** {aluno['numero_interno']}  
        **Pelotão:** {aluno['pelotao']}  
        **Especialidade:** {aluno['especialidade']}  
        **Pontuação Atual:** {pontuacao_atual:.1f}
        """)
        
        # Botões de ação
        if st.button("Registrar Nova Ação"):
            st.session_state.registrar_acao = True
            st.session_state.aluno_acao = aluno_id
            st.rerun()
        
        if st.button("Voltar para Lista"):
            del st.session_state.aluno_selecionado
            st.rerun()
    
    with col2:
        st.subheader("Histórico de Ações")
        if acoes_aluno.empty:
            st.info("Nenhuma ação registrada para este aluno.")
        else:
            for _, acao in acoes_aluno.iterrows():
                # Determinar cor com base na pontuação
                pontuacao = acao.get('pontuacao_efetiva', 0)
                cor = "green" if pontuacao > 0 else "red" if pontuacao < 0 else "gray"
                
                st.markdown(f"""
                <div style="border-left: 3px solid {cor}; padding-left: 10px; margin-bottom: 10px">
                    <p><strong>{acao.get('tipo', 'Ação')}</strong> ({pontuacao:+.1f} pontos) - {acao.get('data', 'N/A')}</p>
                    <p>{acao.get('descricao', '')}</p>
                    <p><small>Registrado por: {acao.get('usuario', 'Sistema')}</small></p>
                </div>
                """, unsafe_allow_html=True)
