import streamlit as st
import pandas as pd
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from database import load_data, init_supabase_client
from auth import check_permission
import json
import fitz  # PyMuPDF
import textwrap # NOVO: Importado para quebra de linha

# --- Funções de Lógica (Backend) ---

def extract_pdf_fields(pdf_bytes: bytes) -> list:
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        fields = reader.get_form_text_fields()
        return list(fields.keys()) if fields else []
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
        return []

def get_aluno_columns() -> list:
    alunos_df = load_data("Alunos")
    if not alunos_df.empty:
        return [""] + sorted(alunos_df.columns.tolist())
    return [""]

# NOVO: Função auxiliar para quebrar o texto
def wrap_text(text, width=40):
    """Quebra um texto longo em várias linhas com um limite de caracteres."""
    return '\n'.join(textwrap.wrap(text, width=width))

def fill_pdf(template_bytes: bytes, student_data: pd.Series, mapping: dict) -> BytesIO:
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter(clone_from=reader)
    
    fill_data = {}
    for pdf_field, config in mapping.items():
        value = ""
        if config['type'] == 'db' and config['value']:
            value = str(student_data.get(config['value'], ''))
        elif config['type'] == 'static':
            value = config['value']

        # ALTERAÇÃO: Aplica a quebra de linha se o valor for grande
        # O campo 'SOLICITAÇÃO' terá uma quebra de linha a cada 80 caracteres.
        # Ajuste o 'width' conforme necessário para outros campos.
        if pdf_field == 'SOLICITAÇÃO':
             fill_data[pdf_field] = wrap_text(value, width=80)
        else:
             fill_data[pdf_field] = value

    if writer.get_form_text_fields():
        for page in writer.pages:
            writer.update_page_form_field_values(page, fill_data)
    
    filled_pdf_buffer = BytesIO()
    writer.write(filled_pdf_buffer)
    filled_pdf_buffer.seek(0)
    return filled_pdf_buffer

def merge_pdfs(pdf_buffers: list) -> BytesIO:
    merger = PdfWriter()
    for buffer in pdf_buffers:
        reader = PdfReader(buffer)
        for page in reader.pages:
            merger.add_page(page)
    merged_pdf_buffer = BytesIO()
    merger.write(merged_pdf_buffer)
    merged_pdf_buffer.seek(0)
    return merged_pdf_buffer

def generate_pdf_previews(pdf_bytes: bytes) -> list:
    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)
        doc.close()
    except Exception as e:
        st.error(f"Erro ao gerar pré-visualização do PDF: {e}")
    return images

# --- Função Principal da Página ---

