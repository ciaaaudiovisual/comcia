import streamlit as st
import pandas as pd
from io import BytesIO
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader



def calcular_auxilio_transporte(linha):
    # Função de cálculo (sem alterações)
    try:
        despesa_diaria = 0
        for i in range(1, 6):
            ida_tarifa = linha.get(f'ida_{i}_tarifa', 0.0)
            volta_tarifa = linha.get(f'volta_{i}_tarifa', 0.0)
            despesa_diaria += float(ida_tarifa if ida_tarifa else 0.0)
            despesa_diaria += float(volta_tarifa if volta_tarifa else 0.0)
        dias_trabalhados = min(int(linha.get('dias_uteis', 0) or 0), 22)
        despesa_mensal = despesa_diaria * dias_trabalhados
        valor_soldo_bruto = linha.get('soldo') # O soldo virá da junção com a tabela do Supabase
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

    # A nova estrutura de abas
    tab1, tab2, tab3, tab4 = st.tabs([
        "1. Carregar Ficheiro de Dados", 
        "2. Gerenciar Tabela de Soldos", 
        "3. Mapeamento do PDF", 
        "4. Gerar Documentos"
    ])

    supabase = init_supabase_client()

    # --- ABA 1: CARREGAR E EDITAR ---
    with tab1:
        st.subheader("Carregar Ficheiro de Dados")

        # Mostra o ficheiro em memória e dá a opção de limpar
        if 'dados_em_memoria' in st.session_state:
            st.info(f"Ficheiro em memória: **{st.session_state['nome_ficheiro']}**")
            if st.button("🗑️ Limpar Ficheiro e Recomeçar"):
                for key in ['dados_em_memoria', 'nome_ficheiro', 'mapeamento_pdf', 'resultados_para_pdf']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV", type="csv")

        if uploaded_file:
            if st.button(f"Processar Ficheiro: {uploaded_file.name}", type="primary"):
                with st.spinner("Processando..."):
                    try:
                        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                        df_preparado = preparar_dataframe(df)
                        st.session_state['dados_em_memoria'] = df_preparado
                        st.session_state['nome_ficheiro'] = uploaded_file.name
                        st.success("Ficheiro processado! Pode editar os dados abaixo ou ir para as próximas abas.")
                    except Exception as e:
                        st.error(f"Erro ao ler ou preparar o ficheiro: {e}")

        # Lógica de edição que só aparece se um ficheiro estiver carregado
        if 'dados_em_memoria' in st.session_state:
            st.markdown("---")
            st.markdown("##### Tabela de Dados para Edição")
            st.info("As alterações feitas aqui são usadas nas outras abas. Para salvá-las permanentemente, baixe o CSV editado.")

            df_editado = st.data_editor(
                st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True
            )
            st.session_state['dados_em_memoria'] = df_editado # Atualiza a sessão com os dados editados

            csv_editado = df_editado.to_csv(index=False, sep=';').encode('latin-1')
            st.download_button(
                label="📥 Baixar CSV Editado", data=csv_editado,
                file_name=f"dados_editados_{st.session_state['nome_ficheiro']}"
            )
 --- ABA 2: GERENCIAR TABELA DE SOLDOS (NOVA FUNCIONALIDADE) ---
    with tab2:
        st.subheader("Gerenciar Tabela de Soldos no Banco de Dados")
        st.info("As alterações feitas aqui são salvas diretamente no Supabase e usadas para todos os cálculos.")
        try:
            soldos_df = load_data("soldos")
            
            # Remove colunas do sistema antes de mostrar ao usuário
            colunas_para_remover = ['id', 'created_at']
            soldos_display = soldos_df.drop(columns=colunas_para_remover, errors='ignore')
            
            colunas_config = {
                "graduacao": st.column_config.TextColumn("Graduação", required=True),
                "soldo": st.column_config.NumberColumn("Soldo (R$)", format="R$ %.2f", required=True)
            }
            
            # Editor para a tabela de soldos
            edited_soldos_df = st.data_editor(
                soldos_display,
                column_config=colunas_config,
                num_rows="dynamic",
                use_container_width=True
            )
            
            if st.button("Salvar Alterações nos Soldos", type="primary"):
                with st.spinner("Salvando..."):
                    # Usamos 'upsert' para atualizar ou inserir novos registros
                    supabase.table("soldos").upsert(
                        edited_soldos_df.to_dict(orient='records'),
                        on_conflict='graduacao' # 'graduacao' é a chave única
                    ).execute()
                    st.success("Tabela de soldos atualizada com sucesso!")
                    load_data.clear() # Limpa o cache para garantir que os dados sejam recarregados
                    st.rerun()

        except Exception as e:
            st.error(f"Erro ao carregar ou salvar a tabela de soldos: {e}")

   # --- ABA 2: MAPEAMENTO DO PDF ---
    with tab3:
        st.subheader("Mapear Campos do PDF para os Dados da Tabela")
    
        # Verifica se os dados da Aba 1 estão disponíveis na sessão
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue e processe um ficheiro na aba '1. Carregar e Editar Dados' primeiro.")
        else:
            st.info("Faça o upload do seu modelo PDF preenchível (.pdf). A aplicação irá ler os campos de formulário disponíveis.")
    
            # Uploader para o modelo PDF
            pdf_template_file = st.file_uploader(
                "Carregue o seu modelo PDF",
                type="pdf",
                key="pdf_mapper_uploader"
            )
    
            if pdf_template_file:
                try:
                    # Usa a biblioteca pypdf para ler os campos do formulário
                    reader = PdfReader(BytesIO(pdf_template_file.getvalue()))
                    pdf_fields = list(reader.get_form_text_fields().keys())
    
                    if not pdf_fields:
                        st.warning("Atenção: Nenhum campo de formulário editável foi encontrado neste PDF. Verifique se o seu ficheiro é um formulário preenchível.")
                    else:
                        st.success(f"{len(pdf_fields)} campos de formulário encontrados no PDF.")
    
                        # Prepara a lista de colunas disponíveis para o mapeamento
                        # Inclui as colunas originais e as que serão calculadas posteriormente
                        df_cols = st.session_state['dados_em_memoria'].columns.tolist()
                        calculated_cols = ['despesa_diaria', 'despesa_mensal_total', 'parcela_descontada_6_porcento', 'auxilio_transporte_pago']
                        all_system_columns = ["-- Não Mapear Este Campo --"] + sorted(df_cols + calculated_cols)
    
                        # Carrega um mapeamento já salvo na sessão, se houver
                        saved_mapping = st.session_state.get('mapeamento_pdf', {})
    
                        with st.form("pdf_mapping_form"):
                            st.markdown("##### Mapeie cada campo do PDF para uma coluna dos seus dados:")
                            user_mapping = {}
                            
                            # Cria uma caixa de seleção para cada campo do PDF
                            for field in sorted(pdf_fields):
                                # Lógica de "mapeamento inteligente" para sugerir a melhor opção
                                best_guess = saved_mapping.get(field, "-- Não Mapear Este Campo --")
                                if best_guess == "-- Não Mapear Este Campo --":
                                    field_simplified = field.lower().replace("_", "").replace(" ", "")
                                    for col in all_system_columns:
                                        col_simplified = col.lower().replace("_", "")
                                        if field_simplified == col_simplified:
                                            best_guess = col
                                            break
                                
                                index = all_system_columns.index(best_guess) if best_guess in all_system_columns else 0
    
                                user_mapping[field] = st.selectbox(
                                    f"Campo do PDF: `{field}`",
                                    options=all_system_columns,
                                    index=index
                                )
                            
                            submitted = st.form_submit_button("Salvar Mapeamento", type="primary")
                            if submitted:
                                # Salva o mapeamento e o ficheiro PDF na sessão para uso na próxima aba
                                st.session_state['mapeamento_pdf'] = user_mapping
                                st.session_state['pdf_template_bytes'] = pdf_template_file.getvalue()
                                st.success("Mapeamento salvo com sucesso! Já pode ir para a aba 'Gerar Documentos'.")
    
                except Exception as e:
                    st.error(f"Ocorreu um erro ao processar o ficheiro PDF: {e}")
