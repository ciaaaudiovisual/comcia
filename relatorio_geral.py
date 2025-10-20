# relatorio_geral.py (versão com correção definitiva de carregamento de dados)

import streamlit as st
import pandas as pd
from io import BytesIO
from fpdf import FPDF
from database import load_data
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final
from aluno_selection_components import render_alunos_filter_and_selection

# ==============================================================================
# FUNÇÕES DE PROCESSAMENTO E GERAÇÃO DE ARQUIVOS
# ==============================================================================

# Esta função NÃO usa cache para garantir que sempre processe os dados mais recentes
def processar_dados_alunos(alunos_selecionados_df, todos_alunos_df):
    """
    Calcula as métricas e coleta as anotações para os alunos selecionados.
    Retorna um DataFrame pronto para exibição.
    """
    # As ações são carregadas aqui dentro para garantir que os dados sejam sempre os mais recentes
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_selecionados_df.empty or acoes_df.empty or tipos_acao_df.empty:
        return pd.DataFrame()

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}

    dados_processados = []
    for _, aluno in alunos_selecionados_df.iterrows():
        aluno_id_str = str(aluno['id'])
        acoes_do_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == aluno_id_str].copy()
        
        soma_pontos = acoes_do_aluno['pontuacao_efetiva'].sum()
        media_academica = float(aluno.get('media_academica', 0.0))
        
        conceito_final = calcular_conceito_final(soma_pontos, media_academica, todos_alunos_df, config_dict)
        
        anotacoes_positivas = acoes_do_aluno[acoes_do_aluno['pontuacao_efetiva'] > 0]
        anotacoes_negativas = acoes_do_aluno[acoes_do_aluno['pontuacao_efetiva'] < 0]

        dados_processados.append({
            'id': aluno_id_str, 'nome_guerra': aluno.get('nome_guerra', 'N/A'),
            'numero_interno': aluno.get('numero_interno', 'S/N'), 'pelotao': aluno.get('pelotao', 'N/A'),
            'soma_pontos_acoes': soma_pontos, 'conceito_final': conceito_final,
            'anotacoes_positivas': anotacoes_positivas, 'anotacoes_negativas': anotacoes_negativas
        })
        
    return pd.DataFrame(dados_processados)

def to_excel(df: pd.DataFrame) -> bytes:
    """Converte um DataFrame para um arquivo Excel em memória."""
    output = BytesIO()
    df_export = df[['numero_interno', 'nome_guerra', 'pelotao', 'conceito_final', 'soma_pontos_acoes']].copy()
    df_export.rename(columns={
        'numero_interno': 'Nº Interno', 'nome_guerra': 'Nome de Guerra', 'pelotao': 'Pelotão',
        'conceito_final': 'Conceito Final', 'soma_pontos_acoes': 'Saldo de Pontos'
    }, inplace=True)
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_export.to_excel(writer, index=False, sheet_name='Relatorio_Geral')
        for i, col in enumerate(df_export.columns):
            column_len = max(df_export[col].astype(str).map(len).max(), len(col))
            writer.sheets['Relatorio_Geral'].set_column(i, i, column_len + 2)
    return output.getvalue()

def generate_summary_pdf(df: pd.DataFrame) -> bytes:
    """Gera um PDF com o resumo dos alunos."""
    class PDF(FPDF):
        def header(self):
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Relatório Geral de Alunos', 0, 1, 'C')
            self.ln(5)
        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF()
    pdf.add_page()
    
    for _, aluno in df.iterrows():
        if pdf.get_y() > 220:
            pdf.add_page()
            
        pdf.set_font('Arial', 'B', 11)
        pdf.cell(0, 8, f"{aluno['nome_guerra']} (Nº {aluno['numero_interno']} | Pel: {aluno['pelotao']})", 1, 1, 'L')
        
        pdf.set_font('Arial', '', 10)
        pdf.cell(95, 8, f"Conceito Final: {aluno['conceito_final']:.3f}", 1, 0, 'C')
        pdf.cell(95, 8, f"Saldo de Pontos: {aluno['soma_pontos_acoes']:.2f}", 1, 1, 'C')
        
        y_before_notes = pdf.get_y()
        pdf.set_font('Arial', 'B', 9)
        pdf.multi_cell(95, 6, "Anotações Positivas:", 1, 'L')
        
        pdf.set_y(y_before_notes)
        pdf.set_x(105)
        pdf.multi_cell(95, 6, "Anotações Negativas:", 1, 'L')
        
        y_pos = pdf.get_y()
        y_neg = pdf.get_y()
        
        pdf.set_font('Arial', '', 8)
        if not aluno['anotacoes_positivas'].empty:
            for _, an in aluno['anotacoes_positivas'].iterrows():
                pdf.set_xy(10, y_pos)
                pdf.multi_cell(95, 5, f"- {an['nome']} ({an['pontuacao_efetiva']:+.1f})", 0, 'L')
                y_pos += 5
        
        if not aluno['anotacoes_negativas'].empty:
            for _, an in aluno['anotacoes_negativas'].iterrows():
                pdf.set_xy(105, y_neg)
                pdf.multi_cell(95, 5, f"- {an['nome']} ({an['pontuacao_efetiva']:+.1f})", 0, 'L')
                y_neg += 5
        
        pdf.set_y(max(y_pos, y_neg) + 5)
        pdf.ln(5)

    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================

