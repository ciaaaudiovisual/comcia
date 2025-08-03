import streamlit as st
import pandas as pd
from io import BytesIO
import traceback

# Importando as funções de conexão e de geração de PDF
from config import init_supabase_client
from acoes import load_data
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader

# --- Bloco de Funções Essenciais ---

def calcular_auxilio_transporte(linha):
    """Sua função de cálculo principal."""
    try:
        despesa_diaria = 0
        for i in range(1, 6):
            ida_tarifa = linha.get(f'ida_{i}_tarifa', 0.0)
            volta_tarifa = linha.get(f'volta_{i}_tarifa', 0.0)
            despesa_diaria += float(ida_tarifa if ida_tarifa else 0.0)
            despesa_diaria += float(volta_tarifa if volta_tarifa else 0.0)
        dias_trabalhados = min(int(linha.get('dias_uteis', 0) or 0), 22)
        despesa_mensal = despesa_diaria * dias_trabalhados
        valor_soldo_bruto = linha.get('soldo')
        try:
            soldo = float(valor_soldo_bruto)
        except (ValueError, TypeError):
            soldo = 0.0
        parcela_beneficiario = ((soldo * 0.06) / 30) * dias_trabalhados if soldo > 0 and dias_trabalhados > 0 else 0.0
        auxilio_pago = max(0.0, despesa_mensal - parcela_beneficiario)
        return pd.Series({
            'despesa_diaria': round(despesa_diaria, 2), 'dias_trabalhados': dias_trabalhados,
            'despesa_mensal_total': round(despesa_mensal, 2), 'parcela_descontada_6_porcento': round(parcela_beneficiario, 2),
            'auxilio_transporte_pago': round(auxilio_pago, 2)
        })
    except Exception as e:
        print(f"Erro no cálculo para NIP {linha.get('numero_interno', 'N/A')}: {e}")
        return pd.Series()

