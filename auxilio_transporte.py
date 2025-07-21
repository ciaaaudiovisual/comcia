import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from auth import check_permission
from aluno_selection_components import render_alunos_filter_and_selection
from io import BytesIO

# --- Funções de Cálculo ---

def calcular_decat(transporte_data, soldo_valor):
    """Realiza todos os cálculos para o DeCAT com base nos dados fornecidos."""
    
    # Garante que os valores são numéricos, tratando nulos como zero.
    ida_1 = pd.to_numeric(transporte_data.get('ida_1_tarifa'), errors='coerce') or 0
    ida_2 = pd.to_numeric(transporte_data.get('ida_2_tarifa'), errors='coerce') or 0
    ida_3 = pd.to_numeric(transporte_data.get('ida_3_tarifa'), errors='coerce') or 0
    ida_4 = pd.to_numeric(transporte_data.get('ida_4_tarifa'), errors='coerce') or 0
    volta_1 = pd.to_numeric(transporte_data.get('volta_1_tarifa'), errors='coerce') or 0
    volta_2 = pd.to_numeric(transporte_data.get('volta_2_tarifa'), errors='coerce') or 0
    volta_3 = pd.to_numeric(transporte_data.get('volta_3_tarifa'), errors='coerce') or 0
    volta_4 = pd.to_numeric(transporte_data.get('volta_4_tarifa'), errors='coerce') or 0
    dias_uteis = pd.to_numeric(transporte_data.get('dias_uteis'), errors='coerce') or 0
    soldo = pd.to_numeric(soldo_valor, errors='coerce') or 0

    # Cálculos conforme as regras
    despesa_diaria = ida_1 + ida_2 + ida_3 + ida_4 + volta_1 + volta_2 + volta_3 + volta_4
    despesa_mensal = despesa_diaria * dias_uteis
    parcela_beneficiario = (soldo * 0.06 / 30) * dias_uteis if soldo > 0 else 0
    auxilio_pago = despesa_mensal - parcela_beneficiario
    
    # Garante que o auxílio não seja negativo
    auxilio_pago = max(0, auxilio_pago)

    return {
        "despesa_diaria": despesa_diaria,
        "despesa_mensal": despesa_mensal,
        "parcela_beneficiario": parcela_beneficiario,
        "auxilio_pago": auxilio_pago
    }

# --- NOVA FUNÇÃO: Criar modelo Excel ---
def create_excel_template():
    """Cria um modelo Excel em memória para o usuário baixar."""
    # Define as colunas do modelo. 'nip' é a chave para identificar o aluno.
    template_data = {
        'nip': ['12345678'],
        'dias_uteis': [22],
        'ida_1_empresa': ['Exemplo Empresa'], 'ida_1_linha': ['100'], 'ida_1_tarifa': [4.50],
        'ida_2_empresa': [''], 'ida_2_linha': [''], 'ida_2_tarifa': [0.00],
        'ida_3_empresa': [''], 'ida_3_linha': [''], 'ida_3_tarifa': [0.00],
        'ida_4_empresa': [''], 'ida_4_linha': [''], 'ida_4_tarifa': [0.00],
        'volta_1_empresa': ['Exemplo Empresa'], 'volta_1_linha': ['100'], 'volta_1_tarifa': [4.50],
        'volta_2_empresa': [''], 'volta_2_linha': [''], 'volta_2_tarifa': [0.00],
        'volta_3_empresa': [''], 'volta_3_linha': [''], 'volta_3_tarifa': [0.00],
        'volta_4_empresa': [''], 'volta_4_linha': [''], 'volta_4_tarifa': [0.00],
        'texto_encarregado': ['Texto padrão para o encarregado.']
    }
    df = pd.DataFrame(template_data)
    
    # Salva o DataFrame em um objeto de bytes na memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='AuxilioTransporte')
    
    return output.getvalue()

# --- Seções da UI ---

def gestao_soldos_tab(supabase):
    """Renderiza a aba para gerenciar os soldos."""
    st.subheader("Tabela de Soldos por Graduação")
    st.info("Atualize aqui os valores de soldo para cada graduação.")
    
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

