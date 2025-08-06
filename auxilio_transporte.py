import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
from PyPDF2 import PdfReader, PdfWriter
# A importação do fitz (PyMuPDF) é a mudança principal
import fitz
import re
from difflib import SequenceMatcher

# --- FUNÇÕES DE LÓGICA E MANIPULAÇÃO DE PDF ---

def create_excel_template():
    """Cria um template .xlsx em memória com colunas sugeridas para download."""
    colunas_template = [
        'NOME COMPLETO', 'POSTO/GRAD', 'NIP', 'ENDERECO_COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
        'SOLDO', 'DIAS_UTEIS', 'DESPESA_DIARIA',
        'EMPRESA_IDA_1', 'TRAJETO_IDA_1', 'TARIFA_IDA_1',
        'EMPRESA_VOLTA_1', 'TRAJETO_VOLTA_1', 'TARIFA_VOLTA_1',
    ]
    df_template = pd.DataFrame(columns=colunas_template)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Modelo')
    return output.getvalue()

def get_pdf_form_fields(pdf_bytes: bytes) -> list:
    """Extrai os nomes dos campos de formulário usando PyMuPDF para consistência."""
    fields = []
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        for page in doc:
            for widget in page.widgets():
                if widget.field_name and widget.field_name not in fields:
                    fields.append(widget.field_name)
        doc.close()
        return fields
    except Exception as e:
        st.error(f"Erro ao ler os campos do PDF: {e}")
        return []

# --- FUNÇÃO DE PREENCHIMENTO REESCRITA COM PyMuPDF (fitz) ---
def fill_pdf_form(template_bytes: bytes, data_row: pd.Series, mapping: dict) -> BytesIO:
    """
    Preenche um formulário PDF usando a biblioteca PyMuPDF (fitz).
    """
    doc = fitz.open(stream=template_bytes, filetype="pdf")

    for page in doc:
        for widget in page.widgets():
            field_name = widget.field_name
            if field_name in mapping:
                csv_column = mapping[field_name]
                if csv_column != "-- Não Mapear --" and csv_column in data_row:
                    value = str(data_row.get(csv_column, ''))
                    widget.field_value = value
                    widget.update()

    output_buffer = BytesIO()
    # CORREÇÃO FINAL: O método save() recebe o buffer diretamente, sem a palavra-chave 'stream'.
    doc.save(output_buffer, garbage=3, deflate=True)
    doc.close()
    
    output_buffer.seek(0)
    return output_buffer


def merge_pdfs(pdf_buffers: list) -> BytesIO:
    """
    Junta uma lista de PDFs. Esta função pode continuar usando PyPDF2.
    """
    merger = PdfWriter()
    for buffer in pdf_buffers:
        buffer.seek(0)
        try:
            reader = PdfReader(buffer)
            for page in reader.pages:
                merger.add_page(page)
        except Exception as e:
            st.error(f"Não foi possível juntar um dos PDFs gerados. Erro: {e}")
            return BytesIO()
    output_buffer = BytesIO()
    merger.write(output_buffer)
    merger.close()
    output_buffer.seek(0)
    return output_buffer

# --- FUNÇÕES DE SIMILARIDADE (SEM ALTERAÇÕES) ---
def clean_text(text: str) -> str:
    if not isinstance(text, str): return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def find_best_match(target_field: str, available_columns: list, threshold=0.6) -> str:
    if not target_field or not available_columns: return ""
    clean_target = clean_text(target_field)
    best_match = ""
    highest_score = 0.0
    for option in available_columns:
        if option == "-- Não Mapear --": continue
        clean_option = clean_text(option)
        score = SequenceMatcher(None, clean_target, clean_option).ratio()
        if score > highest_score:
            highest_score, best_match = score, option
    if highest_score >= threshold:
        return best_match
    return ""