def preparar_dataframe(df):
    """Prepara o DataFrame do CSV, agora SEM a necessidade da coluna 'SOLDO'."""
    df_copy = df.iloc[:, 1:].copy()
    mapa_colunas = {
        'NÚMERO INTERNO DO ALUNO': 'numero_interno', 'NOME COMPLETO': 'nome_completo', 'POSTO/GRAD': 'graduacao',
        'DIAS ÚTEIS (MÁX 22)': 'dias_uteis', 'ANO DE REFERÊNCIA': 'ano_referencia',
        'ENDEREÇO COMPLETO': 'endereco', 'BAIRRO': 'bairro', 'CIDADE': 'cidade', 'CEP': 'cep'
    }
    for i in range(1, 6):
        for direcao in ["IDA", "VOLTA"]:
            mapa_colunas[f'{i}ª EMPRESA ({direcao})'] = f'{direcao.lower()}_{i}_empresa'
            mapa_colunas[f'{i}º TRAJETO ({direcao})'] = f'{direcao.lower()}_{i}_linha'
            mapa_colunas[f'{i}ª TARIFA ({direcao})'] = f'{direcao.lower()}_{i}_tarifa'
    df_copy.rename(columns=mapa_colunas, inplace=True, errors='ignore')
    for col in df_copy.select_dtypes(include=['object']).columns:
        df_copy[col] = df_copy[col].str.upper().str.strip()
    colunas_numericas = ['dias_uteis'] + [f'ida_{i}_tarifa' for i in range(1, 6)] + [f'volta_{i}_tarifa' for i in range(1, 6)]
    for col in colunas_numericas:
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col].astype(str).str.replace(',', '.'), errors='coerce')
    df_copy.fillna(0, inplace=True)
    return df_copy

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Gestão de Auxílio Transporte")
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs([
        "1. Carregar Ficheiro", 
        "2. Gerenciar Soldos", 
        "3. Mapeamento PDF", 
        "4. Gerar Documentos"
    ])

    supabase = init_supabase_client()

    with tab1:
        st.subheader("Carregar Ficheiro de Dados do Mês")
        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV", type="csv", key="aux_transp_uploader")
        
        if uploaded_file:
            if st.button(f"Processar Ficheiro: {uploaded_file.name}", type="primary"):
                with st.spinner("Processando..."):
                    try:
                        # Limpa dados antigos da sessão para garantir um novo processamento
                        if 'dados_do_csv' in st.session_state:
                            del st.session_state['dados_do_csv']

                        df_csv = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                        df_preparado = preparar_dataframe(df_csv)
                        st.session_state['dados_do_csv'] = df_preparado
                        st.session_state['nome_ficheiro'] = uploaded_file.name
                        st.success("Ficheiro processado! Vá para a aba 'Gerar Documentos' para ver os resultados com o soldo.")
                    except Exception as e:
                        st.error(f"Erro ao ler o ficheiro: {e}")
                        st.error(traceback.format_exc())

    with tab2:
        st.subheader("Gerenciar Tabela de Soldos")
        st.info("As alterações feitas aqui são salvas diretamente no Supabase.")
        try:
            soldos_df = load_data("soldos")
            colunas_para_remover = ['id', 'created_at']
            soldos_display = soldos_df.drop(columns=colunas_para_remover, errors='ignore')
            colunas_config = {
                "graduacao": st.column_config.TextColumn("Graduação", required=True),
                "soldo": st.column_config.NumberColumn("Soldo (R$)", format="R$ %.2f", required=True)
            }
            edited_soldos_df = st.data_editor(
                soldos_display, 
                column_config=colunas_config, 
                num_rows="dynamic", 
                use_container_width=True,
                key="soldos_editor"
            )
            if st.button("Salvar Alterações nos Soldos"):
                with st.spinner("Salvando..."):
                    supabase.table("soldos").upsert(
                        edited_soldos_df.to_dict(orient='records'),
                        on_conflict='graduacao'
                    ).execute()
                    st.success("Tabela de soldos atualizada!")
                    load_data.clear()
                    st.rerun()
        except Exception as e:
            st.error(f"Erro ao carregar ou salvar soldos: {e}")

    with tab3:
        st.subheader("Mapear Campos do PDF")
        if 'dados_do_csv' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar Ficheiro'.")
        else:
            st.info("Faça o upload do seu modelo PDF preenchível para mapear os campos.")
            pdf_template_file = st.file_uploader("Carregue o modelo PDF", type="pdf", key="pdf_mapper_uploader")

            if pdf_template_file:
                # O código de mapeamento iria aqui
                st.info("Funcionalidade de mapeamento a ser implementada aqui.")


    with tab4:
        st.subheader("Gerar Documentos Finais")
        if 'dados_do_csv' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar Ficheiro'.")
        else:
            df_do_csv = st.session_state['dados_do_csv'].copy()
            
            with st.spinner("Buscando soldos atualizados e juntando dados..."):
                df_soldos_atual = load_data("soldos")
                
                df_do_csv['graduacao'] = df_do_csv['graduacao'].astype(str).str.strip()
                df_soldos_atual['graduacao'] = df_soldos_atual['graduacao'].astype(str).str.strip()
                
                df_completo = pd.merge(df_do_csv, df_soldos_atual[['graduacao', 'soldo']], on='graduacao', how='left')
                df_completo['soldo'].fillna(0, inplace=True)
                
                calculos_df = df_completo.apply(calcular_auxilio_transporte, axis=1)
                df_com_calculo = pd.concat([df_completo, calculos_df], axis=1)

            st.markdown("#### Filtro para Seleção")
            st.info("Selecione os militares para gerar o documento. Deixe em branco para incluir todos.")
            
            nomes_validos = df_com_calculo['nome_completo'].dropna().unique()
            opcoes_filtro = sorted(nomes_validos)
            
            selecionados = st.multiselect("Selecione por Nome Completo:", options=opcoes_filtro)
            
            if selecionados:
                df_para_gerar = df_com_calculo[df_com_calculo['nome_completo'].isin(selecionados)]
            else:
                df_para_gerar = df_com_calculo

            st.dataframe(df_para_gerar)

            if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                with st.spinner("Gerando PDFs... Isso pode demorar um pouco."):
                    try:
                        template_bytes = st.session_state['pdf_template_bytes']
                        mapping = st.session_state['mapeamento_pdf']
                        
                        filled_pdfs = []
                        progress_bar = st.progress(0)
                        total_docs = len(df_para_gerar)

                        for i, (_, aluno_row) in enumerate(df_para_gerar.iterrows()):
                            # Preenche o PDF para o aluno atual
                            pdf_preenchido = fill_pdf_auxilio(template_bytes, aluno_row, mapping)
                            filled_pdfs.append(pdf_preenchido)
                            progress_bar.progress((i + 1) / total_docs, text=f"Gerando: {aluno_row['nome_completo']}")

                        # Junta todos os PDFs num único ficheiro
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
                        file_name="Declaracoes_Auxilio_Transporte.pdf",
                        mime="application/pdf"
                    )