#- ABA 4: GERAR DOCUMENTOS ---
    with tab4:
        st.subheader("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar Ficheiro de Dados'.")
        else:
            df_do_csv = st.session_state['dados_em_memoria'].copy()
            
            with st.spinner("Buscando soldos atualizados e juntando dados..."):
                # Carrega a tabela de soldos mais recente do Supabase
                df_soldos_atual = load_data("soldos")
                
                # Prepara as chaves para a junção
                df_do_csv['graduacao'] = df_do_csv['graduacao'].astype(str).str.strip()
                df_soldos_atual['graduacao'] = df_soldos_atual['graduacao'].astype(str).str.strip()

                # JUNÇÃO DINÂMICA: Adiciona o soldo aos dados do CSV
                df_completo = pd.merge(
                    df_do_csv,
                    df_soldos_atual[['graduacao', 'soldo']],
                    on='graduacao',
                    how='left'
                )
                df_completo['soldo'].fillna(0, inplace=True)

                # Aplica os cálculos ao DataFrame completo
                calculos_df = df_completo.apply(calcular_auxilio_transporte, axis=1)
                df_com_calculo = pd.concat([df_completo, calculos_df], axis=1)


            st.markdown("#### Filtro para Seleção")
            nomes_validos = df_com_calculo['nome_completo'].dropna().unique()
            opcoes_filtro = sorted(nomes_validos)
            selecionados = st.multiselect("Selecione por Nome Completo:", options=opcoes_filtro)
            
            df_para_gerar = df_com_calculo[df_com_calculo['nome_completo'].isin(selecionados)] if selecionados else df_com_calculo
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
