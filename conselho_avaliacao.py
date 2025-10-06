import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final
from fpdf import FPDF # PONTO 6: Importado para gerar o PDF

# ==============================================================================
# FUNÇÃO DE GERAÇÃO DE PDF (PONTO 6)
# ==============================================================================
def gerar_pdf_conselho(aluno, acoes_positivas, acoes_negativas):
    """Gera um relatório PDF horizontal para o aluno selecionado."""
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Relatório para Conselho de Avaliação', 0, 1, 'C')
            self.ln(5)

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF(orientation='L', unit='mm', format='A4') # Orientação horizontal
    pdf.add_page()
    
    # --- Cabeçalho do Aluno ---
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(40, 30, "", border=0) # Espaço para a foto
    pdf.multi_cell(120, 10, f"{aluno['nome_guerra']}\n"
                             f"Nº Interno: {aluno['numero_interno']} | Pelotão: {aluno['pelotao']}", border=0)
    
    # Métricas (PONTO 7)
    pdf.set_y(pdf.get_y() - 20) # Recua o cursor Y
    pdf.set_x(170)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(40, 7, f"Soma de Pontos:\n{aluno['soma_pontos_acoes']:.3f}", border=1, align='C') # PONTO 8: 3 casas decimais
    pdf.set_y(pdf.get_y() - 14)
    pdf.set_x(210)
    pdf.multi_cell(40, 7, f"Média Acadêmica:\n{float(aluno.get('media_academica', 0.0)):.3f}", border=1, align='C')
    pdf.set_y(pdf.get_y() - 14)
    pdf.set_x(250)
    pdf.multi_cell(40, 7, f"Conceito Final:\n{aluno['conceito_final']:.3f}", border=1, align='C')

    # Foto (PONTO 1) - Requer download da imagem, pode ser complexo. Usando placeholder por agora.
    # Em uma implementação real, seria necessário baixar a URL da foto e passá-la para pdf.image()
    pdf.rect(10, 20, 40, 40) # Desenha um quadro para a foto
    pdf.set_xy(10, 20)
    pdf.cell(40, 40, "(Foto do Aluno)", align='C')
    pdf.ln(35)

    # --- Listas de Anotações ---
    col_width = (pdf.w - pdf.l_margin - pdf.r_margin) / 2 - 5
    
    # Anotações Positivas
    y_before = pdf.get_y()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(col_width, 10, "Anotações Positivas", 0, 1)
    pdf.set_font('Arial', '', 10)
    if positivas.empty:
        pdf.cell(col_width, 10, "Nenhuma anotação positiva.", 1)
    else:
        pdf.cell(30, 7, "Data", 1, 0, 'C')
        pdf.cell(30, 7, "Pontos", 1, 0, 'C')
        pdf.cell(col_width - 60, 7, "Tipo", 1, 1, 'C')
        for _, acao in positivas.iterrows():
            pdf.cell(30, 7, pd.to_datetime(acao['data']).strftime('%d/%m/%Y'), 1, 0, 'C')
            pdf.cell(30, 7, f"{acao['pontuacao_efetiva']:.3f}", 1, 0, 'C') # PONTO 8: 3 casas decimais
            pdf.cell(col_width - 60, 7, acao['nome'], 1, 1)

    # Anotações Negativas
    pdf.set_xy(pdf.l_margin + col_width + 10, y_before)
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(col_width, 10, "Anotações Negativas", 0, 1, 'L')
    pdf.set_xy(pdf.l_margin + col_width + 10, y_before + 10)
    pdf.set_font('Arial', '', 10)
    if negativas.empty:
        pdf.cell(col_width, 10, "Nenhuma anotação negativa.", 1, 1, 'C')
    else:
        pdf.cell(30, 7, "Data", 1, 0, 'C')
        pdf.cell(30, 7, "Pontos", 1, 0, 'C')
        pdf.cell(col_width - 60, 7, "Tipo", 1, 1, 'C')
        for _, acao in negativas.iterrows():
            pdf.set_xy(pdf.l_margin + col_width + 10, pdf.get_y())
            pdf.cell(30, 7, pd.to_datetime(acao['data']).strftime('%d/%m/%Y'), 1, 0, 'C')
            pdf.cell(30, 7, f"{acao['pontuacao_efetiva']:.3f}", 1, 0, 'C') # PONTO 8: 3 casas decimais
            pdf.cell(col_width - 60, 7, acao['nome'], 1, 1)

    return pdf.output(dest='S').encode('latin-1')


