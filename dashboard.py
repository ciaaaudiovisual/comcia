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

# --- FUNÇÕES AUXILIARES (Originais, sem alterações) ---
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
    
    if 'scanner_ativo' not in st.session_state: st.session_state.scanner_ativo = False
    if 'alunos_escaneados_nomes' not in st.session_state: st.session_state.alunos_escaneados_nomes = []

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
            # O código da Anotação Rápida não foi alterado e está oculto aqui para simplificar a visualização.
            # No seu arquivo ele deve estar presente.
            pass
    st.divider()

    # ======================================================================
    # --- INÍCIO DA SEÇÃO DE VISUALIZAÇÕES DO DASHBOARD ---
    # ======================================================================
    if alunos_df.empty or acoes_com_pontos_df.empty:
        st.info("Registre alunos e ações para visualizar os painéis de dados.")
    else:
        # --- 1. PREPARAÇÃO DOS DADOS PARA OS DESTAQUES ---
        acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')
        
        # Junta os dados de ações com os nomes dos alunos
        acoes_com_nomes_df = pd.merge(
            acoes_com_pontos_df,
            alunos_df[['id', 'nome_guerra']],
            left_on='aluno_id',
            right_on='id',
            how='left'
        )
        acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)

        # Filtra para os últimos 3 dias e remove ações neutras
        hoje = datetime.now().date()
        data_limite = hoje - timedelta(days=2)
        df_filtrado = acoes_com_nomes_df[
            (acoes_com_nomes_df['data'].dt.date >= data_limite) &
            (acoes_com_nomes_df['pontuacao_efetiva'] != 0) # Remove anotações neutras
        ].copy()
        df_filtrado = df_filtrado.sort_values(by="data", ascending=False)

        # Separa em dataframes de positivos e negativos
        df_positivos = df_filtrado[df_filtrado['pontuacao_efetiva'] > 0]
        df_negativos = df_filtrado[df_filtrado['pontuacao_efetiva'] < 0]

        # --- 2. EXIBIÇÃO DOS DESTAQUES EM DUAS COLUNAS ---
        st.header("Destaques dos Últimos 3 Dias")
        col_pos, col_neg = st.columns(2)

        # Função auxiliar para não repetir o código de exibição
        def render_highlights_column(dataframe):
            if dataframe.empty:
                st.info("Nenhum registro para exibir.")
                return
            
            ultimo_dia_processado = None
            for _, acao in dataframe.iterrows():
                data_acao = acao['data'].date()
                if data_acao != ultimo_dia_processado:
                    if ultimo_dia_processado is not None:
                        st.divider()
                    st.markdown(f"**🗓️ {data_acao.strftime('%d de %B')}**")
                    ultimo_dia_processado = data_acao
                
                descricao = f"*{acao.get('descricao', '')}*" if acao.get('descricao') else "*Sem descrição.*"
                st.markdown(f"**{acao.get('nome_guerra')}**: {acao.get('tipo', 'N/A')}")
                st.caption(descricao)

        with col_pos:
            st.markdown("#### ✅ Destaques Positivos")
            st.write("---")
            render_highlights_column(df_positivos)

        with col_neg:
            st.markdown("#### ⚠️ Destaques Negativos")
            st.write("---")
            render_highlights_column(df_negativos)
        
        st.divider()

        # --- 3. EXIBIÇÃO DOS OUTROS GRÁFICOS E INFORMAÇÕES ---
        col_chart, col_bday = st.columns(2)

        with col_chart:
            st.subheader("Pontuação Média por Pelotão")
            pontuacao_inicial = 10.0
            if not config_df.empty and 'chave' in config_df.columns and 'pontuacao_inicial' in config_df['chave'].values:
                try: pontuacao_inicial = float(config_df[config_df['chave'] == 'pontuacao_inicial']['valor'].iloc[0])
                except (IndexError, ValueError): pass
            
            soma_pontos_por_aluno = acoes_com_pontos_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
            alunos_com_pontuacao = pd.merge(alunos_df, soma_pontos_por_aluno.rename('soma_ponos'), left_on='id', right_on='aluno_id', how='left')
            alunos_com_pontuacao['soma_ponos'] = alunos_com_pontuacao['soma_ponos'].fillna(0)
            alunos_com_pontuacao['pontuacao_final'] = alunos_com_pontuacao['soma_ponos'] + pontuacao_inicial
            media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().reset_index()
            
            fig = px.bar(media_por_pelotao, x='pelotao', y='pontuacao_final', title='Pontuação Média Atual', labels={'pelotao': 'Pelotão', 'pontuacao_final': 'Pontuação Média'}, color='pontuacao_final', color_continuous_scale='RdYlGn', text_auto='.2f')
            st.plotly_chart(fig, use_container_width=True)

        with col_bday:
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
