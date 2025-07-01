import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
from datetime import datetime, timedelta
from database import load_data
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final

# =============================================================================
# FUNÇÕES DE RENDERIZAÇÃO DAS ABAS
# =============================================================================

def render_graficos_tab(acoes_filtradas, alunos_filtrados, config_dict, view_mode):
    st.header("Análise Gráfica")
    
    grafico_tipo = st.selectbox(
        "Selecione o tipo de gráfico",
        ["Pontuação por Pelotão", "Distribuição de Ações", "Ranking de Ações (Top 5)"]
    )

    if grafico_tipo == "Pontuação por Pelotão":
        show_pontuacao_pelotao(alunos_filtrados, acoes_filtradas, config_dict, view_mode)
    elif grafico_tipo == "Distribuição de Ações":
        show_distribuicao_acoes(acoes_filtradas)
    elif grafico_tipo == "Ranking de Ações (Top 5)":
        show_ranking_acoes(acoes_filtradas)

def render_rankings_tab(acoes_filtradas, alunos_filtrados):
    st.header("Rankings de Alunos (baseado na Variação de Pontos)")
    
    if acoes_filtradas.empty:
        st.info("Nenhuma ação registrada para os filtros selecionados."); return

    pontuacao_periodo = acoes_filtradas.groupby('aluno_id')['pontuacao_efetiva'].sum().reset_index()
    alunos_com_pontuacao = pd.merge(alunos_filtrados, pontuacao_periodo, left_on='id', right_on='aluno_id', how='inner')
    
    if alunos_com_pontuacao.empty:
        st.info("Nenhum aluno com ações para os filtros selecionados."); return

    top_positivos = alunos_com_pontuacao[alunos_com_pontuacao['pontuacao_efetiva'] > 0].sort_values('pontuacao_efetiva', ascending=False).head(5)
    top_negativos = alunos_com_pontuacao[alunos_com_pontuacao['pontuacao_efetiva'] < 0].sort_values('pontuacao_efetiva').head(5)
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🌟 Mais Pontuados")
        if top_positivos.empty:
            st.info("Nenhum aluno com pontuação positiva.")
        else:
            for i, (_, aluno) in enumerate(top_positivos.iterrows()):
                st.write(f"#{i+1}: **{aluno['nome_guerra']}** ({aluno['pelotao']}) - {aluno['pontuacao_efetiva']:+.2f} pts")
    with col2:
        st.subheader("⚠️ Menos Pontuados")
        if top_negativos.empty:
            st.info("Nenhum aluno com pontuação negativa.")
        else:
            for i, (_, aluno) in enumerate(top_negativos.iterrows()):
                st.write(f"#{i+1}: **{aluno['nome_guerra']}** ({aluno['pelotao']}) - {aluno['pontuacao_efetiva']:+.2f} pts")

def render_evolucao_tab(acoes_filtradas, alunos_filtrados, config_dict, view_mode):
    st.header("Evolução de Desempenho")
    tipo_visao = st.radio("Analisar por:", ["Individual", "Pelotão"], horizontal=True)
    
    if tipo_visao == "Individual":
        show_evolucao_individual_comparativa(acoes_filtradas, alunos_filtrados, config_dict, view_mode)
    else:
        show_evolucao_pelotao_comparativa(acoes_filtradas, alunos_filtrados, config_dict, view_mode)

# =============================================================================
# FUNÇÕES DE GRÁFICOS CORRIGIDAS
# =============================================================================

def show_pontuacao_pelotao(alunos_df, acoes_df, config_dict, view_mode):
    titulo = "Conceito Médio por Pelotão" if view_mode == 'Conceito Final' else "Saldo Médio de Pontos por Pelotão"
    st.subheader(titulo)

    if acoes_df.empty: st.info("Dados de ações insuficientes para gerar este relatório."); return

    soma_pontos_por_aluno = acoes_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
    alunos_com_pontos = pd.merge(alunos_df, soma_pontos_por_aluno.rename('pontos_acoes'), left_on='id', right_on='aluno_id', how='left')
    alunos_com_pontos['pontos_acoes'] = alunos_com_pontos['pontos_acoes'].fillna(0)

    if view_mode == 'Conceito Final':
        alunos_com_pontos['valor_final'] = alunos_com_pontos.apply(lambda row: calcular_conceito_final(row['pontos_acoes'], float(row.get('media_academica', 0.0)), alunos_df, config_dict), axis=1)
    else:
        alunos_com_pontos['valor_final'] = alunos_com_pontos['pontos_acoes']

    media_por_pelotao = alunos_com_pontos.groupby('pelotao')['valor_final'].mean().reset_index()
    fig = px.bar(media_por_pelotao, x='pelotao', y='valor_final', title=titulo, text_auto='.2f')
    
    fig.update_layout(template="plotly_white")
    st.plotly_chart(fig, use_container_width=True, theme=None) # <-- CORREÇÃO APLICADA

