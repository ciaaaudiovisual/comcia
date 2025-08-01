import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from io import BytesIO
import json
import re
from aluno_selection_components import render_alunos_filter_and_selection
from pypdf import PdfReader, PdfWriter

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_auxilio_transporte():
    st.title("🚌 Gestão de Auxílio Transporte (DeCAT)")
    supabase = init_supabase_client()
    
    tab_importacao, tab_individual, tab_gestao, tab_soldos, tab_gerar_doc = st.tabs([
        "1. Importação Guiada", "2. Lançamento Individual", 
        "3. Gerenciar Dados", "4. Gerenciar Soldos", "5. Gerar Documento"
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
        gerar_documento_tab(supabase)


# --- FUNÇÕES AUXILIARES PARA GERAÇÃO DE PDF ---
def fill_pdf_auxilio(template_bytes: bytes, aluno_data: pd.Series) -> BytesIO:
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter(clone_from=reader)
    
    # Adapte as chaves deste dicionário para corresponderem EXATAMENTE aos nomes dos campos no seu PDF
    pdf_field_mapping = {
        'NOME COMPLETO': 'nome_completo', 'NIP': 'nip', 'ENDEREÇO': 'endereco',
        'BAIRRO': 'bairro', 'CIDADE': 'cidade', 'CEP': 'cep', 'ANO': 'ano_referencia'
    }

    fill_data = {
        pdf_field: str(aluno_data.get(df_column, ''))
        for pdf_field, df_column in pdf_field_mapping.items()
    }
    
    for i in range(1, 5):
        fill_data[f'EMPRESA IDA {i}'] = str(aluno_data.get(f'ida_{i}_empresa', ''))
        fill_data[f'LINHA IDA {i}'] = str(aluno_data.get(f'ida_{i}_linha', ''))
        fill_data[f'TARIFA IDA {i}'] = f"R$ {aluno_data.get(f'ida_{i}_tarifa', 0.0):.2f}"
        fill_data[f'EMPRESA VOLTA {i}'] = str(aluno_data.get(f'volta_{i}_empresa', ''))
        fill_data[f'LINHA VOLTA {i}'] = str(aluno_data.get(f'volta_{i}_linha', ''))
        fill_data[f'TARIFA VOLTA {i}'] = f"R$ {aluno_data.get(f'volta_{i}_tarifa', 0.0):.2f}"

    if writer.get_form_text_fields():
        for page in writer.pages:
            writer.update_page_form_field_values(page, fill_data)
            
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer

def merge_pdfs(pdf_buffers: list) -> BytesIO:
    merger = PdfWriter()
    for buffer in pdf_buffers:
        reader = PdfReader(buffer)
        for page in reader.pages:
            merger.add_page(page)
    merged_pdf_buffer = BytesIO()
    merger.write(merged_pdf_buffer)
    merged_pdf_buffer.seek(0)
    return merged_pdf_buffer


# --- ABA DE GERAÇÃO DE DOCUMENTOS ---
def gerar_documento_tab(supabase):
    st.subheader("Gerador de Documentos de Solicitação de Auxílio Transporte")
    
    NOME_TEMPLATE = "auxilio_transporte_template.pdf"

    with st.expander("Configurar Modelo de PDF"):
        st.info(f"Faça o upload do seu modelo de PDF preenchível. Ele será salvo no sistema como '{NOME_TEMPLATE}'.")
        uploaded_template = st.file_uploader("Selecione o seu modelo de PDF", type="pdf", key="pdf_template_uploader")
        
        if uploaded_template:
            if st.button("Salvar Modelo no Sistema"):
                with st.spinner("Salvando modelo..."):
                    try:
                        supabase.storage.from_("templates").upload(
                            NOME_TEMPLATE, uploaded_template.getvalue(), {"content-type": "application/pdf", "x-upsert": "true"}
                        )
                        st.success("Modelo salvo com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar o modelo: {e}")

    st.divider()
    
    st.markdown("#### 1. Selecione os Alunos")
    alunos_df = load_data("Alunos")
    transporte_df = load_data("auxilio_transporte")

    if transporte_df.empty:
        st.warning("Nenhum dado de transporte foi cadastrado para preencher os documentos.")
        return

    alunos_df['id'] = alunos_df['id'].astype(str)
    transporte_df['aluno_id'] = transporte_df['aluno_id'].astype(str)
    
    # Junta as informações dos alunos com os dados de transporte
    dados_completos_df = pd.merge(alunos_df, transporte_df, left_on='id', right_on='aluno_id', how='inner')

    # --- CORREÇÃO APLICADA AQUI ---
    # Renomeia a coluna 'id_x' (ID do aluno) para 'id' para evitar o KeyError.
    if 'id_x' in dados_completos_df.columns:
        dados_completos_df.rename(columns={'id_x': 'id'}, inplace=True)

    # O componente para selecionar alunos agora pode ser exibido
    alunos_selecionados_df = render_alunos_filter_and_selection(
        key_suffix="docgen_transporte", 
        include_full_name_search=True
    )
    
    if alunos_selecionados_df.empty:
        st.info("Use os filtros para selecionar os alunos para os quais deseja gerar o documento.")
        return

    st.markdown(f"**{len(alunos_selecionados_df)} aluno(s) selecionado(s).**")
    
    st.markdown("#### 2. Gere o Documento Consolidado")
    if st.button(f"Gerar PDF para os {len(alunos_selecionados_df)} alunos", type="primary"):
        with st.spinner("Preparando para gerar os documentos..."):
            try:
                template_bytes = supabase.storage.from_("templates").download(NOME_TEMPLATE)
            except Exception as e:
                st.error(f"Falha ao carregar o modelo de PDF do sistema: {e}")
                st.warning("Por favor, faça o upload do modelo na seção 'Configurar Modelo de PDF' acima.")
                return

            # Filtra os dados completos para incluir apenas os alunos selecionados
            # Agora esta linha funciona, pois a coluna 'id' existe.
            ids_selecionados = alunos_selecionados_df['id'].tolist()
            dados_para_gerar_df = dados_completos_df[dados_completos_df['id'].isin(ids_selecionados)]

            if dados_para_gerar_df.empty:
                st.error("Nenhum dos alunos selecionados possui dados de transporte cadastrados para preencher o documento.")
                return

            filled_pdfs = []
            progress_bar = st.progress(0, text="Gerando documentos...")
            total_alunos = len(dados_para_gerar_df)

            for i, (_, aluno_row) in enumerate(dados_para_gerar_df.iterrows()):
                filled_pdfs.append(fill_pdf_auxilio(template_bytes, aluno_row))
                progress_bar.progress((i + 1) / total_alunos, text=f"Gerando documento para: {aluno_row['nome_guerra']}")
            
            final_pdf_buffer = merge_pdfs(filled_pdfs)
            st.session_state['final_pdf_auxilio'] = final_pdf_buffer.getvalue()

    if 'final_pdf_auxilio' in st.session_state:
        st.balloons()
        st.download_button(
            label="✅ Baixar Documento Consolidado (.pdf)",
            data=st.session_state['final_pdf_auxilio'],
            file_name="solicitacoes_auxilio_transporte.pdf",
            mime="application/pdf"
        )

# --- ABA DE IMPORTAÇÃO GUIADA ---
def importacao_guiada_tab(supabase):
    st.subheader("Assistente de Importação de Dados do Google Forms")
    st.markdown("#### Passo 1: Carregue o ficheiro (CSV ou Excel)")
    uploaded_file = st.file_uploader("Escolha o ficheiro...", type=["csv", "xlsx"])

    if not uploaded_file:
        st.info("Aguardando o upload do ficheiro para iniciar.")
        return

    try:
        df_import = pd.read_csv(uploaded_file, delimiter=';') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        st.session_state['df_import_cache'] = df_import
        st.session_state['import_file_columns'] = df_import.columns.tolist()
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return

    st.markdown("---")
    st.markdown("#### Passo 2: Mapeie as colunas do seu ficheiro")
    st.info("O sistema tenta pré-selecionar o seu último mapeamento.")

    config_df = load_data("Config")
    mapeamento_salvo = json.loads(config_df[config_df['chave'] == 'mapeamento_auxilio_transporte']['valor'].iloc[0]) if 'mapeamento_auxilio_transporte' in config_df['chave'].values else {}

    # --- LÓGICA DE MAPEAMENTO CORRIGIDA ---
    campos_sistema = {
        # Formato: "chave_no_sistema": ("Nome para Exibição", ([palavras_chave_inclusao], [palavras_chave_exclusao]))
        "numero_interno": ("Número Interno*", (["número interno"], [])),
        "ano_referencia": ("Ano de Referência*", (["ano"], [])),
        "endereco": ("Endereço Domiciliar", (["endereço"], [])),
        "bairro": ("Bairro", (["bairro"], [])),
        "cidade": ("Cidade", (["cidade"], [])),
        "cep": ("CEP", (["cep"], [])),
        "dias_uteis": ("Quantidade de Dias", (["dias"], [])),
    }
    for i in range(1, 5):
        campos_sistema[f'ida_{i}_empresa'] = (f"{i}ª Empresa (Ida)", ([f"{i}ª", "empresa"], ["volta"]))
        campos_sistema[f'ida_{i}_linha'] = (f"{i}ª Linha (Ida)", ([f"{i}º", "trajeto"], ["volta"]))
        campos_sistema[f'ida_{i}_tarifa'] = (f"{i}ª Tarifa (Ida)", ([f"{i}ª", "tarifa"], ["volta"]))
        campos_sistema[f'volta_{i}_empresa'] = (f"{i}ª Empresa (Volta)", ([f"{i}ª", "empresa", "volta"], []))
        campos_sistema[f'volta_{i}_linha'] = (f"{i}ª Linha (Volta)", ([f"{i}º", "trajeto", "volta"], []))
        campos_sistema[f'volta_{i}_tarifa'] = (f"{i}ª Tarifa (Volta)", ([f"{i}ª", "tarifa", "volta"], []))

    opcoes_ficheiro = ["-- Não importar este campo --"] + st.session_state['import_file_columns']

    def get_best_match_index(search_criteria, all_options, saved_option):
        if saved_option in all_options:
            return all_options.index(saved_option)
        
        must_include, must_exclude = search_criteria
        for i, option in enumerate(all_options):
            option_lower = option.lower()
            if all(inc.lower() in option_lower for inc in must_include) and not any(exc.lower() in option_lower for exc in must_exclude):
                return i
        return 0

    with st.form("mapping_form"):
        mapeamento_usuario = {}
        campos_gerais = ["numero_interno", "ano_referencia", "endereco", "bairro", "cidade", "cep", "dias_uteis"]
        st.markdown("**Dados Gerais e de Endereço**")
        cols_gerais = st.columns(3)
        for i, key in enumerate(campos_gerais):
            display_name, search_criteria = campos_sistema[key]
            index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
            mapeamento_usuario[key] = cols_gerais[i % 3].selectbox(f"**{display_name}**", options=opcoes_ficheiro, key=f"map_{key}", index=index)
        
        st.markdown("**Itinerários de Ida**")
        cols_ida = st.columns(4)
        for i in range(1, 5):
            with cols_ida[i-1]:
                st.markdown(f"**{i}º Trajeto (Ida)**")
                for tipo in ["empresa", "linha", "tarifa"]:
                    key = f"ida_{i}_{tipo}"
                    display_name, search_criteria = campos_sistema[key]
                    index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
                    mapeamento_usuario[key] = st.selectbox(display_name.split('(')[0].strip(), options=opcoes_ficheiro, key=f"map_{key}", index=index)

        st.markdown("**Itinerários de Volta**")
        cols_volta = st.columns(4)
        for i in range(1, 5):
            with cols_volta[i-1]:
                st.markdown(f"**{i}º Trajeto (Volta)**")
                for tipo in ["empresa", "linha", "tarifa"]:
                    key = f"volta_{i}_{tipo}"
                    display_name, search_criteria = campos_sistema[key]
                    index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
                    mapeamento_usuario[key] = st.selectbox(display_name.split('(')[0].strip(), options=opcoes_ficheiro, key=f"map_{key}", index=index)

        if st.form_submit_button("Validar Mapeamento e Pré-visualizar", type="primary"):
            st.session_state['mapeamento_final'] = mapeamento_usuario
            try:
                supabase.table("Config").upsert({"chave": "mapeamento_auxilio_transporte", "valor": json.dumps(mapeamento_usuario)}).execute()
                st.toast("Mapeamento salvo!", icon="💾")
            except Exception as e:
                st.warning(f"Não foi possível salvar o mapeamento: {e}")

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
