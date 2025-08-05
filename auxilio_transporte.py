import streamlit as st
import pandas as pd
from io import BytesIO
import traceback
import re

# Importe as suas funções de geração de PDF a partir do ficheiro de utilitários
from pdf_utils import fill_pdf_auxilio, merge_pdfs
from pypdf import PdfReader

# --- Bloco de Funções Essenciais ---

def create_excel_template():
    """Cria um template XLSX vazio com o cabeçalho correto para download."""
    colunas_template = [
        'Carimbo de data/hora', 'NÚMERO INTERNO DO ALUNO', 'NOME COMPLETO', 'POSTO/GRAD', 'SOLDO',
        'DIAS ÚTEIS (MÁX 22)', 'ANO DE REFERÊNCIA', 'ENDEREÇO COMPLETO', 'BAIRRO', 'CIDADE', 'CEP',
        '1ª EMPRESA (IDA)', '1º TRAJETO (IDA)', '1ª TARIFA (IDA)', '1ª EMPRESA (VOLTA)', '1º TRAJETO (VOLTA)', '1ª TARIFA (VOLTA)',
        '2ª EMPRESA (IDA)', '2º TRAJETO (IDA)', '2ª TARIFA (IDA)', '2ª EMPRESA (VOLTA)', '2º TRAJETO (VOLTA)', '2ª TARIFA (VOLTA)',
        # Adicione mais colunas até o 5º trajeto se necessário
    ]
    df_template = pd.DataFrame(columns=colunas_template)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_template.to_excel(writer, index=False, sheet_name='Modelo')
    return output.getvalue()

def calcular_auxilio_transporte(linha):
    """Calcula os valores do auxílio transporte para uma única linha de dados."""
    try:
        despesa_diaria = 0
        for i in range(1, 6):
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
            'despesa_diaria': round(despesa_diaria, 2),
            'dias_trabalhados': dias_trabalhados,
            'despesa_mensal_total': round(despesa_mensal, 2),
            'parcela_descontada_6_porcento': round(parcela_beneficiario, 2),
            'auxilio_transporte_pago': round(auxilio_pago, 2)
        })
    except Exception as e:
        print(f"Erro no cálculo para NIP {linha.get('numero_interno', 'N/A')}: {e}")
        return pd.Series()