def show_relatorio_geral():
    st.title("Relatório Geral de Alunos")
    st.caption("Uma visão planilhada e compacta do desempenho e anotações dos alunos.")

    if not check_permission('acesso_pagina_relatorios'):
        st.error("Acesso negado."); return

    alunos_df = load_data("Alunos")
    if alunos_df.empty:
        st.warning("Nenhum aluno cadastrado no sistema."); return

    st.subheader("1. Selecione os Alunos ou Pelotões")
    alunos_selecionados_df = render_alunos_filter_and_selection(key_suffix="relatorio_geral", include_full_name_search=True)

    st.divider()

    st.subheader("2. Relatório de Desempenho")
    if alunos_selecionados_df.empty:
        st.info("Utilize os filtros acima para selecionar os alunos que deseja analisar.")
    else:
        with st.spinner("Processando dados dos alunos selecionados..."):
            df_relatorio = processar_dados_alunos(alunos_selecionados_df, alunos_df)

        st.info(f"Exibindo relatório para **{len(df_relatorio)}** aluno(s) selecionado(s).")
        
        sort_option = st.radio("Ordenar por:", ["Número Interno", "Maior Conceito"], horizontal=True, index=0)

        if sort_option == "Número Interno":
            df_relatorio['numero_interno_str'] = df_relatorio['numero_interno'].astype(str)
            split_cols = df_relatorio['numero_interno_str'].str.split('-', expand=True)
            df_relatorio['sort_part_1'] = split_cols[0]
            df_relatorio['sort_part_2'] = pd.to_numeric(split_cols.get(1), errors='coerce').fillna(0)
            df_relatorio['sort_part_3'] = pd.to_numeric(split_cols.get(2), errors='coerce').fillna(0)
            df_relatorio = df_relatorio.sort_values(by=['sort_part_1', 'sort_part_2', 'sort_part_3'])
        else:
            df_relatorio = df_relatorio.sort_values(by='conceito_final', ascending=False)

        st.write("")

        for _, aluno_data in df_relatorio.iterrows():
            with st.container(border=True):
                col_info, col_metricas, col_pos, col_neg = st.columns([1.5, 1, 2, 2])
                with col_info:
                    st.markdown(f"**{aluno_data['nome_guerra']}**")
                    st.caption(f"Nº {aluno_data['numero_interno']} | Pel: {aluno_data['pelotao']}")
                with col_metricas:
                    st.metric("Conceito Final", f"{aluno_data['conceito_final']:.3f}")
                    st.metric("Saldo de Pontos", f"{aluno_data['soma_pontos_acoes']:.2f}", delta_color="off")
                with col_pos:
                    st.markdown("✅ **Positivas**")
                    anotacoes = aluno_data['anotacoes_positivas']
                    if anotacoes.empty:
                        st.caption("Nenhuma anotação.")
                    else:
                        for _, an in anotacoes.sort_values('data', ascending=False).iterrows():
                            st.caption(f"- {an['nome']} ({an['pontuacao_efetiva']:+.1f})")
                with col_neg:
                    st.markdown("⚠️ **Negativas**")
                    anotacoes = aluno_data['anotacoes_negativas']
                    if anotacoes.empty:
                        st.caption("Nenhuma anotação.")
                    else:
                        for _, an in anotacoes.sort_values('data', ascending=False).iterrows():
                            st.caption(f"- {an['nome']} ({an['pontuacao_efetiva']:+.1f})")
        
        st.divider()
        st.subheader("3. Exportar Relatório")
        
        if not df_relatorio.empty:
            col_pdf, col_excel = st.columns(2)
            with col_pdf:
                pdf_bytes = generate_summary_pdf(df_relatorio)
                st.download_button(
                    label="📄 Baixar Relatório em PDF", data=pdf_bytes,
                    file_name=f"relatorio_geral_{pd.Timestamp.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", use_container_width=True
                )
            with col_excel:
                excel_bytes = to_excel(df_relatorio)
                st.download_button(
                    label="📊 Baixar Planilha em Excel", data=excel_bytes,
                    file_name=f"relatorio_geral_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True
                )
