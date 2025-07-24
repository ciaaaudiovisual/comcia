# controle_pernoite.py

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from io import BytesIO
from fpdf import FPDF

# --- FUNÇÃO PARA GERAR PDF (sem alterações) ---
def gerar_pdf_pernoite(cabecalho_texto, data_selecionada, lista_alunos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    pdf.cell(0, 10, cabecalho_texto, 0, 1, 'C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data: {data_selecionada.strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(10)
    
    pdf.set_font("Arial", '', 12)
    for aluno in lista_alunos:
        pdf.cell(0, 8, f"- {str(aluno)}", 0, 1)
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total de Militares em Pernoite: {len(lista_alunos)}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# --- PÁGINA PRINCIPAL DO MÓDULO (VERSÃO FINAL CORRIGIDA) ---
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
        # Usamos uma chave para a data para que o estado não se perca ao mudar de pelotão
        if 'data_selecionada_pernoite' not in st.session_state:
            st.session_state.data_selecionada_pernoite = datetime.now().date()
        
        data_selecionada = st.date_input(
            "Selecione a Data", 
            key="data_selecionada_pernoite",
            on_change=lambda: st.session_state.pop('pernoite_status_carregado', None) # Limpa o status ao mudar a data
        )
    with col2:
        pelotoes = ["Todos"] + sorted(alunos_df['pelotao'].dropna().unique().tolist())
        pelotao_selecionado = st.selectbox(
            "Selecione o Pelotão", 
            pelotoes, 
            key="pelotao_pernoite",
            on_change=lambda: st.session_state.pop('pernoite_status_carregado', None) # Limpa o status ao mudar o pelotão
        )

    # Filtrar alunos com base na seleção
    alunos_filtrados_df = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao_selecionado]
    
    alunos_visiveis_ids = [str(id) for id in alunos_filtrados_df['id'].tolist()]

    st.markdown("---")
    st.subheader("2. Marque os Alunos em Pernoite")

    # --- LÓGICA DE ESTADO MELHORADA ---
    # Carrega o estado do banco de dados APENAS UMA VEZ por mudança de data/pelotão
    if 'pernoite_status' not in st.session_state:
        st.session_state.pernoite_status = {}
    
    if not st.session_state.get('pernoite_status_carregado'):
        if not pernoite_df.empty and data_selecionada:
            pernoite_df['data'] = pd.to_datetime(pernoite_df['data']).dt.date
            pernoite_hoje_df = pernoite_df[pernoite_df['data'] == data_selecionada]
            alunos_presentes_ids = [str(id) for id in pernoite_hoje_df[pernoite_hoje_df['presente'] == True]['aluno_id'].tolist()]
        else:
            alunos_presentes_ids = []
        
        # Preenche o estado da sessão com os dados do banco
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = aluno_id in alunos_presentes_ids
        st.session_state.pernoite_status_carregado = True

    # Botões de Ação em Massa
    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    if col_b1.button("Marcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = True
    
    if col_b2.button("Desmarcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = False
    
    st.write("") 

    # Exibe a lista de alunos com checkboxes que manipulam o session_state
    for _, aluno in alunos_filtrados_df.sort_values('nome_guerra').iterrows():
        aluno_id_str = str(aluno['id'])
        st.session_state.pernoite_status[aluno_id_str] = st.checkbox(
            label=f"**{aluno['nome_guerra']}** ({aluno.get('numero_interno', 'S/N')})",
            value=st.session_state.pernoite_status.get(aluno_id_str, False),
            key=f"check_{aluno_id_str}"
        )

    st.write("") 
    # Botão Único para Salvar
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
                    st.session_state.pop('pernoite_status_carregado', None) # Força recarregar os dados na próxima vez
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    
    st.markdown("---")
    st.subheader("3. Gerar Relatório em PDF")

    config_df = load_data("Config")
    cabecalho_salvo = config_df[config_df['chave'] == 'cabecalho_pernoite_pdf']['valor'].iloc[0] if 'cabecalho_pernoite_pdf' in config_df['chave'].values else "Relação de Militares em Pernoite"
    cabecalho_editado = st.text_area("Cabeçalho do PDF", value=cabecalho_salvo)
    
    if st.button("Salvar Cabeçalho Padrão"):
        supabase.table("Config").upsert({'chave': 'cabecalho_pernoite_pdf', 'valor': cabecalho_editado}).execute()
        st.success("Cabeçalho padrão salvo!"); load_data.clear()

    # --- CORREÇÃO DO BUG ---
    # A lista para o PDF agora é gerada a partir do ESTADO ATUAL DA TELA (session_state),
    # e não mais do que está salvo no banco de dados.
    ids_selecionados_na_tela = [
        aluno_id for aluno_id, marcado in st.session_state.pernoite_status.items() 
        if marcado and aluno_id in alunos_visiveis_ids
    ]
    
    alunos_para_pdf_df = alunos_df[alunos_df['id'].astype(str).isin(ids_selecionados_na_tela)]
    lista_nomes_pdf = sorted(alunos_para_pdf_df['nome_guerra'].tolist())

    st.write(f"**Total de militares marcados para pernoite (nesta tela):** {len(lista_nomes_pdf)}")

    if st.button("Gerar PDF", type="secondary"):
        if not lista_nomes_pdf:
            st.warning("Nenhum aluno está marcado como 'pernoite' na tela.")
        else:
            pdf_bytes = gerar_pdf_pernoite(cabecalho_editado, data_selecionada, lista_nomes_pdf)
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
