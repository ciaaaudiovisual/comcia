import streamlit as st
import pandas as pd
from datetime import datetime
import numpy as np
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final
from fpdf import FPDF

# ==============================================================================
# FUNÇÃO DE CACHE E PROCESSAMENTO DE DADOS
# ==============================================================================
@st.cache_data(ttl=3600)
def process_turma_data(pelotao_selecionado, sort_order):
    alunos_df_orig = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df_orig.empty:
        return {}, [], pd.DataFrame(), pd.DataFrame()

    alunos_df = alunos_df_orig[alunos_df_orig['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()

    if pelotao_selecionado != "Todos":
        alunos_df = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]

    if alunos_df.empty:
        return {}, [], pd.DataFrame(), pd.DataFrame()

    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)

    soma_pontos_por_aluno = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
    
    alunos_df['id'] = alunos_df['id'].astype(str)
    soma_pontos_por_aluno.index = soma_pontos_por_aluno.index.astype(str)
    
    alunos_df['soma_pontos_acoes'] = alunos_df['id'].map(soma_pontos_por_aluno).fillna(0)
    
    alunos_df['conceito_final'] = alunos_df.apply(
        lambda row: calcular_conceito_final(
            row['soma_pontos_acoes'],
            float(row.get('media_academica', 0.0)),
            alunos_df_orig,
            config_dict
        ),
        axis=1
    )
    
    alunos_df['media_academica_num'] = pd.to_numeric(alunos_df['media_academica'], errors='coerce').fillna(0.0)
    alunos_df['classificacao_final_prevista'] = ((alunos_df['media_academica_num'] * 3) + (alunos_df['conceito_final'] * 2)) / 5

    alunos_df['numero_interno_num'] = pd.to_numeric(alunos_df['numero_interno'].str.extract('(\d+)', expand=False), errors='coerce').fillna(9999)

    if sort_order == 'Conceito (Maior > Menor)':
        alunos_df = alunos_df.sort_values('conceito_final', ascending=False)
    elif sort_order == 'Ordem Alfabética':
        alunos_df = alunos_df.sort_values('nome_guerra')
    else: # Padrão: Número Interno
        alunos_df = alunos_df.sort_values('numero_interno_num')

    student_id_list = alunos_df['id'].tolist()
    options = {}
    for _, aluno in alunos_df.iterrows():
        indicator = "⚠️ " if aluno['conceito_final'] < 7.0 else ""
        label = f"{indicator}{aluno['numero_interno']} - {aluno['nome_guerra']}"
        options[aluno['id']] = label
        
    return options, student_id_list, alunos_df, acoes_com_pontos

# ==============================================================================
# FUNÇÕES DE RENDERIZAÇÃO E GERAÇÃO DE PDF
# ==============================================================================
def gerar_pdf_conselho(aluno, acoes_positivas, acoes_negativas, acoes_neutras):
    # (Esta função está correta, sem alterações necessárias)
    pass

