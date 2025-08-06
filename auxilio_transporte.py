import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
import re
from difflib import SequenceMatcher

# Importe as suas funções de geração de PDF a partir do ficheiro de utilitários
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader

# --- Bloco de Funções Essenciais ---

def create_excel_template():
    """Cria um template XLSX vazio com o cabeçalho correto para download."""
    colunas_template = [
        'Carimbo de data/hora', 'NÚMERO INTERNO DO ALUNO', 'NOME COMPLETO', 'POSTO/GRAD', 'SOLDO',
        'DIAS ÚTEIS (MÁX 22)', 'ANO DE REFERÊNCIA', 'ENDEREÇO COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
        '1ª EMPRESA (IDA)', '1º TRAJETO (IDA)', '1ª TARIFA (IDA)', '1ª EMPRESA (VOLTA)', '1º TRAJETO (VOLTA)', '1ª TARIFA (VOLTA)',
        '2ª EMPRESA (IDA)', '2º TRAJETO (IDA)', '2ª TARIFA (IDA)', '2ª EMPRESA (VOLTA)', '2º TRAJETO (VOLTA)', '2ª TARIFA (VOLTA)',
        '3ª EMPRESA (IDA)', '3º TRAJETO (IDA)', '3ª TARIFA (IDA)', '3ª EMPRESA (VOLTA)', '3º TRAJETO (VOLTA)', '3ª TARIFA (VOLTA)',
        '4ª EMPRESA (IDA)', '4º TRAJETO (IDA)', '4ª TARIFA (IDA)', '4ª EMPRESA (VOLTA)', '4º TRAJETO (VOLTA)', '4ª TARIFA (VOLTA)',
        '5ª EMPRESA (IDA)', '5º TRAJETO (IDA)', '5ª TARIFA (IDA)', '5ª EMPRESA (VOLTA)', '5º TRAJETO (VOLTA)', '5ª TARIFA (VOLTA)'
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

def preparar_dataframe(df):
    """Prepara o DataFrame do CSV com renomeação insensível a maiúsculas/minúsculas."""
    df_copy = df.iloc[:, 1:].copy()
    
    mapa_colunas_lower = {
        'numero interno do aluno': 'numero_interno', 'nome completo': 'nome_completo', 'posto/grad': 'graduacao',
        'soldo': 'soldo', 'dias úteis (máx 22)': 'dias_uteis', 'ano de referência': 'ano_referencia',
        'endereço completo': 'endereco', 'bairro': 'bairro', 'cidade': 'cidade', 'cep': 'cep'
    }
    for i in range(1, 6):
        for direcao in ["ida", "volta"]:
            mapa_colunas_lower[f'{i}ª empresa ({direcao})'] = f'{direcao}_{i}_empresa'
            mapa_colunas_lower[f'{i}º trajeto ({direcao})'] = f'{direcao}_{i}_linha'
            mapa_colunas_lower[f'{i}ª tarifa ({direcao})'] = f'{direcao}_{i}_tarifa'

    rename_map = {col_original: mapa_colunas_lower.get(col_original.lower().strip()) 
                  for col_original in df_copy.columns 
                  if mapa_colunas_lower.get(col_original.lower().strip())}

    df_copy.rename(columns=rename_map, inplace=True)
    
    for col in df_copy.select_dtypes(include=['object']).columns:
        df_copy[col] = df_copy[col].str.upper().str.strip()

    colunas_numericas = ['soldo', 'dias_uteis'] + [f'ida_{i}_tarifa' for i in range(1, 6)] + [f'volta_{i}_tarifa' for i in range(1, 6)]
    for col in colunas_numericas:
        if col in df_copy.columns:
            s = df_copy[col].astype(str).str.replace(r'[^\d,.]', '', regex=True).str.replace(',', '.')
            df_copy[col] = pd.to_numeric(s, errors='coerce')
    
    df_copy.fillna(0, inplace=True)
    return df_copy


def calcular_auxilio_transporte(linha):
    """Calcula os valores do auxílio transporte para uma única linha de dados."""
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
            'despesa_diaria': round(despesa_diaria, 2),
            'dias_trabalhados': dias_trabalhados,
            'despesa_mensal_total': round(despesa_mensal, 2),
            'parcela_descontada_6_porcento': round(parcela_beneficiario, 2),
            'auxilio_transporte_pago': round(auxilio_pago, 2)
        })
    except Exception as e:
        print(f"Erro no cálculo para NIP {linha.get('numero_interno', 'N/A')}: {e}")
        return pd.Series()
# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Gestão de Auxílio Transporte (Baseado em Ficheiro)")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["1. Carregar e Editar Dados", "2. Mapeamento PDF", "3. Gerar Documentos"])


    with tab1:
        st.subheader("Carregar e Mapear Ficheiro de Dados")
        st.info("Este assistente irá ajudá-lo a carregar e a mapear os dados do seu ficheiro CSV para o formato correto do sistema.")

        # --- Etapa 1: Upload do Ficheiro ---
        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV com todos os dados", type="csv")
        
        # --- Etapa 2: Mapeamento Interativo ---
        if uploaded_file:
            df_raw = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
            # Remove a primeira coluna de data/hora do Forms
            if "Carimbo de data/hora" in df_raw.columns:
                df_raw = df_raw.iloc[:, 1:]
            
            colunas_do_csv = df_raw.columns.tolist()
            
            # O "esquema" de colunas que o sistema precisa para os cálculos
            schema_essencial = {
                'numero_interno': 'obrigatório', 'nome_completo': 'obrigatório', 'graduacao': 'obrigatório',
                'soldo': 'obrigatório', 'dias_uteis': 'obrigatório', 'ano_referencia': 'opcional',
                'endereco': 'opcional', 'bairro': 'opcional', 'cidade': 'opcional', 'cep': 'opcional'
            }
            # Adiciona os campos de itinerário dinamicamente
            for i in range(1, 6):
                for t in ['empresa', 'linha', 'tarifa']:
                    schema_essencial[f'ida_{i}_{t}'] = 'opcional'
                    schema_essencial[f'volta_{i}_{t}'] = 'opcional'

            with st.form("data_mapping_form"):
                st.markdown("##### Mapeamento de Colunas de Dados")
                st.warning("Associe as colunas do seu ficheiro (à direita) com as colunas que o sistema necessita (à esquerda).")
                mapeamento_usuario = {}
                for col_sistema, tipo in schema_essencial.items():
                    melhor_sugestao = guess_best_match(col_sistema, colunas_do_csv)
                    opcoes = ["-- Ignorar esta coluna --"] + colunas_do_csv
                    index = opcoes.index(melhor_sugestao) if melhor_sugestao else 0
                    mapeamento_usuario[col_sistema] = st.selectbox(f"Campo do Sistema: **`{col_sistema}`** ({tipo})", options=opcoes, index=index)

                if st.form_submit_button("Aplicar Mapeamento e Processar", type="primary"):
                    df_mapeado = pd.DataFrame()
                    colunas_mapeadas = {}
                    
                    # Constrói o novo DataFrame com base no mapeamento
                    for col_sistema, col_csv in mapeamento_usuario.items():
                        if col_csv != "-- Ignorar esta coluna --":
                            df_mapeado[col_sistema] = df_raw[col_csv]
                    
                    # Validação final
                    colunas_obrigatorias_em_falta = [
                        cs for cs, tipo in schema_essencial.items() 
                        if tipo == 'obrigatório' and cs not in df_mapeado.columns
                    ]
                    
                    if colunas_obrigatorias_em_falta:
                        st.error(f"Erro: As seguintes colunas obrigatórias não foram mapeadas: **{', '.join(colunas_obrigatorias_em_falta)}**")
                    else:
                        # Limpeza final dos dados já mapeados
                        df_processado = preparar_dataframe(df_mapeado) # <--- CORREÇÃO APLICADA AQUI
                        st.session_state['dados_em_memoria'] = df_processado
                        st.session_state['nome_ficheiro'] = uploaded_file.name
                        st.success("Dados mapeados e processados com sucesso! Pode editar na tabela abaixo ou ir para as próximas abas.")
            
        if 'dados_em_memoria' in st.session_state:
            st.markdown("---")
            st.markdown("##### Tabela de Dados para Edição")
            df_editado = st.data_editor(st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True)
            st.session_state['dados_em_memoria'] = df_editado 
            
    with tab2:
        st.subheader("Mapear Campos do PDF para os Dados")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar e Editar Dados'.")
        else:
            pdf_template_file = st.file_uploader("Carregue o modelo PDF", type="pdf", key="pdf_mapper_uploader")
            if pdf_template_file:
                try:
                    reader = PdfReader(BytesIO(pdf_template_file.getvalue()))
                    pdf_fields = list(reader.get_form_text_fields().keys())
                    if not pdf_fields:
                        st.warning("Nenhum campo de formulário editável foi encontrado neste PDF.")
                    else:
                        st.success(f"{len(pdf_fields)} campos encontrados.")
                        df_cols = st.session_state['dados_em_memoria'].columns.tolist()
                        calculated_cols = ['despesa_diaria', 'despesa_mensal_total', 'parcela_descontada_6_porcento', 'auxilio_transporte_pago']
                        all_system_columns = ["-- Não Mapear --"] + sorted(df_cols + calculated_cols)
                        saved_mapping = st.session_state.get('mapeamento_pdf', {})

                        with st.form("pdf_mapping_form"):
                            user_mapping = {}
                            st.markdown("**Mapeie cada campo do PDF para uma coluna dos dados:**")
                            for field in sorted(pdf_fields):
                                best_guess = saved_mapping.get(field) or guess_best_match(field, all_system_columns) or "-- Não Mapear --"
                                index = all_system_columns.index(best_guess) if best_guess in all_system_columns else 0
                                user_mapping[field] = st.selectbox(f"Campo do PDF: `{field}`", options=all_system_columns, index=index)
                            
                            if st.form_submit_button("Salvar Mapeamento", type="primary"):
                                st.session_state['mapeamento_pdf'] = user_mapping
                                st.session_state['pdf_template_bytes'] = pdf_template_file.getvalue()
                                st.success("Mapeamento salvo!")
                except Exception as e:
                    st.error(f"Erro ao processar o PDF: {e}")
 

    with tab3:
        st.subheader("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar e Editar Dados'.")
        elif 'mapeamento_pdf' not in st.session_state or 'pdf_template_bytes' not in st.session_state:
            st.warning("Por favor, carregue o modelo PDF e salve o mapeamento na aba '2. Mapeamento PDF'.")
        else:
            df_final = st.session_state['dados_em_memoria'].copy()
            colunas_essenciais = ['nome_completo', 'numero_interno']
            colunas_em_falta = [col for col in colunas_essenciais if col not in df_final.columns]
            if colunas_em_falta:
                st.error(f"Erro: Colunas essenciais não foram encontradas: {', '.join(colunas_em_falta)}. Verifique o seu CSV.")
            else:
                with st.spinner("Calculando valores..."):
                    calculos_df = df_final.apply(calcular_auxilio_transporte, axis=1)
                    df_com_calculo = pd.concat([df_final, calculos_df], axis=1)
                
                st.markdown("#### Filtro para Seleção")
                nomes_validos = df_com_calculo['nome_completo'].dropna().unique()
                opcoes_filtro = sorted(nomes_validos)
                selecionados = st.multiselect("Selecione por Nome Completo:", options=opcoes_filtro)
                df_para_gerar = df_com_calculo[df_com_calculo['nome_completo'].isin(selecionados)] if selecionados else df_com_calculo
                st.dataframe(df_para_gerar)
                 
    
                if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                    with st.spinner("Gerando PDFs..."):
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
