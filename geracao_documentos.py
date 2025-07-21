import streamlit as st
import pandas as pd
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from database import load_data, init_supabase_client
from auth import check_permission
import json

# --- Funções de Lógica (Backend) - Sem alterações ---

def extract_pdf_fields(pdf_bytes: bytes) -> list:
    """Lê um arquivo PDF em bytes e extrai os nomes dos campos de formulário."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        fields = reader.get_form_text_fields()
        return list(fields.keys()) if fields else []
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
        return []

def get_aluno_columns() -> list:
    """Carrega os dados dos alunos e retorna a lista de colunas disponíveis."""
    alunos_df = load_data("Alunos")
    if not alunos_df.empty:
        return [""] + sorted(alunos_df.columns.tolist())
    return [""]

def fill_pdf(template_bytes: bytes, student_data: pd.Series, mapping: dict) -> BytesIO:
    """Preenche um único PDF com os dados de um aluno ou textos fixos usando o mapeamento."""
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)

    fill_data = {}
    for pdf_field, config in mapping.items():
        if config['type'] == 'db' and config['value']:
            fill_data[pdf_field] = str(student_data.get(config['value'], ''))
        elif config['type'] == 'static':
            fill_data[pdf_field] = config['value']

    if writer.pages:
        writer.update_page_form_field_values(writer.pages[0], fill_data)
    
    filled_pdf_buffer = BytesIO()
    writer.write(filled_pdf_buffer)
    filled_pdf_buffer.seek(0)
    return filled_pdf_buffer

def merge_pdfs(pdf_buffers: list) -> BytesIO:
    """Unifica uma lista de PDFs (em BytesIO) em um único arquivo."""
    merger = PdfWriter()
    for buffer in pdf_buffers:
        reader = PdfReader(buffer)
        for page in reader.pages:
            merger.add_page(page)
            
    merged_pdf_buffer = BytesIO()
    merger.write(merged_pdf_buffer)
    merged_pdf_buffer.seek(0)
    return merged_pdf_buffer

# --- Função Principal da Página (Fluxo Unificado) ---

def show_geracao_documentos_direto():
    st.title("📄 Gerador de Documentos Direto")

    if not check_permission('acesso_pagina_geracao_documentos'):
        st.error("Acesso negado. Apenas administradores podem acessar esta página.")
        return

    # Inicializa clientes
    supabase = init_supabase_client()
    aluno_columns = get_aluno_columns()

    # --- Passo 1: Upload do Modelo ---
    st.header("1. Carregue o Modelo de PDF")
    uploaded_file = st.file_uploader("Selecione um arquivo PDF com campos de formulário", type="pdf")

    if uploaded_file:
        # Armazena os bytes do PDF na sessão para não perdê-lo ao interagir com outros widgets
        st.session_state.uploaded_pdf_bytes = uploaded_file.getvalue()
        pdf_fields = extract_pdf_fields(st.session_state.uploaded_pdf_bytes)

        if not pdf_fields:
            st.warning("Nenhum campo de formulário editável foi encontrado neste PDF.")
            return

        # --- Passo 2: Mapeamento dos Campos ---
        st.header("2. Mapeie os Campos do PDF")
        st.info(f"Campos encontrados: {', '.join(pdf_fields)}")

        mapping = {}
        for field in pdf_fields:
            st.markdown(f"--- \n**Campo PDF:** `{field}`")
            map_type = st.radio(
                "Tipo de preenchimento:",
                ("Mapear da Coluna do Aluno", "Inserir Texto Fixo"),
                key=f"type_{field}", horizontal=True, label_visibility="collapsed"
            )
            if map_type == "Mapear da Coluna do Aluno":
                db_column = st.selectbox("Coluna do Aluno:", options=aluno_columns, key=f"map_{field}")
                mapping[field] = {'type': 'db', 'value': db_column}
            else:
                static_text = st.text_area("Texto Fixo:", key=f"static_{field}")
                mapping[field] = {'type': 'static', 'value': static_text}
        
        # Armazena o mapeamento na sessão
        st.session_state.field_mapping = mapping

        # --- Passo 3: Seleção dos Alunos ---
        st.header("3. Selecione os Alunos")
        alunos_df = load_data("Alunos")
        if 'selecionar' not in alunos_df.columns:
            alunos_df.insert(0, 'selecionar', False)

        select_all = st.checkbox("Selecionar Todos/Nenhum")
        if select_all:
            alunos_df['selecionar'] = True

        edited_df = st.data_editor(
            alunos_df[['selecionar', 'numero_interno', 'nome_guerra', 'pelotao']],
            use_container_width=True, hide_index=True, key="aluno_selector",
            disabled=['numero_interno', 'nome_guerra', 'pelotao']
        )
        
        alunos_selecionados_df = edited_df[edited_df['selecionar']]

        # --- Passo 4: Geração e Download ---
        st.header("4. Gerar Documento Final")
        if st.button(f"Gerar Documentos para {len(alunos_selecionados_df)} Aluno(s)", type="primary"):
            if alunos_selecionados_df.empty:
                st.warning("Nenhum aluno foi selecionado.")
            else:
                with st.spinner("Gerando documentos..."):
                    try:
                        template_bytes = st.session_state.uploaded_pdf_bytes
                        current_mapping = st.session_state.field_mapping

                        filled_pdfs = []
                        ids_selecionados = alunos_df[edited_df['selecionar']].index
                        dados_completos_alunos_df = load_data("Alunos").loc[ids_selecionados]

                        for _, aluno_row in dados_completos_alunos_df.iterrows():
                            filled_pdf = fill_pdf(template_bytes, aluno_row, current_mapping)
                            filled_pdfs.append(filled_pdf)
                        
                        final_pdf_buffer = merge_pdfs(filled_pdfs)
                        
                        st.session_state.final_pdf_bytes = final_pdf_buffer.getvalue()
                        st.session_state.final_pdf_filename = f"{uploaded_file.name.replace('.pdf', '')}_gerado.pdf"
                    
                    except Exception as e:
                        st.error(f"Ocorreu um erro durante a geração: {e}")
        
        if "final_pdf_bytes" in st.session_state and st.session_state.final_pdf_bytes:
            st.success("Documento consolidado gerado com sucesso!")
            st.download_button(
                label="📥 Baixar Documento Final",
                data=st.session_state.final_pdf_bytes,
                file_name=st.session_state.final_pdf_filename,
                mime="application/pdf"
            )
            # Limpa os bytes após o download para o botão sumir
            st.session_state.final_pdf_bytes = None
