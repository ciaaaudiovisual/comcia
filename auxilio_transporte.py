import streamlit as st
import pandas as pd
from io import BytesIO

# Importando as funções de conexão do seu ficheiro de configuração e as funções de cálculo
from config import init_supabase_client
from acoes import load_data # Usando a função load_data que está em acoes.py ou outro local central
# Linha nova e corrigida em auxilio_transporte.py
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
    except Exception as e:
        st.error(f"Erro no cálculo para a linha com dados {linha.get('numero_interno')}. Detalhe: {e}")
        return pd.Series() # Retorna uma Series vazia em caso de erro

# Função principal da página, que será chamada pelo app.py
def show_auxilio_transporte():
    st.header("🚌 Geração de Declaração de Auxílio Transporte (Versão Simplificada)")
    st.markdown("---")
    st.info("Este módulo utiliza um único ficheiro CSV como fonte de dados para todos os cálculos.")

    # ETAPA 1: UPLOAD DO FICHEIRO CSV ÚNICO
    uploaded_file = st.file_uploader(
        "Carregue o seu ficheiro de dados (.csv)", 
        type="csv",
        help="Este ficheiro deve ser o exportado do Google Forms, com ponto e vírgula (;) como separador."
    )

    if not uploaded_file:
        st.warning("Aguardando o ficheiro de dados para iniciar.")
        return

    # ETAPA 2: PROCESSAMENTO E CÁLCULO
    if st.button("Processar Ficheiro e Calcular Valores", type="primary"):
        with st.spinner("Processando..."):
            try:
                # Carrega o CSV. O separador deve ser ponto e vírgula.
                df = pd.read_csv(uploaded_file, sep=';')

                # --- PREPARAÇÃO DOS DADOS ---
                
                # 1. Remove a primeira coluna ("Carimbo de data/hora")
                df = df.iloc[:, 1:]
                
                # 2. Mapeia os nomes das colunas do seu ficheiro para os nomes padrão do sistema
                mapa_colunas = {
                    'NÚMERO INTERNO DO ALUNO': 'numero_interno',
                    'NOME COMPLETO': 'nome_completo',
                    'POSTO/GRAD': 'graduacao',
                    'SOLDO': 'soldo', # Assumindo que a coluna de soldo se chama 'SOLDO'
                    'DIAS ÚTEIS (MÁX 22)': 'dias_uteis',
                    'ANO DE REFERÊNCIA': 'ano_referencia',
                    'ENDEREÇO COMPLETO': 'endereco',
                    'BAIRRO': 'bairro',
                    'CIDADE': 'cidade',
                    'CEP': 'cep'
                }
                for i in range(1, 5):
                    mapa_colunas[f'{i}ª EMPRESA (IDA)'] = f'ida_{i}_empresa'
                    mapa_colunas[f'{i}º TRAJETO (IDA)'] = f'ida_{i}_linha'
                    mapa_colunas[f'{i}ª TARIFA (IDA)'] = f'ida_{i}_tarifa'
                    mapa_colunas[f'{i}ª EMPRESA (VOLTA)'] = f'volta_{i}_empresa'
                    mapa_colunas[f'{i}º TRAJETO (VOLTA)'] = f'volta_{i}_linha'
                    mapa_colunas[f'{i}ª TARIFA (VOLTA)'] = f'volta_{i}_tarifa'
                
                df.rename(columns=mapa_colunas, inplace=True)
                
                # 3. Converte colunas numéricas, tratando possíveis erros
                colunas_numericas = ['dias_uteis', 'soldo'] + [f'ida_{i}_tarifa' for i in range(1, 5)] + [f'volta_{i}_tarifa' for i in range(1, 5)]
                for col in colunas_numericas:
                    if col in df.columns:
                        # Substitui vírgula por ponto e converte para número
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
                
                df.fillna(0, inplace=True) # Preenche valores nulos com 0 após conversão

                # 4. Aplica a função de cálculo a cada linha do DataFrame
                calculos_df = df.apply(calcular_auxilio_transporte, axis=1)

                # 5. Junta os resultados dos cálculos à tabela original
                resultados_finais_df = pd.concat([df, calculos_df], axis=1)

                st.success(f"Processamento concluído! Foram calculados {len(resultados_finais_df)} registos.")
                st.dataframe(resultados_finais_df)

                # Armazena na sessão para a etapa de geração do PDF
                st.session_state['resultados_para_pdf'] = resultados_finais_df

            except Exception as e:
                st.error(f"Ocorreu um erro durante o processamento. Verifique o formato do ficheiro e das colunas. Detalhes: {e}")

    # ETAPA 3: GERAÇÃO DOS DOCUMENTOS PDF
    if 'resultados_para_pdf' in st.session_state:
        st.markdown("---")
        st.subheader("3. Geração dos Documentos")
        
        df_para_gerar = st.session_state['resultados_para_pdf']
        
        if st.button(f"Gerar PDF para os {len(df_para_gerar)} registos", type="primary"):
            st.info("Funcionalidade de geração de PDF a ser conectada.")
            # Exemplo de como a lógica seria chamada:
            # pdf_final = gerar_pdfs_consolidados(df_para_gerar, "caminho/do/modelo.pdf")
            # st.download_button("Baixar PDFs", data=pdf_final, file_name="Declaracoes.pdf")