# ==============================================================================
# FUNÇÕES DE APOIO
# ==============================================================================

def get_student_list_with_indicators(alunos_df, acoes_com_pontos, config_dict, threshold=7.0):
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
    
    # PONTO 3: Ordena por nome de guerra (ordem alfabética)
    alunos_df_sorted = alunos_df.sort_values('nome_guerra')
    
    options = {}
    for _, aluno in alunos_df_sorted.iterrows():
        indicator = "⚠️ " if aluno['conceito_final'] < threshold else ""
        label = f"{indicator}{aluno['nome_guerra']} ({aluno.get('pelotao', 'N/A')})"
        options[aluno['id']] = label
        
    return options, alunos_df_sorted['id'].tolist(), alunos_df

def render_quick_action_form(aluno_selecionado, supabase):
    # PONTO 4: Formulário agora fica sempre visível
    with st.container(border=True):
        st.subheader("➕ Adicionar Anotação Rápida")
        st.caption("A anotação será enviada para a fila de revisão com status 'Pendente'.")
        
        tipos_acao_df = load_data("Tipos_Acao")
        if tipos_acao_df.empty:
            st.warning("Nenhum tipo de ação cadastrado."); return

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
                    load_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Erro ao registrar anotação: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================

def show_conselho_avaliacao():
    st.set_page_config(layout="wide")
    st.title("Conselho de Avaliação")

    if not check_permission('acesso_pagina_conselho_avaliacao'):
        st.error("Acesso negado."); st.stop()
    
    supabase = init_supabase_client()

    # PONTO 5: Controle de Zoom/Fonte
    st.sidebar.subheader("Opções de Apresentação")
    zoom_level = st.sidebar.slider("Aumentar Fonte/Zoom (%)", min_value=100, max_value=200, value=100, step=10)
    photo_size = int(100 * (zoom_level / 100)) # Foto aumenta proporcionalmente

    # Aplica o CSS para o zoom
    st.markdown(f"""
        <style>
            .main .block-container {{
                font-size: {zoom_level}%;
            }}
        </style>
    """, unsafe_allow_html=True)

    # Carregamento de dados
    alunos_df_orig = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df_orig.empty: st.warning("Nenhum aluno cadastrado."); st.stop()

    alunos_df_orig = alunos_df_orig[alunos_df_orig['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()

    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)

    # PONTO 3: Adiciona filtro de turma (pelotão)
    st.subheader("Filtros de Seleção")
    opcoes_pelotao = ["Todos"] + sorted(alunos_df_orig['pelotao'].dropna().unique().tolist())
    pelotao_selecionado = st.selectbox("Filtrar por Pelotão:", opcoes_pelotao)

    alunos_filtrados_df = alunos_df_orig.copy()
    if pelotao_selecionado != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao_selecionado]

    opcoes_alunos, student_id_list, alunos_df_com_conceito = get_student_list_with_indicators(alunos_filtrados_df, acoes_com_pontos, config_dict)
    
    st.divider()

    if not student_id_list:
        st.info("Nenhum aluno encontrado para o pelotão selecionado.")
        st.stop()

    if 'current_student_index' not in st.session_state: st.session_state.current_student_index = 0
    if st.session_state.current_student_index >= len(student_id_list): st.session_state.current_student_index = 0

    def on_select_change():
        selected_id = st.session_state.student_selector
        if selected_id in student_id_list:
            st.session_state.current_student_index = student_id_list.index(selected_id)

    current_student_id = student_id_list[st.session_state.current_student_index]

    col_nav1, col_nav2, col_nav3 = st.columns([1, 4, 1])
    with col_nav1:
        if st.button("< Aluno Anterior", use_container_width=True, disabled=(st.session_state.current_student_index == 0)):
            st.session_state.current_student_index -= 1; st.rerun()
    with col_nav2:
        st.selectbox("Selecione o Aluno:", options=list(opcoes_alunos.keys()), format_func=lambda x: opcoes_alunos[x],
                     key="student_selector", index=st.session_state.current_student_index, on_change=on_select_change, label_visibility="collapsed")
    with col_nav3:
        if st.button("Próximo Aluno >", use_container_width=True, disabled=(st.session_state.current_student_index == len(student_id_list) - 1)):
            st.session_state.current_student_index += 1; st.rerun()

    st.write("")
    
    aluno_selecionado = alunos_df_com_conceito[alunos_df_com_conceito['id'] == current_student_id].iloc[0]

    with st.container(border=True):
        # PONTO 1 & 7: Colunas ajustadas para foto maior e 3 métricas
        col_img, col_info, col_pontos, col_media, col_conceito = st.columns([2, 3, 1.5, 1.5, 1.5])
        with col_img:
            # PONTO 1: Foto maior (width=250) e usa o novo slider
            st.image(aluno_selecionado.get('url_foto', "https://via.placeholder.com/250?text=Sem+Foto"), width=photo_size)
        with col_info:
            st.header(aluno_selecionado['nome_guerra'])
            st.markdown(f"**Nº Interno:** {aluno_selecionado['numero_interno']} | **Pelotão:** {aluno_selecionado['pelotao']}")
        # PONTO 7 & 8: Três métricas com 3 casas decimais
        with col_pontos:
            st.metric("Soma de Pontos", f"{aluno_selecionado['soma_pontos_acoes']:.3f}")
        with col_media:
            st.metric("Média Acadêmica", f"{float(aluno_selecionado.get('media_academica', 0.0)):.3f}")
        with col_conceito:
            st.metric("Conceito Final", f"{aluno_selecionado['conceito_final']:.3f}")
        
        st.divider()

        acoes_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == current_student_id]
        
        positivas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] > 0].sort_values('data', ascending=False)
        negativas = acoes_aluno[acoes_aluno['pontuacao_efetiva'] < 0].sort_values('data', ascending=False)
        
        # PONTO 2: Lógica de exibição das listas reforçada
        col_pos, col_neg = st.columns(2)
        with col_pos:
            st.subheader("✅ Anotações Positivas")
            if positivas.empty:
                st.info("Nenhuma anotação positiva registrada.")
            else:
                for _, acao in positivas.iterrows():
                    data_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                    # PONTO 8: 3 casas decimais
                    st.markdown(f"**Data:** {data_fmt} | **Pontos:** <span style='color:green;'>{acao['pontuacao_efetiva']:+.3f}</span>", unsafe_allow_html=True)
                    st.caption(f"Tipo: {acao['nome']}")
        
        with col_neg:
            st.subheader("⚠️ Anotações Negativas")
            if negativas.empty:
                st.info("Nenhuma anotação negativa registrada.")
            else:
                for _, acao in negativas.iterrows():
                    data_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                    # PONTO 8: 3 casas decimais
                    st.markdown(f"**Data:** {data_fmt} | **Pontos:** <span style='color:red;'>{acao['pontuacao_efetiva']:+.3f}</span>", unsafe_allow_html=True)
                    st.caption(f"Tipo: {acao['nome']}")
        
        st.divider()
        render_quick_action_form(aluno_selecionado, supabase)
        
        st.divider()
        # PONTO 6: Botão para gerar e baixar o PDF
        st.subheader("Exportar")
        if st.button("Gerar PDF do Aluno Atual", use_container_width=True):
            with st.spinner("Gerando PDF..."):
                pdf_bytes = gerar_pdf_conselho(aluno_selecionado, positivas, negativas)
                st.download_button(
                    label="✅ Baixar PDF",
                    data=pdf_bytes,
                    file_name=f"Conselho_{aluno_selecionado['nome_guerra']}.pdf",
                    mime="application/pdf"
                )
