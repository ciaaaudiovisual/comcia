import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data, init_supabase_client
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode
import plotly.express as px
from acoes import calcular_pontuacao_efetiva
from auth import check_permission

# --- FUNÇÕES AUXILIARES (Sem alterações) ---
def decodificar_codigo_de_barras(upload_de_imagem):
    """Lê um arquivo de imagem e retorna uma lista de NIPs encontrados."""
    try:
        imagem = Image.open(upload_de_imagem)
        imagem_cv = np.array(imagem)
        codigos_barras = decode(imagem_cv)
        nips_encontrados = []
        if not codigos_barras:
            return nips_encontrados, "Nenhum código de barras encontrado na imagem."
        for codigo in codigos_barras:
            nip = codigo.data.decode('utf-8')
            if len(nip) == 8 and nip.isdigit():
                nips_encontrados.append(nip)
        if not nips_encontrados:
            return [], "Código(s) de barras encontrado(s), mas nenhum é um NIP válido (8 dígitos)."
        return nips_encontrados, f"{len(nips_encontrados)} NIP(s) encontrado(s) com sucesso!"
    except Exception as e:
        return [], f"Erro ao processar a imagem: {e}"

def display_pending_items():
    """Mostra um painel unificado de ordens do dia e tarefas pendentes."""
    ordens_df = load_data("Ordens_Diarias")
    tarefas_df = load_data("Tarefas")
    logged_in_user = st.session_state.get('username')
    ordens_pendentes_hoje = pd.DataFrame()
    if not ordens_df.empty and 'status' in ordens_df.columns:
        hoje = datetime.now().date()
        ordens_df['data'] = pd.to_datetime(ordens_df['data']).dt.date
        ordens_pendentes_hoje = ordens_df[(ordens_df['status'] == 'Pendente') & (ordens_df['data'] == hoje)]
    tarefas_pendentes_usuario = pd.DataFrame()
    if logged_in_user and not tarefas_df.empty and 'status' in tarefas_df.columns:
        tarefas_pendentes_usuario = tarefas_df[(tarefas_df['status'] != 'Concluída') & ((tarefas_df['responsavel'] == logged_in_user) | (tarefas_df['responsavel'] == 'Todos') | (pd.isna(tarefas_df['responsavel'])) | (tarefas_df['responsavel'] == ''))]
    if not ordens_pendentes_hoje.empty or not tarefas_pendentes_usuario.empty:
        with st.container(border=True):
            st.subheader("📣 Ordens e Tarefas Pendentes", anchor=False)
            if not ordens_pendentes_hoje.empty:
                st.markdown("**Ordens do Dia:**")
                for _, ordem in ordens_pendentes_hoje.iterrows():
                    st.warning(f"**Ordem:** {ordem.get('texto', 'N/A')} - *Por: {ordem.get('autor_id', 'N/A')}*")
            if not tarefas_pendentes_usuario.empty:
                st.markdown("**Suas Tarefas Pendentes:**")
                for _, tarefa in tarefas_pendentes_usuario.iterrows():
                    st.info(f"**Tarefa:** {tarefa.get('texto', 'N/A')} - *(Atribuída a: {tarefa.get('responsavel') or 'Todos'})*")
        st.divider()

