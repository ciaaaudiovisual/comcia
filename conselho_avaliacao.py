import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final # Reutiliza as funções de cálculo já existentes

# ==============================================================================
# FUNÇÕES DE APOIO
# ==============================================================================

def get_student_list_with_indicators(alunos_df, acoes_com_pontos, config_dict, threshold=7.0):
    """
    Cria a lista de alunos para o seletor, adicionando um indicador de atenção
    para aqueles com conceito abaixo do limiar.
    """
    soma_pontos_por_aluno = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
    
    alunos_df['id'] = alunos_df['id'].astype(str)
    soma_pontos_por_aluno.index = soma_pontos_por_aluno.index.astype(str)
    
    alunos_df['soma_pontos_acoes'] = alunos_df['id'].map(soma_pontos_por_aluno).fillna(0)
    
    alunos_df['conceito_final'] = alunos_df.apply(
        lambda row: calcular_conceito_final(
            row['soma_pontos_acoes'],
            float(row.get('media_academica', 0.0)),
            alunos_df,
            config_dict
        ),
        axis=1
    )
    
    alunos_df_sorted = alunos_df.sort_values('nome_guerra')
    
    # Cria os rótulos com o indicador de atenção
    options = {}
    for _, aluno in alunos_df_sorted.iterrows():
        indicator = "⚠️ " if aluno['conceito_final'] < threshold else ""
        label = f"{indicator}{aluno['nome_guerra']} ({aluno.get('pelotao', 'N/A')})"
        options[aluno['id']] = label
        
    return options, alunos_df_sorted['id'].tolist()

