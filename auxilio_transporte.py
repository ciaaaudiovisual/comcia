import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
import re
from difflib import SequenceMatcher
# Se 'pdf_utils' for um ficheiro seu, certifique-se que ele está na mesma pasta.
# Caso contrário, pode ser necessário instalar uma biblioteca.
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader

# --- Configuração da Página ---
st.set_page_config(
    page_title="Gerador de PDF a partir de CSV",
    page_icon="📄",
    layout="wide"
)

# --- Funções Utilitárias ---

def create_excel_template():
    """Cria um template XLSX com colunas sugeridas para download."""
    colunas_template = [
        'NOME COMPLETO', 'POSTO/GRAD', 'NIP', 'NUMERO INTERNO', 'ENDEREÇO COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
        'SOLDO', 'DIAS UTEIS', 'DESPESA DIARIA',
        'EMPRESA IDA 1', 'TRAJETO IDA 1', 'TARIFA IDA 1', 
        'EMPRESA VOLTA 1', 'TRAJETO VOLTA 1', 'TARIFA VOLTA 1',
        # Adicione mais colunas conforme necessário
    ]
    df_template = pd.DataFrame(columns=colunas_template)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Modelo')
    return output.getvalue()

def clean_text(text):
    """Função auxiliar para limpar e normalizar nomes de colunas para comparação."""
    if not isinstance(text, str): return ""
    return re.sub(r'[^a-z0-9]', '', text.lower())

def guess_best_match(target_column, available_columns, threshold=0.6):
    """Encontra a melhor correspondência para uma coluna-alvo, usando um algoritmo de semelhança."""
    best_match = ""
    highest_score = 0.0
    clean_target = clean_text(target_column)

    for option in available_columns:
        if option == "-- Não Mapear --": continue
        clean_option = clean_text(option)
        score = SequenceMatcher(None, clean_target, clean_option).ratio()
        if score > highest_score:
            highest_score = score
            best_match = option
    
    if highest_score >= threshold:
        return best_match
    return ""

