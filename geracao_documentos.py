import streamlit as st
import pandas as pd
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from database import load_data, init_supabase_client
from auth import check_permission
import json
import re # Importa a biblioteca de expressões regulares para "limpar" o nome do ficheiro

# --- Funções de Lógica (Backend) ---

def extract_pdf_fields(pdf_bytes: bytes) -> list:
    """Lê um arquivo PDF em bytes e extrai os nomes dos campos de formulário."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        fields = reader.get_form_text_fields()
        if fields is None:
            return []
        return list(fields.keys())
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
            # Pega o dado do banco de dados
            fill_data[pdf_field] = str(student_data.get(config['value'], ''))
        elif config['type'] == 'static':
            # Usa o texto fixo
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

# --- Seções da Interface do Usuário ---

def manage_templates_section(supabase, aluno_columns):
    """Renderiza a UI para gerenciamento de modelos."""
    with st.container(border=True):
        st.subheader("1. Cadastrar ou Atualizar um Modelo")
        
        uploaded_file = st.file_uploader("Carregue um modelo de PDF com campos de formulário", type="pdf")

        if uploaded_file:
            st.session_state.uploaded_pdf_bytes = uploaded_file.getvalue()
            pdf_fields = extract_pdf_fields(st.session_state.uploaded_pdf_bytes)
            
            if not pdf_fields:
                st.warning("Nenhum campo de formulário editável foi encontrado neste PDF.")
                return

            st.info(f"Campos encontrados no PDF: {', '.join(pdf_fields)}")

            with st.form("template_mapping_form"):
                st.markdown("##### Mapeie os campos do PDF:")
                
                mapping = {}
                for field in pdf_fields:
                    st.markdown(f"--- \n**Campo PDF:** `{field}`")
                    
                    map_type = st.radio(
                        "Tipo de preenchimento:",
                        ("Mapear da Coluna do Aluno", "Inserir Texto Fixo"),
                        key=f"type_{field}",
                        horizontal=True,
                        label_visibility="collapsed"
                    )

                    if map_type == "Mapear da Coluna do Aluno":
                        db_column = st.selectbox("Coluna do Aluno:", options=aluno_columns, key=f"map_{field}")
                        mapping[field] = {'type': 'db', 'value': db_column}
                    else:
                        # --- CORREÇÃO: Usar st.text_area para textos longos ---
                        static_text = st.text_area("Texto Fixo:", key=f"static_{field}")
                        mapping[field] = {'type': 'static', 'value': static_text}
                
                template_name = st.text_input("Dê um nome para este modelo (ex: Papeleta de Pagamento)*")
                
                if st.form_submit_button("Salvar Modelo"):
                    if not template_name:
                        st.error("O nome do modelo é obrigatório.")
                    else:
                        with st.spinner("Salvando modelo..."):
                            try:
                                bucket_name = "modelos-pdf"
                                
                                temp_name = template_name.replace(' ', '_')
                                sanitized_name = re.sub(r'[^\w-]', '', temp_name)
                                sanitized_name = sanitized_name[:100]
                                file_path = f"{sanitized_name}.pdf"

                                supabase.storage.from_(bucket_name).upload(
                                    file=st.session_state.uploaded_pdf_bytes,
                                    path=file_path,
                                    file_options={"content-type": "application/pdf", "x-upsert": "true"}
                                )
                                
                                supabase.table("documento_modelos").upsert({
                                    "nome_modelo": template_name,
                                    "mapeamento": json.dumps(mapping),
                                    "path_pdf_storage": file_path
                                }).execute()
                                
                                st.success(f"Modelo '{template_name}' salvo com sucesso!")
                                load_data.clear()
                            except Exception as e:
                                st.error(f"Erro ao salvar o modelo: {e}")

def generate_documents_section(supabase):
    """Renderiza a UI para a geração de documentos em massa."""
    with st.container(border=True):
        st.subheader("2. Gerar Documentos em Massa")

        modelos_df = load_data("documento_modelos")
        if modelos_df.empty:
            st.info("Nenhum modelo cadastrado. Cadastre um na seção acima.")
            return

        modelo_selecionado_nome = st.selectbox("Selecione um modelo", options=modelos_df['nome_modelo'].tolist())
        
        if modelo_selecionado_nome:
            alunos_df = load_data("Alunos")
            if 'selecionar' not in alunos_df.columns:
                alunos_df.insert(0, 'selecionar', False)

            st.markdown("##### Selecione os alunos para a geração:")
            
            select_all = st.checkbox("Selecionar Todos/Nenhum")
            if select_all:
                alunos_df['selecionar'] = True
            
            edited_df = st.data_editor(
                alunos_df[['selecionar', 'numero_interno', 'nome_guerra', 'pelotao']],
                use_container_width=True, hide_index=True, key="aluno_selector",
                disabled=['numero_interno', 'nome_guerra', 'pelotao']
            )
            
            alunos_selecionados_df = edited_df[edited_df['selecionar']]

            if st.button(f"Gerar Documentos para {len(alunos_selecionados_df)} Aluno(s)", type="primary"):
                if alunos_selecionados_df.empty:
                    st.warning("Nenhum aluno foi selecionado.")
                else:
                    with st.spinner("Gerando documentos..."):
                        try:
                            modelo_info = modelos_df[modelos_df['nome_modelo'] == modelo_selecionado_nome].iloc[0]
                            path_pdf = modelo_info['path_pdf_storage']
                            mapeamento = json.loads(modelo_info['mapeamento'])
                            
                            bucket_name = "modelos-pdf"
                            template_pdf_bytes = supabase.storage.from_(bucket_name).download(path_pdf)

                            filled_pdfs = []
                            ids_selecionados = alunos_df.loc[alunos_df.index.isin(alunos_selecionados_df.index[edited_df['selecionar']]), 'id'].tolist()
                            dados_completos_alunos_df = load_data("Alunos")
                            dados_completos_alunos_df = dados_completos_alunos_df[dados_completos_alunos_df['id'].isin(ids_selecionados)]

                            for _, aluno_row in dados_completos_alunos_df.iterrows():
                                filled_pdf = fill_pdf(template_pdf_bytes, aluno_row, mapeamento)
                                filled_pdfs.append(filled_pdf)
                            
                            final_pdf_buffer = merge_pdfs(filled_pdfs)
                            
                            st.session_state.final_pdf_bytes = final_pdf_buffer.getvalue()
                            st.session_state.final_pdf_filename = f"{modelo_selecionado_nome.replace(' ', '_')}_gerado.pdf"
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
                st.session_state.final_pdf_bytes = None

# --- Função Principal da Página ---
def show_geracao_documentos():
    st.title("📄 Gerador de Documentos")
    
    if not check_permission('acesso_pagina_geracao_documentos'):
        st.error("Acesso negado. Apenas administradores podem acessar esta página.")
        return

    supabase = init_supabase_client()
    aluno_columns = get_aluno_columns()

    st.header("Gerenciamento de Modelos")
    manage_templates_section(supabase, aluno_columns)

    st.divider()

    st.header("Geração em Massa")
    generate_documents_section(supabase)