def show_geracao_documentos():
    st.title("📄 Gerador de Documentos")

    if not check_permission('acesso_pagina_geracao_documentos'):
        st.error("Acesso negado.")
        return

    supabase = init_supabase_client()
    aluno_columns = get_aluno_columns()

    st.header("1. Carregue o Modelo de PDF")
    uploaded_file = st.file_uploader(
        "Selecione um arquivo PDF com campos de formulário", 
        type="pdf",
        on_change=lambda: st.session_state.clear() if 'uploaded_pdf_bytes' in st.session_state else None
    )

    if uploaded_file:
        st.session_state.uploaded_pdf_bytes = uploaded_file.getvalue()
        
    if 'uploaded_pdf_bytes' in st.session_state:
        pdf_fields = extract_pdf_fields(st.session_state.uploaded_pdf_bytes)

        if not pdf_fields:
            st.warning("Nenhum campo de formulário editável foi encontrado neste PDF.")
            st.stop()

        st.header("2. Mapeie os Campos do PDF")
        st.info(f"Campos encontrados: {', '.join(pdf_fields)}")

        with st.form("mapping_form"):
            mapping = {}
            for field in pdf_fields:
                with st.container(border=True):
                    st.markdown(f"**Campo PDF:** `{field}`")
                    map_type = st.radio(
                        "Fonte dos dados:", ("Coluna do Aluno", "Texto Fixo"),
                        key=f"type_{field}", horizontal=True, label_visibility="collapsed"
                    )
                    if map_type == "Coluna do Aluno":
                        db_column = st.selectbox("Selecione a Coluna:", options=aluno_columns, key=f"map_{field}")
                        mapping[field] = {'type': 'db', 'value': db_column}
                    else:
                        static_text = st.text_area("Digite o Texto Fixo:", key=f"static_{field}", height=100)
                        mapping[field] = {'type': 'static', 'value': static_text}
            
            if st.form_submit_button("Confirmar Mapeamento", type="primary"):
                st.session_state.field_mapping = mapping
                st.success("Mapeamento confirmado!")

        if 'field_mapping' in st.session_state:
            st.header("3. Selecione os Alunos e Gere o Documento")
            
            alunos_df = load_data("Alunos")
            
            st.subheader("Filtros")
            col1, col2 = st.columns(2)
            
            with col1:
                pelotoes_unicos = alunos_df['pelotao'].unique()
                lista_pelotoes = sorted([str(p) for p in pelotoes_unicos if pd.notna(p)])
                pelotoes_selecionados = st.multiselect("Filtrar por Pelotão:", options=lista_pelotoes)

            with col2:
                termo_busca = st.text_input("Buscar por Nome de Guerra ou Nº Interno:")

            alunos_filtrados_df = alunos_df.copy()
            if pelotoes_selecionados:
                alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'].isin(pelotoes_selecionados)]
            if termo_busca:
                alunos_filtrados_df = alunos_filtrados_df[
                    alunos_filtrados_df['nome_guerra'].str.contains(termo_busca, case=False, na=False) |
                    alunos_filtrados_df['numero_interno'].astype(str).str.contains(termo_busca, case=False, na=False)
                ]

            st.subheader("Seleção de Alunos")
            if 'selecionar' not in alunos_filtrados_df.columns:
                alunos_filtrados_df.insert(0, 'selecionar', False)

            if st.checkbox("Selecionar Todos/Nenhum (visíveis na tabela)"):
                alunos_filtrados_df['selecionar'] = True
            
            edited_df = st.data_editor(
                alunos_filtrados_df[['selecionar', 'numero_interno', 'nome_guerra', 'pelotao']],
                use_container_width=True, hide_index=True, key="aluno_selector"
            )
            
            alunos_para_gerar_df = edited_df[edited_df['selecionar']]
            
            if st.button(f"Gerar Documento para {len(alunos_para_gerar_df)} Aluno(s)"):
                if alunos_para_gerar_df.empty:
                    st.warning("Nenhum aluno foi selecionado.")
                else:
                    with st.spinner("Gerando documentos..."):
                        try:
                            template_bytes = st.session_state.uploaded_pdf_bytes
                            current_mapping = st.session_state.field_mapping
                            filled_pdfs = []
                            ids_selecionados = alunos_para_gerar_df.index
                            dados_completos_alunos_df = alunos_df.loc[ids_selecionados]

                            for _, aluno_row in dados_completos_alunos_df.iterrows():
                                filled_pdf = fill_pdf(template_bytes, aluno_row, current_mapping)
                                filled_pdfs.append(filled_pdf)
                            
                            final_pdf_buffer = merge_pdfs(filled_pdfs)
                            
                            st.session_state.final_pdf_bytes = final_pdf_buffer.getvalue()
                            st.session_state.final_pdf_filename = f"{uploaded_file.name.replace('.pdf', '')}_gerado.pdf"
                        except Exception as e:
                            st.error(f"Ocorreu um erro durante a geração: {e}")
                            print(f"Erro detalhado na geração: {e}")

            if 'final_pdf_bytes' in st.session_state and st.session_state.final_pdf_bytes:
                st.header("4. Pré-visualização e Download")
                st.success("Documento consolidado gerado!")
                
                st.download_button(
                    label="📥 Baixar Documento Final (.pdf)",
                    data=st.session_state.final_pdf_bytes,
                    file_name=st.session_state.final_pdf_filename,
                    mime="application/pdf"
                )

                with st.spinner("Carregando pré-visualização..."):
                    preview_images = generate_pdf_previews(st.session_state.final_pdf_bytes)
                
                if preview_images:
                    tabs = st.tabs([f"Página {i+1}" for i in range(len(preview_images))])
                    for i, tab in enumerate(tabs):
                        with tab:
                            # CORREÇÃO: Parâmetro obsoleto trocado
                            st.image(preview_images[i], caption=f"Página {i+1}", use_container_width=True)
                else:
                    st.warning("Não foi possível gerar a pré-visualização.")
