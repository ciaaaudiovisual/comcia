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
        st.info("Carregue um ficheiro CSV e associe as suas colunas aos campos que o sistema utilizará para preencher o PDF.")
        
        st.download_button(
            label="Baixar Modelo de Dados (.xlsx)",
            data=create_excel_template(),
            file_name="modelo_dados.xlsx",
            mime="application/vnd.ms-excel"
        )

        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV com todos os dados", type="csv")
        
        if uploaded_file:
            try:
                df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', dtype=str).fillna('')
                colunas_do_csv = df_raw.columns.tolist()
                
                # Nomes de campos ideais/sugeridos para padronização.
                schema_sugerido = [
                    'nome_completo', 'graduacao', 'nip', 'numero_interno', 'endereco', 'bairro', 'cidade', 'cep',
                    'tarifa_1_ida', 'tarifa_1_volta', 'soldo', 'dias'
                ]

                # Combina as colunas sugeridas com as colunas reais do ficheiro.
                # Isto garante que NENHUMA coluna do seu CSV seja ignorada no mapeamento.
                campos_para_mapear = sorted(list(set(schema_sugerido + colunas_do_csv)))

                with st.form("data_mapping_form"):
                    st.markdown("##### Mapeamento de Colunas")
                    st.warning("Associe as colunas do seu ficheiro (à direita) com os campos do sistema (à esquerda).")
                    st.info("Para manter uma coluna do seu ficheiro com o nome original, simplesmente mapeie-a para ela mesma.")
                    
                    mapeamento_usuario = {}
                    for campo_sistema in campos_para_mapear:
                        melhor_sugestao = guess_best_match(campo_sistema, colunas_do_csv)
                        
                        if melhor_sugestao:
                            default_selection = melhor_sugestao
                        elif campo_sistema in colunas_do_csv:
                            default_selection = campo_sistema
                        else:
                            default_selection = "-- Não Mapear --"

                        opcoes = ["-- Não Mapear --"] + colunas_do_csv
                        index = opcoes.index(default_selection) if default_selection in opcoes else 0
                        mapeamento_usuario[campo_sistema] = st.selectbox(f"Campo do Sistema: **`{campo_sistema}`**", options=opcoes, index=index, key=f"map_{campo_sistema}")

                    if st.form_submit_button("Aplicar Mapeamento e Carregar Dados", type="primary"):
                        df_mapeado = pd.DataFrame()
                        
                        for campo_sistema, col_csv in mapeamento_usuario.items():
                            if col_csv != "-- Não Mapear --":
                                df_mapeado[campo_sistema] = df_raw[col_csv]
                        
                        if df_mapeado.empty:
                            st.error("Nenhuma coluna foi mapeada. Por favor, mapeie pelo menos uma coluna.")
                        else:
                            st.session_state['dados_em_memoria'] = df_mapeado
                            st.session_state['nome_ficheiro'] = uploaded_file.name
                            st.success("Dados mapeados com sucesso! Pode editar na tabela abaixo ou avançar para as próximas abas.")
            except Exception as e:
                st.error(f"Erro ao ler ou processar o ficheiro CSV: {e}")
                st.error(traceback.format_exc())

        if 'dados_em_memoria' in st.session_state:
            st.markdown("---")
            st.subheader("Tabela de Dados para Edição")
            st.info("Aqui pode fazer ajustes manuais nos dados antes de gerar os documentos.")
            df_editado = st.data_editor(st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True)
            st.session_state['dados_em_memoria'] = df_editado 
            
    with tab2:
        st.header("Mapear Campos do PDF")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue e mapeie um ficheiro na aba '1. Carregar e Editar Dados'.")
        else:
            pdf_template_file = st.file_uploader("Carregue o modelo PDF editável", type="pdf", key="pdf_mapper_uploader")
            
            if pdf_template_file:
                try:
                    reader = PdfReader(BytesIO(pdf_template_file.getvalue()))
                    pdf_fields = list(reader.get_form_text_fields().keys())
                    
                    if not pdf_fields:
                        st.warning("Nenhum campo de formulário editável foi encontrado neste PDF. Verifique se o PDF é um formulário.")
                    else:
                        st.success(f"Encontrados {len(pdf_fields)} campos no PDF.")
                        
                        df_cols = st.session_state['dados_em_memoria'].columns.tolist()
                        all_system_columns = ["-- Não Mapear --"] + sorted(df_cols)
                        saved_mapping = st.session_state.get('mapeamento_pdf', {})

                        with st.form("pdf_mapping_form"):
                            user_mapping = {}
                            st.markdown("**Mapeie cada campo do PDF para uma coluna dos seus dados:**")
                            
                            for field in sorted(pdf_fields):
                                best_guess = saved_mapping.get(field) or guess_best_match(field, all_system_columns) or "-- Não Mapear --"
                                index = all_system_columns.index(best_guess) if best_guess in all_system_columns else 0
                                user_mapping[field] = st.selectbox(f"Campo do PDF: `{field}`", options=all_system_columns, index=index)
                            
                            if st.form_submit_button("Salvar Mapeamento do PDF", type="primary"):
                                st.session_state['mapeamento_pdf'] = user_mapping
                                st.session_state['pdf_template_bytes'] = pdf_template_file.getvalue()
                                st.success("Mapeamento do PDF salvo com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao processar o ficheiro PDF: {e}")
                    st.error(traceback.format_exc())

    with tab3:
        st.header("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue e mapeie um ficheiro na aba '1. Carregar e Editar Dados'.")
        elif 'mapeamento_pdf' not in st.session_state or 'pdf_template_bytes' not in st.session_state:
            st.warning("Por favor, carregue o modelo PDF e salve o mapeamento na aba '2. Mapeamento do PDF'.")
        else:
            df_final = st.session_state['dados_em_memoria'].copy()
            
            if 'nome_completo' not in df_final.columns:
                 st.info("Para usar o filtro por nome, mapeie uma coluna para o campo 'nome_completo' na Aba 1.")
                 df_para_gerar = df_final
                 st.dataframe(df_para_gerar)
            else:
                st.subheader("Filtro para Geração")
                nomes_validos = df_final['nome_completo'].dropna().unique()
                opcoes_filtro = sorted(list(nomes_validos))
                
                selecionados = st.multiselect("Selecione por Nome Completo para gerar (deixe em branco para todos):", options=opcoes_filtro)
                
                if selecionados:
                    df_para_gerar = df_final[df_final['nome_completo'].isin(selecionados)]
                else:
                    df_para_gerar = df_final
                
                st.dataframe(df_para_gerar)
                 
            if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                if df_para_gerar.empty:
                    st.warning("Nenhuma linha selecionada para gerar o PDF.")
                else:
                    with st.spinner("A preencher e a juntar os PDFs..."):
                        try:
                            template_bytes = st.session_state['pdf_template_bytes']
                            mapping = st.session_state['mapeamento_pdf']
                            filled_pdfs = []
                            progress_bar = st.progress(0)
                            
                            for i, row_data in enumerate(df_para_gerar.iterrows()):
                                pdf_preenchido = fill_pdf_auxilio(template_bytes, row_data, mapping)
                                filled_pdfs.append(pdf_preenchido)
                                nome_aluno = row_data.get('nome_completo', f'Linha {i+1}')
                                progress_bar.progress((i + 1) / len(df_para_gerar), text=f"Gerando: {nome_aluno}")
                            
                            final_pdf_buffer = merge_pdfs(filled_pdfs)
                            st.session_state['pdf_final_bytes'] = final_pdf_buffer.getvalue()
                            
                            progress_bar.empty()
                            st.success("Documento consolidado gerado com sucesso!")
                            st.balloons()

                        except NameError:
                            st.error("Erro: As funções 'fill_pdf_auxilio' e 'merge_pdfs' não foram encontradas. Verifique se o ficheiro 'pdf_utils.py' está correto e na mesma pasta da aplicação.")
                        except Exception as e:
                            st.error(f"Ocorreu um erro durante a geração dos PDFs: {e}")
                            st.error(traceback.format_exc())

            if 'pdf_final_bytes' in st.session_state:
                st.download_button(
                    label="✅ Baixar Documento Consolidado (.pdf)",
                    data=st.session_state['pdf_final_bytes'],
                    file_name=f"Documentos_{st.session_state.get('nome_ficheiro', 'Consolidado')}.pdf",
                    mime="application/pdf"
                )

# Ponto de entrada da aplicação
if __name__ == "__main__":
    run_app()