def calculo_decat_tab(supabase):
    """Renderiza a aba principal para cálculo e gestão do DeCAT."""
    st.subheader("Cálculo e Preenchimento do DeCAT")

    alunos_df = load_data("Alunos")
    soldos_df = load_data("soldos")
    transporte_df = load_data("auxilio_transporte")

    st.markdown("##### 1. Selecione um Aluno")
    aluno_selecionado_df = render_alunos_filter_and_selection(
        key_suffix="decat_aluno_selector", include_full_name_search=True
    )

    if aluno_selecionado_df.empty or len(aluno_selecionado_df) > 1:
        st.info("Por favor, use os filtros para selecionar um único aluno.")
        return

    aluno_atual = aluno_selecionado_df.iloc[0]
    st.success(f"Aluno selecionado: **{aluno_atual['nome_guerra']} ({aluno_atual['numero_interno']})**")
    
    dados_transporte_atuais = {}
    if not transporte_df.empty:
        transporte_df['aluno_id'] = transporte_df['aluno_id'].astype(str)
        aluno_atual['id'] = str(aluno_atual['id'])
        dados_aluno_transporte = transporte_df[transporte_df['aluno_id'] == aluno_atual['id']]
        if not dados_aluno_transporte.empty:
            dados_transporte_atuais = dados_aluno_transporte.iloc[0].to_dict()

    soldo_valor = 0
    if not soldos_df.empty and 'graduacao' in aluno_atual and pd.notna(aluno_atual['graduacao']):
        soldo_info = soldos_df[soldos_df['graduacao'] == aluno_atual['graduacao']]
        if not soldo_info.empty:
            soldo_valor = soldo_info.iloc[0]['valor']
    
    st.divider()
    st.markdown("##### 2. Preencha os Dados do Transporte")

    with st.form("decat_form"):
        dias_uteis = st.number_input("Dias considerados", min_value=0, step=1, value=int(dados_transporte_atuais.get('dias_uteis', 22)))
        
        st.markdown("**Itinerário de Ida (Residência -> Trabalho)**")
        for i in range(1, 5):
            c1, c2, c3 = st.columns(3)
            globals()[f'ida_{i}_empresa'] = c1.text_input(f"Empresa {i}", value=dados_transporte_atuais.get(f'ida_{i}_empresa', ''))
            globals()[f'ida_{i}_linha'] = c2.text_input(f"Linha {i}", value=dados_transporte_atuais.get(f'ida_{i}_linha', ''))
            globals()[f'ida_{i}_tarifa'] = c3.number_input(f"Tarifa {i} (R$)", min_value=0.0, step=0.01, format="%.2f", value=float(dados_transporte_atuais.get(f'ida_{i}_tarifa', 0.0)))

        st.markdown("**Itinerário de Volta (Trabalho -> Residência)**")
        for i in range(1, 5):
            c1, c2, c3 = st.columns(3)
            globals()[f'volta_{i}_empresa'] = c1.text_input(f"Empresa {i} ", value=dados_transporte_atuais.get(f'volta_{i}_empresa', ''))
            globals()[f'volta_{i}_linha'] = c2.text_input(f"Linha {i} ", value=dados_transporte_atuais.get(f'volta_{i}_linha', ''))
            globals()[f'volta_{i}_tarifa'] = c3.number_input(f"Tarifa {i} (R$) ", min_value=0.0, step=0.01, format="%.2f", value=float(dados_transporte_atuais.get(f'volta_{i}_tarifa', 0.0)))

        st.markdown("##### 3. Textos Personalizados para Assinaturas")
        texto_encarregado = st.text_area("Texto para 'Encarregado do Militar'", value=dados_transporte_atuais.get('texto_encarregado', ''))

        if st.form_submit_button("Salvar e Calcular", type="primary"):
            dados_para_salvar = {"aluno_id": aluno_atual['id'], "dias_uteis": dias_uteis, "texto_encarregado": texto_encarregado}
            for i in range(1, 5):
                dados_para_salvar.update({
                    f'ida_{i}_empresa': globals()[f'ida_{i}_empresa'], f'ida_{i}_linha': globals()[f'ida_{i}_linha'], f'ida_{i}_tarifa': globals()[f'ida_{i}_tarifa'],
                    f'volta_{i}_empresa': globals()[f'volta_{i}_empresa'], f'volta_{i}_linha': globals()[f'volta_{i}_linha'], f'volta_{i}_tarifa': globals()[f'volta_{i}_tarifa']
                })
            
            try:
                supabase.table("auxilio_transporte").upsert(dados_para_salvar, on_conflict='aluno_id').execute()
                st.success("Dados de transporte salvos!")
                load_data.clear()
                st.session_state.calculos_decat = calcular_decat(dados_para_salvar, soldo_valor)
            except Exception as e:
                st.error(f"Erro ao salvar os dados: {e}")

    if 'calculos_decat' in st.session_state:
        st.divider()
        st.markdown("##### 4. Resultados do Cálculo")
        resultados = st.session_state.calculos_decat
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Despesa Diária", f"R$ {resultados['despesa_diaria']:.2f}")
        c2.metric("Despesa Mensal", f"R$ {resultados['despesa_mensal']:.2f}")
        c3.metric("Parcela Beneficiário (6%)", f"R$ {resultados['parcela_beneficiario']:.2f}")
        c4.metric("Auxílio a ser Pago", f"R$ {resultados['auxilio_pago']:.2f}", delta_color="off")
        del st.session_state.calculos_decat

def importacao_massa_tab(supabase):
    """Renderiza a aba para importação de dados em massa."""
    st.subheader("Importar Dados em Massa (CSV / Excel)")
    st.info("O ficheiro deve conter uma coluna 'nip' para identificar os alunos. O sistema irá ATUALIZAR os dados de transporte para os NIPs existentes e INSERIR para os novos.")
    
    # Botão para baixar o modelo
    excel_modelo_bytes = create_excel_template()
    st.download_button(
        label="Baixar Modelo de Importação (.xlsx)",
        data=excel_modelo_bytes,
        file_name="modelo_auxilio_transporte.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    uploaded_file = st.file_uploader("Escolha um ficheiro CSV ou Excel", type=["csv", "xlsx"])
    
    if uploaded_file:
        try:
            df_import = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
            
            alunos_df = load_data("Alunos")[['id', 'nip']]
            alunos_df['nip'] = alunos_df['nip'].astype(str)
            df_import['nip'] = df_import['nip'].astype(str)

            df_to_upsert = pd.merge(df_import, alunos_df, on='nip', how='inner')
            
            if df_to_upsert.empty:
                st.error("Nenhum NIP do ficheiro corresponde a um aluno cadastrado.")
            else:
                df_to_upsert.rename(columns={'id': 'aluno_id'}, inplace=True)
                df_to_upsert.drop(columns=['nip'], inplace=True)
                records_to_upsert = df_to_upsert.to_dict(orient='records')

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
    
    tab1, tab2, tab3 = st.tabs(["Cálculo do DeCAT", "Gerenciar Soldos", "Importação em Massa"])

    with tab1:
        calculo_decat_tab(supabase)
    with tab2:
        gestao_soldos_tab(supabase)
    with tab3:
        importacao_massa_tab(supabase)
