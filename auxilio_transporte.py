import streamlit as st
import pandas as pd
from io import BytesIO
from pypdf import PdfReader # CORREÇÃO 1: Importação adicionada

# --- Bloco de Funções Essenciais ---

def create_excel_template():
    """Cria um template XLSX vazio com o cabeçalho correto para download."""
    colunas_template = [
        'Carimbo de data/hora', 'NÚMERO INTERNO DO ALUNO', 'NOME COMPLETO', 'POSTO/GRAD', 'SOLDO',
        'DIAS ÚTEIS (MÁX 22)', 'ANO DE REFERÊNCIA', 'ENDEREÇO COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
        '1ª EMPRESA (IDA)', '1º TRAJETO (IDA)', '1ª TARIFA (IDA)', '1ª EMPRESA (VOLTA)', '1º TRAJETO (VOLTA)', '1ª TARIFA (VOLTA)',
        '2ª EMPRESA (IDA)', '2º TRAJETO (IDA)', '2ª TARIFA (IDA)', '2ª EMPRESA (VOLTA)', '2º TRAJETO (VOLTA)', '2ª TARIFA (VOLTA)',
        '3ª EMPRESA (IDA)', '3º TRAJETO (IDA)', '3ª TARIFA (IDA)', '3ª EMPRESA (VOLTA)', '3º TRAJETO (VOLTA)', '3ª TARIFA (VOLTA)',
        '4ª EMPRESA (IDA)', '4º TRAJETO (IDA)', '4ª TARIFA (IDA)', '4ª EMPRESA (VOLTA)', '4º TRAJETO (VOLTA)', '4ª TARIFA (VOLTA)'
    ]
    df_template = pd.DataFrame(columns=colunas_template)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Modelo')
    return output.getvalue()

def formatar_nip(nip):
    """Formata uma string de 8 dígitos para XX.XXXX.XX"""
    nip_str = str(nip).strip()
    if len(nip_str) == 8 and nip_str.isdigit():
        return f"{nip_str[:2]}.{nip_str[2:6]}.{nip_str[6:]}"
    return nip # Retorna o original se não for um NIP válido de 8 dígitos

def preparar_dataframe(df):
    """Limpa, renomeia e padroniza o DataFrame carregado."""
    df = df.iloc[:, 1:].copy()
    mapa_colunas = {
        'NÚMERO INTERNO DO ALUNO': 'numero_interno', 'NOME COMPLETO': 'nome_completo', 'POSTO/GRAD': 'graduacao',
        'SOLDO': 'soldo', 'DIAS ÚTEIS (MÁX 22)': 'dias_uteis', 'ANO DE REFERÊNCIA': 'ano_referencia',
        'ENDEREÇO COMPLETO': 'endereco', 'BAIRRO': 'bairro', 'CIDADE': 'cidade', 'CEP': 'cep'
    }
    for i in range(1, 5):
        for direcao in ["IDA", "VOLTA"]:
            mapa_colunas[f'{i}ª EMPRESA ({direcao})'] = f'{direcao.lower()}_{i}_empresa'
            mapa_colunas[f'{i}º TRAJETO ({direcao})'] = f'{direcao.lower()}_{i}_linha'
            mapa_colunas[f'{i}ª TARIFA ({direcao})'] = f'{direcao.lower()}_{i}_tarifa'
    df.rename(columns=mapa_colunas, inplace=True, errors='ignore')
    
    # CORREÇÃO 2: Converter todas as colunas de texto para MAIÚSCULAS
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].str.upper()

    colunas_numericas = ['dias_uteis', 'soldo'] + [f'ida_{i}_tarifa' for i in range(1, 5)] + [f'volta_{i}_tarifa' for i in range(1, 5)]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    df.fillna(0, inplace=True)
    return df