# --- PÁGINA PRINCIPAL DO DASHBOARD ---
def show_dashboard():
    user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
    st.title(f"Dashboard - Bem-vindo(a), {user_display_name}!")
    
    display_pending_items()
    
    supabase = init_supabase_client()
    
    if 'scanner_ativo' not in st.session_state:
        st.session_state.scanner_ativo = False
    if 'alunos_escaneados_nomes' not in st.session_state:
        st.session_state.alunos_escaneados_nomes = []

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if not acoes_df.empty and not tipos_acao_df.empty:
        acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    else:
        acoes_com_pontos_df = pd.DataFrame()

    if check_permission('pode_escanear_cracha'):
        with st.expander("⚡ Anotação Rápida em Massa", expanded=False):
            # O código do scanner e do formulário de anotação em massa permanece aqui.
            # Foi ocultado nesta resposta para focar na mudança do gráfico, mas ele existe no seu código.
            pass
    st.divider()

    if alunos_df.empty or acoes_com_pontos_df.empty:
        st.info("Registre alunos e ações para visualizar os painéis de dados.")
    else:
        # --- PREPARAÇÃO DE DADOS (Sem alterações) ---
        acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')
        acoes_com_nomes_df = pd.merge(acoes_com_pontos_df, alunos_df[['id', 'nome_guerra']], left_on='aluno_id', right_on='id', how='left')
        acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)
        hoje = datetime.now().date()
        data_limite = hoje - timedelta(days=2)
        df_filtrado = acoes_com_nomes_df[(acoes_com_nomes_df['data'].dt.date >= data_limite) & (acoes_com_nomes_df['pontuacao_efetiva'] != 0)].copy()
        df_filtrado = df_filtrado.sort_values(by="data", ascending=False)
        df_positivos = df_filtrado[df_filtrado['pontuacao_efetiva'] > 0]
        df_negativos = df_filtrado[df_filtrado['pontuacao_efetiva'] < 0]

        # --- SEÇÃO DE DESTAQUES (Sem alterações) ---
        st.header("Destaques dos Últimos 3 Dias")
        col_pos, col_neg = st.columns(2)
        def render_highlights_column_collapsible(dataframe, is_first_day_expanded=True):
            if dataframe.empty:
                st.info("Nenhum registro para exibir.")
                return
            grouped_by_day = dataframe.groupby(dataframe['data'].dt.date)
            sorted_days = sorted(grouped_by_day.groups.keys(), reverse=True)
            is_first_iteration = True
            for day in sorted_days:
                day_df = grouped_by_day.get_group(day)
                label = f"🗓️ {day.strftime('%d de %B de %Y')} ({len(day_df)} {'item' if len(day_df) == 1 else 'itens'})"
                should_be_expanded = is_first_iteration and is_first_day_expanded
                with st.expander(label, expanded=should_be_expanded):
                    for _, acao in day_df.iterrows():
                        descricao = f"*{acao.get('descricao', '')}*" if acao.get('descricao') else "*Sem descrição.*"
                        st.markdown(f"**{acao.get('nome_guerra')}**: {acao.get('tipo', 'N/A')}")
                        st.caption(descricao)
                is_first_iteration = False
        with col_pos:
            st.markdown("#### ✅ Destaques Positivos")
            st.write("---")
            render_highlights_column_collapsible(df_positivos)
        with col_neg:
            st.markdown("#### ⚠️ Destaques Negativos")
            st.write("---")
            render_highlights_column_collapsible(df_negativos)
        st.divider()
        
        # --- GRÁFICO DE PELOTÃO COM VISUALIZAÇÃO DINÂMICA ---
        st.subheader("Análise de Desempenho por Pelotão")
        
        chart_mode = st.radio(
            "Selecione o modo de visualização do gráfico:",
            ["Conceito Médio", "Soma de Pontos (Positivo vs. Negativo)"],
            horizontal=True,
            key="chart_view_mode"
        )

        if chart_mode == "Conceito Médio":
            pontuacao_inicial = 10.0
            if not config_df.empty and 'chave' in config_df.columns and 'pontuacao_inicial' in config_df['chave'].values:
                try: pontuacao_inicial = float(config_df[config_df['chave'] == 'pontuacao_inicial']['valor'].iloc[0])
                except (IndexError, ValueError): pass
            
            soma_pontos_por_aluno = acoes_com_pontos_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
            alunos_com_pontuacao = pd.merge(alunos_df, soma_pontos_por_aluno.rename('soma_pontos'), left_on='id', right_on='aluno_id', how='left')
            alunos_com_pontuacao['soma_pontos'] = alunos_com_pontuacao['soma_pontos'].fillna(0)
            alunos_com_pontuacao['pontuacao_final'] = alunos_com_pontuacao['soma_pontos'] + pontuacao_inicial
            media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().reset_index()
            
            fig = px.bar(media_por_pelotao, 
                         x='pelotao', 
                         y='pontuacao_final', 
                         title='Conceito Médio Atual por Pelotão', 
                         labels={'pelotao': 'Pelotão', 'pontuacao_final': 'Conceito Médio'}, 
                         color='pontuacao_final', 
                         color_continuous_scale='RdYlGn', 
                         text_auto='.2f')
            st.plotly_chart(fig, use_container_width=True)

        else: # Soma de Pontos (Positivo vs. Negativo)
            acoes_com_alunos_df = pd.merge(acoes_com_pontos_df, alunos_df[['id', 'pelotao']], left_on='aluno_id', right_on='id', how='left')
            
            acoes_com_alunos_df['pontos_positivos'] = acoes_com_alunos_df['pontuacao_efetiva'].where(acoes_com_alunos_df['pontuacao_efetiva'] > 0, 0)
            acoes_com_alunos_df['pontos_negativos'] = acoes_com_alunos_df['pontuacao_efetiva'].where(acoes_com_alunos_df['pontuacao_efetiva'] < 0, 0)
            
            soma_por_pelotao = acoes_com_alunos_df.groupby('pelotao')[['pontos_positivos', 'pontos_negativos']].sum().reset_index()

            df_melted = pd.melt(soma_por_pelotao, 
                                id_vars=['pelotao'], 
                                value_vars=['pontos_positivos', 'pontos_negativos'], 
                                var_name='Tipo de Pontuação', 
                                value_name='Total de Pontos')
            
            df_melted['Tipo de Pontuação'] = df_melted['Tipo de Pontuação'].map({'pontos_positivos': 'Positivos', 'pontos_negativos': 'Negativos'})

            fig = px.bar(df_melted, 
                         x='pelotao', 
                         y='Total de Pontos', 
                         color='Tipo de Pontuação',
                         barmode='group',
                         title='Soma de Pontos Positivos vs. Negativos por Pelotão',
                         labels={'pelotao': 'Pelotão', 'Total de Pontos': 'Soma dos Pontos'},
                         color_discrete_map={'Positivos': 'green', 'Negativos': 'red'},
                         text_auto='.1f')
            st.plotly_chart(fig, use_container_width=True)

        # --- SEÇÃO DE ANIVERSARIANTES (Sem alterações) ---
        st.subheader("🎂 Aniversariantes (Próximos 7 dias)")
        if not alunos_df.empty and 'data_nascimento' in alunos_df.columns:
            alunos_df['data_nascimento'] = pd.to_datetime(alunos_df['data_nascimento'], errors='coerce')
            alunos_nasc_validos = alunos_df.dropna(subset=['data_nascimento'])
            hoje = datetime.now().date()
            periodo_de_dias = [hoje + timedelta(days=i) for i in range(7)]
            aniversarios_no_periodo = [d.strftime('%m-%d') for d in periodo_de_dias]
            aniversariantes_df = alunos_nasc_validos[alunos_nasc_validos['data_nascimento'].dt.strftime('%m-%d').isin(aniversarios_no_periodo)].copy()
            if not aniversariantes_df.empty:
                aniversariantes_df['dia_mes'] = aniversariantes_df['data_nascimento'].dt.strftime('%m-%d')
                aniversariantes_df = aniversariantes_df.sort_values(by='dia_mes')
                for _, aluno in aniversariantes_df.iterrows():
                    st.success(f"**{aluno['nome_guerra']}** - {aluno['data_nascimento'].strftime('%d/%m')}")
            else:
                st.info("Nenhum aniversariante nos próximos 7 dias.")
