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
from alunos import calcular_pontuacao_efetiva

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
            if st.button("📸 Iniciar/Parar Leitor de Crachás", type="primary"):
                st.session_state.scanner_ativo = not st.session_state.scanner_ativo
                if not st.session_state.scanner_ativo:
                    st.session_state.alunos_escaneados_nomes = []

            if st.session_state.scanner_ativo:
                with st.container(border=True):
                    st.info("O modo scanner está ativo. Aponte a câmera para um ou mais crachás e tire a foto.")
                    imagem_cracha = st.camera_input("Escanear Crachá(s)", label_visibility="collapsed")
                    if imagem_cracha is not None:
                        nips, msg = decodificar_codigo_de_barras(imagem_cracha)
                        if nips:
                            if 'nip' in alunos_df.columns:
                                alunos_encontrados_df = alunos_df[alunos_df['nip'].isin(nips)]
                                if not alunos_encontrados_df.empty:
                                    nomes_encontrados = alunos_encontrados_df['nome_guerra'].tolist()
                                    novos_nomes = [nome for nome in nomes_encontrados if nome not in st.session_state.alunos_escaneados_nomes]
                                    st.session_state.alunos_escaneados_nomes.extend(novos_nomes)
                                    if novos_nomes: st.toast(f"Alunos adicionados: {', '.join(novos_nomes)}", icon="✅")
                                    else: st.toast("Todos os alunos escaneados já estavam na lista.", icon="ℹ️")
                                else:
                                    st.warning("Nenhum aluno encontrado no banco de dados com o(s) NIP(s) lido(s).")
                            else:
                                st.error("A coluna 'nip' não existe na tabela de Alunos para realizar a busca.")
                        else:
                            st.error(msg)
            
            with st.form("anotacao_rapida_form"):
                if not alunos_df.empty:
                    alunos_opcoes_dict = {f"{aluno['nome_guerra']} (Nº: {aluno.get('numero_interno', 'S/N')})": aluno['nome_guerra'] for _, aluno in alunos_df.sort_values('nome_guerra').iterrows()}
                    alunos_opcoes_labels = list(alunos_opcoes_dict.keys())
                else:
                    alunos_opcoes_dict = {}
                    alunos_opcoes_labels = []

                alunos_selecionados_labels = st.multiselect("Selecione os Alunos", options=alunos_opcoes_labels, default=[label for label, nome in alunos_opcoes_dict.items() if nome in st.session_state.get('alunos_escaneados_nomes', [])])
                alunos_selecionados = [alunos_opcoes_dict[label] for label in alunos_selecionados_labels]
                
                opcoes_finais, tipos_opcoes_map = [], {}
                if not tipos_acao_df.empty:
                    tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
                    positivas_df, neutras_df, negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')
                    if not positivas_df.empty:
                        opcoes_finais.append("--- AÇÕES POSITIVAS ---"); [opcoes_finais.append(r['nome']) or tipos_opcoes_map.update({r['nome']: r}) for _, r in positivas_df.iterrows()]
                    if not neutras_df.empty:
                        opcoes_finais.append("--- AÇÕES NEUTRAS ---"); [opcoes_finais.append(r['nome']) or tipos_opcoes_map.update({r['nome']: r}) for _, r in neutras_df.iterrows()]
                    if not negativas_df.empty:
                        opcoes_finais.append("--- AÇÕES NEGATIVAS ---"); [opcoes_finais.append(r['nome']) or tipos_opcoes_map.update({r['nome']: r}) for _, r in negativas_df.iterrows()]
                
                tipo_selecionado_str = st.selectbox("Tipo de Ação", options=opcoes_finais)
                descricao = st.text_area("Descrição da Ação (Opcional)")
                
                if st.form_submit_button("Registrar Ação"):
                    if not alunos_selecionados or not tipo_selecionado_str or tipo_selecionado_str.startswith("---"):
                        st.warning("Selecione ao menos um aluno e um tipo de ação válido.")
                    else:
                        try:
                            ids_alunos_selecionados = alunos_df[alunos_df['nome_guerra'].isin(alunos_selecionados)]['id'].tolist()
                            tipo_acao_info = tipos_opcoes_map[tipo_selecionado_str]
                            novas_acoes = []
                            for aluno_id in ids_alunos_selecionados:
                                nova_acao = {'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_acao_info['id']),'tipo': tipo_acao_info['nome'],'descricao': descricao,'data': datetime.now().strftime('%Y-%m-%d'),'usuario': st.session_state.username,'lancado_faia': False}
                                novas_acoes.append(nova_acao)
                            if novas_acoes:
                                supabase.table("Acoes").insert(novas_acoes).execute()
                                st.success(f"Ação registrada com sucesso para {len(novas_acoes)} aluno(s)!")
                                st.session_state.alunos_escaneados_nomes = []
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
        acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)
        hoje = datetime.now().date()
        data_limite = hoje - timedelta(days=2)
        df_filtrado = acoes_com_nomes_df[(acoes_com_nomes_df['data'].dt.date >= data_limite) & (acoes_com_nomes_df['pontuacao_efetiva'] != 0)].copy()
        df_filtrado = df_filtrado.sort_values(by="data", ascending=False)
        df_positivos = df_filtrado[df_filtrado['pontuacao_efetiva'] > 0]
        df_negativos = df_filtrado[df_filtrado['pontuacao_efetiva'] < 0]

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
        
        st.subheader("Análise de Desempenho por Pelotão")
        
        pelotoes_para_exibir = ["MIKE-1", "MIKE-2", "MIKE-3", "MIKE-4", "MIKE-5", "QTPA"]
        
        chart_mode = st.radio(
            "Selecione o modo de visualização do gráfico:",
            ["Conceito Médio", "Soma de Pontos (Valor)", "Quantidade de Anotações"],
            horizontal=True,
            key="chart_view_mode"
        )

        alunos_df_filtrado = alunos_df[alunos_df['pelotao'].isin(pelotoes_para_exibir)]
        acoes_com_alunos_df = pd.merge(acoes_com_pontos_df, alunos_df_filtrado[['id', 'pelotao']], left_on='aluno_id', right_on='id', how='inner')

        if acoes_com_alunos_df.empty:
            st.info(f"Nenhuma ação encontrada para os pelotões selecionados: {', '.join(pelotoes_para_exibir)}")
        else:
            if chart_mode == "Conceito Médio":
                pontuacao_inicial = 10.0
                if not config_df.empty and 'chave' in config_df.columns and 'pontuacao_inicial' in config_df['chave'].values:
                    try: pontuacao_inicial = float(config_df[config_df['chave'] == 'pontuacao_inicial']['valor'].iloc[0])
                    except (IndexError, ValueError): pass
                
                soma_pontos_por_aluno = acoes_com_alunos_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
                alunos_com_pontuacao = pd.merge(alunos_df_filtrado, soma_pontos_por_aluno.rename('soma_pontos'), left_on='id', right_on='aluno_id', how='left')
                alunos_com_pontuacao['soma_pontos'] = alunos_com_pontuacao['soma_pontos'].fillna(0)
                alunos_com_pontuacao['pontuacao_final'] = alunos_com_pontuacao['soma_pontos'] + pontuacao_inicial
                media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().reset_index()
                
                fig = px.bar(media_por_pelotao, x='pelotao', y='pontuacao_final', title='Conceito Médio Atual por Pelotão', labels={'pelotao': 'Pelotão', 'pontuacao_final': 'Conceito Médio'}, color='pontuacao_final', color_continuous_scale='RdYlGn', text_auto='.2f')
                st.plotly_chart(fig, use_container_width=True)

            elif chart_mode == "Soma de Pontos (Valor)":
                acoes_com_alunos_df['pontos_positivos'] = acoes_com_alunos_df['pontuacao_efetiva'].where(acoes_com_alunos_df['pontuacao_efetiva'] > 0, 0)
                acoes_com_alunos_df['pontos_negativos'] = acoes_com_alunos_df['pontuacao_efetiva'].where(acoes_com_alunos_df['pontuacao_efetiva'] < 0, 0)
                soma_por_pelotao = acoes_com_alunos_df.groupby('pelotao')[['pontos_positivos', 'pontos_negativos']].sum().reset_index()
                df_melted = pd.melt(soma_por_pelotao, id_vars=['pelotao'], value_vars=['pontos_positivos', 'pontos_negativos'], var_name='Tipo de Pontuação', value_name='Total de Pontos')
                df_melted['Tipo de Pontuação'] = df_melted['Tipo de Pontuação'].map({'pontos_positivos': 'Positivos', 'pontos_negativos': 'Negativos'})
                fig = px.bar(df_melted, x='pelotao', y='Total de Pontos', color='Tipo de Pontuação', barmode='group', title='Soma dos Valores de Pontos por Pelotão', labels={'pelotao': 'Pelotão', 'Total de Pontos': 'Soma dos Pontos'}, color_discrete_map={'Positivos': 'green', 'Negativos': 'red'}, text_auto='.1f')
                st.plotly_chart(fig, use_container_width=True)

            else: # Quantidade de Anotações
                df_positivas = acoes_com_alunos_df[acoes_com_alunos_df['pontuacao_efetiva'] > 0]
                df_negativas = acoes_com_alunos_df[acoes_com_alunos_df['pontuacao_efetiva'] < 0]
                contagem_positivas = df_positivas.groupby('pelotao').size().reset_index(name='Positivas')
                contagem_negativas = df_negativas.groupby('pelotao').size().reset_index(name='Negativas')
                
                contagem_df = pd.merge(contagem_positivas, contagem_negativas, on='pelotao', how='outer').fillna(0)
                
                df_melted = pd.melt(contagem_df, id_vars=['pelotao'], value_vars=['Positivas', 'Negativas'], var_name='Tipo de Anotação', value_name='Quantidade')

                fig = px.bar(df_melted, x='pelotao', y='Quantidade', color='Tipo de Anotação', barmode='group', title='Quantidade de Anotações por Pelotão', labels={'pelotao': 'Pelotão', 'Quantidade': 'Nº de Anotações'}, color_discrete_map={'Positivas': 'green', 'Negativas': 'red'}, text_auto=True)
                st.plotly_chart(fig, use_container_width=True)

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
