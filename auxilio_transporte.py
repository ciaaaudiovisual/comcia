import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from auth import check_permission
from io import BytesIO

# --- Funções de Apoio ---

def create_excel_template():
    """Cria um modelo Excel em memória para o usuário baixar."""
    template_data = {
        'numero_interno': ['M-1-101'],
        'dias_uteis': [22],
        'ida_1_empresa': ['Exemplo'], 'ida_1_linha': ['100'], 'ida_1_tarifa': [4.50],
        'ida_2_empresa': [''], 'ida_2_linha': [''], 'ida_2_tarifa': [0.00],
        'ida_3_empresa': [''], 'ida_3_linha': [''], 'ida_3_tarifa': [0.00],
        'ida_4_empresa': [''], 'ida_4_linha': [''], 'ida_4_tarifa': [0.00],
        'volta_1_empresa': ['Exemplo'], 'volta_1_linha': ['100'], 'volta_1_tarifa': [4.50],
        'volta_2_empresa': [''], 'volta_2_linha': [''], 'volta_2_tarifa': [0.00],
        'volta_3_empresa': [''], 'volta_3_linha': [''], 'volta_3_tarifa': [0.00],
        'volta_4_empresa': [''], 'volta_4_linha': [''], 'volta_4_tarifa': [0.00],
        'texto_encarregado': ['Texto padrão.'],
        'endereco': ['Rua Exemplo, 123'],
        'bairro': ['Bairro Exemplo'],
        'cidade': ['Cidade Exemplo'],
        'cep': ['12345-678'],
        'despesa_diaria_informada': [9.00],
        'ano_do_curso': ['2025'],
        'departamento': ['Exemplo']
    }
    df = pd.DataFrame(template_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='AuxilioTransporte')
    return output.getvalue()

# --- Seções da UI ---

def gestao_soldos_tab(supabase):
    """Renderiza a aba para gerenciar os soldos."""
    st.subheader("Tabela de Soldos por Graduação")
    st.info("Edite, adicione ou remova graduações e soldos.")
    
    soldos_df = load_data("soldos")
    
    edited_df = st.data_editor(
        soldos_df, num_rows="dynamic", use_container_width=True, key="soldos_editor"
    )
    
    if st.button("Salvar Alterações nos Soldos"):
        try:
            records_to_upsert = edited_df.to_dict(orient='records')
            supabase.table("soldos").upsert(records_to_upsert, on_conflict='graduacao').execute()
            st.success("Tabela de soldos atualizada!")
            load_data.clear()
        except Exception as e:
            st.error(f"Erro ao salvar os soldos: {e}")

def gestao_decat_tab(supabase):
    """Renderiza a aba principal para visualização e edição dos dados do DeCAT."""
    st.subheader("Dados de Transporte Cadastrados")
    st.info("Visualize e edite os dados de transporte dos alunos que solicitaram o benefício.")

    alunos_df = load_data("Alunos")
    transporte_df = load_data("auxilio_transporte")

    if transporte_df.empty:
        st.warning("Nenhum dado de auxílio transporte cadastrado. Use a aba 'Importação em Massa'.")
        return

    transporte_df['aluno_id'] = transporte_df['aluno_id'].astype(str)
    alunos_df['id'] = alunos_df['id'].astype(str)
    
    display_df = pd.merge(
        transporte_df, 
        alunos_df[['id', 'numero_interno', 'nome_guerra']], 
        left_on='aluno_id', 
        right_on='id', 
        how='left'
    )
    
    colunas_info_aluno = ['numero_interno', 'nome_guerra']
    colunas_transporte = [col for col in transporte_df.columns if col not in ['id', 'aluno_id', 'created_at']]
    display_df = display_df[colunas_info_aluno + colunas_transporte]
    
    edited_df = st.data_editor(
        display_df,
        hide_index=True,
        use_container_width=True,
        key="transporte_editor",
        disabled=['numero_interno', 'nome_guerra'] 
    )

    if st.button("Salvar Alterações na Tabela"):
        with st.spinner("Salvando..."):
            try:
                edited_df_com_id = pd.merge(edited_df, alunos_df[['numero_interno', 'id']], on='numero_interno', how='left')
                edited_df_com_id.rename(columns={'id': 'aluno_id'}, inplace=True)
                
                colunas_para_remover = ['numero_interno', 'nome_guerra']
                records_to_upsert = edited_df_com_id.drop(columns=colunas_para_remover).to_dict(orient='records')

                supabase.table("auxilio_transporte").upsert(records_to_upsert, on_conflict='aluno_id').execute()
                st.success("Alterações salvas com sucesso!")
                load_data.clear()
            except Exception as e:
                st.error(f"Erro ao salvar alterações: {e}")

