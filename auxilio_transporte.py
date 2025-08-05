import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
import re

# Importando as funções de conexão e de geração de PDF
from config import init_supabase_client
from acoes import load_data
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader

# --- Bloco de Funções Essenciais ---

def clean_text(text):
    """Função auxiliar para limpar e normalizar nomes de colunas para comparação."""
    # Remove acentos, caracteres especiais e espaços, e converte para minúsculas
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9]', '', text)
    return text

def apply_data_cleaning(df):
    """Aplica as conversões de tipo e formatação final ao DataFrame já mapeado."""
    df_copy = df.copy()
    for col in df_copy.select_dtypes(include=['object']).columns:
        df_copy[col] = df_copy[col].str.upper().str.strip()

    colunas_numericas = ['dias_uteis', 'soldo'] + [f'ida_{i}_tarifa' for i in range(1, 6)] + [f'volta_{i}_tarifa' for i in range(1, 6)]
    for col in colunas_numericas:
        if col in df_copy.columns:
            # Lógica de limpeza robusta para valores monetários
            df_copy[col] = df_copy[col].astype(str).str.replace('R$', '', regex=False).str.strip()
            df_copy[col] = pd.to_numeric(df_copy[col].str.replace(',', '.'), errors='coerce')
    
    df_copy.fillna(0, inplace=True)
    return df_copy
    
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

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1. Tabela Geral e Importação",
        "2. Edição Individual",
        "3. Gerenciar Soldos", 
        "4. Mapeamento PDF", 
        "5. Gerar Documentos"
    ])

    supabase = init_supabase_client()
    NOME_TABELA_TRANSPORTE = "auxilio_transporte_dados"
    NOME_TABELA_SOLDOS = "soldos"
    NOME_TABELA_ALUNOS = "Alunos"
    
    schema_esperado = [
        'numero_interno', 'nome_completo', 'graduacao', 'dias_uteis', 'ano_referencia',
        'endereco', 'bairro', 'cidade', 'cep'
    ] + [f'{d}_{i}_{t}' for i in range(1, 6) for d in ['ida', 'volta'] for t in ['empresa', 'linha', 'tarifa']]
    @st.cache_data(ttl=600)
    def carregar_dados_completos():
        df_transporte = load_data(NOME_TABELA_TRANSPORTE)
        df_soldos = load_data(NOME_TABELA_SOLDOS)
        
        # --- CORREÇÃO: VERIFICAÇÃO ROBUSTA DAS COLUNAS ---

        # Verifica se a tabela de transporte está vazia ou sem a coluna 'graduacao'
        if df_transporte.empty:
            return pd.DataFrame() # Retorna vazio se não houver dados de transporte
        if 'graduacao' not in df_transporte.columns:
             st.error(f"A sua tabela '{NOME_TABELA_TRANSPORTE}' no Supabase precisa de ter uma coluna chamada 'graduacao'.")
             return pd.DataFrame()

        # Verifica se a tabela de soldos está vazia ou sem as colunas necessárias
        if df_soldos.empty:
            st.warning(f"A tabela '{NOME_TABELA_SOLDOS}' está vazia. Não será possível associar os soldos.")
            df_soldos = pd.DataFrame(columns=['graduacao', 'soldo'])
        if 'graduacao' not in df_soldos.columns or 'soldo' not in df_soldos.columns:
            st.error(f"A sua tabela '{NOME_TABELA_SOLDOS}' no Supabase precisa de ter as colunas 'graduacao' e 'soldo'.")
            # Continua a execução, mas o soldo será 0
            df_soldos = pd.DataFrame(columns=['graduacao', 'soldo'])
        
        # Padronização e junção dos dados
        df_transporte['graduacao'] = df_transporte['graduacao'].astype(str).str.strip().str.upper()
        df_soldos['graduacao'] = df_soldos['graduacao'].astype(str).str.strip().str.upper()

        df_completo = pd.merge(df_transporte, df_soldos[['graduacao', 'soldo']], on='graduacao', how='left')
        df_completo['soldo'].fillna(0, inplace=True)
        return df_completo

    dados_completos_df = pd.DataFrame()
    try:
        dados_completos_df = carregar_dados_completos()
    except Exception as e:
        st.error(f"Erro ao carregar dados do Supabase: {e}")
    
    with tab1:
        st.subheader("Visualizar Dados e Importar Ficheiro CSV")
        
        with st.expander("Adicionar ou Atualizar em Massa via Ficheiro CSV"):
            uploaded_file = st.file_uploader("Carregue um ficheiro CSV", type="csv", key="csv_uploader_main")
            
            if uploaded_file:
                df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                colunas_do_csv = df_raw.columns.tolist()

                st.markdown("##### Mapeamento de Colunas")
                st.info("Verifique e corrija as associações entre as colunas do seu ficheiro e as colunas do sistema.")

                with st.form("mapping_form"):
                    mapeamento_usuario = {}
                    for col_sistema in schema_esperado:
                        melhor_sugestao = ""
                        clean_col_sistema = clean_text(col_sistema)
                        for col_csv in colunas_do_csv:
                            if clean_col_sistema in clean_text(col_csv):
                                melhor_sugestao = col_csv
                                break
                        
                        opcoes = ["-- Ignorar esta coluna --"] + colunas_do_csv
                        index = opcoes.index(melhor_sugestao) if melhor_sugestao in opcoes else 0
                        
                        mapeamento_usuario[col_sistema] = st.selectbox(f"Coluna do Sistema: `{col_sistema}`", options=opcoes, index=index)

                    if st.form_submit_button("1. Pré-visualizar Dados Mapeados"):
                        df_mapeado = pd.DataFrame()
                        mapeamento_inverso = {}
                        for col_sistema, col_csv in mapeamento_usuario.items():
                            if col_csv != "-- Ignorar esta coluna --":
                                # Evita que a mesma coluna do CSV seja usada para múltiplos campos do sistema
                                if col_csv in mapeamento_inverso:
                                    st.error(f"Erro: A coluna '{col_csv}' do seu ficheiro foi mapeada para mais de um campo do sistema ('{mapeamento_inverso[col_csv]}' e '{col_sistema}'). Por favor, corrija o mapeamento.")
                                    st.stop()
                                mapeamento_inverso[col_csv] = col_sistema
                                df_mapeado[col_sistema] = df_raw[col_csv]
                        
                        st.session_state['df_mapeado_para_salvar'] = df_mapeado
                        st.success("Mapeamento aplicado. Verifique a pré-visualização abaixo e clique no botão final para salvar.")

                if 'df_mapeado_para_salvar' in st.session_state:
                    st.markdown("##### Pré-visualização")
                    df_preview = st.session_state['df_mapeado_para_salvar']
                    st.dataframe(df_preview)

                    if st.button("2. Confirmar e Salvar no Banco de Dados", type="primary"):
                        if 'numero_interno' not in df_preview.columns:
                            st.error("Erro fatal: A coluna 'numero_interno' é obrigatória e não foi mapeada. Não é possível salvar.")
                        else:
                            with st.spinner("Processando e salvando..."):
                                try:
                                    # Aplica a limpeza final (maiúsculas, tipos numéricos, etc.)
                                    df_final_para_salvar = apply_data_cleaning(df_preview)
                                    
                                    supabase.table(NOME_TABELA_TRANSPORTE).upsert(
                                        df_final_para_salvar.to_dict(orient='records'),
                                        on_conflict='numero_interno,ano_referencia'
                                    ).execute()
                                    
                                    st.success(f"{len(df_final_para_salvar)} registos foram adicionados/atualizados!")
                                    del st.session_state['df_mapeado_para_salvar'] # Limpa a sessão
                                    load_data.clear()
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Erro ao salvar no Supabase: {e}")
                                    st.error(traceback.format_exc())

        st.markdown("---")
        st.subheader("Dados Atuais no Banco de Dados")
        try:
            dados_atuais = load_data(NOME_TABELA_TRANSPORTE)
            st.dataframe(dados_atuais)
        except Exception as e:
            st.error(f"Erro ao carregar dados existentes: {e}")


   
    with tab2:
        st.subheader("Editar Cadastro Individual")
        if dados_completos_df.empty:
            st.warning("Não há dados para editar.")
        else:
            alunos_df = load_data(NOME_TABELA_ALUNOS)
            modo = st.radio("Selecione a Ação:", ["Editar um Cadastro Existente", "Adicionar Novo Cadastro"], horizontal=True)
            dados_aluno = {}
            
            if modo == "Editar um Cadastro Existente":
                nomes_para_selecao = [""] + sorted(dados_completos_df['nome_completo'].unique())
                aluno_selecionado = st.selectbox("Selecione um militar para editar:", options=nomes_para_selecao, key="editar_aluno_select")
                if aluno_selecionado:
                    dados_aluno = dados_completos_df[dados_completos_df['nome_completo'] == aluno_selecionado].iloc[0].to_dict()
            else:
                st.info("Preencha os dados abaixo. Pode buscar um aluno da lista geral para preencher os dados básicos.")
                if not alunos_df.empty:
                    opcoes_alunos = [""] + sorted(alunos_df['nome_completo'].unique())
                    aluno_base = st.selectbox("Buscar dados de um aluno existente:", options=opcoes_alunos, key="adicionar_aluno_select")
                    if aluno_base:
                        dados_aluno = alunos_df[alunos_df['nome_completo'] == aluno_base].iloc[0].to_dict()

            if dados_aluno or modo == "Adicionar Novo Cadastro":
                with st.form("form_edicao_individual"):
                    # --- CORREÇÃO DE INDENTAÇÃO A PARTIR DAQUI ---
                    st.markdown("#### Dados Pessoais e de Referência")
                    c1, c2, c3 = st.columns(3)
                    
                    if modo == "Adicionar Novo Cadastro":
                        dados_aluno['numero_interno'] = c1.text_input("Número Interno (NIP)*", value=dados_aluno.get('numero_interno', ''))
                        dados_aluno['nome_completo'] = c2.text_input("Nome Completo*", value=dados_aluno.get('nome_completo', ''))
                        dados_aluno['graduacao'] = c3.text_input("Graduação*", value=dados_aluno.get('graduacao', ''))
                    else:
                        c1.text_input("Número Interno (NIP)", value=dados_aluno.get('numero_interno', ''), disabled=True)
                        c2.text_input("Nome Completo", value=dados_aluno.get('nome_completo', ''), disabled=True)
                        c3.text_input("Graduação", value=dados_aluno.get('graduacao', ''), disabled=True)
                    
                    dados_aluno['ano_referencia'] = st.number_input("Ano de Referência", value=int(dados_aluno.get('ano_referencia', 2025)))
           
                
                st.markdown("#### Endereço")
                c4, c5 = st.columns([3, 1])
                dados_aluno['endereco'] = c4.text_input("Endereço", value=dados_aluno.get('endereco', ''))
                dados_aluno['bairro'] = c5.text_input("Bairro", value=dados_aluno.get('bairro', ''))
                c6, c7 = st.columns(2)
                dados_aluno['cidade'] = c6.text_input("Cidade", value=dados_aluno.get('cidade', ''))
                dados_aluno['cep'] = c7.text_input("CEP", value=dados_aluno.get('cep', ''))
                
                st.markdown("#### Itinerários")
                dados_aluno['dias_uteis'] = st.number_input("Dias Úteis (máx 22)", min_value=0, max_value=22, value=int(dados_aluno.get('dias_uteis', 22)))
                
                for i in range(1, 6):
                    with st.expander(f"{i}º Trajeto"):
                        col_ida, col_volta = st.columns(2)
                        with col_ida:
                            st.markdown(f"**Ida {i}**")
                            dados_aluno[f'ida_{i}_empresa'] = st.text_input(f"Empresa Ida {i}", value=dados_aluno.get(f'ida_{i}_empresa', ''), key=f'ida_emp_{i}')
                            dados_aluno[f'ida_{i}_linha'] = st.text_input(f"Linha Ida {i}", value=dados_aluno.get(f'ida_{i}_linha', ''), key=f'ida_lin_{i}')
                            dados_aluno[f'ida_{i}_tarifa'] = st.number_input(f"Tarifa Ida {i}", min_value=0.0, value=float(dados_aluno.get(f'ida_{i}_tarifa', 0.0)), format="%.2f", key=f'ida_tar_{i}')
                        with col_volta:
                            st.markdown(f"**Volta {i}**")
                            dados_aluno[f'volta_{i}_empresa'] = st.text_input(f"Empresa Volta {i}", value=dados_aluno.get(f'volta_{i}_empresa', ''), key=f'vol_emp_{i}')
                            dados_aluno[f'volta_{i}_linha'] = st.text_input(f"Linha Volta {i}", value=dados_aluno.get(f'volta_{i}_linha', ''), key=f'vol_lin_{i}')
                            dados_aluno[f'volta_{i}_tarifa'] = st.number_input(f"Tarifa Volta {i}", min_value=0.0, value=float(dados_aluno.get(f'volta_{i}_tarifa', 0.0)), format="%.2f", key=f'vol_tar_{i}')

                # --- CAMPOS CALCULADOS (APENAS VISUALIZAÇÃO) ---
                st.markdown("---")
                st.markdown("#### Valores Calculados (Atualizados em tempo real)")
                # Para calcular, precisamos do soldo. Buscamos ele na tabela de soldos.
                soldos_df = load_data(NOME_TABELA_SOLDOS)
                soldo_do_aluno = 0.0
                if not soldos_df.empty and 'graduacao' in dados_aluno:
                    graduacao_upper = str(dados_aluno['graduacao']).upper().strip()
                    soldos_df['graduacao_upper'] = soldos_df['graduacao'].astype(str).str.upper().str.strip()
                    resultado_soldo = soldos_df[soldos_df['graduacao_upper'] == graduacao_upper]
                    if not resultado_soldo.empty:
                        soldo_do_aluno = resultado_soldo['soldo'].iloc[0]
                dados_aluno['soldo'] = soldo_do_aluno
                
                valores_calculados = calcular_auxilio_transporte(dados_aluno)
                c8, c9, c10, c11, c12 = st.columns(5)
                c8.metric("Soldo", f"R$ {dados_aluno.get('soldo', 0.0):,.2f}")
                c9.metric("Despesa Diária", f"R$ {valores_calculados.get('despesa_diaria', 0.0):,.2f}")
                c10.metric("Despesa Mensal", f"R$ {valores_calculados.get('despesa_mensal_total', 0.0):,.2f}")
                c11.metric("Desconto 6%", f"R$ {valores_calculados.get('parcela_descontada_6_porcento', 0.0):,.2f}")
                c12.metric("Valor a Receber", f"R$ {valores_calculados.get('auxilio_pago', 0.0):,.2f}")

                if st.form_submit_button("Salvar Dados", type="primary"):
                    if not dados_aluno.get('numero_interno') or not dados_aluno.get('nome_completo') or not dados_aluno.get('graduacao'):
                        st.error("Os campos 'Número Interno', 'Nome Completo' e 'Graduação' são obrigatórios.")
                    else:
                        with st.spinner("Salvando..."):
                            try:
                                # Prepara o dicionário para salvar, removendo campos que não pertencem a esta tabela
                                dados_para_salvar = dados_aluno.copy()
                                campos_a_remover = [
                                    'id', 'created_at', 'soldo', 'despesa_diaria', 'despesa_mensal_total', 
                                    'parcela_descontada_6_porcento', 'auxilio_pago', 'om', 'status', 'turma'
                                ]
                                for campo in campos_a_remover:
                                    dados_para_salvar.pop(campo, None)

                                supabase.table(NOME_TABELA_TRANSPORTE).upsert(
                                    dados_para_salvar,
                                    on_conflict='numero_interno,ano_referencia'
                                ).execute()
                                st.success(f"Dados salvos com sucesso!")
                                carregar_dados_completos.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")

    # --- ABA 3: GERENCIAR SOLDOS ---
    with tab3:
        st.subheader("Gerenciar Tabela de Soldos")
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
                    supabase.table(NOME_TABELA_SOLDOS).upsert(
                        edited_soldos_df.to_dict(orient='records'),
                        on_conflict='graduacao'
                    ).execute()
                    st.success("Tabela de soldos atualizada!")
                    load_data.clear() # Limpa o cache para garantir que os dados sejam recarregados
                    st.rerun()
        except Exception as e:
            st.error(f"Erro ao carregar ou salvar soldos: {e}")

    with tab4:
        st.subheader("Mapear Campos do PDF")
        if 'dados_do_csv' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar & Editar Ficheiro'.")
        else:
            st.info("Faça o upload do seu modelo PDF preenchível para mapear os campos.")
            pdf_template_file = st.file_uploader("Carregue o modelo PDF", type="pdf", key="pdf_mapper_uploader")

            if pdf_template_file:
                try:
                    reader = PdfReader(BytesIO(pdf_template_file.getvalue()))
                    pdf_fields = list(reader.get_form_text_fields().keys())

                    if not pdf_fields:
                        st.warning("Nenhum campo de formulário editável foi encontrado neste PDF.")
                    else:
                        st.success(f"{len(pdf_fields)} campos encontrados no PDF.")
                        df_cols = st.session_state['dados_do_csv'].columns.tolist()
                        calculated_cols = ['despesa_diaria', 'despesa_mensal_total', 'parcela_descontada_6_porcento', 'auxilio_transporte_pago']
                        all_system_columns = ["-- Não Mapear --"] + sorted(df_cols + calculated_cols)
                        saved_mapping = st.session_state.get('mapeamento_pdf', {})

                        with st.form("pdf_mapping_form"):
                            user_mapping = {}
                            st.markdown("**Mapeie cada campo do PDF para uma coluna dos dados:**")
                            for field in sorted(pdf_fields):
                                best_guess = saved_mapping.get(field, "-- Não Mapear --")
                                index = all_system_columns.index(best_guess) if best_guess in all_system_columns else 0
                                user_mapping[field] = st.selectbox(f"Campo do PDF: `{field}`", options=all_system_columns, index=index)
                            
                            if st.form_submit_button("Salvar Mapeamento", type="primary"):
                                st.session_state['mapeamento_pdf'] = user_mapping
                                st.session_state['pdf_template_bytes'] = pdf_template_file.getvalue()
                                st.success("Mapeamento salvo com sucesso! Já pode ir para a aba 'Gerar Documentos'.")
                except Exception as e:
                    st.error(f"Erro ao processar o PDF: {e}")


    with tab5:
        st.subheader("Gerar Documentos Finais")
        st.info("Esta aba agora pode usar tanto os dados do CSV carregado quanto os dados salvos no banco de dados.")

        # Opção para o utilizador escolher a fonte dos dados
        fonte_dados = st.radio(
            "Escolha a fonte de dados para gerar os PDFs:",
            ["Usar dados do ficheiro CSV carregado nesta sessão", "Usar dados permanentes do Banco de Dados"],
            horizontal=True
        )

        df_para_processar = None
        if fonte_dados == "Usar dados do ficheiro CSV carregado nesta sessão":
            if 'dados_do_csv' in st.session_state:
                df_para_processar = st.session_state['dados_do_csv'].copy()
            else:
                st.warning("Nenhum ficheiro CSV foi carregado nesta sessão. Por favor, carregue um ficheiro na Aba 1.")
        
        else: # Usar dados do Banco de Dados
            with st.spinner("Carregando dados do Supabase..."):
                df_para_processar = load_data(NOME_TABELA_TRANSPORTE)

        if df_para_processar is not None and not df_para_processar.empty:
            with st.spinner("Buscando soldos atualizados e juntando dados..."):
                # A lógica de junção e cálculo continua a mesma
                df_soldos_atual = load_data("soldos")
                df_para_processar['graduacao'] = df_para_processar['graduacao'].astype(str).str.strip()
                df_soldos_atual['graduacao'] = df_soldos_atual['graduacao'].astype(str).str.strip()
                df_completo = pd.merge(df_para_processar, df_soldos_atual[['graduacao', 'soldo']], on='graduacao', how='left')
                df_completo['soldo'].fillna(0, inplace=True)
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
                        
                        for i, (_, aluno_row) in enumerate(df_para_gerar.iterrows()):
                            pdf_preenchido = fill_pdf_auxilio(template_bytes, aluno_row, mapping)
                            filled_pdfs.append(pdf_preenchido)
                            progress_bar.progress((i + 1) / len(df_para_gerar), text=f"Gerando: {aluno_row['nome_completo']}")
                        
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
