import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from io import BytesIO
import json
import re
from aluno_selection_components import render_alunos_filter_and_selection
from pypdf import PdfReader, PdfWriter

# --- FUNÇÃO DE CÁLCULO CENTRAL ---
def calcular_auxilio_transporte(linha):
    """
    Calcula todos os valores do auxílio transporte para uma única linha de dados.
    A linha deve ser o resultado do merge entre Alunos, Transporte e Soldos.
    """
    try:
        # 1. Despesa Diária
        despesa_diaria = 0
        for i in range(1, 5):
            despesa_diaria += float(linha.get(f'ida_{i}_tarifa', 0.0) or 0.0)
            despesa_diaria += float(linha.get(f'volta_{i}_tarifa', 0.0) or 0.0)

        # 2. Dias Trabalhados (limitado a 22)
        dias_trabalhados = min(int(linha.get('dias_uteis', 0) or 0), 22)

        # 3. Despesa Mensal
        despesa_mensal = despesa_diaria * dias_trabalhados

        # 4. Parcela do Beneficiário
        soldo = float(linha.get('soldo', 0.0) or 0.0)
        parcela_beneficiario = 0.0
        if soldo > 0 and dias_trabalhados > 0:
            parcela_beneficiario = ((soldo * 0.06) / 30) * dias_trabalhados

        # 5. Auxílio a ser Pago (não pode ser negativo)
        auxilio_pago = max(0.0, despesa_mensal - parcela_beneficiario)

        return pd.Series({
            'despesa_diaria': round(despesa_diaria, 2),
            'despesa_mensal': round(despesa_mensal, 2),
            'parcela_beneficiario': round(parcela_beneficiario, 2),
            'auxilio_pago': round(auxilio_pago, 2)
        })
    except (ValueError, TypeError):
        return pd.Series({'despesa_diaria': 0.0, 'despesa_mensal': 0.0, 'parcela_beneficiario': 0.0, 'auxilio_pago': 0.0})

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_auxilio_transporte():
    st.title("🚌 Gestão de Auxílio Transporte (DeCAT)")
    supabase = init_supabase_client()
    
    tab_importacao, tab_individual, tab_gestao, tab_soldos, tab_gerar_doc = st.tabs([
        "1. Importação Guiada", "2. Lançamento Individual", 
        "3. Gerenciar Dados", "4. Gerenciar Soldos", "5. Gerar Documento"
    ])

    soldos_df = load_data("soldos")
    opcoes_posto_grad = [""]
    if not soldos_df.empty and 'graduacao' in soldos_df.columns:
        opcoes_posto_grad += sorted(soldos_df['graduacao'].unique().tolist())

    with tab_importacao:
        importacao_guiada_tab(supabase)
    with tab_individual:
        lancamento_individual_tab(supabase, opcoes_posto_grad)
    with tab_gestao:
        gestao_decat_tab(supabase)
    with tab_soldos:
        gestao_soldos_tab(supabase)
    with tab_gerar_doc:
        gerar_documento_tab(supabase)


def create_excel_template():
    """Cria um modelo Excel em memória para o usuário baixar."""
    # Define os cabeçalhos das colunas exatamente como o sistema espera
    template_data = {
        'NÚMERO INTERNO DO ALUNO': ['M-01-101'],
        'ANO DE REFERÊNCIA': [2025],
        'POSTO/GRADUAÇÃO': ['ALUNO'],
        'ENDEREÇO COMPLETO': ['Rua Exemplo, 123'],
        'BAIRRO': ['Bairro Exemplo'],
        'CIDADE': ['Cidade Exemplo'],
        'CEP': ['12345-678'],
        'DIAS ÚTEIS (MÁX 22)': [22],
        '1ª EMPRESA (IDA)': ['Empresa A'],
        '1º TRAJETO (IDA)': ['Linha 100'],
        '1ª TARIFA (IDA)': [4.50],
        '2ª EMPRESA (IDA)': [''], '2º TRAJETO (IDA)': [''], '2ª TARIFA (IDA)': [''],
        '3ª EMPRESA (IDA)': [''], '3º TRAJETO (IDA)': [''], '3ª TARIFA (IDA)': [''],
        '4ª EMPRESA (IDA)': [''], '4º TRAJETO (IDA)': [''], '4ª TARIFA (IDA)': [''],
        '1ª EMPRESA (VOLTA)': ['Empresa A'],
        '1º TRAJETO (VOLTA)': ['Linha 100'],
        '1ª TARIFA (VOLTA)': [4.50],
        '2ª EMPRESA (VOLTA)': [''], '2º TRAJETO (VOLTA)': [''], '2ª TARIFA (VOLTA)': [''],
        '3ª EMPRESA (VOLTA)': [''], '3º TRAJETO (VOLTA)': [''], '3ª TARIFA (VOLTA)': [''],
        '4ª EMPRESA (VOLTA)': [''], '4º TRAJETO (VOLTA)': [''], '4ª TARIFA (VOLTA)': [''],
    }
    df = pd.DataFrame(template_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='ModeloAuxilioTransporte')
    return output.getvalue()

