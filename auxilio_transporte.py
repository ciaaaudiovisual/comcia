import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from io import BytesIO
import json # Importado para salvar/carregar o mapeamento
from aluno_selection_components import render_alunos_filter_and_selection

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_auxilio_transporte():
    st.title("🚌 Gestão de Auxílio Transporte (DeCAT)")
    supabase = init_supabase_client()
    
    # Organiza a página em abas para uma melhor experiência
    tab_importacao, tab_individual, tab_gestao, tab_soldos, tab_gerar_doc = st.tabs([
        "1. Importação Guiada", 
        "2. Lançamento Individual", 
        "3. Gerenciar Dados", 
        "4. Gerenciar Soldos",
        "5. Gerar Documento"
    ])

    with tab_importacao:
        importacao_guiada_tab(supabase)
    with tab_individual:
        lancamento_individual_tab(supabase)
    with tab_gestao:
        gestao_decat_tab(supabase)
    with tab_soldos:
        gestao_soldos_tab(supabase)
    with tab_gerar_doc:
        st.subheader("Gerar Documento de Solicitação")
        st.info("Funcionalidade em desenvolvimento.")


# --- ABA DE IMPORTAÇÃO GUIADA (VERSÃO MELHORADA) ---
def importacao_guiada_tab(supabase):
    st.subheader("Assistente de Importação de Dados do Google Forms")
    st.markdown("Siga os passos para importar os dados de forma segura e validada.")

    st.markdown("#### Passo 1: Carregue o ficheiro (CSV ou Excel)")
    uploaded_file = st.file_uploader(
        "Escolha o ficheiro exportado do Google Forms", 
        type=["csv", "xlsx"],
        help="O sistema lembrará seu último mapeamento de colunas bem-sucedido."
    )

    if not uploaded_file:
        st.info("Aguardando o upload do ficheiro para iniciar o assistente.")
        return

    try:
        # CORREÇÃO: Adiciona o delimitador ';' para ler o CSV corretamente
        df_import = pd.read_csv(uploaded_file, delimiter=';') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        st.session_state['df_import_cache'] = df_import
        st.session_state['import_file_columns'] = df_import.columns.tolist()
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        st.warning("Verifique se o delimitador do seu CSV é o ponto e vírgula ';'.")
        return

    st.markdown("---")
    st.markdown("#### Passo 2: Mapeie as colunas do seu ficheiro")
    st.info("O sistema tenta pré-selecionar o seu último mapeamento. Confirme ou ajuste se necessário.")

    # Carrega o último mapeamento salvo do banco de dados
    config_df = load_data("Config")
    mapeamento_salvo = {}
    if 'mapeamento_auxilio_transporte' in config_df['chave'].values:
        try:
            json_string = config_df[config_df['chave'] == 'mapeamento_auxilio_transporte']['valor'].iloc[0]
            mapeamento_salvo = json.loads(json_string)
        except:
            mapeamento_salvo = {}

    # Define todos os campos que o sistema pode importar
    campos_sistema = {
        "numero_interno": "Número Interno do Aluno*", "ano_referencia": "Ano de Referência do Benefício*",
        "endereco": "Endereço Domiciliar", "bairro": "Bairro", "cidade": "Cidade", "cep": "CEP",
        "dias_uteis": "Quantidade de Dias",
    }
    for i in range(1, 5):
        campos_sistema[f"ida_{i}_empresa"] = f"{i}ª Empresa (Ida)"
        campos_sistema[f"ida_{i}_linha"] = f"{i}ª Linha/Trajeto (Ida)"
        campos_sistema[f"ida_{i}_tarifa"] = f"{i}ª Tarifa (Ida)"
    for i in range(1, 5):
        campos_sistema[f"volta_{i}_empresa"] = f"{i}ª Empresa (Volta)"
        campos_sistema[f"volta_{i}_linha"] = f"{i}ª Linha/Trajeto (Volta)"
        campos_sistema[f"volta_{i}_tarifa"] = f"{i}ª Tarifa (Volta)"
    
    opcoes_ficheiro = ["-- Não importar este campo --"] + st.session_state['import_file_columns']
    
    with st.form("mapping_form"):
        mapeamento_usuario = {}
        st.markdown("**Dados Gerais e de Endereço**")
        cols_gerais = st.columns(3)
        campos_gerais = ["numero_interno", "ano_referencia", "endereco", "bairro", "cidade", "cep", "dias_uteis"]
        for i, key in enumerate(campos_gerais):
            display_name = campos_sistema[key]
            index_salvo = opcoes_ficheiro.index(mapeamento_salvo.get(key)) if mapeamento_salvo.get(key) in opcoes_ficheiro else 0
            mapeamento_usuario[key] = cols_gerais[i % 3].selectbox(f"**{display_name}**", options=opcoes_ficheiro, key=f"map_{key}", index=index_salvo)
        
        st.markdown("**Itinerários de Ida**")
        cols_ida = st.columns(4)
        for i in range(1, 5):
            with cols_ida[i-1]:
                st.markdown(f"**{i}º Trajeto (Ida)**")
                index_empresa = opcoes_ficheiro.index(mapeamento_salvo.get(f'ida_{i}_empresa')) if mapeamento_salvo.get(f'ida_{i}_empresa') in opcoes_ficheiro else 0
                index_linha = opcoes_ficheiro.index(mapeamento_salvo.get(f'ida_{i}_linha')) if mapeamento_salvo.get(f'ida_{i}_linha') in opcoes_ficheiro else 0
                index_tarifa = opcoes_ficheiro.index(mapeamento_salvo.get(f'ida_{i}_tarifa')) if mapeamento_salvo.get(f'ida_{i}_tarifa') in opcoes_ficheiro else 0
                mapeamento_usuario[f'ida_{i}_empresa'] = st.selectbox(f"Empresa", options=opcoes_ficheiro, key=f"map_ida_{i}_empresa", index=index_empresa)
                mapeamento_usuario[f'ida_{i}_linha'] = st.selectbox(f"Linha", options=opcoes_ficheiro, key=f"map_ida_{i}_linha", index=index_linha)
                mapeamento_usuario[f'ida_{i}_tarifa'] = st.selectbox(f"Tarifa", options=opcoes_ficheiro, key=f"map_ida_{i}_tarifa", index=index_tarifa)

        st.markdown("**Itinerários de Volta**")
        cols_volta = st.columns(4)
        for i in range(1, 5):
            with cols_volta[i-1]:
                st.markdown(f"**{i}º Trajeto (Volta)**")
                index_empresa = opcoes_ficheiro.index(mapeamento_salvo.get(f'volta_{i}_empresa')) if mapeamento_salvo.get(f'volta_{i}_empresa') in opcoes_ficheiro else 0
                index_linha = opcoes_ficheiro.index(mapeamento_salvo.get(f'volta_{i}_linha')) if mapeamento_salvo.get(f'volta_{i}_linha') in opcoes_ficheiro else 0
                index_tarifa = opcoes_ficheiro.index(mapeamento_salvo.get(f'volta_{i}_tarifa')) if mapeamento_salvo.get(f'volta_{i}_tarifa') in opcoes_ficheiro else 0
                mapeamento_usuario[f'volta_{i}_empresa'] = st.selectbox(f"Empresa", options=opcoes_ficheiro, key=f"map_volta_{i}_empresa", index=index_empresa)
                mapeamento_usuario[f'volta_{i}_linha'] = st.selectbox(f"Linha", options=opcoes_ficheiro, key=f"map_volta_{i}_linha", index=index_linha)
                mapeamento_usuario[f'volta_{i}_tarifa'] = st.selectbox(f"Tarifa", options=opcoes_ficheiro, key=f"map_volta_{i}_tarifa", index=index_tarifa)

        submitted = st.form_submit_button("Validar Mapeamento e Pré-visualizar", type="primary")
        if submitted:
            st.session_state['mapeamento_final'] = mapeamento_usuario
            try:
                mapeamento_json = json.dumps(mapeamento_usuario)
                supabase.table("Config").upsert({"chave": "mapeamento_auxilio_transporte", "valor": mapeamento_json}).execute()
                st.toast("Mapeamento salvo para uso futuro!", icon="💾")
            except Exception as e:
                st.warning(f"Não foi possível salvar o mapeamento: {e}")

    if 'mapeamento_final' in st.session_state:
        st.markdown("---")
        st.markdown("#### Passo 3: Valide os dados antes de importar")
        
        with st.spinner("Processando e validando os dados..."):
            df_import = st.session_state['df_import_cache'].copy()
            mapeamento = st.session_state['mapeamento_final']

            if mapeamento['numero_interno'] == '-- Não importar este campo --' or mapeamento['ano_referencia'] == '-- Não importar este campo --':
                st.error("ERRO: 'Número Interno do Aluno' e 'Ano de Referência' são campos obrigatórios para o mapeamento.")
                return

            rename_dict = {v: k for k, v in mapeamento.items() if v != '-- Não importar este campo --'}
            df_processado = df_import[list(rename_dict.keys())].rename(columns=rename_dict)
            
            alunos_df = load_data("Alunos")[['id', 'numero_interno', 'nome_guerra']]
            df_processado['numero_interno'] = df_processado['numero_interno'].astype(str).str.strip().str.upper()
            alunos_df['numero_interno'] = alunos_df['numero_interno'].astype(str).str.strip().str.upper()

            df_final = pd.merge(df_processado, alunos_df, on='numero_interno', how='left')
            df_final.rename(columns={'id': 'aluno_id'}, inplace=True)

            sucesso_df = df_final.dropna(subset=['aluno_id'])
            falha_df = df_final[df_final['aluno_id'].isna()]

            st.success(f"**Validação Concluída!** Foram encontrados **{len(sucesso_df)}** alunos correspondentes no sistema.")
            if not falha_df.empty:
                st.warning(f"Não foi possível encontrar **{len(falha_df)}** alunos. Verifique os 'Números Internos' abaixo:")
                st.dataframe(falha_df[['numero_interno']], use_container_width=True)

            st.markdown("**Pré-visualização dos dados a serem importados:**")
            st.dataframe(sucesso_df, use_container_width=True)
            st.session_state['registros_para_importar'] = sucesso_df

    if 'registros_para_importar' in st.session_state and not st.session_state['registros_para_importar'].empty:
         if st.button("Confirmar e Salvar no Sistema", type="primary"):
            with st.spinner("Salvando dados no banco de dados..."):
                try:
                    st.toast("Iniciando processo de importação...", icon="⏳")
                    registros = st.session_state['registros_para_importar'].copy()
                    
                    colunas_db = list(campos_sistema.keys()) + ['aluno_id']
                    registros_para_upsert = registros[[col for col in colunas_db if col in registros.columns]]

                    st.toast("Convertendo tipos de dados...", icon="⚙️")
                    registros_para_upsert['aluno_id'] = pd.to_numeric(registros_para_upsert['aluno_id'], errors='coerce').astype('Int64')
                    registros_para_upsert['ano_referencia'] = pd.to_numeric(registros_para_upsert['ano_referencia'], errors='coerce').astype('Int64')
                    
                    if 'dias_uteis' in registros_para_upsert:
                        registros_para_upsert['dias_uteis'] = pd.to_numeric(registros_para_upsert['dias_uteis'], errors='coerce').fillna(0).astype(int)
                    
                    for col in registros_para_upsert.columns:
                        if 'tarifa' in col:
                            registros_para_upsert[col] = pd.to_numeric(
                                registros_para_upsert[col].astype(str).str.replace(',', '.'), errors='coerce'
                            ).fillna(0.0)
                    
                    registros_para_upsert.dropna(subset=['aluno_id', 'ano_referencia'], inplace=True)
                    
                    st.toast(f"Enviando {len(registros_para_upsert)} registros para o banco de dados...", icon="➡️")
                    supabase.table("auxilio_transporte").upsert(
                        registros_para_upsert.to_dict(orient='records'),
                        on_conflict='aluno_id,ano_referencia'
                    ).execute()
                    
                    st.success(f"**Importação Concluída!** {len(registros_para_upsert)} registros foram salvos no sistema.")
                    
                    for key in ['df_import_cache', 'mapeamento_final', 'registros_para_importar']:
                        if key in st.session_state:
                            del st.session_state[key]
                    load_data.clear()
                
                except Exception as e:
                    st.error(f"**Ocorreu um erro durante a importação final:** {e}")
                    st.error("Verifique os tipos de dados no seu ficheiro. Campos como 'Ano de Referência' e 'Tarifas' devem conter apenas números.")

