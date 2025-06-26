import streamlit as st
import pandas as pd
import plotly.express as px
from database import load_data
from datetime import datetime, timedelta


def show_relatorios():
    st.title("Relatórios e Gráficos")
    
    # Carregar dados
    alunos_df = load_data("Sistema_Acoes_Militares", "Alunos")
    acoes_df = load_data("Sistema_Acoes_Militares", "Acoes")
    
    if alunos_df.empty or acoes_df.empty:
        st.warning("Dados insuficientes para gerar relatórios. Adicione alunos e registre ações primeiro.")
        return
    
    # Abas para diferentes tipos de relatórios
    tab1, tab2, tab3 = st.tabs(["📊 Gráficos", "🏆 Rankings", "📈 Evolução"])
    
    with tab1:
        # Selecionar tipo de gráfico
        grafico_tipo = st.selectbox(
            "Selecione o tipo de gráfico",
            ["Pontuação por Pelotão", "Distribuição de Ações"]
        )
        
        if grafico_tipo == "Pontuação por Pelotão":
            show_pontuacao_pelotao(alunos_df, acoes_df)
        elif grafico_tipo == "Distribuição de Ações":
            show_distribuicao_acoes(acoes_df)
    
    with tab2:
        # Rankings de alunos
        st.subheader("Rankings de Alunos")
        
        # Período de tempo
        periodo = st.radio(
            "Selecione o período",
            ["Hoje", "Esta Semana", "Este Mês", "Todo o Período"],
            horizontal=True
        )
        
        # Filtrar ações pelo período selecionado
        acoes_filtradas = acoes_df.copy()
        hoje = datetime.now().date()
        
        if periodo == "Hoje":
            acoes_filtradas = acoes_df[pd.to_datetime(acoes_df['data']).dt.date == hoje]
        elif periodo == "Esta Semana":
            inicio_semana = hoje - timedelta(days=hoje.weekday())
            acoes_filtradas = acoes_df[pd.to_datetime(acoes_df['data']).dt.date >= inicio_semana]
        elif periodo == "Este Mês":
            inicio_mes = datetime(hoje.year, hoje.month, 1).date()
            acoes_filtradas = acoes_df[pd.to_datetime(acoes_df['data']).dt.date >= inicio_mes]
        
        if acoes_filtradas.empty:
            st.info(f"Nenhuma ação registrada no período: {periodo}")
        else:
            # Calcular pontuação por aluno no período
            pontuacao_periodo = acoes_filtradas.groupby('aluno_id')['pontuacao_efetiva'].sum().reset_index()
            
            # Mesclar com dados dos alunos
            alunos_com_pontuacao = pd.merge(
                alunos_df,
                pontuacao_periodo,
                left_on='id',
                right_on='aluno_id',
                how='inner'  # Apenas alunos com ações no período
            )
            
            # Mostrar rankings
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🌟 Mais Pontuados")
                top_positivos = alunos_com_pontuacao.sort_values('pontuacao_efetiva', ascending=False).head(5)
                
                for i, (_, aluno) in enumerate(top_positivos.iterrows()):
                    st.write(f"{i+1}. **{aluno['nome_guerra']}** ({aluno['pelotao']}) - {aluno['pontuacao_efetiva']:+.1f} pts")
            
            with col2:
                st.subheader("⚠️ Menos Pontuados")
                top_negativos = alunos_com_pontuacao.sort_values('pontuacao_efetiva').head(5)
                
                for i, (_, aluno) in enumerate(top_negativos.iterrows()):
                    st.write(f"{i+1}. **{aluno['nome_guerra']}** ({aluno['pelotao']}) - {aluno['pontuacao_efetiva']:+.1f} pts")
    
    with tab3:
        show_evolucao_pontuacao(alunos_df, acoes_df)