# --- FUNÇÃO PRINCIPAL DA PÁGINA (SEM ALTERAÇÕES NA UI) ---
def show_auxilio_transporte():
    st.set_page_config(page_title="Gerador de Auxílio Transporte", page_icon="📄", layout="wide")
    st.title("📄 Gerador de Documentos de Auxílio Transporte")
    st.markdown("---")

    if 'page_loaded' not in st.session_state:
        st.session_state.clear()
        st.session_state.page_loaded = True

    tab1, tab2, tab3 = st.tabs(["1. Carregar Dados", "2. Mapear Campos do PDF", "3. Gerar Documentos"])

    with tab1:
        st.header("Carregar Ficheiro de Dados")
        st.download_button("Baixar Modelo de Dados (.xlsx)", create_excel_template(), "modelo_auxilio_transporte.xlsx")
        
        uploaded_file = st.file_uploader("Carregue o seu ficheiro (CSV ou Excel)", type=["csv", "xlsx"])
        
        if uploaded_file:
            try:
                # --- CORREÇÃO DE CODIFICAÇÃO DE CARACTERES ---
                if uploaded_file.name.endswith('.csv'):
                    encodings_to_try = ['utf-8', 'latin-1', 'cp1252']
                    df_raw = None
                    for encoding in encodings_to_try:
                        try:
                            uploaded_file.seek(0) # Volta ao início do ficheiro para cada tentativa
                            df_raw = pd.read_csv(uploaded_file, sep=';', encoding=encoding, dtype=str).fillna('')
                            st.toast(f"Ficheiro lido com sucesso (codificação: {encoding})", icon="✅")
                            break # Para na primeira tentativa bem-sucedida
                        except UnicodeDecodeError:
                            continue # Tenta a próxima codificação
                    
                    if df_raw is None:
                        st.error("Não foi possível ler o ficheiro CSV. Verifique a codificação do texto (recomenda-se salvar como UTF-8).")
                        st.stop()
                else: # Para ficheiros .xlsx
                    df_raw = pd.read_excel(uploaded_file, dtype=str).fillna('')
                # --- FIM DA CORREÇÃO ---
                
                st.session_state['dados_carregados'] = df_raw
                st.session_state['nome_ficheiro'] = uploaded_file.name
                st.success(f"Ficheiro '{uploaded_file.name}' carregado com sucesso!")

            except Exception as e:
                st.error(f"Erro ao ler o ficheiro: {e}")
                if 'dados_carregados' in st.session_state:
                    del st.session_state['dados_carregados']

        if 'dados_carregados' in st.session_state:
            st.subheader("Edite os dados se necessário")
            st.info("As alterações feitas aqui serão usadas na geração do documento.")
            st.session_state['dados_carregados'] = st.data_editor(
                st.session_state['dados_carregados'], 
                num_rows="dynamic", 
                use_container_width=True
            )


    with tab2:
        st.header("Carregar e Mapear Modelo PDF")
        if 'dados_carregados' not in st.session_state:
            st.warning("Primeiro, carregue um ficheiro de dados na Aba 1.")
        else:
            pdf_template_file = st.file_uploader("Carregue o modelo PDF editável", type="pdf")
            if pdf_template_file:
                st.session_state.pdf_template_bytes = pdf_template_file.getvalue()
                pdf_fields = get_pdf_form_fields(st.session_state.pdf_template_bytes)
                if not pdf_fields:
                    st.warning("Nenhum campo de formulário editável foi encontrado neste PDF. Verifique o ficheiro.")
                else:
                    st.success(f"Encontrados {len(pdf_fields)} campos no PDF. Tentando mapear automaticamente...")
                    df_cols = ["-- Não Mapear --"] + sorted(st.session_state['dados_carregados'].columns.tolist())
                    with st.form("pdf_mapping_form"):
                        st.markdown("##### Associe as colunas do seu ficheiro aos campos do PDF:")
                        user_mapping = {}
                        for field in sorted(pdf_fields):
                            suggestion = find_best_match(field, df_cols)
                            suggestion_index = df_cols.index(suggestion) if suggestion in df_cols else 0
                            user_mapping[field] = st.selectbox(f"Campo do PDF: `{field}`", df_cols, index=suggestion_index, key=f"map_{field}")
                        if st.form_submit_button("Salvar Mapeamento", type="primary"):
                            st.session_state.mapeamento_pdf = user_mapping
                            st.success("Mapeamento salvo com sucesso!")

    with tab3:
        st.header("Gerar Documentos Finais")
        if 'dados_carregados' not in st.session_state: st.warning("Carregue um ficheiro de dados na Aba 1.")
        elif 'mapeamento_pdf' not in st.session_state: st.warning("Carregue e mapeie o modelo PDF na Aba 2.")
        else:
            df_final = st.session_state['dados_carregados']
            st.dataframe(df_final)
            if st.button(f"Gerar PDF para os {len(df_final)} registros", type="primary", use_container_width=True):
                if df_final.empty: st.error("A tabela de dados está vazia.")
                else:
                    # --- BLOCO DE GERAÇÃO COM DIAGNÓSTICOS ---
                    progress_bar = st.progress(0.0)
                    status_text = st.empty()
                    total_records = len(df_final)
                    
                    try:
                        template_bytes = st.session_state.pdf_template_bytes
                        mapping = st.session_state.mapeamento_pdf
                        
                        filled_pdfs = []
                        # Usar enumerate para ter um contador (i)
                        for i, (index, row) in enumerate(df_final.iterrows()):
                            # Pega o nome do aluno da coluna 'NOME COMPLETO' para exibir o status
                            aluno_nome = row.get('NOME COMPLETO', f'Registro #{i+1}')
                            status_text.info(f"⚙️ Processando: {aluno_nome} ({i + 1}/{total_records})")
                            
                            # A chamada para a função de preenchimento permanece a mesma
                            filled_pdf_buffer = fill_pdf_form(template_bytes, row, mapping)
                            filled_pdfs.append(filled_pdf_buffer)
                            
                            # Atualiza a barra de progresso
                            progress_bar.progress((i + 1) / total_records)

                        status_text.info("🔄 Juntando os PDFs...")
                        if filled_pdfs:
                            st.session_state.pdf_final_bytes = merge_pdfs(filled_pdfs).getvalue()
                            status_text.success("✅ Documento consolidado gerado com sucesso!")
                            st.balloons()
                        else:
                            status_text.error("Nenhum PDF pôde ser gerado. Verifique os logs de erro.")
                    except Exception as e:
                        status_text.error(f"Erro na geração dos PDFs: {e}")
                        st.error(traceback.format_exc())

            if 'pdf_final_bytes' in st.session_state:
                nome_arquivo_final = st.session_state.get('nome_ficheiro', 'Consolidado').split('.')[0]
                st.download_button(label="✅ Baixar Documento Consolidado (.pdf)", data=st.session_state.pdf_final_bytes, file_name=f"Documentos_{nome_arquivo_final}.pdf", mime="application/pdf")

if __name__ == "__main__":
    show_auxilio_transporte()