# --- ABA DE LANÇAMENTO INDIVIDUAL (ATUALIZADA) ---
def lancamento_individual_tab(supabase):
    st.subheader("Adicionar ou Editar Dados para um Aluno")

    alunos_df = load_data("Alunos")
    transporte_df = load_data("auxilio_transporte")

    st.markdown("##### 1. Selecione um Aluno")
    aluno_selecionado_df = render_alunos_filter_and_selection(
        key_suffix="transporte_individual", include_full_name_search=True
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
        dados_aluno_transporte = transporte_df[transporte_df['aluno_id'] == aluno_atual['id']].sort_values('ano_referencia', ascending=False)
        if not dados_aluno_transporte.empty:
            dados_transporte_atuais = dados_aluno_transporte.iloc[0].to_dict()
    
    st.divider()
    st.markdown("##### 2. Preencha os Dados do Transporte")

    with st.form("form_individual"):
        c_ano, c_dias = st.columns(2)
        
        valor_ano_atual = dados_transporte_atuais.get('ano_referencia')
        ano_default = int(valor_ano_atual) if pd.notna(valor_ano_atual) else 2025
        ano_referencia = c_ano.number_input("Ano de Referência*", min_value=2020, max_value=2050, value=ano_default, step=1)
        
        dias_uteis = c_dias.number_input("Dias considerados", min_value=0, step=1, value=int(dados_transporte_atuais.get('dias_uteis', 22)))
        
        endereco = st.text_input("Endereço", value=dados_transporte_atuais.get('endereco', ''))
        c_bairro, c_cidade, c_cep = st.columns(3)
        bairro = c_bairro.text_input("Bairro", value=dados_transporte_atuais.get('bairro', ''))
        cidade = c_cidade.text_input("Cidade", value=dados_transporte_atuais.get('cidade', ''))
        cep = c_cep.text_input("CEP", value=dados_transporte_atuais.get('cep', ''))
        
        st.markdown("**Itinerário de Ida**")
        ida_data = {}
        for i in range(1, 5):
            c1, c2, c3 = st.columns(3)
            ida_data[f'empresa_{i}'] = c1.text_input(f"Empresa {i} (Ida)", value=dados_transporte_atuais.get(f'ida_{i}_empresa', ''), key=f'ida_{i}_empresa_ind')
            ida_data[f'linha_{i}'] = c2.text_input(f"Linha {i} (Ida)", value=dados_transporte_atuais.get(f'ida_{i}_linha', ''), key=f'ida_{i}_linha_ind')
            ida_data[f'tarifa_{i}'] = c3.number_input(f"Tarifa {i} (Ida) R$", min_value=0.0, step=0.01, format="%.2f", value=float(dados_transporte_atuais.get(f'ida_{i}_tarifa', 0.0)), key=f'ida_{i}_tarifa_ind')

        st.markdown("**Itinerário de Volta**")
        volta_data = {}
        for i in range(1, 5):
            c1, c2, c3 = st.columns(3)
            volta_data[f'empresa_{i}'] = c1.text_input(f"Empresa {i} (Volta)", value=dados_transporte_atuais.get(f'volta_{i}_empresa', ''), key=f'volta_{i}_empresa_ind')
            volta_data[f'linha_{i}'] = c2.text_input(f"Linha {i} (Volta)", value=dados_transporte_atuais.get(f'volta_{i}_linha', ''), key=f'volta_{i}_linha_ind')
            volta_data[f'tarifa_{i}'] = c3.number_input(f"Tarifa {i} (Volta) R$", min_value=0.0, step=0.01, format="%.2f", value=float(dados_transporte_atuais.get(f'volta_{i}_tarifa', 0.0)), key=f'volta_{i}_tarifa_ind')

        if st.form_submit_button("Salvar Dados para este Aluno", type="primary"):
            dados_para_salvar = {
                "aluno_id": int(aluno_atual['id']), "ano_referencia": ano_referencia, "dias_uteis": dias_uteis,
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
                st.success("Dados de transporte salvos com sucesso!")
                load_data.clear()
            except Exception as e:
                st.error(f"Erro ao salvar os dados: {e}")


# --- ABA DE GESTÃO DE DADOS (ATUALIZADA) ---
def gestao_decat_tab(supabase):
    st.subheader("Dados de Transporte Cadastrados")
    st.info("Visualize e edite os dados de transporte dos alunos que solicitaram o benefício.")

    alunos_df = load_data("Alunos")
    transporte_df = load_data("auxilio_transporte")

    if transporte_df.empty:
        st.warning("Nenhum dado de auxílio transporte cadastrado.")
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
    
    colunas_info_aluno = ['numero_interno', 'nome_guerra', 'ano_referencia']
    colunas_transporte_existentes = [col for col in transporte_df.columns if col not in ['id', 'aluno_id', 'created_at', 'ano_referencia']]
    colunas_finais = colunas_info_aluno + colunas_transporte_existentes
    
    # Garante que apenas colunas existentes no dataframe são selecionadas
    colunas_a_exibir = [col for col in colunas_finais if col in display_df.columns]
    
    edited_df = st.data_editor(
        display_df[colunas_a_exibir], hide_index=True, use_container_width=True,
        key="transporte_editor", disabled=['numero_interno', 'nome_guerra'] 
    )

    if st.button("Salvar Alterações na Tabela"):
        with st.spinner("Salvando..."):
            try:
                edited_df_com_id = pd.merge(edited_df, alunos_df[['numero_interno', 'id']], on='numero_interno', how='left')
                edited_df_com_id.rename(columns={'id': 'aluno_id'}, inplace=True)
                
                colunas_para_remover = ['numero_interno', 'nome_guerra']
                records_to_upsert = edited_df_com_id.drop(columns=colunas_para_remover).to_dict(orient='records')

                supabase.table("auxilio_transporte").upsert(records_to_upsert, on_conflict='aluno_id,ano_referencia').execute()
                st.success("Alterações salvas com sucesso!")
                load_data.clear()
            except Exception as e:
                st.error(f"Erro ao salvar alterações: {e}")

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