# --- Função Principal da Aplicação ---
def show_auxilio_transporte():
    st.title("📄 Gerador de Documentos a partir de ficheiro CSV")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["1. Carregar e Editar Dados", "2. Mapeamento do PDF", "3. Gerar Documentos"])

    with tab1:
        st.header("Carregar e Mapear Ficheiro de Dados")
        st.download_button("Baixar Modelo de Dados (.xlsx)", create_excel_template(), "modelo_dados.xlsx")
        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV", type="csv")
        
        if uploaded_file:
            try:
                df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', dtype=str).fillna('')
                colunas_do_csv = df_raw.columns.tolist()
                
                schema_sugerido = ['nome_completo', 'graduacao', 'nip', 'numero_interno', 'endereco', 'bairro', 'cidade', 'cep', 'tarifa_1_ida', 'tarifa_1_volta', 'soldo', 'dias']
                campos_para_mapear = sorted(list(set(schema_sugerido + colunas_do_csv)))

                with st.form("data_mapping_form"):
                    st.markdown("##### Mapeamento de Colunas")
                    st.info("Associe as colunas do seu ficheiro (direita) aos campos do sistema (esquerda). Para manter o nome original, mapeie para si mesmo.")
                    
                    mapeamento_usuario = {}
                    for campo in campos_para_mapear:
                        sugestao = guess_best_match(campo, colunas_do_csv) or (campo if campo in colunas_do_csv else "-- Não Mapear --")
                        opcoes = ["-- Não Mapear --"] + colunas_do_csv
                        index = opcoes.index(sugestao) if sugestao in opcoes else 0
                        mapeamento_usuario[campo] = st.selectbox(f"Campo do Sistema: **`{campo}`**", opcoes, index=index, key=f"map_{campo}")

                    if st.form_submit_button("Aplicar Mapeamento e Carregar Dados", type="primary"):
                        df_mapeado = pd.DataFrame({campo: df_raw[col_csv] for campo, col_csv in mapeamento_usuario.items() if col_csv != "-- Não Mapear --"})
                        if df_mapeado.empty:
                            st.error("Nenhuma coluna foi mapeada.")
                        else:
                            st.session_state['dados_em_memoria'], st.session_state['nome_ficheiro'] = df_mapeado, uploaded_file.name
                            st.success("Dados mapeados! Pode editar na tabela abaixo ou avançar.")
            except Exception as e:
                st.error(f"Erro ao ler o CSV: {e}")

        if 'dados_em_memoria' in st.session_state:
            st.subheader("Tabela de Dados para Edição")
            st.session_state['dados_em_memoria'] = st.data_editor(st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True)
            
    with tab2:
        st.header("Mapear Campos do PDF")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Carregue e mapeie um ficheiro na Aba 1.")
        else:
            pdf_template_file = st.file_uploader("Carregue o modelo PDF editável", type="pdf", key="pdf_mapper")
            if pdf_template_file:
                try:
                    reader = PdfReader(BytesIO(pdf_template_file.getvalue()))
                    pdf_fields = list(reader.get_form_text_fields().keys())
                    
                    if not pdf_fields:
                        st.warning("Nenhum campo de formulário editável encontrado neste PDF.")
                    else:
                        st.success(f"Encontrados {len(pdf_fields)} campos no PDF.")
                        df_cols = ["-- Não Mapear --"] + sorted(st.session_state['dados_em_memoria'].columns.tolist())
                        saved_mapping = st.session_state.get('mapeamento_pdf', {})

                        with st.form("pdf_mapping_form"):
                            user_mapping = {field: st.selectbox(f"Campo do PDF: `{field}`", df_cols, index=df_cols.index(saved_mapping.get(field) or guess_best_match(field, df_cols) or "-- Não Mapear --")) for field in sorted(pdf_fields)}
                            if st.form_submit_button("Salvar Mapeamento do PDF", type="primary"):
                                st.session_state.update({'mapeamento_pdf': user_mapping, 'pdf_template_bytes': pdf_template_file.getvalue()})
                                st.success("Mapeamento do PDF salvo!")
                except Exception as e:
                    st.error(f"Erro ao processar o PDF: {e}")

    with tab3:
        st.header("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Carregue e mapeie um ficheiro na Aba 1.")
        elif 'mapeamento_pdf' not in st.session_state:
            st.warning("Carregue e mapeie o modelo PDF na Aba 2.")
        else:
            df_final = st.session_state['dados_em_memoria'].copy()

            # Bloco de limpeza de formato de moeda
            colunas_tarifa = [col for col in df_final.columns if 'tarifa' in col.lower()]
            if colunas_tarifa:
                st.toast(f"Limpando formato de moeda das colunas: {', '.join(colunas_tarifa)}")
                for col in colunas_tarifa:
                    df_final[col] = df_final[col].astype(str).str.replace('R$', '', regex=False).str.strip().str.replace('.', '', regex=False).str.replace(',', '.', regex=False)

            df_para_gerar = df_final
            if 'nome_completo' in df_final.columns:
                st.subheader("Filtro para Geração")
                selecionados = st.multiselect("Selecione por Nome Completo:", sorted(list(df_final['nome_completo'].dropna().unique())))
                if selecionados:
                    df_para_gerar = df_final[df_final['nome_completo'].isin(selecionados)]
            
            st.dataframe(df_para_gerar)
                 
            if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                if not df_para_gerar.empty:
                    with st.spinner("Gerando PDFs..."):
                        try:
                            template_bytes, mapping = st.session_state['pdf_template_bytes'], st.session_state['mapeamento_pdf']
                            filled_pdfs = [fill_pdf_auxilio(template_bytes, row, mapping) for _, row in df_para_gerar.iterrows()]
                            st.session_state['pdf_final_bytes'] = merge_pdfs(filled_pdfs).getvalue()
                            st.success("Documento consolidado gerado com sucesso!")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Erro na geração dos PDFs: {e}")
                            st.error(traceback.format_exc())

            if 'pdf_final_bytes' in st.session_state:
                st.download_button("✅ Baixar Documento Consolidado (.pdf)", st.session_state['pdf_final_bytes'], f"Documentos_{st.session_state.get('nome_ficheiro', 'Consolidado')}.pdf", "application/pdf")

if __name__ == "__main__":
    run_app()
