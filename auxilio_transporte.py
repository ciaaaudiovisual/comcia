import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
from PyPDF2 import PdfReader, PdfWriter
# Importação necessária para a correção final do "flatten"
from PyPDF2.generic import NameObject
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
    """Extrai os nomes dos campos de formulário de um PDF."""
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        if reader.get_form_text_fields():
            return list(reader.get_form_text_fields().keys())
        return []
    except Exception as e:
        st.error(f"Erro ao ler os campos do PDF: {e}")
        return []

# --- FUNÇÃO DE PREENCHIMENTO DE PDF COM A CORREÇÃO DEFINITIVA ---
def fill_pdf_form(template_bytes: bytes, data_row: pd.Series, mapping: dict) -> BytesIO:
    """
    Preenche um formulário PDF para uma única linha de dados.
    Esta versão contém a correção final para os erros de atributo e visibilidade.
    """
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter()

    # 1. Copia as páginas do template para o novo ficheiro.
    # Isso garante que cada PDF gerado comece com uma cópia limpa.
    for page in reader.pages:
        writer.add_page(page)

    # 2. Preenche os campos do formulário com os dados da linha atual.
    fill_data = {}
    for pdf_field, csv_column in mapping.items():
        if csv_column != "-- Não Mapear --" and csv_column in data_row:
            value = str(data_row.get(csv_column, ''))
            fill_data[pdf_field] = value
    
    for page in writer.pages:
        try:
            writer.update_page_form_field_values(page=page, fields=fill_data)
        except Exception as e:
            st.warning(f"Aviso ao preencher a página: {e}")

    # 3. "Achata" os campos para que fiquem sempre visíveis.
    # Esta é a correção final para o 'AttributeError'.
    # Usamos NameObject("/Ff") ao invés de uma string.
    for page in writer.pages:
        if "/Annots" in page:
            for annot in page["/Annots"]:
                obj = annot.get_object()
                if obj.get("/T") and obj.get("/V"): # Se é um campo de formulário com valor
                    obj.update({
                        NameObject("/Ff"): 1 # Define o campo como "apenas leitura"
                    })

    # 4. Escreve o PDF finalizado no buffer de memória.
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer


def merge_pdfs(pdf_buffers: list) -> BytesIO:
    """Junta uma lista de PDFs (em BytesIO) em um único ficheiro."""
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
    """Normaliza o texto para comparação: minúsculas e apenas alfanuméricos."""
    if not isinstance(text, str):
        return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def find_best_match(target_field: str, available_columns: list, threshold=0.6) -> str:
    """Encontra a melhor correspondência para um campo alvo dentro de uma lista de colunas."""
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
                df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', dtype=str).fillna('') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file, dtype=str).fillna('')
                st.session_state['dados_carregados'], st.session_state['nome_ficheiro'] = df_raw, uploaded_file.name
                st.success(f"Ficheiro '{uploaded_file.name}' carregado com sucesso!")
            except Exception as e:
                st.error(f"Erro ao ler o ficheiro: {e}")
                if 'dados_carregados' in st.session_state: del st.session_state['dados_carregados']
        if 'dados_carregados' in st.session_state:
            st.subheader("Edite os dados se necessário")
            st.info("As alterações feitas aqui serão usadas na geração do documento.")
            st.session_state['dados_carregados'] = st.data_editor(st.session_state['dados_carregados'], num_rows="dynamic", use_container_width=True)

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
                    with st.spinner("Gerando documentos... Por favor, aguarde."):
                        try:
                            template_bytes, mapping = st.session_state.pdf_template_bytes, st.session_state.mapeamento_pdf
                            filled_pdfs = [fill_pdf_form(template_bytes, row, mapping) for _, row in df_final.iterrows()]
                            if filled_pdfs:
                                st.session_state.pdf_final_bytes = merge_pdfs(filled_pdfs).getvalue()
                                st.success("Documento consolidado gerado com sucesso!")
                                st.balloons()
                            else:
                                st.error("Nenhum PDF pôde ser gerado. Verifique os logs de erro.")
                        except Exception as e:
                            st.error(f"Erro na geração dos PDFs: {e}")
                            st.error(traceback.format_exc())
            if 'pdf_final_bytes' in st.session_state:
                nome_arquivo_final = st.session_state.get('nome_ficheiro', 'Consolidado').split('.')[0]
                st.download_button(label="✅ Baixar Documento Consolidado (.pdf)", data=st.session_state.pdf_final_bytes, file_name=f"Documentos_{nome_arquivo_final}.pdf", mime="application/pdf")

if __name__ == "__main__":
    show_auxilio_transporte()