def preparar_dataframe(df):
    """Prepara o DataFrame do CSV, incluindo a coluna 'SOLDO'."""
    df_copy = df.iloc[:, 1:].copy()
    mapa_colunas = {
        'NÚMERO INTERNO DO ALUNO': 'numero_interno', 'NOME COMPLETO': 'nome_completo', 'POSTO/GRAD': 'graduacao',
        'SOLDO': 'soldo',
        'DIAS ÚTEIS (MÁX 22)': 'dias_uteis', 'ANO DE REFERÊNCIA': 'ano_referencia',
        'ENDEREÇO COMPLETO': 'endereco', 'BAIRRO': 'bairro', 'CIDADE': 'cidade', 'CEP': 'cep'
    }
    for i in range(1, 6):
        for direcao in ["IDA", "VOLTA"]:
            mapa_colunas[f'{i}ª EMPRESA ({direcao})'] = f'{direcao.lower()}_{i}_empresa'
            mapa_colunas[f'{i}º TRAJETO ({direcao})'] = f'{direcao.lower()}_{i}_linha'
            mapa_colunas[f'{i}ª TARIFA ({direcao})'] = f'{direcao.lower()}_{i}_tarifa'
            
    df_copy.rename(columns=mapa_colunas, inplace=True, errors='ignore')
    
    for col in df_copy.select_dtypes(include=['object']).columns:
        df_copy[col] = df_copy[col].str.upper().str.strip()

    colunas_numericas = ['soldo', 'dias_uteis'] + [f'ida_{i}_tarifa' for i in range(1, 6)] + [f'volta_{i}_tarifa' for i in range(1, 6)]
    for col in colunas_numericas:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].astype(str).str.replace('R$', '', regex=False).str.strip()
            df_copy[col] = pd.to_numeric(df_copy[col].str.replace(',', '.'), errors='coerce')
    
    df_copy.fillna(0, inplace=True)
    return df_copy

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Gestão de Auxílio Transporte (Baseado em Ficheiro)")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["1. Carregar e Editar Dados", "2. Mapeamento PDF", "3. Gerar Documentos"])

    with tab1:
        st.subheader("Carregar e Editar Ficheiro de Dados")

        # Botão para baixar o modelo de preenchimento
        st.markdown("##### Modelo de Preenchimento")
        modelo_bytes = create_excel_template()
        st.download_button(
            label="📥 Baixar Modelo Padrão (.xlsx)",
            data=modelo_bytes,
            file_name="modelo_auxilio_transporte.xlsx"
        )
        st.markdown("---")

        if 'dados_em_memoria' in st.session_state:
            st.info(f"Ficheiro em memória: **{st.session_state['nome_ficheiro']}**")
            if st.button("🗑️ Limpar Ficheiro e Recomeçar"):
                for key in ['dados_em_memoria', 'nome_ficheiro', 'mapeamento_pdf', 'pdf_template_bytes']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV com todos os dados", type="csv")

        if uploaded_file:
            if st.button(f"Processar Ficheiro: {uploaded_file.name}", type="primary"):
                with st.spinner("Processando..."):
                    try:
                        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                        df_preparado = preparar_dataframe(df)
                        st.session_state['dados_em_memoria'] = df_preparado
                        st.session_state['nome_ficheiro'] = uploaded_file.name
                        st.success("Ficheiro processado!")
                    except Exception as e:
                        st.error(f"Erro ao ler o ficheiro: {e}")

        if 'dados_em_memoria' in st.session_state:
            st.markdown("---")
            st.markdown("##### Tabela de Dados para Edição")
            st.info("As alterações feitas aqui são usadas nas outras abas. Para salvá-las, baixe o CSV editado.")

            df_editado = st.data_editor(
                st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True
            )
            st.session_state['dados_em_memoria'] = df_editado 

            csv_editado = df_editado.to_csv(index=False, sep=';').encode('latin-1')
            st.download_button(
                label="📥 Baixar CSV Editado", data=csv_editado,
                file_name=f"dados_editados_{st.session_state['nome_ficheiro']}"
            )
   # --- ABA 2: EDIÇÃO INDIVIDUAL (VERSÃO CORRIGIDA E OTIMIZADA) ---
    with tab2:
        st.subheader("Editar Cadastro Individual")
        if dados_completos_df.empty:
            st.warning("Não há dados para editar.")
        else:
            # Selecionar o militar para edição
            nomes_para_selecao = [""] + sorted(dados_completos_df['nome_completo'].unique())
            aluno_selecionado = st.selectbox("Selecione um militar para editar:", options=nomes_para_selecao)

            if aluno_selecionado:
                # Pega os dados originais do militar selecionado
                dados_aluno_originais = dados_completos_df[dados_completos_df['nome_completo'] == aluno_selecionado].iloc[0].to_dict()
                
                with st.form("form_edicao_individual"):
                    # Cria um novo dicionário para armazenar os valores editados no formulário
                    dados_aluno_editados = dados_aluno_originais.copy()

                    st.markdown("#### Dados Pessoais e de Referência")
                    c1, c2, c3 = st.columns(3)
                    c1.text_input("Nome Completo", value=dados_aluno_editados.get('nome_completo', ''), disabled=True)
                    c2.text_input("Graduação", value=dados_aluno_editados.get('graduacao', ''), disabled=True)
                    # Lê o valor do widget e o armazena no dicionário de dados editados
                    dados_aluno_editados['ano_referencia'] = c3.number_input("Ano de Referência", value=int(dados_aluno_editados.get('ano_referencia', 2025)))

                    st.markdown("#### Endereço")
                    c4, c5 = st.columns([3, 1])
                    dados_aluno_editados['endereco'] = c4.text_input("Endereço", value=dados_aluno_editados.get('endereco', ''))
                    dados_aluno_editados['bairro'] = c5.text_input("Bairro", value=dados_aluno_editados.get('bairro', ''))
                    c6, c7 = st.columns(2)
                    dados_aluno_editados['cidade'] = c6.text_input("Cidade", value=dados_aluno_editados.get('cidade', ''))
                    dados_aluno_editados['cep'] = c7.text_input("CEP", value=dados_aluno_editados.get('cep', ''))
                    
                    st.markdown("#### Itinerários")
                    dados_aluno_editados['dias_uteis'] = st.number_input("Dias Úteis (máx 22)", min_value=0, max_value=22, value=int(dados_aluno_editados.get('dias_uteis', 22)))
                    
                    for i in range(1, 6):
                        with st.expander(f"{i}º Trajeto"):
                            col_ida, col_volta = st.columns(2)
                            with col_ida:
                                st.markdown(f"**Ida {i}**")
                                dados_aluno_editados[f'ida_{i}_empresa'] = st.text_input(f"Empresa Ida {i}", value=dados_aluno_editados.get(f'ida_{i}_empresa', ''), key=f'ida_emp_{i}')
                                dados_aluno_editados[f'ida_{i}_linha'] = st.text_input(f"Linha Ida {i}", value=dados_aluno_editados.get(f'ida_{i}_linha', ''), key=f'ida_lin_{i}')
                                # CORREÇÃO: Lê o valor do widget e o armazena
                                dados_aluno_editados[f'ida_{i}_tarifa'] = st.number_input(f"Tarifa Ida {i}", min_value=0.0, value=float(dados_aluno_editados.get(f'ida_{i}_tarifa', 0.0)), format="%.2f", key=f'ida_tar_{i}')
                            with col_volta:
                                st.markdown(f"**Volta {i}**")
                                dados_aluno_editados[f'volta_{i}_empresa'] = st.text_input(f"Empresa Volta {i}", value=dados_aluno_editados.get(f'volta_{i}_empresa', ''), key=f'vol_emp_{i}')
                                dados_aluno_editados[f'volta_{i}_linha'] = st.text_input(f"Linha Volta {i}", value=dados_aluno_editados.get(f'volta_{i}_linha', ''), key=f'vol_lin_{i}')
                                # CORREÇÃO: Lê o valor do widget e o armazena
                                dados_aluno_editados[f'volta_{i}_tarifa'] = st.number_input(f"Tarifa Volta {i}", min_value=0.0, value=float(dados_aluno_editados.get(f'volta_{i}_tarifa', 0.0)), format="%.2f", key=f'vol_tar_{i}')

                    # --- CAMPOS CALCULADOS (ATUALIZADOS EM TEMPO REAL) ---
                    st.markdown("---")
                    st.markdown("#### Valores Calculados (Pré-visualização)")
                    # CORREÇÃO: O cálculo é feito com os dados acabados de ler dos widgets
                    valores_calculados = calcular_auxilio_transporte(dados_aluno_editados)
                    
                    c8, c9, c10, c11, c12 = st.columns(5)
                    c8.metric("Soldo", f"R$ {dados_aluno_editados.get('soldo', 0.0):,.2f}")
                    c9.metric("Despesa Diária", f"R$ {valores_calculados.get('despesa_diaria', 0.0):,.2f}")
                    c10.metric("Despesa Mensal", f"R$ {valores_calculados.get('despesa_mensal_total', 0.0):,.2f}")
                    c11.metric("Desconto 6%", f"R$ {valores_calculados.get('parcela_descontada_6_porcento', 0.0):,.2f}")
                    c12.metric("Valor a Receber", f"R$ {valores_calculados.get('auxilio_pago', 0.0):,.2f}")

                    if st.form_submit_button("Salvar Alterações", type="primary"):
                        with st.spinner("Salvando..."):
                            try:
                                dados_para_salvar = dados_aluno_editados.copy()
                                campos_a_remover = ['id', 'created_at', 'despesa_diaria', 'despesa_mensal_total', 'parcela_descontada_6_porcento', 'auxilio_pago']
                                for campo in campos_a_remover:
                                    dados_para_salvar.pop(campo, None)

                                supabase.table(NOME_TABELA_TRANSPORTE).upsert(
                                    dados_para_salvar,
                                    on_conflict='numero_interno,ano_referencia'
                                ).execute()
                                st.success(f"Dados do(a) militar {aluno_selecionado} salvos com sucesso!")
                                carregar_dados_completos.clear()
                            except Exception as e:
                                st.error(f"Erro ao salvar: {e}")

    with tab3:
        st.subheader("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar e Editar Dados'.")
        elif 'mapeamento_pdf' not in st.session_state or 'pdf_template_bytes' not in st.session_state:
            st.warning("Por favor, carregue o modelo PDF e salve o mapeamento na aba '2. Mapeamento PDF'.")
        else:
            df_final = st.session_state['dados_em_memoria'].copy()
            
            with st.spinner("Calculando valores..."):
                calculos_df = df_final.apply(calcular_auxilio_transporte, axis=1)
                df_com_calculo = pd.concat([df_final, calculos_df], axis=1)

            st.markdown("#### Filtro para Seleção")
            nomes_validos = df_com_calculo['nome_completo'].dropna().unique()
            opcoes_filtro = sorted(nomes_validos)
            selecionados = st.multiselect("Selecione por Nome Completo:", options=opcoes_filtro)
            
            df_para_gerar = df_com_calculo[df_com_calculo['nome_completo'].isin(selecionados)] if selecionados else df_com_calculo
            st.dataframe(df_para_gerar)

            if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                with st.spinner("Gerando PDFs..."):
                    try:
                        template_bytes = st.session_state['pdf_template_bytes']
                        mapping = st.session_state['mapeamento_pdf']
                        filled_pdfs = []
                        progress_bar = st.progress(0)
                        
                        for i, (_, aluno_row) in enumerate(df_para_gerar.iterrows()):
                            pdf_preenchido = fill_pdf_auxilio(template_bytes, aluno_row, mapping)
                            filled_pdfs.append(pdf_preenchido)
                            progress_bar.progress((i + 1) / len(df_para_gerar), text=f"Gerando: {aluno_row['nome_completo']}")
                        
                        final_pdf_buffer = merge_pdfs(filled_pdfs)
                        st.session_state['pdf_final_bytes'] = final_pdf_buffer.getvalue()
                        progress_bar.empty()
                        
                        st.success("Documento consolidado gerado com sucesso!")
                        st.balloons()

                    except Exception as e:
                        st.error(f"Ocorreu um erro durante a geração dos PDFs: {e}")
                        st.error(traceback.format_exc())

                if 'pdf_final_bytes' in st.session_state:
                    st.download_button(
                        label="✅ Baixar Documento Consolidado (.pdf)",
                        data=st.session_state['pdf_final_bytes'],
                        file_name="Declaracoes_Auxilio_Transporte.pdf",
                        mime="application/pdf"
                    )
