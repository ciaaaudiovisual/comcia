import streamlit as st
import pandas as pd
from io import BytesIO

# Tente importar as funções de PDF do seu ficheiro de utilitários.
# Se ainda não o criou, pode manter esta linha comentada.
# from pdf_utils import fill_pdf_auxilio, merge_pdfs
# from pypdf import PdfReader


# --- Bloco de Funções Essenciais ---

def calcular_auxilio_transporte(linha):
    """Calcula os valores do auxílio transporte para uma única linha de dados."""
    try:
        despesa_diaria = 0
        # O loop agora vai de 1 a 5 para incluir a nova opção de transporte
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
    """Limpa, renomeia e padroniza o DataFrame carregado a partir do CSV."""
    df_copy = df.iloc[:, 1:].copy() # Remove a primeira coluna ("Carimbo de data/hora")
    
    mapa_colunas = {
        'NÚMERO INTERNO DO ALUNO': 'numero_interno', 'NOME COMPLETO': 'nome_completo', 'POSTO/GRAD': 'graduacao',
        'SOLDO': 'soldo', 'DIAS ÚTEIS (MÁX 22)': 'dias_uteis', 'ANO DE REFERÊNCIA': 'ano_referencia',
        'ENDEREÇO COMPLETO': 'endereco', 'BAIRRO': 'bairro', 'CIDADE': 'cidade', 'CEP': 'cep'
    }
    for i in range(1, 6): # Atualizado para 5 transportes
        for direcao in ["IDA", "VOLTA"]:
            mapa_colunas[f'{i}ª EMPRESA ({direcao})'] = f'{direcao.lower()}_{i}_empresa'
            # A coluna do trajeto no seu ficheiro usa 'º', então tratamos disso
            mapa_colunas[f'{i}º TRAJETO ({direcao})'] = f'{direcao.lower()}_{i}_linha'
            mapa_colunas[f'{i}ª TARIFA ({direcao})'] = f'{direcao.lower()}_{i}_tarifa'
            
    df_copy.rename(columns=mapa_colunas, inplace=True)
    
    # Converte todas as colunas de texto para MAIÚSCULAS
    for col in df_copy.select_dtypes(include=['object']).columns:
        df_copy[col] = df_copy[col].str.upper().str.strip()

    # Converte colunas numéricas, tratando vírgulas e erros
    colunas_numericas = ['dias_uteis', 'soldo'] + [f'ida_{i}_tarifa' for i in range(1, 6)] + [f'volta_{i}_tarifa' for i in range(1, 6)]
    for col in colunas_numericas:
        if col in df_copy.columns:
            df_copy[col] = pd.to_numeric(df_copy[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    df_copy.fillna(0, inplace=True)
    return df_copy

# --- Função Principal da Página ---
def show_auxilio_transporte():
    st.header("🚌 Gestão de Auxílio Transporte (Baseado em Ficheiro)")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["1. Carregar e Editar Dados", "2. Mapeamento do PDF", "3. Gerar Documentos"])

    # --- ABA 1: CARREGAR E EDITAR ---
    with tab1:
        st.subheader("Carregar Ficheiro de Dados")

        # Mostra o ficheiro em memória e dá a opção de limpar
        if 'dados_em_memoria' in st.session_state:
            st.info(f"Ficheiro em memória: **{st.session_state['nome_ficheiro']}**")
            if st.button("🗑️ Limpar Ficheiro e Recomeçar"):
                for key in ['dados_em_memoria', 'nome_ficheiro', 'mapeamento_pdf', 'resultados_para_pdf']:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

        uploaded_file = st.file_uploader("Carregue o seu ficheiro CSV", type="csv")

        if uploaded_file:
            if st.button(f"Processar Ficheiro: {uploaded_file.name}", type="primary"):
                with st.spinner("Processando..."):
                    try:
                        df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                        df_preparado = preparar_dataframe(df)
                        st.session_state['dados_em_memoria'] = df_preparado
                        st.session_state['nome_ficheiro'] = uploaded_file.name
                        st.success("Ficheiro processado! Pode editar os dados abaixo ou ir para as próximas abas.")
                    except Exception as e:
                        st.error(f"Erro ao ler ou preparar o ficheiro: {e}")

        # Lógica de edição que só aparece se um ficheiro estiver carregado
        if 'dados_em_memoria' in st.session_state:
            st.markdown("---")
            st.markdown("##### Tabela de Dados para Edição")
            st.info("As alterações feitas aqui são usadas nas outras abas. Para salvá-las permanentemente, baixe o CSV editado.")

            df_editado = st.data_editor(
                st.session_state['dados_em_memoria'], num_rows="dynamic", use_container_width=True
            )
            st.session_state['dados_em_memoria'] = df_editado # Atualiza a sessão com os dados editados

            csv_editado = df_editado.to_csv(index=False, sep=';').encode('latin-1')
            st.download_button(
                label="📥 Baixar CSV Editado", data=csv_editado,
                file_name=f"dados_editados_{st.session_state['nome_ficheiro']}"
            )

    # --- ABA 2: MAPEAMENTO DO PDF ---
    with tab2:
        st.subheader("Mapear Campos do PDF")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar e Editar Dados'.")
        else:
            st.info("Faça o upload do seu modelo PDF preenchível para mapear os campos.")
            pdf_template = st.file_uploader("Carregue o modelo PDF", type="pdf", key="pdf_uploader")

            if pdf_template:
                # O código de mapeamento iria aqui, usando o pdf_template e os dados da sessão
                st.info("Funcionalidade de mapeamento a ser implementada aqui.")

# --- ABA 3: GERAR DOCUMENTOS ---
    with tab3:
        st.subheader("Gerar Documentos Finais")
        if 'dados_em_memoria' not in st.session_state:
            st.warning("Por favor, carregue um ficheiro na aba '1. Carregar e Editar Dados'.")
        else:
            df_final = st.session_state['dados_em_memoria'].copy()
            
            with st.spinner("Calculando valores..."):
                calculos_df = df_final.apply(calcular_auxilio_transporte, axis=1)
                df_com_calculo = pd.concat([df_final, calculos_df], axis=1)

            st.markdown("#### Filtro para Seleção")
            st.info("Selecione os militares para gerar o documento. Deixe em branco para incluir todos.")
            
            # --- INÍCIO DA CORREÇÃO ---
            # Remove valores nulos, pega os nomes únicos e depois ordena.
            nomes_validos = df_com_calculo['nome_completo'].dropna().unique()
            opcoes_filtro = sorted(nomes_validos)
            # --- FIM DA CORREÇÃO ---

            selecionados = st.multiselect("Selecione por Nome Completo:", options=opcoes_filtro)
            
            if selecionados:
                df_para_gerar = df_com_calculo[df_com_calculo['nome_completo'].isin(selecionados)]
            else:
                df_para_gerar = df_com_calculo

            st.dataframe(df_para_gerar)

            if st.button(f"Gerar PDF para os {len(df_para_gerar)} selecionados", type="primary"):
                st.info("Lógica de geração de PDF a ser conectada aqui.")


                # Exemplo:
                # if 'mapeamento_pdf' in st.session_state and pdf_template is not None:
                #     pdf_final = gerar_pdfs_consolidados(df_para_gerar, pdf_template, st.session_state['mapeamento_pdf'])
                #     st.download_button("Baixar PDFs", data=pdf_final, file_name="Declaracoes.pdf")
                # else:
                #     st.error("Por favor, carregue e salve o mapeamento do PDF na Aba 2.")
