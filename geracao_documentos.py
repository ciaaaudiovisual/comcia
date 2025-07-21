import streamlit as st
import pandas as pd
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from database import load_data, init_supabase_client
from auth import check_permission
import json
import fitz  # Importa a PyMuPDF

# --- Funções de Lógica (Backend) ---

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

def generate_pdf_previews(pdf_bytes: bytes) -> list:
    """Converte as páginas de um PDF em imagens para pré-visualização."""
    images = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            pix = page.get_pixmap()
            img_bytes = pix.tobytes("png")
            images.append(img_bytes)
        doc.close()
    except Exception as e:
        st.error(f"Erro ao gerar pré-visualização do PDF: {e}")
    return images

# --- Função Principal da Página (Fluxo Final e Corrigido) ---

def show_geracao_documentos_final():
    st.title("📄 Gerador de Documentos")

    if not check_permission('acesso_pagina_geracao_documentos'):
        st.error("Acesso negado. Apenas administradores podem acessar esta página.")
        return

    # Inicializa clientes e dados
    supabase = init_supabase_client()
    aluno_columns = get_aluno_columns()

    # --- Passo 1: Upload do Modelo ---
    st.header("1. Carregue o Modelo de PDF")
    uploaded_file = st.file_uploader(
        "Selecione um arquivo PDF com campos de formulário", 
        type="pdf",
        # Limpa o estado da sessão se um novo arquivo for carregado
        on_change=lambda: st.session_state.clear() if 'uploaded_pdf_bytes' in st.session_state else None
    )

    if uploaded_file:
        st.session_state.uploaded_pdf_bytes = uploaded_file.getvalue()
        
    if 'uploaded_pdf_bytes' in st.session_state:
        pdf_fields = extract_pdf_fields(st.session_state.uploaded_pdf_bytes)

        if not pdf_fields:
            st.warning("Nenhum campo de formulário editável foi encontrado neste PDF.")
            st.stop()

        # --- Passo 2: Mapeamento dos Campos ---
        st.header("2. Mapeie os Campos do PDF")
        st.info(f"Campos encontrados: {', '.join(pdf_fields)}")

        mapping = {}
        # Usar um formulário garante que o mapeamento seja "submetido" de uma vez
        with st.form("mapping_form"):
            for field in pdf_fields:
                # CORREÇÃO: Isola cada bloco de mapeamento em um container para evitar bugs de UI
                with st.container(border=True):
                    st.markdown(f"**Campo PDF:** `{field}`")
                    map_type = st.radio(
                        "Fonte dos dados:",
                        ("Coluna do Aluno", "Texto Fixo"),
                        key=f"type_{field}", horizontal=True, label_visibility="collapsed"
                    )

                    if map_type == "Coluna do Aluno":
                        db_column = st.selectbox("Selecione a Coluna:", options=aluno_columns, key=f"map_{field}")
                        mapping[field] = {'type': 'db', 'value': db_column}
                    else:
                        static_text = st.text_area("Digite o Texto Fixo:", key=f"static_{field}", height=100)
                        mapping[field] = {'type': 'static', 'value': static_text}
            
            # Botão para confirmar o mapeamento e mostrar os próximos passos
            if st.form_submit_button("Confirmar Mapeamento", type="primary"):
                st.session_state.field_mapping = mapping
                st.success("Mapeamento confirmado!")

        # --- Passo 3: Seleção dos Alunos e Geração ---
        if 'field_mapping' in st.session_state:
            st.header("3. Selecione os Alunos e Gere o Documento")
            
            alunos_df = load_data("Alunos")
            if 'selecionar' not in alunos_df.columns:
                alunos_df.insert(0, 'selecionar', False)

            edited_df = st.data_editor(
                alunos_df[['selecionar', 'numero_interno', 'nome_guerra', 'pelotao']],
                use_container_width=True, hide_index=True, key="aluno_selector",
                disabled=['numero_interno', 'nome_guerra', 'pelotao']
            )
            
            alunos_selecionados_df = edited_df[edited_df['selecionar']]
            
            if st.button(f"Gerar Documento para {len(alunos_selecionados_df)} Aluno(s)"):
                if alunos_selecionados_df.empty:
                    st.warning("Nenhum aluno foi selecionado.")
                else:
                    with st.spinner("Gerando documentos..."):
                        try:
                            # Pega os dados da sessão atual
                            template_bytes = st.session_state.uploaded_pdf_bytes
                            current_mapping = st.session_state.field_mapping

                            filled_pdfs = []
                            ids_selecionados = alunos_df[edited_df['selecionar']].index
                            dados_completos_alunos_df = load_data("Alunos").loc[ids_selecionados]

                            for _, aluno_row in dados_completos_alunos_df.iterrows():
                                filled_pdf = fill_pdf(template_bytes, aluno_row, current_mapping)
                                filled_pdfs.append(filled_pdf)
                            
                            final_pdf_buffer = merge_pdfs(filled_pdfs)
                            
                            # Salva os bytes do PDF final e o nome do arquivo na sessão
                            st.session_state.final_pdf_bytes = final_pdf_buffer.getvalue()
                            st.session_state.final_pdf_filename = f"{uploaded_file.name.replace('.pdf', '')}_gerado.pdf"
                        except Exception as e:
                            st.error(f"Ocorreu um erro durante a geração: {e}")
                            print(f"Erro detalhado na geração: {e}") # Log no console

            # --- Passo 4: Pré-visualização e Download ---
            if 'final_pdf_bytes' in st.session_state and st.session_state.final_pdf_bytes:
                st.header("4. Pré-visualização e Download")
                st.success("Documento consolidado gerado!")
                
                # Botão de download fica em destaque no topo da seção
                st.download_button(
                    label="📥 Baixar Documento Final (.pdf)",
                    data=st.session_state.final_pdf_bytes,
                    file_name=st.session_state.final_pdf_filename,
                    mime="application/pdf"
                )

                # Gera e exibe a pré-visualização
                with st.spinner("Carregando pré-visualização..."):
                    preview_images = generate_pdf_previews(st.session_state.final_pdf_bytes)
                
                if preview_images:
                    # Cria abas para cada página, permitindo a navegação
                    tabs = st.tabs([f"Página {i+1}" for i in range(len(preview_images))])
                    for i, tab in enumerate(tabs):
                        with tab:
                            st.image(preview_images[i], caption=f"Página {i+1}", use_column_width=True)
                else:
                    st.warning("Não foi possível gerar a pré-visualização.")
