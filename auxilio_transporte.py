import streamlit as st
import pandas as pd
from io import BytesIO

# Importando as funções de conexão do seu projeto
from config import init_supabase_client
from acoes import load_data

# --- Bloco de Funções Essenciais ---

def calcular_auxilio_transporte(linha):
    # Sua função de cálculo principal (sem alterações)
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

def validate_and_map_dataframe(df, required_columns, table_name):
    """
    Verifica se um DataFrame contém as colunas necessárias. Se não, pede ao usuário para mapeá-las.
    Retorna o DataFrame corrigido ou o original se tudo estiver OK. Retorna None se o mapeamento estiver pendente.
    """
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if not missing_cols:
        return df # Tudo certo, retorna o dataframe original

    st.warning(f"Na tabela '{table_name}', as seguintes colunas essenciais não foram encontradas: `{', '.join(missing_cols)}`")
    st.info("Por favor, mapeie as colunas em falta para as colunas existentes na sua tabela ou escolha deixar o campo vazio.")

    user_mapping = {}
    cols_para_mapear = st.columns(len(missing_cols))
    
    options = ['-- Deixar Vazio --'] + df.columns.tolist()

    for i, col_name in enumerate(missing_cols):
        user_mapping[col_name] = cols_para_mapear[i].selectbox(
            f"Mapear coluna '{col_name}':", 
            options=options,
            key=f"map_{table_name}_{col_name}"
        )
    
    if st.button(f"Aplicar Mapeamento para a Tabela '{table_name}'"):
        df_corrigido = df.copy()
        for system_col, user_col in user_mapping.items():
            if user_col != '-- Deixar Vazio --':
                df_corrigido[system_col] = df_corrigido[user_col]
            else:
                df_corrigido[system_col] = None # Deixa a coluna vazia (nula)
        st.success(f"Mapeamento aplicado para '{table_name}'!")
        return df_corrigido
    
    return None # Retorna None para indicar que a validação está pendente

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Gestão de Auxílio Transporte")
    st.markdown("---")
    
    NOME_TABELA_TRANSPORTE = "auxilio_transporte_dados"
    NOME_TABELA_ALUNOS = "Alunos"
    NOME_TABELA_SOLDOS = "soldos"
    
    try:
        # Carregamento inicial dos dados
        df_transporte_raw = load_data(NOME_TABELA_TRANSPORTE)
        df_alunos_raw = load_data(NOME_TABELA_ALUNOS)
        df_soldos_raw = load_data(NOME_TABELA_SOLDOS)

        # Validação e Mapeamento Interativo
        required_cols_transporte = ['numero_interno', 'ano_referencia']
        required_cols_alunos = ['numero_interno', 'nome_completo', 'graduacao']
        required_cols_soldos = ['graduacao', 'soldo']

        df_transporte = validate_and_map_dataframe(df_transporte_raw, required_cols_transporte, NOME_TABELA_TRANSPORTE)
        df_alunos = validate_and_map_dataframe(df_alunos_raw, required_cols_alunos, NOME_TABELA_ALUNOS)
        df_soldos = validate_and_map_dataframe(df_soldos_raw, required_cols_soldos, NOME_TABELA_SOLDOS)

        # Se algum mapeamento estiver pendente, a aplicação aguarda a ação do usuário
        if df_transporte is None or df_alunos is None or df_soldos is None:
            st.warning("Aguardando a conclusão do mapeamento de colunas...")
            st.stop()

        # Se chegou aqui, todos os dataframes estão validados e prontos para a junção
        with st.spinner("Unindo os dados..."):
            # A lógica de junção que já tínhamos, agora com os dataframes validados
            df_transporte['numero_interno'] = df_transporte['numero_interno'].astype(str).str.strip()
            df_alunos['numero_interno'] = df_alunos['numero_interno'].astype(str).str.strip()
            df_alunos['graduacao'] = df_alunos['graduacao'].astype(str).str.strip()
            df_soldos['graduacao'] = df_soldos['graduacao'].astype(str).str.strip()

            df_com_aluno = pd.merge(df_transporte, df_alunos[['numero_interno', 'nome_completo', 'graduacao']], on='numero_interno', how='left')
            df_completo = pd.merge(df_com_aluno, df_soldos[['graduacao', 'soldo']], on='graduacao', how='left')
            df_completo['soldo'].fillna(0, inplace=True)
            df_completo['nome_completo'].fillna("ALUNO NÃO ENCONTRADO", inplace=True)
            st.session_state['dados_transporte_completos'] = df_completo

    except Exception as e:
        st.error(f"Ocorreu um erro crítico durante o carregamento. Verifique se as tabelas existem. Erro: {e}")
        st.stop()

    tab1, tab2 = st.tabs(["1. Consultar, Filtrar e Editar", "2. Gerar Documentos"])

    with tab1:
        st.subheader("Consultar e Editar Dados de Transporte")
        df_para_mostrar = st.session_state['dados_transporte_completos'].copy()

        # Filtros (funcionam da mesma forma)
        # ... (código dos filtros aqui) ...

        st.markdown("##### Tabela de Dados")
        st.info("As colunas 'Nome Completo' e 'Soldo' são carregadas dinamicamente e não são editáveis aqui.")
        
        # Colunas que não devem ser editadas pelo usuário nesta tela
        colunas_desabilitadas = ['nome_completo', 'graduacao', 'soldo']
        
        df_editado = st.data_editor(df_para_mostrar, disabled=colunas_desabilitadas, use_container_width=True, key="editor_transporte", hide_index=True)

        if st.button("Salvar Alterações", type="primary"):
            with st.spinner("Salvando..."):
                try:
                    # Antes de salvar, removemos as colunas que vieram de outras tabelas ('Alunos', 'soldos')
                    colunas_para_remover = ['nome_completo', 'graduacao', 'soldo']
                    df_para_salvar = pd.DataFrame(df_editado).drop(columns=colunas_para_remover, errors='ignore')

                    supabase.table(NOME_TABELA_TRANSPORTE).upsert(
                        df_para_salvar.to_dict(orient='records'),
                        on_conflict='numero_interno,ano_referencia' # Chave para identificar o registro
                    ).execute()
                    st.success("Alterações salvas com sucesso!")
                    load_data.clear()
                    del st.session_state['dados_transporte_completos']
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar as alterações: {e}")



    with tab2:
        st.subheader("Gerar Documentos em PDF")
        st.info("Esta aba usará os dados salvos no banco de dados para gerar os documentos.")
        
        # Filtra os dados com base na seleção da primeira aba
        df_para_gerar = df_para_mostrar.copy()
        
        if df_para_gerar.empty:
            st.warning("Nenhum dado selecionado para gerar documentos. Use os filtros na aba anterior.")
        else:
            with st.spinner("Calculando valores para os documentos..."):
                calculos_df = df_para_gerar.apply(calcular_auxilio_transporte, axis=1)
                df_com_calculo = pd.concat([df_para_gerar.reset_index(drop=True), calculos_df.reset_index(drop=True)], axis=1)
            
            st.markdown(f"**{len(df_com_calculo)} registos selecionados para geração:**")
            st.dataframe(df_com_calculo)

            if st.button(f"Gerar PDF para os {len(df_com_calculo)} registos exibidos", type="primary"):
                st.info("Lógica de geração de PDF a ser conectada aqui.")
                # Aqui entraria a sua lógica para chamar as funções de mapeamento e geração de PDF.
