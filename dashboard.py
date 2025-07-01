import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data, init_supabase_client
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode
import plotly.express as px
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final
from auth import check_permission

# --- FUNÇÃO PARA DECODIFICAR CÓDIGO DE BARRAS (Sem alterações) ---
def decodificar_codigo_de_barras(upload_de_imagem):
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

# --- FUNÇÃO PARA EXIBIR ORDENS E TAREFAS PENDENTES (Sem alterações) ---
def display_pending_items():
    ordens_df = load_data("Ordens_Diarias")
    tarefas_df = load_data("Tarefas")
    logged_in_user = st.session_state.get('username')
    
    ordens_pendentes_hoje = pd.DataFrame()
    if not ordens_df.empty and 'status' in ordens_df.columns:
        hoje = datetime.now().date()
        ordens_df['data'] = pd.to_datetime(ordens_df['data']).dt.date
        ordens_pendentes_hoje = ordens_df[
            (ordens_df['status'] == 'Pendente') & (ordens_df['data'] == hoje)
        ]

    tarefas_pendentes_usuario = pd.DataFrame()
    if logged_in_user and not tarefas_df.empty and 'status' in tarefas_df.columns:
        tarefas_pendentes_usuario = tarefas_df[
            (tarefas_df['status'] != 'Concluída') &
            ((tarefas_df['responsavel'] == logged_in_user) | (tarefas_df['responsavel'] == 'Todos') | (pd.isna(tarefas_df['responsavel'])) | (tarefas_df['responsavel'] == ''))
        ]

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

