import streamlit as st
import pandas as pd
from io import BytesIO

# Importando as funções de conexão do seu ficheiro de configuração e as funções de cálculo
from config import init_supabase_client
from acoes import load_data # Usando a função load_data que está em acoes.py ou outro local central
from geracao_documentos import fill_pdf_auxilio, merge_pdfs # Funções que geram o PDF

# Esta é a sua função de cálculo principal. Ela permanece a mesma.
def calcular_auxilio_transporte(linha):
    try:
        despesa_diaria = 0
        for i in range(1, 5):
            # Tenta converter tarifas para float, tratando erros
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
        st.error(f"Erro no cálculo para a linha com dados {linha.get('numero_interno')}. Detalhe: {e}")
        return None

# Esta é a função principal que será chamada pelo app.py
def show_auxilio_transporte():
    st.header("🚌 Geração de Declaração de Auxílio Transporte")
    st.markdown("---")

    # ETAPA 1: CARREGAR DADOS DE SOLDOS DO SUPABASE
    try:
        with st.spinner("Conectando à base de dados para buscar a tabela de soldos..."):
            supabase = init_supabase_client()
            soldos_df = load_data("soldos")
        st.success("Tabela de soldos carregada com sucesso do Supabase.")
    except Exception as e:
        st.error(f"Não foi possível conectar à base de dados. Erro: {e}")
        st.stop()

    # ETAPA 2: UPLOAD DOS FICHEIROS CSV PELO UTILIZADOR
    st.subheader("1. Carregue os Ficheiros de Dados")
    col1, col2 = st.columns(2)
    with col1:
        uploaded_transporte_file = st.file_uploader("Ficheiro de Transporte do Mês (.csv)", type="csv", help="Este deve ser o ficheiro como 'decat tste.csv', com ponto e vírgula como separador.")
    with col2:
        uploaded_alunos_file = st.file_uploader("Ficheiro com a Lista de Alunos (.csv)", type="csv", help="Este deve ser o ficheiro 'Alunos_rows.csv'.")

    # O código só prossegue se ambos os ficheiros forem carregados
    if not uploaded_transporte_file or not uploaded_alunos_file:
        st.info("Aguardando o upload de ambos os ficheiros para iniciar o processamento.")
        return

    # ETAPA 3: PROCESSAMENTO E CÁLCULO
    st.subheader("2. Processamento, Cálculo e Validação")
    if st.button("Iniciar Processamento dos Dados", type="primary"):
        with st.spinner("Lendo ficheiros, juntando tabelas e calculando valores..."):
            try:
                # Leitura dos ficheiros CSV
                transporte_df = pd.read_csv(uploaded_transporte_file, sep=';', encoding='latin-1')
                alunos_df = pd.read_csv(uploaded_alunos_file)

                # --- LÓGICA DE CORRESPONDÊNCIA DE COLUNAS ---
                # Mapeia os nomes das colunas do ficheiro de transporte para os nomes padrão do sistema
                mapa_colunas = {
                    'NÚMERO INTERNO DO ALUNO': 'numero_interno',
                    'ANO DE REFERÊNCIA': 'ano_referencia',
                    'ENDEREÇO COMPLETO': 'endereco',
                    'BAIRRO': 'bairro',
                    'CIDADE': 'cidade',
                    'CEP': 'cep',
                    'DIAS ÚTEIS (MÁX 22)': 'dias_uteis',
                }
                # Mapeia dinamicamente as colunas de itinerário
                for i in range(1, 5):
                    mapa_colunas[f'{i}ª EMPRESA (IDA)'] = f'ida_{i}_empresa'
                    mapa_colunas[f'{i}º TRAJETO (IDA)'] = f'ida_{i}_linha'
                    mapa_colunas[f'{i}ª TARIFA (IDA)'] = f'ida_{i}_tarifa'
                    mapa_colunas[f'{i}ª EMPRESA (VOLTA)'] = f'volta_{i}_empresa'
                    mapa_colunas[f'{i}º TRAJETO (VOLTA)'] = f'volta_{i}_linha'
                    mapa_colunas[f'{i}ª TARIFA (VOLTA)'] = f'volta_{i}_tarifa'
                
                transporte_df.rename(columns=mapa_colunas, inplace=True)

                # Limpeza e padronização das chaves de junção
                transporte_df['numero_interno'] = transporte_df['numero_interno'].astype(str).str.strip().str.upper()
                alunos_df['numero_interno'] = alunos_df['numero_interno'].astype(str).str.strip().str.upper()
                soldos_df['graduacao'] = soldos_df['graduacao'].astype(str).str.strip()
                alunos_df['graduacao'] = alunos_df['graduacao'].astype(str).str.strip()

                # 1. Juntar dados de transporte com os dados dos alunos para obter a 'graduacao'
                dados_completos = pd.merge(
                    transporte_df,
                    alunos_df[['numero_interno', 'nome_completo', 'graduacao']],
                    on='numero_interno',
                    how='left'
                )

                # 2. Juntar o resultado com os soldos para obter o valor do 'soldo'
                dados_completos = pd.merge(
                    dados_completos,
                    soldos_df,
                    on='graduacao',
                    how='left'
                )

                # 3. Tratar dados faltantes após as junções
                dados_completos['soldo'].fillna(0, inplace=True)
                dados_completos.dropna(subset=['graduacao'], inplace=True) # Remove linhas onde o aluno ou graduação não foram encontrados

                # 4. Aplicar a função de cálculo
                calculos_df = dados_completos.apply(calcular_auxilio_transporte, axis=1)

                # 5. Unir os resultados dos cálculos à tabela final
                resultados_finais_df = pd.concat([dados_completos, calculos_df], axis=1)

                st.success(f"Processamento concluído! Foram encontrados e calculados {len(resultados_finais_df)} registos válidos.")
                st.dataframe(resultados_finais_df)

                # Armazenar os resultados na sessão para o passo de geração de PDF
                st.session_state['resultados_para_pdf'] = resultados_finais_df

            except FileNotFoundError:
                st.error("Erro: Um dos ficheiros não foi encontrado. Verifique os caminhos.")
            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento. Detalhes: {e}")

    # ETAPA 4: GERAÇÃO DOS DOCUMENTOS
    if 'resultados_para_pdf' in st.session_state:
        st.subheader("3. Geração dos Documentos PDF")
        
        df_para_gerar = st.session_state['resultados_para_pdf']
        
        if st.button(f"Gerar {len(df_para_gerar)} Documentos", type="primary"):
            st.info("Funcionalidade de geração de PDF ainda a ser conectada.")
            # Aqui você chamaria a sua lógica de geração de PDF. Exemplo:
            # try:
            #     # Supondo que você tenha um modelo PDF carregado
            #     with open("caminho/do/seu/modelo.pdf", "rb") as f:
            #         modelo_pdf_bytes = f.read()
                
            #     pdf_final_bytes = gerar_pdfs_consolidados(df_para_gerar, modelo_pdf_bytes)
                
            #     st.download_button(
            #         label="✅ Baixar PDFs Consolidados",
            #         data=pdf_final_bytes,
            #         file_name="Declaracoes_Auxilio_Transporte.pdf",
            #         mime="application/pdf"
            #     )
            # except Exception as e:
            #     st.error(f"Erro ao gerar o PDF: {e}")
