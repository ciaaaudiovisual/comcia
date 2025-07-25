import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data, init_supabase_client
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode
import plotly.express as px
from alunos import calcular_pontuacao_efetiva
from auth import check_permission
import pytz

# --- ALTERAÇÃO: Importar o componente de seleção de alunos ---
from aluno_selection_components import render_alunos_filter_and_selection

# --- FUNÇÕES AUXILIARES ---
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
def load_dashboard_data():
    """Carrega todos os dados necessários para o dashboard e os armazena no session_state."""
    if 'dashboard_data_loaded' not in st.session_state:
        st.session_state.alunos_df = load_data("Alunos")
        st.session_state.acoes_df = load_data("Acoes")
        st.session_state.tipos_acao_df = load_data("Tipos_Acao")
        st.session_state.config_df = load_data("Config")
        st.session_state.ordens_df = load_data("Ordens_Diarias")
        st.session_state.tarefas_df = load_data("Tarefas")
        st.session_state.dashboard_data_loaded = True

# --- PÁGINA PRINCIPAL DO DASHBOARD (MODIFICADA) ---
def show_dashboard():
    # Garante que os dados são carregados apenas uma vez por sessão
    load_dashboard_data()

    # Pega os dados do session_state em vez de chamar load_data repetidamente
    alunos_df = st.session_state.alunos_df
    acoes_df = st.session_state.acoes_df
    tipos_acao_df = st.session_state.tipos_acao_df
    config_df = st.session_state.config_df

    user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
    st.title(f"Dashboard - Bem-vindo(a), {user_display_name}!")
    
    display_pending_items()
    
    supabase = init_supabase_client()
    
    if 'scanner_ativo' not in st.session_state: st.session_state.scanner_ativo = False
    if 'alunos_escaneados_df' not in st.session_state: st.session_state.alunos_escaneados_df = pd.DataFrame()

    acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df) if not acoes_df.empty and not tipos_acao_df.empty else pd.DataFrame()

    if check_permission('pode_escanear_cracha'):
        with st.expander("⚡ Anotação Rápida em Massa", expanded=False):
            if st.button("📸 Iniciar/Parar Leitor de Crachás", type="primary"):
                st.session_state.scanner_ativo = not st.session_state.scanner_ativo
                if not st.session_state.scanner_ativo:
                    st.session_state.alunos_escaneados_df = pd.DataFrame()

            if st.session_state.scanner_ativo:
                with st.container(border=True):
                    st.info("O modo scanner está ativo. Aponte a câmera para um ou mais crachás e tire a foto.")
                    imagem_cracha = st.camera_input("Escanear Crachá(s)", label_visibility="collapsed")
                    if imagem_cracha is not None:
                        nips, msg = decodificar_codigo_de_barras(imagem_cracha)
                        if nips and 'nip' in alunos_df.columns:
                            alunos_encontrados_df = alunos_df[alunos_df['nip'].isin(nips)]
                            if not alunos_encontrados_df.empty:
                                st.session_state.alunos_escaneados_df = pd.concat([st.session_state.alunos_escaneados_df, alunos_encontrados_df]).drop_duplicates(subset=['id'])
                                st.toast(f"Alunos adicionados: {', '.join(alunos_encontrados_df['nome_guerra'].tolist())}", icon="✅")
                            else: st.warning("Nenhum aluno encontrado com o(s) NIP(s) lido(s).")
                        else: st.error(msg)
            
            st.subheader("Seleção de Alunos")
            alunos_selecionados_df = render_alunos_filter_and_selection(key_suffix="dashboard_quick_action", include_full_name_search=True)
            
            if not st.session_state.alunos_escaneados_df.empty:
                alunos_selecionados_df = pd.concat([alunos_selecionados_df, st.session_state.alunos_escaneados_df]).drop_duplicates(subset=['id'])

            with st.form("anotacao_rapida_form"):
                if not alunos_selecionados_df.empty:
                    nomes_selecionados = ", ".join(alunos_selecionados_df['nome_guerra'].tolist())
                    st.info(f"A ação será registrada para ({len(alunos_selecionados_df)}): **{nomes_selecionados}**")
                else: st.warning("Nenhum aluno selecionado.")

                opcoes_finais, tipos_opcoes_map = [], {}
                if not tipos_acao_df.empty:
                    tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
                    for df, cat in [(tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome'), "POSITIVAS"),
                                    (tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome'), "NEUTRAS"),
                                    (tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome'), "NEGATIVAS")]:
                        if not df.empty:
                            opcoes_finais.append(f"--- AÇÕES {cat} ---")
                            for _, r in df.iterrows():
                                opcoes_finais.append(r['nome']); tipos_opcoes_map[r['nome']] = r
                
                tipo_selecionado_str = st.selectbox("Tipo de Ação", options=opcoes_finais)
                descricao = st.text_area("Descrição da Ação (Opcional)")
                
                if st.form_submit_button("Registrar Ação"):
                    if alunos_selecionados_df.empty or not tipo_selecionado_str or tipo_selecionado_str.startswith("---"):
                        st.warning("Selecione ao menos um aluno e um tipo de ação válido.")
                    else:
                        try:
                            ids_alunos = alunos_selecionados_df['id'].tolist()
                            tipo_info = tipos_opcoes_map[tipo_selecionado_str]
                            novas_acoes = [{'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 'descricao': descricao, 'data': datetime.now().strftime('%Y-%m-%d'), 'usuario': st.session_state.username, 'status': 'Pendente', 'lancado_faia': False} for aluno_id in ids_alunos]
                            if novas_acoes:
                                supabase.table("Acoes").insert(novas_acoes).execute()
                                st.success(f"Ação registrada para {len(novas_acoes)} aluno(s)!")
                                # Limpa os dados para forçar recarregamento na próxima vez
                                del st.session_state.dashboard_data_loaded
                                st.session_state.alunos_escaneados_df = pd.DataFrame()
                                load_data.clear() 
                                st.rerun()
                        except Exception as e:
                            st.error(f"Falha ao salvar a(s) ação(ões): {e}")
    st.divider()
    if alunos_df.empty or acoes_com_pontos_df.empty:
        st.info("Registre alunos e ações para visualizar os painéis de dados.")
    else:
        acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')
        acoes_com_nomes_df = pd.merge(acoes_com_pontos_df, alunos_df[['id', 'nome_guerra']], left_on='aluno_id', right_on='id', how='left')
        if 'nome_guerra' in acoes_com_nomes_df:
            acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)
        
        fuso_horario_local = pytz.timezone('America/Sao_Paulo')
        hoje = datetime.now(fuso_horario_local).date()
        data_limite = hoje - timedelta(days=2)

        df_filtrado = acoes_com_nomes_df[
            (acoes_com_nomes_df['data'].dt.tz_convert(fuso_horario_local).dt.date >= data_limite) &
            (acoes_com_nomes_df['pontuacao_efetiva'] != 0) &
            (acoes_com_nomes_df['status'] != 'Arquivado')
        ].copy()
        
        df_filtrado = df_filtrado.sort_values(by="data", ascending=False)
        
        st.header("Destaques dos Últimos 3 Dias")
        col_pos, col_neg = st.columns(2)

        def render_highlights(dataframe, title, is_expanded):
            st.markdown(f"#### {title}")
            st.write("---")
            if dataframe.empty:
                st.info("Nenhum registro para exibir."); return
            
            # Agrupa por data já convertida para o fuso horário local
            for day, day_df in dataframe.groupby(dataframe['data'].dt.tz_convert(fuso_horario_local).dt.date):
                label = f"🗓️ {day.strftime('%d de %B')} ({len(day_df)} {'item' if len(day_df) == 1 else 'itens'})"
                with st.expander(label, expanded=is_expanded):
                    for _, acao in day_df.iterrows():
                        st.markdown(f"**{acao.get('nome_guerra')}**: {acao.get('tipo', 'N/A')}")
                        st.caption(f"*{acao.get('descricao', 'Sem descrição.')}*")
                is_expanded = False # Expande apenas o primeiro dia
        
        with col_pos: render_highlights(df_filtrado[df_filtrado['pontuacao_efetiva'] > 0], "✅ Destaques Positivos", True)
        with col_neg: render_highlights(df_filtrado[df_filtrado['pontuacao_efetiva'] < 0], "⚠️ Destaques Negativos", True)
        
        st.divider()
        st.subheader("Análise de Desempenho por Pelotão")
        
        if 'pelotao' in alunos_df.columns:
            pelotoes_para_exibir = sorted(alunos_df['pelotao'].dropna().unique().tolist())
            chart_mode = st.radio("Visualização do gráfico:", ["Conceito Médio", "Soma de Pontos (Valor)", "Quantidade de Anotações"], horizontal=True)
            
            acoes_com_alunos_df = pd.merge(acoes_com_pontos_df, alunos_df[alunos_df['pelotao'].isin(pelotoes_para_exibir)][['id', 'pelotao']], left_on='aluno_id', right_on='id', how='inner')
            
            if acoes_com_alunos_df.empty:
                st.info(f"Nenhuma ação encontrada para os pelotões: {', '.join(pelotoes_para_exibir)}")
            else:
                if chart_mode == "Conceito Médio":
                    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
                    linha_base_conceito = float(config_dict.get('linha_base_conceito', 8.5))
                    soma_pontos_por_aluno = acoes_com_alunos_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
                    alunos_com_pontuacao = pd.merge(alunos_df[alunos_df['pelotao'].isin(pelotoes_para_exibir)], soma_pontos_por_aluno.rename('soma_pontos'), left_on='id', right_on='aluno_id', how='left')
                    alunos_com_pontuacao['soma_pontos'] = alunos_com_pontuacao['soma_pontos'].fillna(0)
                    alunos_com_pontuacao['pontuacao_final'] = linha_base_conceito + alunos_com_pontuacao['soma_pontos']
                    media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().reset_index()
                    fig = px.bar(media_por_pelotao, x='pelotao', y='pontuacao_final', title='Conceito Médio por Pelotão', labels={'pelotao': 'Pelotão', 'pontuacao_final': 'Conceito Médio'}, color='pontuacao_final', color_continuous_scale='RdYlGn', text_auto='.2f')
                    st.plotly_chart(fig, use_container_width=True)

                elif chart_mode == "Soma de Pontos (Valor)":
                    soma_por_pelotao = acoes_com_alunos_df.groupby('pelotao')['pontuacao_efetiva'].sum().reset_index()
                    fig = px.bar(soma_por_pelotao, x='pelotao', y='pontuacao_efetiva', title='Saldo de Pontos por Pelotão', labels={'pelotao': 'Pelotão', 'pontuacao_efetiva': 'Saldo de Pontos'}, color='pontuacao_efetiva', color_continuous_scale='RdYlGn', text_auto='.1f')
                    st.plotly_chart(fig, use_container_width=True)

                else: # Quantidade de Anotações
                    contagem_por_tipo = acoes_com_alunos_df.copy()
                    contagem_por_tipo['Tipo de Anotação'] = np.where(contagem_por_tipo['pontuacao_efetiva'] > 0, 'Positivas', 'Negativas')
                    contagem_df = contagem_por_tipo.groupby(['pelotao', 'Tipo de Anotação']).size().reset_index(name='Quantidade')
                    fig = px.bar(contagem_df, x='pelotao', y='Quantidade', color='Tipo de Anotação', barmode='group', title='Quantidade de Anotações por Pelotão', labels={'pelotao': 'Pelotão'}, color_discrete_map={'Positivas': 'green', 'Negativas': 'red'}, text_auto=True)
                    st.plotly_chart(fig, use_container_width=True)

        st.subheader("🎂 Aniversariantes (Próximos 7 dias e Últimos 7 dias)")
        if not alunos_df.empty and 'data_nascimento' in alunos_df.columns:
            alunos_df['data_nascimento'] = pd.to_datetime(alunos_df['data_nascimento'], errors='coerce')
            alunos_nasc_validos = alunos_df.dropna(subset=['data_nascimento'])
            
            # Lógica para encontrar o período de 14 dias (semana passada + semana atual/próxima)
            dia_da_semana_hoje = hoje.weekday() 
            domingo_semana_atual = hoje - timedelta(days=dia_da_semana_hoje) + timedelta(days=6)
            inicio_periodo_busca = domingo_semana_atual - timedelta(days=13)
            
            aniversarios_periodo = [(inicio_periodo_busca + timedelta(days=i)).strftime('%m-%d') for i in range(14)]
            aniversariantes_df = alunos_nasc_validos[alunos_nasc_validos['data_nascimento'].dt.strftime('%m-%d').isin(aniversarios_periodo)].copy()
            
            if not aniversariantes_df.empty:
                aniversariantes_df['dia_mes'] = aniversariantes_df['data_nascimento'].dt.strftime('%m-%d')
                aniversariantes_df = aniversariantes_df.sort_values(by='dia_mes')
                for _, aluno in aniversariantes_df.iterrows():
                    st.success(f"**{aluno.get('numero_interno', 'N/A')}** - **{aluno['nome_guerra']}** - {aluno['data_nascimento'].strftime('%d/%m')}")
            else:
                st.info("Nenhum aniversariante no período.")
