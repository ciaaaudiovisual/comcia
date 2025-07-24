# controle_pernoite.py

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from io import BytesIO
from fpdf import FPDF
import math

# --- FUNÇÃO PARA GERAR PDF (COM CABEÇALHO CORRIGIDO) ---
def gerar_pdf_pernoite(cabecalho_principal, data_selecionada, alunos_df_sorted):
    # Classe interna para controlar o cabeçalho
    class PDF(FPDF):
        def __init__(self, cabecalho_texto):
            super().__init__()
            # Armazena o cabeçalho personalizado
            self.cabecalho_texto = cabecalho_texto

        def header(self):
            # 1. Usa o cabeçalho personalizado que foi passado
            self.set_font("Arial", 'B', 16)
            self.cell(0, 10, self.cabecalho_texto, 0, 1, 'C')
            
            # 2. Adiciona a data
            self.set_font("Arial", '', 12)
            self.cell(0, 10, f"Data: {data_selecionada.strftime('%d/%m/%Y')}", 0, 1, 'C')
            self.ln(5)

            # 3. Adiciona o cabeçalho fixo da tabela
            self.set_font("Arial", 'B', 12)
            self.cell(0, 10, "NÚMERO INTERNO", 1, 1, 'C')

        def footer(self):
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    # Passa o cabeçalho principal ao criar a instância do PDF
    pdf = PDF(cabecalho_principal)
    pdf.add_page()
    pdf.set_font("Arial", '', 10) 

    lista_numeros_internos = alunos_df_sorted['numero_interno'].tolist()
    total_militares = len(lista_numeros_internos)
    num_colunas = 5
    num_linhas = math.ceil(total_militares / num_colunas) + 3

    largura_pagina = pdf.w - 2 * pdf.l_margin
    largura_coluna = largura_pagina / num_colunas
    altura_linha = 8

    idx_militar = 0
    for r in range(num_linhas):
        for c in range(num_colunas):
            numero = str(lista_numeros_internos[idx_militar]) if idx_militar < total_militares else ""
            pdf.cell(largura_coluna, altura_linha, numero, 1, 0, 'C')
            if idx_militar < total_militares:
                idx_militar += 1
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total de Militares em Pernoite: {total_militares}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')


# --- PÁGINA PRINCIPAL DO MÓDULO (COM A LÓGICA DO CABEÇALHO REINTEGRADA) ---
def show_controle_pernoite():
    st.title("Controle de Pernoite")
    st.caption("Marque os alunos e, ao final, clique em 'Salvar Alterações' para gravar os dados.")

    supabase = init_supabase_client()
    
    alunos_df = load_data("Alunos")
    pernoite_df = load_data("pernoite")

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
    
    # LÓGICA DO CABEÇALHO REINTEGRADA
    config_df = load_data("Config")
    cabecalho_salvo = config_df[config_df['chave'] == 'cabecalho_pernoite_pdf']['valor'].iloc[0] if 'cabecalho_pernoite_pdf' in config_df['chave'].values else "Relação de Militares em Pernoite"
    cabecalho_editado = st.text_area("Texto do Cabeçalho Principal do PDF", value=cabecalho_salvo)
    
    if st.button("Salvar Cabeçalho Padrão"):
        supabase.table("Config").upsert({'chave': 'cabecalho_pernoite_pdf', 'valor': cabecalho_editado}).execute()
        st.success("Cabeçalho padrão salvo!"); load_data.clear()

    ids_selecionados_na_tela = [
        aluno_id for aluno_id, marcado in st.session_state.pernoite_status.items() 
        if marcado and aluno_id in alunos_visiveis_ids
    ]
    
    alunos_para_pdf_df = alunos_filtrados_df[alunos_filtrados_df['id'].astype(str).isin(ids_selecionados_na_tela)]
    alunos_para_pdf_df_sorted = alunos_para_pdf_df.sort_values('numero_interno')

    st.write(f"**Total de militares marcados para pernoite (nesta tela):** {len(alunos_para_pdf_df_sorted)}")

    if st.button("Gerar PDF", type="secondary"):
        if alunos_para_pdf_df_sorted.empty:
            st.warning("Nenhum aluno está marcado como 'pernoite' na tela.")
        else:
            # Passa o cabeçalho editado para a função
            pdf_bytes = gerar_pdf_pernoite(cabecalho_editado, data_selecionada, alunos_para_pdf_df_sorted)
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
