import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from io import BytesIO
import json
import re
from aluno_selection_components import render_alunos_filter_and_selection
from pypdf import PdfReader, PdfWriter

# --- FUNÇÕES AUXILIARES E DE CÁLCULO (DEFINIDAS PRIMEIRO) ---

def calcular_auxilio_transporte(linha):
    try:
        despesa_diaria = 0
        for i in range(1, 5):
            despesa_diaria += float(linha.get(f'ida_{i}_tarifa', 0.0) or 0.0)
            despesa_diaria += float(linha.get(f'volta_{i}_tarifa', 0.0) or 0.0)
        dias_trabalhados = min(int(linha.get('dias_uteis', 0) or 0), 22)
        despesa_mensal = despesa_diaria * dias_trabalhados
        soldo = float(linha.get('soldo', 0.0) or 0.0)
        parcela_beneficiario = ((soldo * 0.06) / 30) * dias_trabalhados if soldo > 0 and dias_trabalhados > 0 else 0.0
        auxilio_pago = max(0.0, despesa_mensal - parcela_beneficiario)
        return pd.Series({
            'despesa_diaria': round(despesa_diaria, 2),
            'despesa_mensal': round(despesa_mensal, 2),
            'parcela_beneficiario': round(parcela_beneficiario, 2),
            'auxilio_pago': round(auxilio_pago, 2)
        })
    except (ValueError, TypeError):
        return pd.Series({'despesa_diaria': 0.0, 'despesa_mensal': 0.0, 'parcela_beneficiario': 0.0, 'auxilio_pago': 0.0})

def create_excel_template():
    template_data = {
        'NÚMERO INTERNO DO ALUNO': ['M-01-101'],'ANO DE REFERÊNCIA': [2025],'POSTO/GRADUAÇÃO': ['ALUNO'],
        'ENDEREÇO COMPLETO': ['Rua Exemplo, 123'],'BAIRRO': ['Bairro Exemplo'],'CIDADE': ['Cidade Exemplo'],'CEP': ['12345-678'],
        'DIAS ÚTEIS (MÁX 22)': [22],'1ª EMPRESA (IDA)': ['Empresa A'],'1º TRAJETO (IDA)': ['Linha 100'],'1ª TARIFA (IDA)': [4.50],
        '2ª EMPRESA (IDA)': [''], '2º TRAJETO (IDA)': [''], '2ª TARIFA (IDA)': [''], '3ª EMPRESA (IDA)': [''], '3º TRAJETO (IDA)': [''], '3ª TARIFA (IDA)': [''],
        '4ª EMPRESA (IDA)': [''], '4º TRAJETO (IDA)': [''], '4ª TARIFA (IDA)': [''], '1ª EMPRESA (VOLTA)': ['Empresa A'],
        '1º TRAJETO (VOLTA)': ['Linha 100'], '1ª TARIFA (VOLTA)': [4.50], '2ª EMPRESA (VOLTA)': [''], '2º TRAJETO (VOLTA)': [''], '2ª TARIFA (VOLTA)': [''],
        '3ª EMPRESA (VOLTA)': [''], '3º TRAJETO (VOLTA)': [''], '3ª TARIFA (VOLTA)': [''], '4ª EMPRESA (VOLTA)': [''], '4º TRAJETO (VOLTA)': [''], '4ª TARIFA (VOLTA)': [''],
    }
    df = pd.DataFrame(template_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='ModeloAuxilioTransporte')
    return output.getvalue()

def fill_pdf_auxilio(template_bytes, aluno_data):
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter(clone_from=reader)
    pdf_field_mapping = {
        'NOME COMPLETO': 'nome_completo','NIP': 'nip','ENDEREÇO': 'endereco','BAIRRO': 'bairro',
        'CIDADE': 'cidade','CEP': 'cep','ANO': 'ano_referencia','DESPESA DIARIA': 'despesa_diaria',
        'DESPESA MENSAL': 'despesa_mensal','PARCELA 6%': 'parcela_beneficiario','VALOR FINAL': 'auxilio_pago'
    }
    fill_data = {}
    for pdf_field, df_column in pdf_field_mapping.items():
        valor = aluno_data.get(df_column, '')
        if df_column in ['despesa_diaria', 'despesa_mensal', 'parcela_beneficiario', 'auxilio_pago']:
            fill_data[pdf_field] = f"R$ {float(valor):.2f}"
        else:
            fill_data[pdf_field] = str(valor)
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

