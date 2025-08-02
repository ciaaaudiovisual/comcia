import streamlit as st
import pandas as pd
from io import BytesIO

# Importando as funções de conexão do seu projeto
from config import init_supabase_client
from acoes import load_data # Usando a função load_data que já existe

# --- Bloco de Funções Essenciais ---

def calcular_auxilio_transporte(linha):
    """Sua função de cálculo principal, que permanece a mesma."""
    try:
        despesa_diaria = 0
        for i in range(1, 6):
            ida_tarifa = linha.get(f'ida_{i}_tarifa', 0.0)
            volta_tarifa = linha.get(f'volta_{i}_tarifa', 0.0)
            despesa_diaria += float(ida_tarifa if ida_tarifa else 0.0)
            despesa_diaria += float(volta_tarifa if volta_tarifa else 0.0)
        dias_trabalhados = min(int(linha.get('dias_uteis', 0) or 0), 22)
        despesa_mensal = despesa_diaria * dias_trabalhados
        
        # O 'soldo' aqui virá da junção das tabelas
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

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Gestão de Auxílio Transporte")
    st.markdown("---")
    
    NOME_TABELA_TRANSPORTE = "auxilio_transporte_dados"
    NOME_TABELA_SOLDOS = "soldos"

    try:
        supabase = init_supabase_client()
        with st.spinner("Carregando dados..."):
            # Carrega os dados de transporte E os dados de soldos
            df_transporte = load_data(NOME_TABELA_TRANSPORTE)
            df_soldos = load_data(NOME_TABELA_SOLDOS)
            
            # --- LÓGICA DE JUNÇÃO DINÂMICA DO SOLDO ---
            # Padroniza as chaves de junção
            df_transporte['graduacao'] = df_transporte['graduacao'].astype(str).str.strip()
            df_soldos['graduacao'] = df_soldos['graduacao'].astype(str).str.strip()

            # Remove a coluna de 'soldo' antiga da tabela de transporte para evitar conflitos
            if 'soldo' in df_transporte.columns:
                df_transporte = df_transporte.drop(columns=['soldo'])

            # Junta as tabelas usando a 'graduacao' para buscar o soldo mais recente
            df_completo = pd.merge(
                df_transporte,
                df_soldos[['graduacao', 'soldo']], # Pega apenas as colunas necessárias de soldos
                on='graduacao',
                how='left' # 'left' para manter todos os militares mesmo que não encontre um soldo
            )
            df_completo['soldo'].fillna(0, inplace=True) # Se não encontrar soldo, assume 0

            st.session_state['dados_transporte_completos'] = df_completo
            
        st.success(f"{len(df_completo)} registos carregados e atualizados com os soldos mais recentes.")
    except Exception as e:
        st.error(f"Não foi possível carregar os dados. Erro: {e}")
        st.stop()

    tab1, tab2 = st.tabs(["1. Consultar, Filtrar e Editar", "2. Gerar Documentos"])

    with tab1:
        st.subheader("Consultar e Editar Dados")
        if df_original.empty:
            st.warning("Nenhum dado encontrado na tabela.")
            st.stop()

        df_para_mostrar = df_original.copy()

        # --- FUNCIONALIDADE DE FILTROS ---
        st.markdown("##### Filtros de Seleção")
        col1, col2 = st.columns(2)
        with col1:
            nomes_unicos = sorted(df_para_mostrar['nome_completo'].dropna().unique())
            nomes_selecionados = st.multiselect("Filtrar por Nome:", options=nomes_unicos)
        with col2:
            graduacoes_unicas = sorted(df_para_mostrar['graduacao'].dropna().unique())
            graduacoes_selecionadas = st.multiselect("Filtrar por Graduação:", options=graduacoes_unicas)

        if nomes_selecionados:
            df_para_mostrar = df_para_mostrar[df_para_mostrar['nome_completo'].isin(nomes_selecionados)]
        if graduacoes_selecionadas:
            df_para_mostrar = df_para_mostrar[df_para_mostrar['graduacao'].isin(graduacoes_selecionadas)]

        st.markdown("##### Tabela de Dados")
        st.info("Você pode editar os dados diretamente na tabela. Clique em 'Salvar Alterações' para persistir os dados.")

        colunas_para_remover = ['id', 'created_at']
        df_display = df_para_mostrar.drop(columns=colunas_para_remover, errors='ignore')
        
        # Editor de dados
        df_editado = st.data_editor(
            df_display,
            num_rows="dynamic",
            use_container_width=True,
            key="editor_transporte"
        )

        if st.button("Salvar Alterações no Banco de Dados", type="primary"):
            with st.spinner("Salvando..."):
                try:
                    # Chave de conflito atualizada para corresponder à nova estrutura da tabela
                    supabase.table(NOME_DA_TABELA).upsert(
                        df_editado.to_dict(orient='records'),
                        on_conflict='numero_interno,ano_referencia' 
                    ).execute()
                    st.success("Alterações salvas com sucesso!")
                    # Limpa o cache para recarregar os dados na próxima vez
                    del st.session_state['dados_transporte']
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