def calcular_auxilio_transporte(linha):
    # Sua função de cálculo permanece a mesma...
    try:
        despesa_diaria = 0
        for i in range(1, 5):
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
    except Exception:
        return pd.Series()

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Geração de Declaração de Auxílio Transporte")
    st.markdown("---")

    tab1, tab2, tab3, tab4 = st.tabs(["1. Carregar Dados", "2. Editar & Consultar", "3. Mapeamento do PDF", "4. Gerar Documentos"])

    with tab1:
        st.subheader("Carregar Ficheiro de Dados")
        st.info("Para começar, baixe o modelo padrão ou carregue o seu ficheiro CSV preenchido.")
        
        # FUNCIONALIDADE 6: Botão para baixar modelo
        modelo_bytes = create_excel_template()
        st.download_button(label="📥 Baixar Modelo Padrão (.xlsx)", data=modelo_bytes, file_name="modelo_auxilio_transporte.xlsx")
        
        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV de dados", type="csv")
        if uploaded_file:
            if st.button("Carregar e Preparar Ficheiro"):
                with st.spinner("Processando..."):
                    try:
                        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                        df_preparado = preparar_dataframe(df)
                        st.session_state['dados_brutos'] = df_preparado
                        st.session_state['nome_ficheiro'] = uploaded_file.name
                        st.success("Ficheiro carregado com sucesso! Vá para a aba '2. Editar & Consultar'.")
                    except Exception as e:
                        st.error(f"Erro ao ler o ficheiro: {e}")
    
    with tab2:
        st.subheader("Editar e Consultar Cadastros")
        if 'dados_brutos' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar Dados' primeiro.")
        else:
            # FUNCIONALIDADE 5: Busca por número interno
            st.markdown("##### Buscar um Cadastro Específico")
            numero_busca = st.text_input("Digite o Número Interno para buscar:")
            
            df_para_editar = st.session_state['dados_brutos'].copy()

            if numero_busca:
                df_filtrado = df_para_editar[df_para_editar['numero_interno'].str.contains(numero_busca.upper(), na=False)]
                st.write(f"Encontrados {len(df_filtrado)} registos:")
                st.dataframe(df_filtrado)
            
            st.markdown("##### Edição da Tabela Completa")
            st.info("Você pode editar os dados diretamente na tabela abaixo. As alterações serão usadas na geração do PDF.")
            df_editado = st.data_editor(df_para_editar, num_rows="dynamic", use_container_width=True)
            st.session_state['dados_editados'] = df_editado
            
            st.markdown("##### Exportar Dados Atuais")
            if st.button("Preparar Ficheiro para Download"):
                df_para_exportar = st.session_state['dados_editados'].copy()
                # CORREÇÃO 3: Formatar a coluna NIP
                if 'numero_interno' in df_para_exportar.columns:
                    df_para_exportar['numero_interno'] = df_para_exportar['numero_interno'].apply(formatar_nip)
                
                csv = df_para_exportar.to_csv(index=False, sep=';').encode('latin-1')
                st.session_state['download_csv'] = csv

            if 'download_csv' in st.session_state:
                st.download_button(label="📥 Baixar CSV Editado", data=st.session_state.pop('download_csv'),
                                   file_name=f"dados_editados_{st.session_state.get('nome_ficheiro', 'file.csv')}", mime='text/csv')

    with tab3:
        st.subheader("Mapear Campos do PDF")
        if 'dados_editados' not in st.session_state:
            st.warning("Por favor, carregue e valide os dados na aba '1. Carregar e Editar Dados' primeiro.")
        else:
            st.info("Faça o upload do seu modelo PDF preenchível para mapear os campos.")
            pdf_template = st.file_uploader("Carregue o modelo PDF", type="pdf")

            if pdf_template:
                try:
                    reader = PdfReader(BytesIO(pdf_template.getvalue()))
                    pdf_fields = list(reader.get_form_text_fields().keys())
                    
                    if not pdf_fields:
                        st.warning("Nenhum campo de formulário editável encontrado neste PDF.")
                    else:
                        st.success(f"{len(pdf_fields)} campos encontrados no PDF.")
                        df_para_mapear = st.session_state['dados_editados']
                        colunas_sistema = ["-- Não Mapeado --"] + sorted(df_para_mapear.columns.tolist())
                        
                        with st.form("pdf_mapping_form"):
                            mapeamento_usuario = {}
                            st.markdown("**Mapeie cada campo do seu PDF para uma coluna do seu ficheiro:**")
                            for field in pdf_fields:
                                # Lógica de mapeamento "inteligente" (sugestão)
                                best_guess = next((s for s in colunas_sistema if field.replace("_", " ").lower() in s.lower()), "-- Não Mapeado --")
                                index = colunas_sistema.index(best_guess) if best_guess in colunas_sistema else 0
                                mapeamento_usuario[field] = st.selectbox(f"Campo do PDF: `{field}`", options=colunas_sistema, index=index)
                            
                            if st.form_submit_button("Salvar Mapeamento", type="primary"):
                                st.session_state['mapeamento_pdf'] = mapeamento_usuario
                                st.success("Mapeamento salvo com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao processar o PDF: {e}")

    # --- ABA 3: GERAR DOCUMENTOS ---
    with tab4:
        st.subheader("Gerar Documentos Finais")
        if 'dados_editados' not in st.session_state or 'mapeamento_pdf' not in st.session_state:
            st.warning("Por favor, complete os passos nas abas 1 e 2 primeiro.")
        else:
            df_final = st.session_state['dados_editados'].copy()
            
            # Aplica os cálculos aos dados já editados
            calculos_df = df_final.apply(calcular_auxilio_transporte, axis=1)
            df_final = pd.concat([df_final, calculos_df], axis=1)

            st.markdown("#### Filtro para Seleção")
            st.info("Selecione os militares para os quais deseja gerar o documento. Deixe em branco para selecionar todos.")
            
            opcoes_filtro = df_final['nome_completo'].tolist()
            selecionados = st.multiselect("Selecione por Nome Completo:", options=opcoes_filtro)
            
            if selecionados:
                df_para_gerar = df_final[df_final['nome_completo'].isin(selecionados)]
            else:
                df_para_gerar = df_final # Se nada for selecionado, usa todos

            st.dataframe(df_para_gerar)

            if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                st.info("Lógica de geração de PDF a ser conectada aqui.")
                # Aqui você chamaria a sua lógica para preencher e juntar os PDFs,
                # usando o 'df_para_gerar' e o 'st.session_state['mapeamento_pdf']'.