# --- ABA DE IMPORTAÇÃO GUIADA (COM BOTÃO DE DOWNLOAD) ---
def importacao_guiada_tab(supabase):
    st.subheader("Assistente de Importação de Dados")
    
    st.markdown("#### Passo 1: Baixe o modelo e preencha com os dados")
    st.info("Use o modelo padrão para garantir que as colunas sejam reconhecidas corretamente durante a importação.")
    
    excel_modelo_bytes = create_excel_template()
    st.download_button(
        label="📥 Baixar Modelo de Preenchimento (.xlsx)",
        data=excel_modelo_bytes,
        file_name="modelo_auxilio_transporte.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.markdown("#### Passo 2: Carregue o ficheiro preenchido")
    uploaded_file = st.file_uploader("Escolha o ficheiro...", type=["csv", "xlsx"], key="importer_uploader_at")

    if not uploaded_file:
        st.info("Aguardando o upload do ficheiro para iniciar.")
        return

    try:
        df_import = pd.read_csv(uploaded_file, delimiter=';') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        st.session_state['df_import_cache_at'] = df_import
        st.session_state['import_file_columns_at'] = df_import.columns.tolist()
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return

    st.markdown("---")
    st.markdown("#### Passo 3: Mapeie as colunas do seu ficheiro")
    
    config_df = load_data("Config")
    mapeamento_salvo = json.loads(config_df[config_df['chave'] == 'mapeamento_auxilio_transporte']['valor'].iloc[0]) if 'mapeamento_auxilio_transporte' in config_df['chave'].values else {}


    campos_sistema = {
        "numero_interno": ("Número Interno*", ["número interno"]),
        "ano_referencia": ("Ano de Referência*", ["ano"]),
        "posto_grad": ("Posto/Graduação*", ["posto", "graduação"]),
        "endereco": ("Endereço", ["endereço"]), "bairro": ("Bairro", ["bairro"]), "cidade": ("Cidade", ["cidade"]), "cep": ("CEP", ["cep"]),
        "dias_uteis": ("Dias", ["dias"]),
    }
    for i in range(1, 5):
        campos_sistema[f'ida_{i}_empresa'] = (f"{i}ª Empresa (Ida)", ([f"{i}ª", "empresa"], ["volta"]))
        campos_sistema[f'ida_{i}_linha'] = (f"{i}ª Linha (Ida)", ([f"{i}º", "trajeto"], ["volta"]))
        campos_sistema[f'ida_{i}_tarifa'] = (f"{i}ª Tarifa (Ida)", ([f"{i}ª", "tarifa"], ["volta"]))
        campos_sistema[f'volta_{i}_empresa'] = (f"{i}ª Empresa (Volta)", ([f"{i}ª", "empresa", "volta"], []))
        campos_sistema[f'volta_{i}_linha'] = (f"{i}ª Linha (Volta)", ([f"{i}º", "trajeto", "volta"], []))
        campos_sistema[f'volta_{i}_tarifa'] = (f"{i}ª Tarifa (Volta)", ([f"{i}ª", "tarifa", "volta"], []))

    opcoes_ficheiro = ["-- Não importar este campo --"] + st.session_state['import_file_columns_at']

    def get_best_match_index(search_criteria, all_options, saved_option):
        if saved_option in all_options: return all_options.index(saved_option)
        must_include, must_exclude = search_criteria
        for i, option in enumerate(all_options):
            option_lower = option.lower()
            if all(inc.lower() in option_lower for inc in must_include) and not any(exc.lower() in option_lower for exc in must_exclude): return i
        return 0

    with st.form("mapping_form_at"):
        mapeamento_usuario = {}
        campos_gerais = ["numero_interno", "ano_referencia", "posto_grad", "endereco", "bairro", "cidade", "cep", "dias_uteis"]
        st.markdown("**Dados Gerais**")
        cols_gerais = st.columns(3)
        for i, key in enumerate(campos_gerais):
            display_name, search_criteria = campos_sistema[key]
            index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
            mapeamento_usuario[key] = cols_gerais[i % 3].selectbox(f"**{display_name}**", options=opcoes_ficheiro, key=f"map_at_{key}", index=index)
        
        st.markdown("**Itinerários**")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Ida**")
            for i in range(1, 5):
                for tipo in ["empresa", "linha", "tarifa"]:
                    key = f"ida_{i}_{tipo}"
                    display_name, search_criteria = campos_sistema[key]
                    index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
                    mapeamento_usuario[key] = st.selectbox(display_name, options=opcoes_ficheiro, key=f"map_at_{key}", index=index)
        with c2:
            st.markdown("**Volta**")
            for i in range(1, 5):
                for tipo in ["empresa", "linha", "tarifa"]:
                    key = f"volta_{i}_{tipo}"
                    display_name, search_criteria = campos_sistema[key]
                    index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
                    mapeamento_usuario[key] = st.selectbox(display_name, options=opcoes_ficheiro, key=f"map_at_{key}", index=index)

        if st.form_submit_button("Validar Mapeamento e Pré-visualizar", type="primary"):
            st.session_state['mapeamento_final_at'] = mapeamento_usuario
            try:
                supabase.table("Config").upsert({"chave": "mapeamento_auxilio_transporte", "valor": json.dumps(mapeamento_usuario)}).execute()
                st.toast("Mapeamento salvo!", icon="💾")
            except Exception as e:
                st.warning(f"Não foi possível salvar o mapeamento: {e}")

# --- ABA DE LANÇAMENTO INDIVIDUAL (ATUALIZADA) ---
def lancamento_individual_tab(supabase, opcoes_posto_grad):
    st.subheader("Adicionar ou Editar Dados para um Aluno")
    aluno_selecionado_df = render_alunos_filter_and_selection(key_suffix="transporte_individual", include_full_name_search=True)

    if aluno_selecionado_df.empty or len(aluno_selecionado_df) > 1:
        st.info("Por favor, selecione um único aluno.")
        return

    aluno_atual = aluno_selecionado_df.iloc[0]
    st.success(f"Aluno selecionado: **{aluno_atual['nome_guerra']} ({aluno_atual['numero_interno']})**")
    
    transporte_df = load_data("auxilio_transporte")
    dados_atuais = {}
    if not transporte_df.empty:
        dados_aluno = transporte_df[transporte_df['aluno_id'].astype(str) == str(aluno_atual['id'])].sort_values('ano_referencia', ascending=False)
        if not dados_aluno.empty:
            dados_atuais = dados_aluno.iloc[0].to_dict()

    with st.form("form_individual_at"):
        c1, c2, c3 = st.columns(3)
        ano_referencia = c1.number_input("Ano*", value=int(dados_atuais.get('ano_referencia', 2025)))
        posto_grad = c2.selectbox("Posto/Graduação*", options=opcoes_posto_grad, index=opcoes_posto_grad.index(dados_atuais.get('posto_grad', '')) if dados_atuais.get('posto_grad') in opcoes_posto_grad else 0)
        dias_uteis = c3.number_input("Dias Úteis", value=int(dados_atuais.get('dias_uteis', 22)))
        
        endereco = st.text_input("Endereço", value=dados_atuais.get('endereco', ''))
        c4,c5,c6 = st.columns(3)
        bairro = c4.text_input("Bairro", value=dados_atuais.get('bairro', ''))
        cidade = c5.text_input("Cidade", value=dados_atuais.get('cidade', ''))
        cep = c6.text_input("CEP", value=dados_atuais.get('cep', ''))
        
        ida_data = {}
        volta_data = {}
        st.markdown("**Itinerários**")
        c7, c8 = st.columns(2)
        with c7:
            st.markdown("**Ida**")
            for i in range(1, 5):
                ida_data[f'empresa_{i}'] = st.text_input(f"{i}ª Empresa (Ida)", value=dados_atuais.get(f'ida_{i}_empresa', ''), key=f'ida_empresa_{i}')
                ida_data[f'linha_{i}'] = st.text_input(f"{i}ª Linha (Ida)", value=dados_atuais.get(f'ida_{i}_linha', ''), key=f'ida_linha_{i}')
                ida_data[f'tarifa_{i}'] = st.number_input(f"{i}ª Tarifa (Ida)", value=float(dados_atuais.get(f'ida_{i}_tarifa', 0.0)), min_value=0.0, format="%.2f", key=f'ida_tarifa_{i}')
        with c8:
            st.markdown("**Volta**")
            for i in range(1, 5):
                volta_data[f'empresa_{i}'] = st.text_input(f"{i}ª Empresa (Volta)", value=dados_atuais.get(f'volta_{i}_empresa', ''), key=f'volta_empresa_{i}')
                volta_data[f'linha_{i}'] = st.text_input(f"{i}ª Linha (Volta)", value=dados_atuais.get(f'volta_{i}_linha', ''), key=f'volta_linha_{i}')
                volta_data[f'tarifa_{i}'] = st.number_input(f"{i}ª Tarifa (Volta)", value=float(dados_atuais.get(f'volta_{i}_tarifa', 0.0)), min_value=0.0, format="%.2f", key=f'volta_tarifa_{i}')
        
        if st.form_submit_button("Salvar Dados"):
            dados_para_salvar = {
                "aluno_id": int(aluno_atual['id']), "ano_referencia": ano_referencia,
                "posto_grad": posto_grad, "dias_uteis": dias_uteis,
                "endereco": endereco, "bairro": bairro, "cidade": cidade, "cep": cep
            }
            for i in range(1, 5):
                dados_para_salvar[f'ida_{i}_empresa'] = ida_data[f'empresa_{i}']
                dados_para_salvar[f'ida_{i}_linha'] = ida_data[f'linha_{i}']
                dados_para_salvar[f'ida_{i}_tarifa'] = ida_data[f'tarifa_{i}']
                dados_para_salvar[f'volta_{i}_empresa'] = volta_data[f'empresa_{i}']
                dados_para_salvar[f'volta_{i}_linha'] = volta_data[f'linha_{i}']
                dados_para_salvar[f'volta_{i}_tarifa'] = volta_data[f'tarifa_{i}']
            try:
                supabase.table("auxilio_transporte").upsert(dados_para_salvar, on_conflict='aluno_id,ano_referencia').execute()
                st.success("Dados salvos com sucesso!")
                load_data.clear()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# --- ABA DE GESTÃO DE DADOS ---
def gestao_decat_tab(supabase):
    st.subheader("Dados de Transporte Cadastrados (com Cálculo)")
    
    alunos_df = load_data("Alunos")[['id', 'numero_interno', 'nome_guerra']]
    transporte_df = load_data("auxilio_transporte")
    soldos_df = load_data("soldos")

    if transporte_df.empty:
        st.warning("Nenhum dado de auxílio transporte cadastrado.")
        return

    alunos_df['id'] = alunos_df['id'].astype(str).str.strip()
    transporte_df['aluno_id'] = transporte_df['aluno_id'].astype(str).str.strip()
    
    dados_completos_df = pd.merge(transporte_df, alunos_df, left_on='aluno_id', right_on='id', how='left')
    dados_completos_df = pd.merge(dados_completos_df, soldos_df, left_on='posto_grad', right_on='graduacao', how='left')
    
    calculos_df = dados_completos_df.apply(calcular_auxilio_transporte, axis=1)
    display_df = pd.concat([dados_completos_df, calculos_df], axis=1)
    
    colunas_principais = ['numero_interno', 'nome_guerra', 'ano_referencia', 'posto_grad']
    colunas_calculadas = ['despesa_diaria', 'despesa_mensal', 'parcela_beneficiario', 'auxilio_pago']
    colunas_editaveis = ['dias_uteis', 'endereco', 'bairro', 'cidade', 'cep']
    for i in range(1, 5):
        colunas_editaveis += [f'ida_{i}_empresa', f'ida_{i}_linha', f'ida_{i}_tarifa']
        colunas_editaveis += [f'volta_{i}_empresa', f'volta_{i}_linha', f'volta_{i}_tarifa']
    
    colunas_visiveis = [col for col in colunas_principais + colunas_calculadas + colunas_editaveis if col in display_df.columns]
    
    edited_df = st.data_editor(display_df[colunas_visiveis], hide_index=True, use_container_width=True, disabled=colunas_principais + colunas_calculadas)
    
    if st.button("Salvar Alterações na Tabela de Gestão"):
        # Lógica para salvar as edições
        pass

# --- ABA DE GESTÃO DE SOLDOS ---
def gestao_soldos_tab(supabase):
    st.subheader("Tabela de Soldos por Graduação")
    st.info("Edite, adicione ou remova graduações e soldos.")
    
    soldos_df = load_data("soldos")
    if 'id' in soldos_df.columns:
        soldos_df = soldos_df.drop(columns=['id'])
    
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
