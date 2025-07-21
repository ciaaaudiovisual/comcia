import streamlit as st
import pandas as pd
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from database import load_data, init_supabase_client
from auth import check_permission
import json

# --- Funções de Lógica (Backend) ---

def extract_pdf_fields(pdf_bytes: bytes) -> list:
    """Lê um arquivo PDF em bytes e extrai os nomes dos campos de formulário."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.get_form_text_fields() is None:
            return []
        return list(reader.get_form_text_fields().keys())
    except Exception as e:
        st.error(f"Erro ao ler o PDF: {e}")
        return []

def get_aluno_columns() -> list:
    """Carrega os dados dos alunos e retorna a lista de colunas disponíveis."""
    alunos_df = load_data("Alunos")
    if not alunos_df.empty:
        # Adiciona uma opção em branco para desmapear um campo
        return [""] + sorted(alunos_df.columns.tolist())
    return [""]

def fill_pdf(template_bytes: bytes, student_data: pd.Series, mapping: dict) -> BytesIO:
    """Preenche um único PDF com os dados de um aluno usando o mapeamento."""
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter()
    
    # Copia todas as páginas do modelo original
    for page in reader.pages:
        writer.add_page(page)

    # Preenche os campos do formulário
    writer.update_page_form_field_values(writer.pages[0], {
        pdf_field: str(student_data.get(db_column, ''))
        for pdf_field, db_column in mapping.items()
    })
    
    # Salva o PDF preenchido em um objeto BytesIO na memória
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
        st.subheader("1. Cadastrar Novo Modelo")
        
        uploaded_file = st.file_uploader("Carregue um modelo de PDF com campos de formulário", type="pdf")

        if uploaded_file:
            st.session_state.uploaded_pdf_bytes = uploaded_file.getvalue()
            pdf_fields = extract_pdf_fields(st.session_state.uploaded_pdf_bytes)
            
            if not pdf_fields:
                st.warning("Nenhum campo de formulário editável foi encontrado neste PDF. Por favor, carregue um PDF válido.")
                return

            st.info(f"Campos encontrados no PDF: {', '.join(pdf_fields)}")

            with st.form("template_mapping_form"):
                st.markdown("##### Mapeie os campos do PDF para as colunas do banco de dados:")
                
                mapping = {}
                cols = st.columns(2)
                for i, field in enumerate(pdf_fields):
                    # Distribui os campos entre as colunas para uma UI mais compacta
                    with cols[i % 2]:
                        mapping[field] = st.selectbox(
                            f"Campo PDF: `{field}`", 
                            options=aluno_columns,
                            key=f"map_{field}"
                        )
                
                template_name = st.text_input("Dê um nome para este modelo (ex: Papeleta de Pagamento)*")
                
                if st.form_submit_button("Salvar Modelo"):
                    if not template_name:
                        st.error("O nome do modelo é obrigatório.")
                    else:
                        with st.spinner("Salvando modelo..."):
                            try:
                                # 1. Upload do PDF para o Supabase Storage
                                file_path = f"{template_name.replace(' ', '_')}.pdf"
                                supabase.storage.from_("modelos_pdf").upload(
                                    file=st.session_state.uploaded_pdf_bytes,
                                    path=file_path,
                                    file_options={"content-type": "application/pdf", "x-upsert": "true"}
                                )
                                
                                # 2. Salva os metadados na tabela do banco de dados
                                supabase.table("documento_modelos").upsert({
                                    "nome_modelo": template_name,
                                    "mapeamento": json.dumps(mapping),
                                    "path_pdf_storage": file_path
                                }).execute()
                                
                                st.success(f"Modelo '{template_name}' salvo com sucesso!")
                                load_data.clear() # Limpa o cache para recarregar os modelos
                            except Exception as e:
                                st.error(f"Erro ao salvar o modelo: {e}")

def generate_documents_section(supabase):
    """Renderiza a UI para a geração de documentos em massa."""
    with st.container(border=True):
        st.subheader("2. Gerar Documentos em Massa")

        modelos_df = load_data("documento_modelos")
        if modelos_df.empty:
            st.info("Nenhum modelo de documento cadastrado. Cadastre um modelo na seção acima para começar.")
            return

        modelo_selecionado_nome = st.selectbox("Selecione um modelo", options=modelos_df['nome_modelo'].tolist())
        
        if modelo_selecionado_nome:
            alunos_df = load_data("Alunos")
            if 'selecionar' not in alunos_df.columns:
                alunos_df.insert(0, 'selecionar', False)

            st.markdown("##### Selecione os alunos para a geração:")
            
            # Lógica para o checkbox "Selecionar Todos"
            select_all = st.checkbox("Selecionar Todos/Nenhum")
            if select_all:
                alunos_df['selecionar'] = True
            else:
                # Mantém a seleção manual se "Selecionar Todos" não estiver marcado
                pass

            edited_df = st.data_editor(
                alunos_df[['selecionar', 'numero_interno', 'nome_guerra', 'pelotao']],
                use_container_width=True,
                hide_index=True,
                key="aluno_selector"
            )
            
            alunos_selecionados_df = edited_df[edited_df['selecionar']]

            if st.button(f"Gerar Documentos para {len(alunos_selecionados_df)} Aluno(s)", type="primary"):
                if alunos_selecionados_df.empty:
                    st.warning("Nenhum aluno foi selecionado.")
                else:
                    with st.spinner("Baixando modelo e gerando documentos..."):
                        try:
                            # Busca o modelo selecionado
                            modelo_info = modelos_df[modelos_df['nome_modelo'] == modelo_selecionado_nome].iloc[0]
                            path_pdf = modelo_info['path_pdf_storage']
                            mapeamento = json.loads(modelo_info['mapeamento'])

                            # Baixa o PDF do modelo do Supabase Storage
                            template_pdf_bytes = supabase.storage.from_("modelos_pdf").download(path_pdf)

                            # Gera um PDF para cada aluno selecionado
                            filled_pdfs = []
                            # Busca os dados completos dos alunos selecionados
                            ids_selecionados = alunos_selecionados_df['id'].tolist()
                            dados_completos_alunos_df = alunos_df[alunos_df['id'].isin(ids_selecionados)]

                            for _, aluno_row in dados_completos_alunos_df.iterrows():
                                filled_pdf = fill_pdf(template_pdf_bytes, aluno_row, mapeamento)
                                filled_pdfs.append(filled_pdf)
                            
                            # Unifica todos os PDFs em um só
                            final_pdf_buffer = merge_pdfs(filled_pdfs)
                            
                            st.session_state.final_pdf_bytes = final_pdf_buffer.getvalue()
                            st.session_state.final_pdf_filename = f"{modelo_selecionado_nome.replace(' ', '_')}_gerado.pdf"
                        except Exception as e:
                            st.error(f"Ocorreu um erro durante a geração: {e}")
            
            if "final_pdf_bytes" in st.session_state:
                st.success("Documento consolidado gerado com sucesso!")
                st.download_button(
                    label="📥 Baixar Documento Final",
                    data=st.session_state.final_pdf_bytes,
                    file_name=st.session_state.final_pdf_filename,
                    mime="application/pdf"
                )


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