def importacao_massa_tab(supabase):
    """Renderiza a aba para importação de dados em massa, com lógica de mapeamento."""
    st.subheader("Importar Dados em Massa do Google Forms")
    st.info("O sistema associará os dados ao aluno usando a coluna 'NÚMERO INTERNO' do seu ficheiro.")
    
    excel_modelo_bytes = create_excel_template()
    st.download_button(
        label="Baixar Modelo de Preenchimento (.xlsx)",
        data=excel_modelo_bytes,
        file_name="modelo_auxilio_transporte.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    uploaded_file = st.file_uploader("Escolha o ficheiro CSV exportado do Google Forms", type=["csv"])
    
    if uploaded_file:
        try:
            df_import = pd.read_csv(uploaded_file, delimiter=';')

            # Mapeamento robusto dos nomes de coluna do seu CSV para a base de dados
            column_mapping = {
                'NÚMERO INTERNO (EX. Q-01-105 OU M-01-308)': 'numero_interno',
                'ENDEREÇO DOMICILIAR (EXATAMENTE IGUAL AO COMPROVANTE DE RESIDÊNCIA)': 'endereco',
                'BAIRRO': 'bairro',
                'CIDADE': 'cidade',
                'CEP': 'cep',
                'QUANTIDADE DE DIAS (4 OU 22)': 'dias_uteis',
                'DESPESA DIÁRIA (VALOR GASTO POR DIA, IDA E VOLTA)': 'despesa_diaria_informada',
                'ANO DO CURSO': 'ano_do_curso',
                'DEPARTAMENTO': 'departamento'
            }
            
            # Mapeamento dinâmico para itinerários, lidando com colunas duplicadas
            itinerario_cols = [col for col in df_import.columns if 'TRAJETO' in col or 'EMPRESA' in col or 'TARIFA' in col]
            
            # Ida (primeiras 4 ocorrências de cada tipo)
            for i in range(4):
                column_mapping[itinerario_cols[i*3 + 0]] = f'ida_{i+1}_linha'
                column_mapping[itinerario_cols[i*3 + 1]] = f'ida_{i+1}_empresa'
                column_mapping[itinerario_cols[i*3 + 2]] = f'ida_{i+1}_tarifa'
            # Volta (as 4 ocorrências seguintes)
            for i in range(4):
                column_mapping[itinerario_cols[12 + i*3 + 0]] = f'volta_{i+1}_linha'
                column_mapping[itinerario_cols[12 + i*3 + 1]] = f'volta_{i+1}_empresa'
                column_mapping[itinerario_cols[12 + i*3 + 2]] = f'volta_{i+1}_tarifa'

            df_import.rename(columns=column_mapping, inplace=True)

            alunos_df = load_data("Alunos")[['id', 'numero_interno']]
            alunos_df['numero_interno'] = alunos_df['numero_interno'].astype(str).str.strip().str.upper()
            df_import['numero_interno'] = df_import['numero_interno'].astype(str).str.strip().str.upper()

            df_to_upsert = pd.merge(df_import, alunos_df, on='numero_interno', how='inner')
            
            if df_to_upsert.empty:
                st.error("Nenhum 'NÚMERO INTERNO' do ficheiro corresponde a um aluno cadastrado.")
            else:
                df_to_upsert.rename(columns={'id': 'aluno_id'}, inplace=True)
                
                colunas_db = [col.name for col in supabase.table('auxilio_transporte').select('*').execute().data[0].keys()] if supabase.table('auxilio_transporte').select('*').execute().data else []
                df_final = df_to_upsert[[col for col in df_to_upsert.columns if col in colunas_db]]

                for col in df_final.columns:
                    if 'tarifa' in col or 'despesa_diaria' in col:
                        df_final[col] = df_final[col].astype(str).str.replace(',', '.').astype(float)

                records_to_upsert = df_final.to_dict(orient='records')

                st.subheader("Pré-visualização dos Dados a Importar")
                st.dataframe(df_final)

                if st.button("Confirmar Importação de Dados"):
                    with st.spinner("Importando..."):
                        supabase.table("auxilio_transporte").upsert(records_to_upsert, on_conflict='aluno_id').execute()
                        st.success(f"{len(records_to_upsert)} registros importados/atualizados!")
                        load_data.clear()
        except Exception as e:
            st.error(f"Erro ao processar o ficheiro: {e}")

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.title("🚌 Gestão de Auxílio Transporte (DeCAT)")

    # if not check_permission('acesso_pagina_auxilio_transporte'):
    #     st.error("Acesso negado."); return

    supabase = init_supabase_client()
    
    tab1, tab2, tab3 = st.tabs(["Gerenciar Dados", "Gerenciar Soldos", "Importação em Massa"])

    with tab1:
        gestao_decat_tab(supabase)
    with tab2:
        gestao_soldos_tab(supabase)
    with tab3:
        importacao_massa_tab(supabase)