def merge_pdfs(pdf_buffers):
    merger = PdfWriter()
    for buffer in pdf_buffers:
        reader = PdfReader(buffer)
        for page in reader.pages:
            merger.add_page(page)
    merged_pdf_buffer = BytesIO()
    merger.write(merged_pdf_buffer)
    merged_pdf_buffer.seek(0)
    return merged_pdf_buffer


# --- DEFINIÇÃO DAS FUNÇÕES DE CADA ABA (COMPLETAS) ---

# No ficheiro auxilio_transporte.py, substitua esta função
def importacao_guiada_tab(supabase):
    st.subheader("Assistente de Importação de Dados")
    st.markdown("#### Passo 1: Baixe o modelo e preencha com os dados")
    st.info("Use o modelo padrão para garantir que as colunas sejam reconhecidas corretamente durante a importação.")
    excel_modelo_bytes = create_excel_template()
    st.download_button(label="📥 Baixar Modelo de Preenchimento (.xlsx)",data=excel_modelo_bytes,file_name="modelo_auxilio_transporte.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    st.markdown("#### Passo 2: Carregue o ficheiro preenchido")
    uploaded_file = st.file_uploader("Escolha o ficheiro...", type=["csv", "xlsx"], key="importer_uploader_at")

    if not uploaded_file:
        st.info("Aguardando o upload do ficheiro para iniciar.")
        return

    try:
        df_import = pd.read_csv(uploaded_file, delimiter=';', encoding='latin-1') if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
        st.session_state['df_import_cache_at'] = df_import
    except Exception as e:
        st.error(f"Erro ao ler o ficheiro: {e}")
        return

    st.markdown("---")
    st.markdown("#### Passo 3: Mapeie as colunas do seu ficheiro")
    config_df = load_data("Config")
    mapeamento_salvo = json.loads(config_df[config_df['chave'] == 'mapeamento_auxilio_transporte']['valor'].iloc[0]) if 'mapeamento_auxilio_transporte' in config_df['chave'].values else {}

    campos_sistema = {
        "numero_interno": ("Número Interno*", (["número interno"], [])),"ano_referencia": ("Ano de Referência*", (["ano"], [])),"posto_grad": ("Posto/Graduação*", (["posto", "graduação"], [])),
        "endereco": ("Endereço*", (["endereço"], [])), "bairro": ("Bairro*", (["bairro"], [])), "cidade": ("Cidade*", (["cidade"], [])), "cep": ("CEP*", (["cep"], [])),
        "dias_uteis": ("Dias*", (["dias"], [])),
    }
    for i in range(1, 5):
        obrigatorio = "*" if i == 1 else ""
        campos_sistema[f'ida_{i}_empresa'] = (f"{i}ª Empresa (Ida){obrigatorio}", ([f"{i}ª", "empresa"], ["volta"]))
        campos_sistema[f'ida_{i}_linha'] = (f"{i}ª Linha (Ida){obrigatorio}", ([f"{i}º", "trajeto"], ["volta"]))
        campos_sistema[f'ida_{i}_tarifa'] = (f"{i}ª Tarifa (Ida){obrigatorio}", ([f"{i}ª", "tarifa"], ["volta"]))
        campos_sistema[f'volta_{i}_empresa'] = (f"{i}ª Empresa (Volta){obrigatorio}", ([f"{i}ª", "empresa", "volta"], []))
        campos_sistema[f'volta_{i}_linha'] = (f"{i}ª Linha (Volta){obrigatorio}", ([f"{i}º", "trajeto", "volta"], []))
        campos_sistema[f'volta_{i}_tarifa'] = (f"{i}ª Tarifa (Volta){obrigatorio}", ([f"{i}ª", "tarifa", "volta"], []))

    opcoes_ficheiro = ["-- Não importar este campo --"] + df_import.columns.tolist()

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
            display_name, search_criteria = campos_sistema.get(key, (key, ([], [])))
            index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
            # --- ALTERAÇÃO 1 (Parte A) ---
            label_geral = f"**{display_name}** `(Sistema: {key})`"
            mapeamento_usuario[key] = cols_gerais[i % 3].selectbox(label_geral, options=opcoes_ficheiro, key=f"map_at_{key}", index=index)

        st.markdown("**Itinerários**")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Ida**")
            for i in range(1, 5):
                st.markdown(f"**{i}º Trajeto (Ida)**")
                for tipo in ["empresa", "linha", "tarifa"]:
                    key = f"ida_{i}_{tipo}"
                    display_name, search_criteria = campos_sistema.get(key, (key, ([], [])))
                    index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
                    # --- ALTERAÇÃO 1 (Parte B) ---
                    label_itinerario = f"{display_name} `(Sistema: {key})`"
                    mapeamento_usuario[key] = st.selectbox(label_itinerario, options=opcoes_ficheiro, key=f"map_at_{key}", index=index, label_visibility="collapsed")
        with c2:
            st.markdown("**Volta**")
            for i in range(1, 5):
                st.markdown(f"**{i}º Trajeto (Volta)**")
                for tipo in ["empresa", "linha", "tarifa"]:
                    key = f"volta_{i}_{tipo}"
                    display_name, search_criteria = campos_sistema.get(key, (key, ([], [])))
                    index = get_best_match_index(search_criteria, opcoes_ficheiro, mapeamento_salvo.get(key))
                    # --- ALTERAÇÃO 1 (Parte C) ---
                    label_itinerario = f"{display_name} `(Sistema: {key})`"
                    mapeamento_usuario[key] = st.selectbox(label_itinerario, options=opcoes_ficheiro, key=f"map_at_{key}", index=index, label_visibility="collapsed")

        if st.form_submit_button("Validar Mapeamento e Pré-visualizar", type="primary"):
            st.session_state['mapeamento_final_at'] = mapeamento_usuario
            try:
                supabase.table("Config").upsert({"chave": "mapeamento_auxilio_transporte", "valor": json.dumps(mapeamento_usuario)}).execute()
                st.toast("Mapeamento salvo!", icon="💾")
            except Exception as e:
                st.warning(f"Não foi possível salvar o mapeamento: {e}")

    if 'mapeamento_final_at' in st.session_state:
        st.markdown("---")
        st.markdown("#### Passo 4: Valide os dados antes de importar")
        
        # --- ALTERAÇÃO 2: Bloco de validação inteiro foi reescrito ---
        with st.spinner("Processando e validando os dados..."):
            df_processado = pd.DataFrame()
            system_to_user_map = {k: v for k, v in st.session_state['mapeamento_final_at'].items() if v != '-- Não importar este campo --'}
            for system_col, user_col in system_to_user_map.items():
                if user_col in df_import.columns:
                    df_processado[system_col] = df_import[user_col]

            campos_obrigatorios = [
                'numero_interno', 'ano_referencia', 'posto_grad', 'endereco', 'bairro', 'cidade', 'cep', 'dias_uteis',
                'ida_1_empresa', 'ida_1_linha', 'ida_1_tarifa', 'volta_1_empresa', 'volta_1_linha', 'volta_1_tarifa'
            ]

            colunas_mapeadas = df_processado.columns.tolist()
            if not all(campo in colunas_mapeadas for campo in campos_obrigatorios):
                campos_em_falta = [c for c in campos_obrigatorios if c not in colunas_mapeadas]
                st.error(f"Erro: Nem todos os campos obrigatórios foram mapeados. Faltam: {', '.join(campos_em_falta)}. Por favor, volte ao Passo 3.")
                return

            # Identificar linhas com dados faltando ANTES de removê-las
            linhas_com_dados_faltando = df_processado[df_processado[campos_obrigatorios].isnull().any(axis=1)]
            erros_detalhados = []
            if not linhas_com_dados_faltando.empty:
                for index, row in linhas_com_dados_faltando.iterrows():
                    campos_vazios = [col for col in campos_obrigatorios if pd.isnull(row[col])]
                    num_interno = row.get('numero_interno', f"Linha {index + 2} do arquivo")
                    erros_detalhados.append(f"- **Aluno {num_interno}:** Campos obrigatórios vazios: `{', '.join(campos_vazios)}`.")

            # Manter apenas as linhas completas
            df_completos = df_processado.dropna(subset=campos_obrigatorios).copy()
            
            # Cruzar com a base de alunos
            alunos_df = load_data("Alunos")[['numero_interno', 'nome_guerra']]
            df_completos['numero_interno'] = df_completos['numero_interno'].astype(str).str.strip().str.upper()
            alunos_df['numero_interno'] = alunos_df['numero_interno'].astype(str).str.strip().str.upper()

            registos_finais = pd.merge(df_completos, alunos_df, on='numero_interno', how='inner')
            
            # Identificar alunos não encontrados no sistema
            numeros_internos_completos = set(df_completos['numero_interno'])
            numeros_internos_finais = set(registos_finais['numero_interno'])
            alunos_nao_encontrados = numeros_internos_completos - numeros_internos_finais
            if alunos_nao_encontrados:
                for num_interno in alunos_nao_encontrados:
                     erros_detalhados.append(f"- **Aluno {num_interno}:** Não foi encontrado na base de dados de alunos do sistema.")

            st.success(f"Validação Concluída! Foram encontrados **{len(registos_finais)}** registos completos e válidos para importação.")
            
            # Exibir erros detalhados, se houver
            total_original = len(df_import)
            if len(registos_finais) < total_original:
                 st.warning(f"**Atenção:** {total_original - len(registos_finais)} de {total_original} registros não puderam ser importados.")
                 with st.expander("Clique aqui para ver os detalhes dos erros"):
                      st.markdown("\n".join(erros_detalhados))

            if not registos_finais.empty:
                st.markdown("**Pré-visualização dos registos a serem importados:**")
                st.dataframe(registos_finais)
            
            st.session_state['registros_para_importar_at'] = registos_finais

    if 'registros_para_importar_at' in st.session_state and not st.session_state['registros_para_importar_at'].empty:
         if st.button("Confirmar e Salvar no Sistema", type="primary"):
            with st.spinner("Salvando dados..."):
                try:
                    payload = st.session_state['registros_para_importar_at'].copy()
                    
                    for col in ['ano_referencia', 'dias_uteis']:
                        if col in payload.columns: payload[col] = pd.to_numeric(payload[col], errors='coerce').fillna(0).astype(int)
                    for col in payload.columns:
                        if 'tarifa' in col: payload[col] = pd.to_numeric(payload[col].astype(str).str.replace(',', '.'), errors='coerce').fillna(0.0)

# ...

# ...
                    
                    colunas_a_remover = ['nome_guerra']
                    payload.drop(columns=colunas_a_remover, inplace=True, errors='ignore')
                    
                    supabase.table("auxilio_trans
                    
                                   porte").upsert(
                        payload.to_dict(orient='records'),
                        on_conflict='numero_interno,ano_referencia'
                    ).execute()
                    
                    st.success(f"**Importação Concluída!** {len(payload)} registros salvos.")
                    for key in ['df_import_cache_at', 'mapeamento_final_at', 'registros_para_importar_at']:
                        if key in st.session_state: del st.session_state[key]
                    load_data.clear()
                except Exception as e:
                    st.error(f"**Erro na importação final:** {e}")

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
        dados_aluno = transporte_df[transporte_df['numero_interno'] == aluno_atual['numero_interno']].sort_values('ano_referencia', ascending=False)
        if not dados_aluno.empty:
            dados_atuais = dados_aluno.iloc[0].to_dict()

    with st.form("form_individual_at"):
        c1, c2, c3 = st.columns(3)
        ano_referencia = c1.number_input("Ano*", value=int(dados_atuais.get('ano_referencia', 2025)))
        posto_grad = c2.selectbox("Posto/Graduação*", options=opcoes_posto_grad, index=opcoes_posto_grad.index(dados_atuais.get('posto_grad', '')) if dados_atuais.get('posto_grad') in opcoes_posto_grad else 0)
        dias_uteis = c3.number_input("Dias Úteis*", value=int(dados_atuais.get('dias_uteis', 22)))
        
        endereco = st.text_input("Endereço*", value=dados_atuais.get('endereco', ''))
        c4,c5,c6 = st.columns(3)
        bairro = c4.text_input("Bairro*", value=dados_atuais.get('bairro', ''))
        cidade = c5.text_input("Cidade*", value=dados_atuais.get('cidade', ''))
        cep = c6.text_input("CEP*", value=dados_atuais.get('cep', ''))
        
        ida_data = {}
        volta_data = {}
        st.markdown("**Itinerários (1º Trajeto de Ida e Volta são obrigatórios)**")
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
            campos_obrigatorios_check = {
                "Posto/Graduação": posto_grad, "Endereço": endereco, "Bairro": bairro, "Cidade": cidade, "CEP": cep,
                "Empresa Ida 1": ida_data['empresa_1'], "Linha Ida 1": ida_data['linha_1'],
                "Empresa Volta 1": volta_data['empresa_1'], "Linha Volta 1": volta_data['linha_1']
            }
            campos_em_falta = [nome for nome, valor in campos_obrigatorios_check.items() if not valor]
            if campos_em_falta:
                st.error(f"Erro: Os seguintes campos obrigatórios devem ser preenchidos: {', '.join(campos_em_falta)}")
            else:
                dados_para_salvar = { "numero_interno": aluno_atual['numero_interno'], "ano_referencia": ano_referencia, "posto_grad": posto_grad, "dias_uteis": dias_uteis,
                                      "endereco": endereco, "bairro": bairro, "cidade": cidade, "cep": cep }
                for i in range(1, 5):
                    dados_para_salvar[f'ida_{i}_empresa'] = ida_data[f'empresa_{i}']
                    dados_para_salvar[f'ida_{i}_linha'] = ida_data[f'linha_{i}']
                    dados_para_salvar[f'ida_{i}_tarifa'] = ida_data[f'tarifa_{i}']
                    dados_para_salvar[f'volta_{i}_empresa'] = volta_data[f'empresa_{i}']
                    dados_para_salvar[f'volta_{i}_linha'] = volta_data[f'linha_{i}']
                    dados_para_salvar[f'volta_{i}_tarifa'] = volta_data[f'tarifa_{i}']
                try:
                    supabase.table("auxilio_transporte").upsert(dados_para_salvar, on_conflict='numero_interno,ano_referencia').execute()
                    st.success("Dados salvos com sucesso!")
                    load_data.clear()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

def gestao_decat_tab(supabase):
    st.subheader("Dados de Transporte Cadastrados (com Cálculo)")
    alunos_df = load_data("Alunos")[['numero_interno', 'nome_guerra']]
    transporte_df = load_data("auxilio_transporte")
    soldos_df = load_data("soldos")
    if transporte_df.empty:
        st.warning("Nenhum dado de auxílio transporte cadastrado.")
        return
    
    dados_completos_df = pd.merge(transporte_df, alunos_df, on='numero_interno', how='left')
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
        try:
            colunas_db = [col for col in colunas_editaveis + ['numero_interno', 'ano_referencia'] if col in edited_df.columns]
            records_to_upsert = edited_df[colunas_db].to_dict(orient='records')
            supabase.table("auxilio_transporte").upsert(records_to_upsert, on_conflict='numero_interno,ano_referencia').execute()
            st.success("Alterações salvas com sucesso!")
            load_data.clear()
        except Exception as e:
            st.error(f"Erro ao salvar alterações: {e}")

def gerar_documento_tab(supabase):
    st.subheader("Gerador de Documentos de Solicitação")
    NOME_TEMPLATE = "auxilio_transporte_template.pdf"
    with st.expander("Configurar e Diagnosticar Modelo de PDF", expanded=True):
        st.info("Faça o upload do seu modelo PDF preenchível. O sistema irá analisar o ficheiro e listar os campos de texto encontrados abaixo.")
        uploaded_template = st.file_uploader("Selecione o seu modelo PDF", type="pdf", key="pdf_template_uploader")
        if uploaded_template:
            try:
                reader = PdfReader(BytesIO(uploaded_template.getvalue()))
                if reader.get_form_text_fields():
                    fields = reader.get_form_text_fields().keys()
                    st.success("✅ Campos de texto encontrados neste PDF:")
                    st.text_area("Use estes nomes para ajustar o mapeamento no código (função fill_pdf_auxilio)", value="\n".join(fields), height=200)
                else:
                    st.warning("⚠️ Atenção: Nenhum campo de formulário editável (caixa de texto) foi encontrado neste PDF.")
            except Exception as e:
                st.error(f"Não foi possível ler os campos do PDF: {e}")
        if uploaded_template:
            if st.button("Salvar Modelo no Sistema"):
                with st.spinner("Salvando modelo..."):
                    try:
                        supabase.storage.from_("templates").upload(NOME_TEMPLATE, uploaded_template.getvalue(), {"content-type": "application/pdf", "x-upsert": "true"})
                        st.success("Modelo salvo com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar o modelo: {e}")
    st.divider()
    st.markdown("#### 1. Selecione os Alunos")
    alunos_df = load_data("Alunos")
    transporte_df = load_data("auxilio_transporte")
    soldos_df = load_data("soldos")
    if transporte_df.empty:
        st.warning("Nenhum dado de transporte foi cadastrado para preencher os documentos.")
        return
    
    dados_completos_df = pd.merge(transporte_df, alunos_df, on='numero_interno', how='left')
    dados_completos_df = pd.merge(dados_completos_df, soldos_df, left_on='posto_grad', right_on='graduacao', how='left')
    calculos_df = dados_completos_df.apply(calcular_auxilio_transporte, axis=1)
    dados_completos_df = pd.concat([dados_completos_df, calculos_df], axis=1)
    
    alunos_selecionados_df = render_alunos_filter_and_selection(key_suffix="docgen_transporte", include_full_name_search=True)
    if alunos_selecionados_df.empty:
        st.info("Use os filtros para selecionar os alunos.")
        return
    st.markdown(f"**{len(alunos_selecionados_df)} aluno(s) selecionado(s).**")
    st.markdown("#### 2. Gere o Documento Consolidado")
    if st.button(f"Gerar PDF para os {len(alunos_selecionados_df)} alunos", type="primary"):
        with st.spinner("Preparando..."):
            try:
                template_bytes = supabase.storage.from_("templates").download(NOME_TEMPLATE)
            except Exception as e:
                st.error(f"Falha ao carregar o modelo de PDF: {e}. Faça o upload na seção acima.")
                return
            
            numeros_internos_selecionados = alunos_selecionados_df['numero_interno'].tolist()
            dados_para_gerar_df = dados_completos_df[dados_completos_df['numero_interno'].isin(numeros_internos_selecionados)]
            
            if dados_para_gerar_df.empty:
                st.error("Nenhum dos alunos selecionados possui dados de transporte cadastrados.")
                return

            filled_pdfs = []
            progress_bar = st.progress(0, text=f"Gerando {len(dados_para_gerar_df)} documentos...")
            for i, (_, aluno_row) in enumerate(dados_para_gerar_df.iterrows()):
                filled_pdfs.append(fill_pdf_auxilio(template_bytes, aluno_row))
                progress_bar.progress((i + 1) / len(dados_para_gerar_df), text=f"Gerando: {aluno_row['nome_guerra']}")
            final_pdf_buffer = merge_pdfs(filled_pdfs)
            st.session_state['final_pdf_auxilio'] = final_pdf_buffer.getvalue()

    if 'final_pdf_auxilio' in st.session_state:
        st.balloons()
        st.download_button(label="✅ Baixar Documento Consolidado (.pdf)", data=st.session_state['final_pdf_auxilio'], file_name="solicitacoes_auxilio_transporte.pdf", mime="application/pdf")

def gestao_soldos_tab(supabase):
    st.subheader("Tabela de Soldos por Graduação")
    soldos_df = load_data("soldos")
    if 'id' in soldos_df.columns: soldos_df = soldos_df.drop(columns=['id'])
    edited_df = st.data_editor(soldos_df, num_rows="dynamic", use_container_width=True)
    if st.button("Salvar Alterações nos Soldos"):
        try:
            supabase.table("soldos").upsert(edited_df.to_dict(orient='records'), on_conflict='graduacao').execute()
            st.success("Tabela de soldos atualizada!")
            load_data.clear()
        except Exception as e:
            st.error(f"Erro ao salvar os soldos: {e}")

# --- FUNÇÃO PRINCIPAL QUE É IMPORTADA PELO app.py ---
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