def show_distribuicao_acoes(acoes_df):
    st.subheader("Distribuição de Tipos de Ação")
    if not acoes_df.empty and 'nome' in acoes_df.columns:
        contagem_tipos = acoes_df['nome'].value_counts().reset_index()
        contagem_tipos.columns = ['Tipo de Ação', 'Quantidade']
        fig = px.pie(contagem_tipos, values='Quantidade', names='Tipo de Ação', title='Distribuição de Tipos de Ação no Período', hole=0.4)

        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, theme=None) # <-- CORREÇÃO APLICADA
    else:
        st.info("Nenhuma ação para analisar nos filtros selecionados.")

def show_ranking_acoes(acoes_df):
    st.subheader("Ranking de Tipos de Ação Registrados")
    if acoes_df.empty or 'nome' not in acoes_df.columns:
        st.info("Nenhuma ação para analisar."); return

    col1, col2 = st.columns(2)
    with col1:
        positivas = acoes_df[acoes_df['pontuacao_efetiva'] > 0]['nome'].value_counts().nlargest(5).reset_index()
        positivas.columns = ['Tipo de Ação', 'Ocorrências']
        st.write("Top 5 Ações Positivas:")
        st.dataframe(positivas, use_container_width=True)
    with col2:
        negativas = acoes_df[acoes_df['pontuacao_efetiva'] < 0]['nome'].value_counts().nlargest(5).reset_index()
        negativas.columns = ['Tipo de Ação', 'Ocorrências']
        st.write("Top 5 Ações Negativas:")
        st.dataframe(negativas, use_container_width=True)

def show_evolucao_individual_comparativa(acoes_df, alunos_df, config_dict, view_mode):
    st.subheader("Comparativo de Evolução Individual")
    
    opcoes_alunos = {aluno['id']: f"{aluno['nome_guerra']} ({aluno.get('pelotao', 'N/A')})" for _, aluno in alunos_df.iterrows()}
    alunos_selecionados_ids = st.multiselect("Selecione um ou mais alunos para comparar:", options=list(opcoes_alunos.keys()), format_func=opcoes_alunos.get)

    if not alunos_selecionados_ids:
        st.info("Selecione pelo menos um aluno para ver a evolução."); return

    df_plot = pd.DataFrame()
    for aluno_id in alunos_selecionados_ids:
        acoes_aluno = acoes_df[acoes_df['aluno_id'] == aluno_id].copy()
        if not acoes_aluno.empty:
            acoes_aluno.sort_values('data', inplace=True)
            soma_pontos_acoes = acoes_aluno['pontuacao_efetiva'].cumsum()
            aluno_info = alunos_df[alunos_df['id'] == aluno_id].iloc[0]
            if view_mode == 'Conceito Final':
                media_acad = float(aluno_info.get('media_academica', 0.0))
                acoes_aluno['valor_final'] = soma_pontos_acoes.apply(lambda x: calcular_conceito_final(x, media_acad, alunos_df, config_dict))
            else:
                acoes_aluno['valor_final'] = soma_pontos_acoes
            acoes_aluno['nome_guerra'] = aluno_info['nome_guerra']
            df_plot = pd.concat([df_plot, acoes_aluno])

    if not df_plot.empty:
        titulo = "Evolução do Conceito Final" if view_mode == 'Conceito Final' else "Evolução do Saldo de Pontos"
        fig = px.line(df_plot, x='data', y='valor_final', color='nome_guerra', title=titulo, markers=True, labels={'valor_final': view_mode, 'nome_guerra': 'Aluno'})

        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, theme=None) # <-- CORREÇÃO APLICADA