# --- PÁGINA PRINCIPAL DO DASHBOARD (Sem alterações) ---
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
                        if nips and 'nip' in alunos_df.columns:
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
                            st.error(msg)
            
            with st.form("anotacao_rapida_form"):
                modo_selecao = st.radio("Modo de Seleção de Alunos:", ["Por Filtro", "Seleção Manual (inclui scanner)"], horizontal=True, key="modo_selecao_alunos")
                
                alunos_para_anotar_ids = []
                
                if modo_selecao == "Por Filtro":
                    st.write("Aplique a ação a todos os alunos que correspondem aos filtros abaixo:")
                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
                        pelotao_selecionado = st.selectbox("Filtrar por Pelotão:", opcoes_pelotao)
                    with col_f2:
                        opcoes_especialidade = ["Todas"] + sorted([e for e in alunos_df['especialidade'].unique() if pd.notna(e)])
                        especialidade_selecionada = st.selectbox("Filtrar por Especialidade:", opcoes_especialidade)

                else: # Modo Seleção Manual
                    if not alunos_df.empty:
                        alunos_opcoes_dict = {f"{aluno['nome_guerra']} (Nº: {aluno.get('numero_interno', 'S/N')})": aluno['id'] for _, aluno in alunos_df.sort_values('nome_guerra').iterrows()}
                        alunos_opcoes_labels = list(alunos_opcoes_dict.keys())
                    else:
                        alunos_opcoes_dict, alunos_opcoes_labels = {}, []

                    alunos_selecionados_labels = st.multiselect(
                        "Selecione os Alunos", 
                        options=alunos_opcoes_labels,
                        default=[label for label, id_aluno in alunos_opcoes_dict.items() if alunos_df[alunos_df['id'] == id_aluno].iloc[0]['nome_guerra'] in st.session_state.get('alunos_escaneados_nomes', [])]
                    )

                st.divider()
                
                if not acoes_df.empty:
                    contagem_acoes = acoes_df['tipo_acao_id'].value_counts().to_dict()
                    tipos_acao_df['contagem'] = tipos_acao_df['id'].astype(str).map(contagem_acoes).fillna(0)
                    tipos_acao_df = tipos_acao_df.sort_values('contagem', ascending=False)
                
                tipos_opcoes = {f"{row['nome']} ({float(row.get('pontuacao',0)):.1f})": row['id'] for _, row in tipos_acao_df.iterrows()} if not tipos_acao_df.empty else {}
                tipo_selecionado_label = st.selectbox("Tipo de Ação (mais usados primeiro)", options=tipos_opcoes.keys())
                descricao = st.text_area("Descrição da Ação (Opcional)")
                
                if st.form_submit_button("Registrar Ação em Massa"):
                    if modo_selecao == "Por Filtro":
                        df_filtrado = alunos_df.copy()
                        if pelotao_selecionado != "Todos":
                            df_filtrado = df_filtrado[df_filtrado['pelotao'] == pelotao_selecionado]
                        if especialidade_selecionada != "Todas":
                            df_filtrado = df_filtrado[df_filtrado['especialidade'] == especialidade_selecionada]
                        alunos_para_anotar_ids = df_filtrado['id'].tolist()
                    else: # Modo Seleção Manual
                        alunos_para_anotar_ids = [alunos_opcoes_dict[label] for label in alunos_selecionados_labels]

                    if not alunos_para_anotar_ids or not tipo_selecionado_label:
                        st.warning("Selecione ao menos um aluno (ou um filtro) e um tipo de ação.")
                    else:
                        try:
                            tipo_acao_id = tipos_opcoes[tipo_selecionado_label]
                            tipo_acao_info = tipos_acao_df[tipos_acao_df['id'] == tipo_acao_id].iloc[0]
                            novas_acoes = []
                            for aluno_id in alunos_para_anotar_ids:
                                nova_acao = {'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_acao_id),'tipo': tipo_acao_info['nome'],'descricao': descricao,'data': datetime.now().strftime('%Y-%m-%d'),'usuario': st.session_state.username,'lancado_faia': False}
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
        hoje = datetime.now().date()
        acoes_hoje = acoes_com_pontos_df.dropna(subset=['data'])[acoes_com_pontos_df['data'].dt.date == hoje]

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Destaques do Dia")
            if not acoes_hoje.empty:
                soma_pontos_hoje = acoes_hoje.groupby('aluno_id')['pontuacao_efetiva'].sum()
                
                if not soma_pontos_hoje[soma_pontos_hoje > 0].empty:
                    aluno_positivo_id = str(soma_pontos_hoje.idxmax())
                    aluno_info = alunos_df[alunos_df['id'] == aluno_positivo_id]
                    if not aluno_info.empty: st.success(f"🌟 **Positivo**: {aluno_info.iloc[0]['nome_guerra']}")

                if not soma_pontos_hoje[soma_pontos_hoje < 0].empty:
                    aluno_negativo_id = str(soma_pontos_hoje.idxmin())
                    aluno_info = alunos_df[alunos_df['id'] == aluno_negativo_id]
                    if not aluno_info.empty: st.warning(f"⚠️ **Negativo**: {aluno_info.iloc[0]['nome_guerra']}")
            else:
                st.info("Nenhuma ação registrada hoje.")

        with col2:
            st.subheader("Pontuação Média por Pelotão")
            soma_pontos_por_aluno = acoes_com_pontos_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
            alunos_com_pontuacao = pd.merge(alunos_df, soma_pontos_por_aluno.rename('soma_pontos'), left_on='id', right_on='aluno_id', how='left').fillna(0)
            
            config_dict = config_df.set_index('chave')['valor'].to_dict()
            alunos_com_pontuacao['pontuacao_final'] = alunos_com_pontuacao.apply(
                lambda row: calcular_conceito_final(
                    row['soma_pontos'], float(row.get('media_academica', 0.0)), alunos_df, config_dict
                ), axis=1
            )
            media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().reset_index()
            
            fig = px.bar(media_por_pelotao, x='pelotao', y='pontuacao_final', title='Conceito Médio Atual', labels={'pelotao': 'Pelotão', 'pontuacao_final': 'Conceito Médio'}, color='pontuacao_final', color_continuous_scale='RdYlGn', text_auto='.2f')
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

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
