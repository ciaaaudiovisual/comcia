import streamlit as st
import pandas as pd
from io import BytesIO
from config import init_supabase_client
from acoes import load_data # Usando a função load_data que está em acoes.py ou outro local central
from pdf_utils import fill_pdf_auxilio, merge_pdfs # Importa do novo ficheiro de utilitários

# Esta é a sua função de cálculo principal. Ela permanece a mesma.
def calcular_auxilio_transporte(linha):
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
            'despesa_diaria': round(despesa_diaria, 2),
            'dias_trabalhados': dias_trabalhados,
            'despesa_mensal_total': round(despesa_mensal, 2),
            'parcela_descontada_6_porcento': round(parcela_beneficiario, 2),
            'auxilio_transporte_pago': round(auxilio_pago, 2)
        })
    except Exception:
        return pd.Series()

# Função para preparar o DataFrame (limpeza e renomeação)
def preparar_dataframe(df):
    df = df.iloc[:, 1:].copy() # Remove a primeira coluna (Carimbo de data/hora)
    mapa_colunas = {
        'NÚMERO INTERNO DO ALUNO': 'numero_interno', 'NOME COMPLETO': 'nome_completo',
        'POSTO/GRAD': 'graduacao', 'SOLDO': 'soldo', 'DIAS ÚTEIS (MÁX 22)': 'dias_uteis',
        'ANO DE REFERÊNCIA': 'ano_referencia', 'ENDEREÇO COMPLETO': 'endereco', 'BAIRRO': 'bairro',
        'CIDADE': 'cidade', 'CEP': 'cep'
    }
    for i in range(1, 5):
        mapa_colunas[f'{i}ª EMPRESA (IDA)'] = f'ida_{i}_empresa'
        mapa_colunas[f'{i}º TRAJETO (IDA)'] = f'ida_{i}_linha'
        mapa_colunas[f'{i}ª TARIFA (IDA)'] = f'ida_{i}_tarifa'
        mapa_colunas[f'{i}ª EMPRESA (VOLTA)'] = f'volta_{i}_empresa'
        mapa_colunas[f'{i}º TRAJETO (VOLTA)'] = f'volta_{i}_linha'
        mapa_colunas[f'{i}ª TARIFA (VOLTA)'] = f'volta_{i}_tarifa'
    df.rename(columns=mapa_colunas, inplace=True)
    colunas_numericas = ['dias_uteis', 'soldo'] + [f'ida_{i}_tarifa' for i in range(1, 5)] + [f'volta_{i}_tarifa' for i in range(1, 5)]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    df.fillna(0, inplace=True)
    return df

# --- Função Principal da Página ---

def show_auxilio_transporte():
    st.header("🚌 Geração de Declaração de Auxílio Transporte")
    st.markdown("---")

    # Define as abas para organizar o fluxo de trabalho
    tab1, tab2, tab3 = st.tabs(["1. Carregar e Editar Dados", "2. Mapeamento do PDF", "3. Gerar Documentos"])

    # --- ABA 1: CARREGAR E EDITAR DADOS ---
    with tab1:
        st.subheader("Carregar e Editar o Ficheiro de Dados")
        uploaded_file = st.file_uploader("Carregue o ficheiro CSV de dados", type="csv")

        if uploaded_file:
            if 'dados_carregados' not in st.session_state or st.session_state.get('nome_ficheiro') != uploaded_file.name:
                try:
                    df = pd.read_csv(uploaded_file, sep=';', encoding='latin-1')
                    df_preparado = preparar_dataframe(df)
                    st.session_state['dados_carregados'] = df_preparado
                    st.session_state['nome_ficheiro'] = uploaded_file.name
                    st.success("Ficheiro carregado e preparado com sucesso!")
                except Exception as e:
                    st.error(f"Erro ao ler o ficheiro: {e}")
                    st.stop()
            
            st.info("Abaixo, você pode editar os dados diretamente na tabela. As alterações serão usadas na geração do PDF.")
            
            df_editado = st.data_editor(
                st.session_state['dados_carregados'],
                num_rows="dynamic",
                use_container_width=True
            )
            
            st.session_state['dados_editados'] = df_editado # Salva as edições na sessão

            st.markdown("##### Exportar Dados Editados")
            st.info("Se você fez alterações na tabela, pode baixar o ficheiro CSV atualizado.")
            csv = df_editado.to_csv(index=False, sep=';').encode('latin-1')
            st.download_button(
                label="📥 Baixar CSV Editado",
                data=csv,
                file_name=f"dados_editados_{st.session_state['nome_ficheiro']}",
                mime='text/csv',
            )

    # --- ABA 2: MAPEAMENTO DO PDF ---
    with tab2:
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
    with tab3:
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
