import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
import re
from difflib import SequenceMatcher

# Importe as suas funções de geração de PDF a partir do ficheiro de utilitários
# Certifique-se que este ficheiro 'pdf_utils.py' está na mesma pasta.
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader

# --- Bloco de Funções Utilitárias ---

def create_excel_template():
    """Cria um template XLSX com colunas sugeridas para download."""
    colunas_template = [
        'NÚMERO INTERNO', 'NOME COMPLETO', 'POSTO/GRAD', 'SOLDO',
        'DIAS ÚTEIS', 'ANO DE REFERÊNCIA', 'ENDEREÇO COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
        'EMPRESA IDA 1', 'TRAJETO IDA 1', 'TARIFA IDA 1', 'EMPRESA VOLTA 1', 'TRAJETO VOLTA 1', 'TARIFA VOLTA 1',
        'EMPRESA IDA 2', 'TRAJETO IDA 2', 'TARIFA IDA 2', 'EMPRESA VOLTA 2', 'TRAJETO VOLTA 2', 'TARIFA VOLTA 2',
        'EMPRESA IDA 3', 'TRAJETO IDA 3', 'TARIFA IDA 3', 'EMPRESA VOLTA 3', 'TRAJETO VOLTA 3', 'TARIFA VOLTA 3',
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


# --- Função Principal da Página ---
def show_gerador_pdf_app():
    st.header("📄 Gerador de Documentos a partir de CSV")
    st.markdown("---")

    # Definição das abas da aplicação
    tab1, tab2, tab3 = st.tabs(["1. Carregar e Editar Dados", "2. Mapeamento do PDF", "3. Gerar Documentos"])

    with tab1:
        st.subheader("Carregar e Mapear Ficheiro de Dados")
        st.info("Carregue um ficheiro CSV e associe as suas colunas aos campos que o sistema utilizará para preencher o PDF.")
        
        st.download_button(
            label="Baixar Modelo CSV (.xlsx)",
            data=create_excel_template(),
            file_name="modelo_dados.xlsx",
            mime="application/vnd.ms-excel"
        )

        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV com todos os dados", type="csv")
        
        if uploaded_file:
            try:
                # Ler o ficheiro CSV carregado
                df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin-1', dtype=str).fillna('')
                colunas_do_csv = df_raw.columns.tolist()
                
                # Define os campos padrão que o sistema pode esperar. Pode adaptar esta lista.
                schema_sugerido = [
                    'nome_completo', 'posto_grad', 'nip', 'numero_interno', 'endereco', 'bairro', 'cidade', 'cep',
                    'tarifa_ida_1', 'tarifa_volta_1', 'tarifa_ida_2', 'tarifa_volta_2', 
                    'soldo', 'dias_uteis', 'despesa_diaria' # Campos que podem vir prontos do CSV
                ]

                with st.form("data_mapping_form"):
                    st.markdown("##### Mapeamento de Colunas")
                    st.warning("Associe as colunas do seu ficheiro (à direita) com os campos do sistema (à esquerda).")
                    
                    mapeamento_usuario = {}
                    for campo_sistema in sorted(schema_sugerido):
                        melhor_sugestao = guess_best_match(campo_sistema, colunas_do_csv)
                        opcoes = ["-- Não Mapear --"] + colunas_do_csv
                        index = opcoes.index(melhor_sugestao) if melhor_sugestao else 0
                        mapeamento_usuario[campo_sistema] = st.selectbox(f"Campo do Sistema: **`{campo_sistema}`**", options=opcoes, index=index)

                    if st.form_submit_button("Aplicar Mapeamento", type="primary"):
                        df_mapeado = pd.DataFrame()
                        
                        # Constrói o novo DataFrame com base no mapeamento do utilizador
                        for campo_sistema, col_csv in mapeamento_usuario.items():
                            if col_csv != "-- Não Mapear --":
                                df_mapeado[campo_sistema] = df_raw[col_csv]
                        
                        if df_mapeado.empty:
                            st.error("Nenhuma coluna foi mapeada. Por favor, mapeie pelo menos uma coluna.")
                        else:
                            # Guarda os dados processados na sessão
                            st.session_state['dados_em_memoria'] = df_mapeado
                            st.session_state['nome_ficheiro'] = uploaded_file.name
                            st.success("Dados mapeados com sucesso! Pode editar na tabela abaixo ou avançar para as próximas abas.")
            except Exception as e:
                st.error(f"Erro ao ler o ficheiro CSV: {e}")
                st.error(traceback.format_exc())

        if 'dados_em_memoria' in st.session_state:
            st.markdown("---")
            st.markdown("##### Tabela de Dados para Edição")
            st.info("Aqui pode fazer ajustes manuais nos dados antes de gerar os documentos.")
            df_editado = st.data_editor(st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True)
            st.session_state['dados_em_memoria'] = df_editado 
            
    with tab2:
        st.subheader("Mapear Campos do PDF")
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
        st.subheader("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue e mapeie um ficheiro na aba '1. Carregar e Editar Dados'.")
        elif 'mapeamento_pdf' not in st.session_state or 'pdf_template_bytes' not in st.session_state:
            st.warning("Por favor, carregue o modelo PDF e salve o mapeamento na aba '2. Mapeamento do PDF'.")
        else:
            df_final = st.session_state['dados_em_memoria'].copy()
            
            if 'nome_completo' not in df_final.columns:
                st.error("Erro: A coluna 'nome_completo' não foi mapeada. Ela é necessária para o filtro de seleção.")
            else:
                st.markdown("#### Filtro para Geração")
                nomes_validos = df_final['nome_completo'].dropna().unique()
                opcoes_filtro = sorted(nomes_validos)
                
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
                                
                                for i, (_, row_data) in enumerate(df_para_gerar.iterrows()):
                                    # A função 'fill_pdf_auxilio' é chamada para preencher cada PDF
                                    pdf_preenchido = fill_pdf_auxilio(template_bytes, row_data, mapping)
                                    filled_pdfs.append(pdf_preenchido)
                                    progress_bar.progress((i + 1) / len(df_para_gerar), text=f"Gerando: {row_data.get('nome_completo', f'Linha {i+1}')}")
                                
                                # A função 'merge_pdfs' junta todos os PDFs preenchidos num único ficheiro
                                final_pdf_buffer = merge_pdfs(filled_pdfs)
                                st.session_state['pdf_final_bytes'] = final_pdf_buffer.getvalue()
                                
                                progress_bar.empty()
                                st.success("Documento consolidado gerado com sucesso!")
                                st.balloons()

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
    show_gerador_pdf_app()