def render_quick_action_form(aluno_selecionado, supabase):
    """Renderiza o formulário de anotação rápida."""
    with st.expander("➕ Adicionar Anotação Rápida"):
        st.caption("A anotação será enviada para a fila de revisão com status 'Pendente'.")
        
        tipos_acao_df = load_data("Tipos_Acao")
        if tipos_acao_df.empty:
            st.warning("Nenhum tipo de ação cadastrado.")
            return

        with st.form(f"quick_action_form_{aluno_selecionado['id']}", clear_on_submit=True):
            tipos_opcoes = {tipo['nome']: tipo for _, tipo in tipos_acao_df.sort_values('nome').iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação", options=tipos_opcoes.keys())
            
            data_atual = datetime.now()
            descricao_padrao = f"Anotação realizada durante o Conselho de Avaliação em {data_atual.strftime('%d/%m/%Y')}."
            descricao = st.text_area("Descrição", value=descricao_padrao)
            
            if st.form_submit_button("Registrar Ação"):
                try:
                    tipo_info = tipos_opcoes[tipo_selecionado_str]
                    nova_acao = {
                        'aluno_id': str(aluno_selecionado['id']),
                        'tipo_acao_id': str(tipo_info['id']),
                        'tipo': tipo_info['nome'],
                        'descricao': descricao,
                        'data': data_atual.strftime('%Y-%m-%d %H:%M:%S'),
                        'usuario': st.session_state.username,
                        'status': 'Pendente' # Vai para a fila de revisão
                    }
                    supabase.table("Acoes").insert(nova_acao).execute()
                    st.toast("Anotação rápida registrada com sucesso!", icon="✅")
                    load_data.clear() # Limpa o cache para que a nova anotação apareça ao recarregar
                except Exception as e:
                    st.error(f"Erro ao registrar anotação: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================

def show_conselho_avaliacao():
    st.set_page_config(layout="wide")

    # Lógica para o "Modo Apresentação"
    presentation_mode = 'present' in st.query_params
    if presentation_mode:
        st.html("""
            <style>
                /* Esconde a barra lateral do Streamlit */
                [data-testid="stSidebar"] {
                    display: none;
                }
                /* Ajusta o padding do conteúdo principal para ocupar a tela toda */
                 .main .block-container {
                    padding-top: 2rem;
                    padding-left: 2rem;
                    padding-right: 2rem;
                }
            </style>
        """)
        if st.button("⬅️ Sair do Modo Apresentação"):
            st.query_params.clear()
            st.rerun()

    st.title("Conselho de Avaliação")

    if not check_permission('acesso_pagina_conselho_avaliacao'):
        st.error("Acesso negado. Você não tem permissão para visualizar esta página.")
        st.stop()
    
    supabase = init_supabase_client()

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df.empty:
        st.warning("Nenhum aluno cadastrado no sistema."); return

    # Filtra pelotão 'BAIXA'
    alunos_df = alunos_df[alunos_df['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()

    # Prepara dados para os cálculos
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)

    # Gera a lista de alunos com indicadores e a lista de IDs para navegação
    opcoes_alunos, student_id_list = get_student_list_with_indicators(alunos_df, acoes_com_pontos, config_dict)

    st.divider()

    # --- Seletor de Aluno e Navegação ---
    if 'current_student_index' not in st.session_state:
        st.session_state.current_student_index = 0

    # Atualiza o índice se o seletor for usado
    def on_select_change():
        selected_id = st.session_state.student_selector
        if selected_id in student_id_list:
            st.session_state.current_student_index = student_id_list.index(selected_id)

    # Define o ID do aluno atual com base no índice
    current_student_id = student_id_list[st.session_state.current_student_index]

    col_nav1, col_nav2, col_nav3, col_pres = st.columns([1, 4, 1, 1])
    
    with col_nav1:
        if st.button("< Aluno Anterior", use_container_width=True):
            if st.session_state.current_student_index > 0:
                st.session_state.current_student_index -= 1
                st.rerun()
    with col_nav2:
        st.selectbox(
            "Selecione o Aluno:", 
            options=list(opcoes_alunos.keys()), 
            format_func=lambda x: opcoes_alunos[x],
            key="student_selector",
            index=st.session_state.current_student_index,
            on_change=on_select_change,
            label_visibility="collapsed"
        )
    with col_nav3:
        if st.button("Próximo Aluno >", use_container_width=True):
            if st.session_state.current_student_index < len(student_id_list) - 1:
                st.session_state.current_student_index += 1
                st.rerun()
    with col_pres:
        if not presentation_mode:
            if st.button("🖥️ Modo Apresentação", use_container_width=True):
                st.query_params['present'] = 'true'
                st.rerun()

    st.write("") # Espaçamento

    # --- Ficha do Aluno Selecionado ---
    aluno_selecionado = alunos_df[alunos_df['id'] == current_student_id].iloc[0]

    with st.container(border=True):
        # Header com informações e métricas
        col_img, col_info, col_conceito, col_media = st.columns([1, 4, 1.2, 1.2])
        with col_img:
            st.image(aluno_selecionado.get('url_foto', "https://via.placeholder.com/100?text=Sem+Foto"), width=100)
        with col_info:
            st.header(aluno_selecionado['nome_guerra'])
            st.markdown(f"**Nº Interno:** {aluno_selecionado['numero_interno']} | **Pelotão:** {aluno_selecionado['pelotao']}")
        with col_conceito:
            st.metric("Conceito Atual", f"{aluno_selecionado['conceito_final']:.2f}")
        with col_media:
            st.metric("Média Acadêmica", f"{float(aluno_selecionado.get('media_academica', 0.0)):.2f}")
        
        st.divider()

        # Listas de anotações
        acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == current_student_id]
        
        col_pos, col_neg = st.columns(2)
        with col_pos:
            st.subheader("✅ Anotações Positivas")
            positivas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] > 0].sort_values('data', ascending=False)
            if positivas.empty:
                st.info("Nenhuma anotação positiva registrada.")
            else:
                for _, acao in positivas.iterrows():
                    data_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                    st.markdown(f"**Data:** {data_fmt} | **Pontos:** <span style='color:green;'>{acao['pontuacao_efetiva']:+.2f}</span>", unsafe_allow_html=True)
                    st.caption(f"Tipo: {acao['nome']}")
        
        with col_neg:
            st.subheader("⚠️ Anotações Negativas")
            negativas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] < 0].sort_values('data', ascending=False)
            if negativas.empty:
                st.info("Nenhuma anotação negativa registrada.")
            else:
                for _, acao in negativas.iterrows():
                    data_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                    st.markdown(f"**Data:** {data_fmt} | **Pontos:** <span style='color:red;'>{acao['pontuacao_efetiva']:+.2f}</span>", unsafe_allow_html=True)
                    st.caption(f"Tipo: {acao['nome']}")
        
        st.divider()
        # Formulário de anotação rápida
        render_quick_action_form(aluno_selecionado, supabase)
