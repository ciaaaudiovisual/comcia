# controle_pernoite.py

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from io import BytesIO
from fpdf import FPDF

# --- NOVA FUNÇÃO PARA GERAR PDF FORMATADO COMO TABELA ---
def gerar_pdf_pernoite(data_selecionada, lista_numeros_internos):
    class PDF(FPDF):
        def header(self):
            # Título principal mesclado
            self.set_font("Arial", 'B', 14)
            self.cell(0, 10, "RELAÇÃO DE MILITARES EM PERNOITE", 0, 1, 'C')
            self.set_font("Arial", '', 12)
            self.cell(0, 10, f"Data: {data_selecionada.strftime('%d/%m/%Y')}", 0, 1, 'C')
            self.ln(5)

            # Cabeçalho da tabela "NUMERO INTERNO"
            self.set_font("Arial", 'B', 12)
            # A largura 0 ocupa a página inteira, a borda 1 desenha a caixa
            self.cell(0, 10, "NÚMERO INTERNO", 1, 1, 'C')

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    pdf = PDF('P', 'mm', 'A4')
    pdf.add_page()
    pdf.set_font("Arial", '', 11)

    # Prepara os dados para a tabela
    total_militares = len(lista_numeros_internos)
    num_colunas = 5
    # Força a tabela a ter exatamente 35 linhas
    num_linhas = 35 
    
    # Organiza os números internos na estrutura de 35 linhas x 5 colunas
    # A lógica de preenchimento é vertical (coluna por coluna)
    tabela_dados = [['' for _ in range(num_colunas)] for _ in range(num_linhas)]
    
    idx_militar = 0
    for c in range(num_colunas):
        for r in range(num_linhas):
            if idx_militar < total_militares:
                tabela_dados[r][c] = str(lista_numeros_internos[idx_militar])
                idx_militar += 1

    # Calcula a largura das colunas
    largura_pagina = pdf.w - 2 * pdf.l_margin
    largura_coluna = largura_pagina / num_colunas

    # Desenha a tabela com o grid
    for r in range(num_linhas):
        for c in range(num_colunas):
            # A borda '1' desenha o grid
            pdf.cell(largura_coluna, 8, tabela_dados[r][c], 1, 0, 'C')
        pdf.ln()

    # Adiciona o quantitativo no final
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total de Militares em Pernoite: {total_militares}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')


# --- PÁGINA PRINCIPAL DO MÓDULO (REFEITA) ---
def show_controle_pernoite():
    st.title("Controle de Pernoite")
    st.caption("Marque os alunos e, ao final, clique em 'Salvar Alterações' para gravar os dados.")

    supabase = init_supabase_client()
    
    # Carregar dados
    alunos_df = load_data("Alunos")
    pernoite_df = load_data("pernoite")

    # --- Interface de Seleção ---
    st.subheader("1. Selecione a Data e o Pelotão")
    col1, col2 = st.columns(2)
    with col1:
        if 'data_selecionada_pernoite' not in st.session_state:
            st.session_state.data_selecionada_pernoite = datetime.now().date()
        
        data_selecionada = st.date_input(
            "Selecione a Data", 
            key="data_selecionada_pernoite",
            on_change=lambda: st.session_state.pop('pernoite_status_carregado', None)
        )
    with col2:
        pelotoes = ["Todos"] + sorted(alunos_df['pelotao'].dropna().unique().tolist())
        pelotao_selecionado = st.selectbox(
            "Selecione o Pelotão", 
            pelotoes, 
            key="pelotao_pernoite",
            on_change=lambda: st.session_state.pop('pernoite_status_carregado', None)
        )

    alunos_filtrados_df = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao_selecionado]
    
    alunos_visiveis_ids = [str(id) for id in alunos_filtrados_df['id'].tolist()]

    st.markdown("---")
    st.subheader("2. Marque os Alunos em Pernoite")

    if 'pernoite_status' not in st.session_state:
        st.session_state.pernoite_status = {}
    
    if not st.session_state.get('pernoite_status_carregado'):
        if not pernoite_df.empty and data_selecionada:
            pernoite_df['data'] = pd.to_datetime(pernoite_df['data']).dt.date
            pernoite_hoje_df = pernoite_df[pernoite_df['data'] == data_selecionada]
            alunos_presentes_ids = [str(id) for id in pernoite_hoje_df[pernoite_hoje_df['presente'] == True]['aluno_id'].tolist()]
        else:
            alunos_presentes_ids = []
        
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = aluno_id in alunos_presentes_ids
        st.session_state.pernoite_status_carregado = True

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    if col_b1.button("Marcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = True
        st.rerun()
    
    if col_b2.button("Desmarcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = False
        st.rerun()
    
    st.write("") 

    for _, aluno in alunos_filtrados_df.sort_values('nome_guerra').iterrows():
        aluno_id_str = str(aluno['id'])
        st.session_state.pernoite_status[aluno_id_str] = st.checkbox(
            label=f"**{aluno['nome_guerra']}** ({aluno.get('numero_interno', 'S/N')})",
            value=st.session_state.pernoite_status.get(aluno_id_str, False),
            key=f"check_{aluno_id_str}"
        )

    st.write("") 
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        with st.spinner("A gravar as alterações..."):
            registos_para_salvar = []
            for aluno_id in alunos_visiveis_ids:
                registos_para_salvar.append({
                    'aluno_id': aluno_id,
                    'data': data_selecionada.strftime('%Y-%m-%d'),
                    'presente': st.session_state.pernoite_status.get(aluno_id, False)
                })
            
            if registos_para_salvar:
                try:
                    supabase.table("pernoite").upsert(registos_para_salvar, on_conflict='aluno_id,data').execute()
                    st.success("Alterações salvas com sucesso!")
                    load_data.clear()
                    st.session_state.pop('pernoite_status_carregado', None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    
    st.markdown("---")
    st.subheader("3. Gerar Relatório em PDF")

    # A geração do PDF agora usa o estado atual da tela (session_state)
    ids_selecionados_na_tela = [
        aluno_id for aluno_id, marcado in st.session_state.pernoite_status.items() 
        if marcado and aluno_id in alunos_visiveis_ids
    ]
    
    alunos_para_pdf_df = alunos_filtrados_df[alunos_filtrados_df['id'].astype(str).isin(ids_selecionados_na_tela)]
    
    # ALTERAÇÃO: Passar a lista de NÚMEROS INTERNOS para o PDF
    lista_numeros_internos_pdf = sorted(alunos_para_pdf_df['numero_interno'].dropna().tolist())

    st.write(f"**Total de militares marcados para pernoite (nesta tela):** {len(lista_numeros_internos_pdf)}")

    if st.button("Gerar PDF", type="secondary"):
        if not lista_numeros_internos_pdf:
            st.warning("Nenhum aluno está marcado como 'pernoite' na tela.")
        else:
            # Chama a nova função de gerar PDF
            pdf_bytes = gerar_pdf_pernoite(data_selecionada, lista_numeros_internos_pdf)
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
