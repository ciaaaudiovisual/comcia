import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from auth import check_permission
from aluno_selection_components import render_alunos_filter_and_selection
from io import BytesIO

# --- Funções de Apoio ---

def create_excel_template():
    """Cria um modelo Excel em memória para o usuário baixar, seguindo a ordem do CSV."""
    template_data = {
        'NÚMERO INTERNO (EX. Q-01-105 OU M-01-308)': ['M-1-101'],
        'ENDEREÇO DOMICILIAR (EXATAMENTE IGUAL AO COMPROVANTE DE RESIDÊNCIA)': ['Rua Exemplo, 123'],
        'BAIRRO': ['Bairro Exemplo'], 'CIDADE': ['Cidade Exemplo'], 'CEP': ['12345-678'],
        'QUANTIDADE DE DIAS (4 OU 22)': [22],
        'DESPESA DIÁRIA (VALOR GASTO POR DIA, IDA E VOLTA)': [9.00],
        'ANO DO CURSO': ['2025'], 'DEPARTAMENTO': ['Exemplo'],
        '1º TRAJETO': ['100'], '1ª EMPRESA': ['Empresa Exemplo'], '1ª TARIFA': [4.50],
        '2º TRAJETO': [''], '2ª EMPRESA': [''], '2ª TARIFA': [0.00],
        '3º TRAJETO': [''], '3ª EMPRESA': [''], '3ª TARIFA': [0.00],
        '4º TRAJETO': [''], '4ª EMPRESA': [''], '4ª TARIFA': [0.00],
        '1º TRAJETO (VOLTA)': ['100'], '1ª EMPRESA (VOLTA)': ['Empresa Exemplo'], '1ª TARIFA (VOLTA)': [4.50],
        '2º TRAJETO (VOLTA)': [''], '2ª EMPRESA (VOLTA)': [''], '2ª TARIFA (VOLTA)': [0.00],
        '3º TRAJETO (VOLTA)': [''], '3ª EMPRESA (VOLTA)': [''], '3ª TARIFA (VOLTA)': [0.00],
        '4º TRAJETO (VOLTA)': [''], '4ª EMPRESA (VOLTA)': [''], '4ª TARIFA (VOLTA)': [0.00],
    }
    df = pd.DataFrame(template_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='AuxilioTransporte')
    return output.getvalue()

# --- Seções da UI ---

def lancamento_individual_tab(supabase):
    """Renderiza a aba para adicionar ou editar dados de um único aluno."""
    st.subheader("Adicionar ou Editar Dados de Transporte para um Aluno")

    alunos_df = load_data("Alunos")
    transporte_df = load_data("auxilio_transporte")

    st.markdown("##### 1. Selecione um Aluno")
    aluno_selecionado_df = render_alunos_filter_and_selection(
        key_suffix="decat_aluno_selector", include_full_name_search=True
    )

    if aluno_selecionado_df.empty or len(aluno_selecionado_df) > 1:
        st.info("Por favor, use os filtros para selecionar um único aluno para continuar.")
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
    
    st.divider()
    st.markdown("##### 2. Preencha os Dados do Transporte")

    with st.form("decat_form_individual"):
        st.text_input("Endereço", value=dados_transporte_atuais.get('endereco', ''), key="endereco_ind")
        c_bairro, c_cidade, c_cep = st.columns(3)
        c_bairro.text_input("Bairro", value=dados_transporte_atuais.get('bairro', ''), key="bairro_ind")
        c_cidade.text_input("Cidade", value=dados_transporte_atuais.get('cidade', ''), key="cidade_ind")
        c_cep.text_input("CEP", value=dados_transporte_atuais.get('cep', ''), key="cep_ind")
        st.number_input("Dias considerados", min_value=0, step=1, value=int(dados_transporte_atuais.get('dias_uteis', 22)), key="dias_uteis_ind")
        
        st.markdown("**Itinerário de Ida**")
        for i in range(1, 5):
            c1, c2, c3 = st.columns(3)
            c1.text_input(f"Empresa {i}", value=dados_transporte_atuais.get(f'ida_{i}_empresa', ''), key=f'ida_{i}_empresa_ind')
            c2.text_input(f"Linha {i}", value=dados_transporte_atuais.get(f'ida_{i}_linha', ''), key=f'ida_{i}_linha_ind')
            c3.number_input(f"Tarifa {i} (R$)", min_value=0.0, step=0.01, format="%.2f", value=float(dados_transporte_atuais.get(f'ida_{i}_tarifa', 0.0)), key=f'ida_{i}_tarifa_ind')

        st.markdown("**Itinerário de Volta**")
        for i in range(1, 5):
            c1, c2, c3 = st.columns(3)
            c1.text_input(f"Empresa {i} ", value=dados_transporte_atuais.get(f'volta_{i}_empresa', ''), key=f'volta_{i}_empresa_ind')
            c2.text_input(f"Linha {i} ", value=dados_transporte_atuais.get(f'volta_{i}_linha', ''), key=f'volta_{i}_linha_ind')
            c3.number_input(f"Tarifa {i} (R$) ", min_value=0.0, step=0.01, format="%.2f", value=float(dados_transporte_atuais.get(f'volta_{i}_tarifa', 0.0)), key=f'volta_{i}_tarifa_ind')

        if st.form_submit_button("Salvar Dados para este Aluno", type="primary"):
            dados_para_salvar = {"aluno_id": aluno_atual['id'], "dias_uteis": st.session_state.dias_uteis_ind,
                                 "endereco": st.session_state.endereco_ind, "bairro": st.session_state.bairro_ind,
                                 "cidade": st.session_state.cidade_ind, "cep": st.session_state.cep_ind}
            for i in range(1, 5):
                dados_para_salvar.update({
                    f'ida_{i}_empresa': st.session_state[f'ida_{i}_empresa_ind'], f'ida_{i}_linha': st.session_state[f'ida_{i}_linha_ind'], f'ida_{i}_tarifa': st.session_state[f'ida_{i}_tarifa_ind'],
                    f'volta_{i}_empresa': st.session_state[f'volta_{i}_empresa_ind'], f'volta_{i}_linha': st.session_state[f'volta_{i}_linha_ind'], f'volta_{i}_tarifa': st.session_state[f'volta_{i}_tarifa_ind']
                })
            try:
                supabase.table("auxilio_transporte").upsert(dados_para_salvar, on_conflict='aluno_id').execute()
                st.success("Dados de transporte salvos com sucesso!")
                load_data.clear()
            except Exception as e:
                st.error(f"Erro ao salvar os dados: {e}")

def gestao_soldos_tab(supabase):
    # ... (código existente sem alterações)
    pass

def gestao_decat_tab(supabase):
    # ... (código existente sem alterações)
    pass

def importacao_massa_tab(supabase):
    # ... (código existente sem alterações)
    pass

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.title("🚌 Gestão de Auxílio Transporte (DeCAT)")

    # if not check_permission('acesso_pagina_auxilio_transporte'):
    #     st.error("Acesso negado."); return

    supabase = init_supabase_client()
    
    tab1, tab2, tab3, tab4 = st.tabs(["Lançamento Individual", "Gerenciar Dados", "Gerenciar Soldos", "Importação em Massa"])

    with tab1:
        lancamento_individual_tab(supabase)
    with tab2:
        gestao_decat_tab(supabase)
    with tab3:
        gestao_soldos_tab(supabase)
    with tab4:
        importacao_massa_tab(supabase)