def render_quick_action_form(aluno_selecionado, supabase):
    # (Esta função está correta, sem alterações necessárias)
    pass

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_conselho_avaliacao():
    st.set_page_config(layout="wide")
    
    st.markdown("""
        <style>
            h1 { font-size: 1.8rem !important; margin-bottom: 0px !important; }
            .st-emotion-cache-1y4p8pa { padding-top: 1rem !important; }
            div[data-testid="stHorizontalBlock"] { align-items: flex-start; }
            .student-data-header h2 { font-size: 1.6rem !important; margin-bottom: 0px !important; }
            .student-data-header h3 { font-size: 1.2rem !important; margin-top: 0px !important; color: #555; }
        </style>
    """, unsafe_allow_html=True)

    st.header("Conselho de Avaliação")

    if not check_permission('acesso_pagina_conselho_avaliacao'):
        st.error("Acesso negado."); st.stop()
    
    supabase = init_supabase_client()
    
    # --- CABEÇALHO COM FILTROS, DADOS E MÉTRICAS ---
    header_cols = st.columns([1, 3, 3])
    
    alunos_df_geral = load_data("Alunos")
    opcoes_pelotao = ["Todos"] + sorted(alunos_df_geral['pelotao'].dropna().unique().tolist())
    opcoes_ordem = ['Número Interno', 'Conceito (Maior > Menor)', 'Ordem Alfabética']
    
    pelotao_selecionado = st.session_state.get('filtro_pelotao_conselho', 'Todos')
    sort_order = st.session_state.get('filtro_ordem_conselho', 'Número Interno')
    
    opcoes_alunos, student_id_list, alunos_processados_df, acoes_com_pontos = process_turma_data(pelotao_selecionado, sort_order)
    
    if not student_id_list:
        st.warning("Nenhum aluno encontrado para os filtros selecionados."); st.stop()

    if 'current_student_index' not in st.session_state: st.session_state.current_student_index = 0
    if st.session_state.current_student_index >= len(student_id_list): st.session_state.current_student_index = 0

    def on_select_change():
        selected_id = st.session_state.student_selector_conselho
        if selected_id in student_id_list:
            st.session_state.current_student_index = student_id_list.index(selected_id)
            
    current_student_id = student_id_list[st.session_state.current_student_index]
    aluno_selecionado = alunos_processados_df[alunos_processados_df['id'] == current_student_id].iloc[0]

    with header_cols[0]:
        st.markdown('<div class="student-data-header">', unsafe_allow_html=True)
        st.header(aluno_selecionado['nome_guerra'])
        st.subheader(f"Nº: {aluno_selecionado['numero_interno']} | Pelotão: {aluno_selecionado['pelotao']}")
        st.markdown('</div>', unsafe_allow_html=True)
        st.image(aluno_selecionado.get('url_foto', "https://via.placeholder.com/400x400?text=Sem+Foto"), use_container_width=True)

    with header_cols[1]:
        st.subheader("Métricas de Desempenho")
        st.metric("Soma de Pontos", f"{aluno_selecionado['soma_pontos_acoes']:.3f}")
        st.metric("Média Acadêmica", f"{aluno_selecionado['media_academica_num']:.3f}")
        st.metric("Conceito Final", f"{aluno_selecionado['conceito_final']:.3f}")
        st.metric("Classificação Final (Prevista)", f"{aluno_selecionado['classificacao_final_prevista']:.3f}", 
                  help="Cálculo: (Média Acadêmica * 3 + Conceito Final * 2) / 5")

    with header_cols[2]:
        st.selectbox("Filtrar Turma:", opcoes_pelotao, key="filtro_pelotao_conselho")
        st.selectbox("Ordenar por:", opcoes_ordem, key="filtro_ordem_conselho")
        st.selectbox("Selecionar Militar:", options=list(opcoes_alunos.keys()), format_func=lambda x: opcoes_alunos[x],
                     key="student_selector_conselho", index=st.session_state.current_student_index, on_change=on_select_change)
        
        btn_cols = st.columns(2)
        with btn_cols[0]:
            if st.button("< Anterior", use_container_width=True, disabled=(st.session_state.current_student_index == 0)):
                st.session_state.current_student_index -= 1; st.rerun()
        with btn_cols[1]:
            if st.button("Próximo >", use_container_width=True, disabled=(st.session_state.current_student_index == len(student_id_list) - 1)):
                st.session_state.current_student_index += 1; st.rerun()

    st.divider()

    # --- BLOCO DE ANOTAÇÕES (AGORA COM 2 COLUNAS) ---
    acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
    acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == current_student_id].copy()
    acoes_aluno['pontuacao_efetiva'] = pd.to_numeric(acoes_aluno['pontuacao_efetiva'], errors='coerce').fillna(0)
    
    positivas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] > 0].sort_values('data', ascending=False)
    negativas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] < 0].sort_values('data', ascending=False)
    neutras = acoes_aluno[acoes_aluno['pontuacao_efetiva'] == 0].sort_values('data', ascending=False)
    
    col_pos, col_neg = st.columns(2)

    with col_pos:
        st.subheader("✅ Anotações Positivas")
        if positivas.empty:
            st.info("Nenhuma anotação positiva.")
        else:
            for _, acao in positivas.iterrows():
                pontos = acao.get('pontuacao_efetiva', 0.0)
                data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                st.markdown(f"""<div style="font-size: 0.9em; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 5px;">
                    <b>{data_formatada} - {acao.get('nome', 'N/A')}</b> (<span style='color:green;'>{pontos:+.3f}</span>)
                    <br><small><i>{acao.get('descricao', 'Sem descrição.')}</i></small></div>""", unsafe_allow_html=True)
        
    with col_neg:
        st.subheader("⚠️ Anotações Negativas")
        if negativas.empty:
            st.info("Nenhuma anotação negativa.")
        else:
            for _, acao in negativas.iterrows():
                pontos = acao.get('pontuacao_efetiva', 0.0)
                data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                st.markdown(f"""<div style="font-size: 0.9em; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 5px;">
                    <b>{data_formatada} - {acao.get('nome', 'N/A')}</b> (<span style='color:red;'>{pontos:+.3f}</span>)
                    <br><small><i>{acao.get('descricao', 'Sem descrição.')}</i></small></div>""", unsafe_allow_html=True)

    st.divider()
    
    with st.expander("⚪ Anotações Neutras"):
        if neutras.empty:
            st.info("Nenhuma anotação neutra registrada.")
        else:
             for _, acao in neutras.iterrows():
                pontos = acao.get('pontuacao_efetiva', 0.0)
                data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                st.markdown(f"""<div style="font-size: 0.9em; border-bottom: 1px solid #eee; padding-bottom: 5px; margin-bottom: 5px;">
                    <b>{data_formatada} - {acao.get('nome', 'N/A')}</b> (<span style='color:gray;'>{pontos:+.3f} pts</span>)
                    <br><small><i>{acao.get('descricao', 'Sem descrição.')}</i></small></div>""", unsafe_allow_html=True)

    # --- TABELA DE CLASSIFICAÇÃO FINAL ---
    st.divider()
    st.header("Classificação Final da Turma (sem QTPA)")
    
    df_classificacao = alunos_processados_df[~alunos_processados_df['numero_interno'].astype(str).str.startswith('Q')].copy()
    df_classificacao = df_classificacao.sort_values('classificacao_final_prevista', ascending=False)
    df_classificacao.insert(0, 'Class.', range(1, 1 + len(df_classificacao)))
    
    num_colunas_ranking = 5
    partes = np.array_split(df_classificacao, num_colunas_ranking)
    cols_ranking = st.columns(num_colunas_ranking)

    for i, coluna in enumerate(cols_ranking):
        with coluna:
            for _, aluno_rank in partes[i].iterrows():
                st.markdown(
                    f"**{aluno_rank['Class.']}º:** {aluno_rank['nome_guerra']} ({aluno_rank['numero_interno']}) - **{aluno_rank['classificacao_final_prevista']:.3f}**"
                )

    st.divider()
    # ...(Restante do código, como o formulário de anotação rápida e o PDF)

    # --- FORMULÁRIO DE ANOTAÇÃO RÁPIDA (agora com cache clear) ---
    with st.container(border=True):
        st.subheader("➕ Adicionar Anotação Rápida")
        st.caption("A anotação será enviada para a fila de revisão com status 'Pendente'.")
        
        tipos_acao_df = load_data("Tipos_Acao")
        if tipos_acao_df.empty:
            st.warning("Nenhum tipo de ação cadastrado.")
        else:
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
                            'aluno_id': str(aluno_selecionado['id']), 'tipo_acao_id': str(tipo_info['id']),
                            'tipo': tipo_info['nome'], 'descricao': descricao,
                            'data': data_atual.strftime('%Y-%m-%d %H:%M:%S'),
                            'usuario': st.session_state.username, 'status': 'Pendente'
                        }
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.toast("Anotação rápida registrada com sucesso!", icon="✅")
                        # Limpa os caches para forçar o recarregamento dos dados
                        load_data.clear()
                        process_turma_data.clear() # Limpa o cache específico desta página
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao registrar anotação: {e}")
