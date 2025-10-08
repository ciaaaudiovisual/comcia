# analise_avaliacoes.py

import streamlit as st
import pandas as pd
from database import Database
from gspread_dataframe import get_as_dataframe
import gspread
import numpy as np

# Cache para os dados da planilha, seguindo o padrão do previa_rancho.py
@st.cache_data(ttl=600)  # Cache de 10 minutos
def load_peer_review_data():
    """Conecta ao Google Sheets e carrega os dados da avaliação de pares."""
    try:
        creds = st.secrets["gcp_service_account"]
        sa = gspread.service_account_from_dict(creds)
        spreadsheet = sa.open_by_key(st.secrets["sheets"]["spreadsheet_key"])
        worksheet = spreadsheet.worksheet("Respostas ao formulário 1")
        
        # Carrega os dados e trata colunas vazias
        df = get_as_dataframe(worksheet, evaluate_formulas=True, na_filter=False)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados da planilha: {e}")
        return None

def process_data(df_respostas, df_alunos_master, pelotao):
    """
    Processa os dados brutos das respostas para calcular as métricas de avaliação
    para um pelotão específico.
    """
    if df_respostas is None or df_alunos_master is None or not pelotao:
        return pd.DataFrame()

    # Pega a lista de nomes de guerra do pelotão selecionado
    nomes_alunos_pelotao = df_alunos_master[df_alunos_master['pelotao'] == pelotao]['nome_guerra'].tolist()

    # Identifica as colunas de avaliação de pares no DataFrame de respostas
    colunas_avaliacao = [col for col in df_respostas.columns if 'Avalie os integrantes' in col]
    
    # Filtra as respostas para incluir apenas as de quem pertence ao pelotão selecionado
    respostas_do_pelotao = df_respostas[df_respostas['Selecione seu Pelotão'] == pelotao]

    if respostas_do_pelotao.empty:
        return pd.DataFrame(columns=['Aluno', 'Média Recebida', 'Maior Nota', 'Menor Nota', 'Autoavaliação', 'Diferença (Auto vs Pares)'])

    results = []
    for nome_aluno in nomes_alunos_pelotao:
        # Encontra a coluna de avaliação correspondente a este aluno
        coluna_aluno = next((col for col in colunas_avaliacao if f"[{nome_aluno}]" in col), None)
        
        if coluna_aluno:
            # Coleta todas as notas dadas a este aluno, convertendo para numérico
            notas = pd.to_numeric(respostas_do_pelotao[coluna_aluno], errors='coerce').dropna()
            
            media = notas.mean() if not notas.empty else 0
            maior_nota = notas.max() if not notas.empty else 0
            menor_nota = notas.min() if not notas.empty else 0
            
            # Busca a autoavaliação que o próprio aluno registrou
            autoavaliacao_row = respostas_do_pelotao[respostas_do_pelotao['Seu Nome de Guerra'] == nome_aluno]
            autoavaliacao = pd.to_numeric(autoavaliacao_row['Sua Autoavaliação (Nota)'].iloc[0], errors='coerce') if not autoavaliacao_row.empty else 0
            
            results.append({
                'Aluno': nome_aluno,
                'Média Recebida': round(media, 2),
                'Maior Nota': maior_nota,
                'Menor Nota': menor_nota,
                'Autoavaliação': autoavaliacao,
                'Diferença (Auto vs Pares)': round(autoavaliacao - media, 2)
            })

    return pd.DataFrame(results)

def run():
    """Função principal que renderiza a página no Streamlit."""
    st.title("📊 Análise de Avaliação de Pares")

    df_respostas = load_peer_review_data()

    if df_respostas is not None:
        db = Database()
        df_alunos_master = db.get_alunos_df()

        if df_alunos_master.empty:
            st.warning("Não foi possível carregar a lista de alunos do banco de dados.")
            return

        lista_pelotoes = sorted(df_alunos_master['pelotao'].unique().tolist())
        pelotao_selecionado = st.selectbox("Selecione um Pelotão para analisar:", options=lista_pelotoes)

        if pelotao_selecionado:
            with st.spinner(f"Processando dados para {pelotao_selecionado}..."):
                df_analise = process_data(df_respostas, df_alunos_master, pelotao_selecionado)

            if df_analise.empty:
                st.info("Não há dados de avaliação para o pelotão selecionado ou o processamento falhou.")
                return

            st.subheader(f"Resultados Consolidados - {pelotao_selecionado}")
            
            # Ordena por média para criar um ranking
            df_analise_sorted = df_analise.sort_values(by='Média Recebida', ascending=False)
            st.dataframe(df_analise_sorted.set_index('Aluno'))

            st.subheader("Visualizações Gráficas")
            
            # Gráfico de Barras: Ranking de Médias
            st.bar_chart(df_analise_sorted.set_index('Aluno')[['Média Recebida', 'Autoavaliação']])
            st.caption("Gráfico comparativo entre a média das notas recebidas pelos pares e a nota de autoavaliação.")

            # Gráfico de Dispersão: Percepção vs. Realidade
            st.write("#### Análise de Percepção (Autoavaliação vs. Média dos Pares)")
            st.scatter_chart(df_analise, x='Média Recebida', y='Autoavaliação', color='#ff0000')
            st.caption("Cada ponto representa um aluno. Pontos acima da diagonal indicam autoavaliação superior à média dos pares. Pontos abaixo indicam o oposto.")