def show_evolucao_pelotao_comparativa(acoes_df, alunos_df, config_dict, view_mode):
    st.subheader("Comparativo de Evolução por Pelotão")
    opcoes_pelotao = sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
    pelotoes_selecionados = st.multiselect("Selecione um ou mais pelotões para comparar:", options=opcoes_pelotao, default=opcoes_pelotao)

    if not pelotoes_selecionados:
        st.info("Selecione pelo menos um pelotão."); return
        
    df_plot = pd.DataFrame()
    for pelotao in pelotoes_selecionados:
        alunos_do_pelotao_ids = alunos_df[alunos_df['pelotao'] == pelotao]['id'].tolist()
        acoes_pelotao = acoes_df[acoes_df['aluno_id'].isin(alunos_do_pelotao_ids)].copy()
        if not acoes_pelotao.empty:
            acoes_pelotao.sort_values('data', inplace=True)
            soma_pontos_acoes = acoes_pelotao.groupby('data')['pontuacao_efetiva'].sum().cumsum()
            
            df_temp = soma_pontos_acoes.reset_index()
            if view_mode == 'Conceito Final':
                linha_base = float(config_dict.get('linha_base_conceito', 8.5))
                df_temp['valor_final'] = linha_base + df_temp['pontuacao_efetiva'] / len(alunos_do_pelotao_ids)
            else:
                df_temp['valor_final'] = df_temp['pontuacao_efetiva']
            
            df_temp['pelotao'] = pelotao
            df_plot = pd.concat([df_plot, df_temp])
    
    if not df_plot.empty:
        titulo = "Evolução do Conceito Médio" if view_mode == 'Conceito Final' else "Evolução do Saldo de Pontos Total"
        fig = px.line(df_plot, x='data', y='valor_final', color='pelotao', title=titulo, markers=True, labels={'valor_final': view_mode})
        
        fig.update_layout(template="plotly_white")
        st.plotly_chart(fig, use_container_width=True, theme=None) # <-- CORREÇÃO APLICADA

# =============================================================================
# FUNÇÃO PRINCIPAL DA PÁGINA
# =============================================================================
def show_relatorios():
    st.title("Relatórios e Análises")
    if not check_permission('acesso_pagina_relatorios'):
        st.error("Acesso negado."); return

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    if alunos_df.empty or acoes_df.empty:
        st.warning("Dados insuficientes para gerar relatórios."); return

    acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    if not acoes_com_pontos_df.empty:
        acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')

    st.subheader("Painel de Controle de Relatórios")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            view_mode = st.radio("Visualizar dados por:", ["Conceito Final", "Variação de Pontos"], horizontal=True, key="view_mode")
        with col2:
            tipos_opcoes = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
            tipo_acao_filtro = st.selectbox("Filtrar por Tipo de Ação:", tipos_opcoes)
        
        periodo_opts = ["Todo o Período", "Hoje", "Esta Semana", "Este Mês", "Intervalo Personalizado"]
        periodo_tipo = st.selectbox("Filtrar Período", periodo_opts, key="periodo_tipo")
        start_date, end_date = None, datetime.now().date()
        if periodo_tipo != "Todo o Período":
            if periodo_tipo == "Hoje": start_date = end_date
            elif periodo_tipo == "Esta Semana": start_date = end_date - timedelta(days=end_date.weekday())
            elif periodo_tipo == "Este Mês": start_date = end_date.replace(day=1)
            elif periodo_tipo == "Intervalo Personalizado":
                c_start, c_end = st.columns(2)
                start_date = c_start.date_input("Data Inicial", end_date - timedelta(days=30))
                end_date = c_end.date_input("Data Final", end_date)

    acoes_filtradas = acoes_com_pontos_df.copy()
    if tipo_acao_filtro != "Todos":
        acoes_filtradas = acoes_filtradas[acoes_filtradas['nome'] == tipo_acao_filtro]
    if start_date:
        acoes_filtradas = acoes_filtradas[(acoes_filtradas['data'].dt.date >= start_date) & (acoes_filtradas['data'].dt.date <= end_date)]

    st.write("") 
    pelotoes_validos = sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
    pelotoes = ["Todos os Pelotões"] + pelotoes_validos
    pelotao_selecionado = st.selectbox("Filtrar por Pelotão", pelotoes, key="pelotao_filtro")

    alunos_filtrados = alunos_df.copy()
    if pelotao_selecionado != "Todos os Pelotões":
        alunos_filtrados = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]
        aluno_ids_do_pelotao = alunos_filtrados['id'].tolist()
        acoes_filtradas = acoes_filtradas[acoes_filtradas['aluno_id'].isin(aluno_ids_do_pelotao)]

    st.divider()
    tab1, tab2, tab3 = st.tabs(["📊 Gráficos", "🏆 Rankings", "📈 Evolução"])

    with tab1:
        render_graficos_tab(acoes_filtradas, alunos_filtrados, config_dict, view_mode)
    with tab2:
        render_rankings_tab(acoes_filtradas, alunos_filtrados)
    with tab3:
        render_evolucao_tab(acoes_filtradas, alunos_filtrados, config_dict, view_mode)
