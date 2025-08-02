import streamlit as st
import pandas as pd
from io import BytesIO

# Importando as funções de conexão do seu projeto
from config import init_supabase_client
from acoes import load_data

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
    st.header("🚌 Gestão de Auxílio Transporte")
    st.markdown("---")
    
    NOME_TABELA_TRANSPORTE = "auxilio_transporte_dados"
    NOME_TABELA_ALUNOS = "Alunos"
    NOME_TABELA_SOLDOS = "soldos"

    try:
        supabase = init_supabase_client()
        with st.spinner("Carregando e unindo os dados..."):
            # 1. Carrega as três tabelas necessárias do Supabase
            df_transporte = load_data(NOME_TABELA_TRANSPORTE)
            df_alunos = load_data(NOME_TABELA_ALUNOS)
            df_soldos = load_data(NOME_TABELA_SOLDOS)

            # --- LÓGICA DE JUNÇÃO CORRIGIDA ---
            
            # 2. Padroniza as chaves de junção para evitar erros de tipo ou espaçamento
            df_transporte['numero_interno'] = df_transporte['numero_interno'].astype(str).str.strip()
            df_alunos['numero_interno'] = df_alunos['numero_interno'].astype(str).str.strip()
            df_alunos['graduacao'] = df_alunos['graduacao'].astype(str).str.strip()
            df_soldos['graduacao'] = df_soldos['graduacao'].astype(str).str.strip()

            # 3. Junta TRANSPORTE com ALUNOS para buscar 'nome_completo' e 'graduacao'
            # Usamos how='left' para manter todos os registros de transporte, mesmo que um aluno seja removido da tabela de alunos.
            df_com_aluno = pd.merge(
                df_transporte,
                df_alunos[['numero_interno', 'nome_completo', 'graduacao']],
                on='numero_interno',
                how='left'
            )
            
            # 4. Junta o resultado com SOLDOS para buscar o 'soldo' atualizado
            df_completo = pd.merge(
                df_com_aluno,
                df_soldos[['graduacao', 'soldo']],
                on='graduacao',
                how='left'
            )

            # 5. Trata dados que possam ter ficado nulos após as junções
            df_completo['soldo'].fillna(0, inplace=True)
            df_completo['nome_completo'].fillna("ALUNO NÃO ENCONTRADO", inplace=True)

            # Armazena o resultado final na sessão
            st.session_state['dados_transporte_completos'] = df_completo
            
        st.success(f"{len(df_completo)} registos carregados e processados.")
    except Exception as e:
        st.error(f"Não foi possível carregar os dados. Verifique se as tabelas '{NOME_TABELA_TRANSPORTE}', '{NOME_TABELA_ALUNOS}' e '{NOME_TABELA_SOLDOS}' existem e contêm os dados corretos. Erro: {e}")
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