def show_pontuacao_pelotao(alunos_df, acoes_df):
    st.subheader("Pontuação Média por Pelotão")
    
    # Calcular pontuação por aluno
    if not acoes_df.empty and 'aluno_id' in acoes_df.columns and 'pontuacao_efetiva' in acoes_df.columns:
        pontuacao_por_aluno = acoes_df.groupby('aluno_id')['pontuacao_efetiva'].sum().reset_index()
        
        # Mesclar com dados dos alunos
        alunos_com_pontuacao = pd.merge(
            alunos_df,
            pontuacao_por_aluno,
            left_on='id',
            right_on='aluno_id',
            how='left'
        )
        
        # Preencher valores nulos com pontuação inicial (10)
        alunos_com_pontuacao['pontuacao_efetiva'] = alunos_com_pontuacao['pontuacao_efetiva'].fillna(0) + 10
        
        # Calcular média por pelotão
        media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_efetiva'].mean().reset_index()
        
        # Criar gráfico
        fig = px.bar(
            media_por_pelotao,
            x='pelotao',
            y='pontuacao_efetiva',
            title='Pontuação Média por Pelotão',
            labels={'pelotao': 'Pelotão', 'pontuacao_efetiva': 'Pontuação Média'},
            color='pontuacao_efetiva',
            color_continuous_scale='RdYlGn'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Mostrar tabela com dados
        st.subheader("Dados Detalhados")
        st.dataframe(media_por_pelotao)
    else:
        st.info("Dados insuficientes para gerar este relatório.")

def show_distribuicao_acoes(acoes_df):
    st.subheader("Distribuição de Tipos de Ação")
    
    if not acoes_df.empty and 'tipo' in acoes_df.columns:
        # Contar ocorrências de cada tipo
        contagem_tipos = acoes_df['tipo'].value_counts().reset_index()
        contagem_tipos.columns = ['Tipo de Ação', 'Quantidade']
        
        # Criar gráfico
        fig = px.pie(
            contagem_tipos,
            values='Quantidade',
            names='Tipo de Ação',
            title='Distribuição de Tipos de Ação',
            hole=0.4
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Mostrar tabela com dados
        st.subheader("Dados Detalhados")
        st.dataframe(contagem_tipos)
    else:
        st.info("Dados insuficientes para gerar este relatório.")



def show_evolucao_pontuacao(alunos_df, acoes_df):
    st.subheader("Evolução da Pontuação ao Longo do Tempo")
    
    if not acoes_df.empty and 'data' in acoes_df.columns and 'pontuacao_efetiva' in acoes_df.columns:
        # Converter data para datetime
        acoes_df['data'] = pd.to_datetime(acoes_df['data'])
        
        # Ordenar por data
        acoes_df = acoes_df.sort_values('data')
        
        # Selecionar aluno para visualizar evolução
        if 'aluno_id' in acoes_df.columns:
            alunos_ids = acoes_df['aluno_id'].unique()
            
            if len(alunos_ids) > 0:
                # Criar opções de alunos
                alunos_opcoes = []
                for aluno_id in alunos_ids:
                    aluno = alunos_df[alunos_df['id'] == aluno_id]
                    if not aluno.empty:
                        nome = aluno.iloc[0]['nome_guerra']
                        alunos_opcoes.append(f"{nome} (ID: {aluno_id})")
                    else:
                        alunos_opcoes.append(f"Aluno ID: {aluno_id}")
                
                # Selecionar aluno
                aluno_selecionado = st.selectbox("Selecione o Aluno", alunos_opcoes)
                aluno_id = int(aluno_selecionado.split("ID: ")[1].rstrip(")"))
                
                # Filtrar ações do aluno
                acoes_aluno = acoes_df[acoes_df['aluno_id'] == aluno_id]
                
                if not acoes_aluno.empty:
                    # Calcular pontuação acumulada
                    pontuacao_inicial = 10
                    acoes_aluno['pontuacao_acumulada'] = acoes_aluno['pontuacao_efetiva'].cumsum() + pontuacao_inicial
                    
                    # Criar gráfico
                    fig = px.line(
                        acoes_aluno,
                        x='data',
                        y='pontuacao_acumulada',
                        title=f'Evolução da Pontuação - {aluno_selecionado.split(" (ID")[0]}',
                        labels={'data': 'Data', 'pontuacao_acumulada': 'Pontuação'},
                        markers=True
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Mostrar tabela com dados
                    st.subheader("Histórico de Pontuação")
                    st.dataframe(acoes_aluno[['data', 'tipo', 'pontuacao_efetiva', 'pontuacao_acumulada']])
                else:
                    st.info("Este aluno não possui ações registradas.")
            else:
                st.info("Nenhum aluno com ações registradas.")
        else:
            st.info("Dados insuficientes para gerar este relatório.")
    else:
        st.info("Dados insuficientes para gerar este relatório.")
