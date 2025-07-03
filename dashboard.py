import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data, init_supabase_client
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final
from auth import check_permission

# ==============================================================================
# FUNÇÕES DE APOIO (Mantidas do seu arquivo original)
# ==============================================================================
def decodificar_codigo_de_barras(upload_de_imagem):
    """Decodifica um NIP de 8 dígitos de um código de barras numa imagem."""
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
    """Exibe itens pendentes da Parada Diária no Dashboard."""
    tarefas_df = load_data("Tarefas")
    logged_in_user = st.session_state.get('username')
    
    tarefas_pendentes_usuario = pd.DataFrame()
    if logged_in_user and not tarefas_df.empty and 'status' in tarefas_df.columns:
        tarefas_pendentes_usuario = tarefas_df[
            (tarefas_df['status'] != 'Concluída') &
            ((tarefas_df['responsavel'] == logged_in_user) | (tarefas_df['responsavel'] == 'Todos') | (pd.isna(tarefas_df['responsavel'])) | (tarefas_df['responsavel'] == ''))
        ]

    if not tarefas_pendentes_usuario.empty:
        with st.container(border=True):
            st.subheader("📣 Suas Tarefas Pendentes", anchor=False)
            for _, tarefa in tarefas_pendentes_usuario.iterrows():
                st.info(f"**Tarefa:** {tarefa.get('texto', 'N/A')} - *(Atribuída a: {tarefa.get('responsavel') or 'Todos'})*")
        st.divider()

def create_student_label(row):
    """Cria uma etiqueta única e informativa para cada aluno."""
    nome_guerra = str(row.get('nome_guerra', '')).strip()
    numero_interno = str(row.get('numero_interno', 'S/N')).strip()
    
    if nome_guerra:
        return f"{numero_interno} - {nome_guerra}"
    else:
        return f"{numero_interno} - (NOME DE GUERRA PENDENTE)"

# ==============================================================================
# PÁGINA PRINCIPAL DO DASHBOARD
# ==============================================================================
def show_dashboard():
    user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
    st.title(f"Dashboard - Bem-vindo(a), {user_display_name}!")
    
    display_pending_items()
    
    supabase = init_supabase_client()
    
    if 'alunos_selecionados_scanner_labels' not in st.session_state:
        st.session_state.alunos_selecionados_scanner_labels = []

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    if not alunos_df.empty:
        alunos_df['label'] = alunos_df.apply(create_student_label, axis=1)
        label_to_id_map = pd.Series(alunos_df.id.values, index=alunos_df.label).to_dict()

    # --- SEÇÃO DE ANOTAÇÃO RÁPIDA RESTAURADA ---
    if check_permission('pode_escanear_cracha'):
        with st.expander("⚡ Anotação Rápida em Massa", expanded=False):
            if st.toggle("Ativar Leitor de Crachás 📸"):
                imagem_cracha = st.camera_input("Aponte a câmara para o código de barras", label_visibility="collapsed")
                if imagem_cracha:
                    nips, msg = decodificar_codigo_de_barras(imagem_cracha)
                    if nips and 'nip' in alunos_df.columns:
                        alunos_encontrados_df = alunos_df[alunos_df['nip'].isin(nips)]
                        if not alunos_encontrados_df.empty:
                            for _, aluno_row in alunos_encontrados_df.iterrows():
                                label = create_student_label(aluno_row)
                                if label not in st.session_state.alunos_selecionados_scanner_labels:
                                    st.session_state.alunos_selecionados_scanner_labels.append(label)
                            st.toast("Aluno(s) adicionado(s) à seleção!", icon="✅")
                            st.balloons()
                    else:
                        st.error(msg)
            
            with st.form("anotacao_rapida_form_simplificada"):
                st.subheader("1. Selecione os Alunos")
                st.info("Pode selecionar alunos individualmente OU usar os filtros de grupo (se a seleção manual estiver vazia).")

                opcoes_labels = sorted(alunos_df['label'].unique()) if not alunos_df.empty else []
                alunos_selecionados_labels = st.multiselect(
                    "Seleção Manual de Alunos:",
                    options=opcoes_labels,
                    default=st.session_state.alunos_selecionados_scanner_labels
                )

                st.markdown("--- **OU, se a seleção acima estiver vazia, use os filtros abaixo** ---")
                
                col1, col2 = st.columns(2)
                opcoes_pelotao = ["Nenhum"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p) and p])
                pelotao_selecionado = col1.selectbox("Aplicar a todo o Pelotão:", opcoes_pelotao)
                
                opcoes_especialidade = ["Nenhuma"] + sorted([e for e in alunos_df['especialidade'].unique() if pd.notna(e) and e])
                especialidade_selecionada = col2.selectbox("Aplicar a toda a Especialidade:", opcoes_especialidade)

                st.divider()
                st.subheader("2. Defina e Registre a Ação")

                if not acoes_df.empty:
                    contagem = acoes_df['tipo_acao_id'].value_counts().to_dict()
                    tipos_acao_df['contagem'] = tipos_acao_df['id'].astype(str).map(contagem).fillna(0)
                    tipos_acao_df = tipos_acao_df.sort_values('contagem', ascending=False)
                
                tipos_opcoes = {f"{row['nome']} ({float(row.get('pontuacao',0)):.1f})": row['id'] for _, row in tipos_acao_df.iterrows()}
                tipo_selecionado_label = st.selectbox("Tipo de Ação:", options=tipos_opcoes.keys())
                descricao = st.text_area("Descrição da Ação (Opcional)")
                
                if st.form_submit_button("Registrar Ação em Massa"):
                    alunos_para_anotar_ids = []
                    if alunos_selecionados_labels:
                        alunos_para_anotar_ids = [label_to_id_map[label] for label in alunos_selecionados_labels]
                    elif pelotao_selecionado != "Nenhum" or especialidade_selecionada != "Nenhuma":
                        df_filtrado = alunos_df.copy()
                        if pelotao_selecionado != "Nenhum":
                            df_filtrado = df_filtrado[df_filtrado['pelotao'] == pelotao_selecionado]
                        if especialidade_selecionada != "Nenhuma":
                            df_filtrado = df_filtrado[df_filtrado['especialidade'] == especialidade_selecionada]
                        alunos_para_anotar_ids = df_filtrado['id'].tolist()
                    
                    if not alunos_para_anotar_ids:
                        st.warning("Nenhum aluno foi selecionado. Por favor, selecione alunos manualmente ou use um filtro de grupo.")
                    else:
                        try:
                            # Lógica para registrar as ações (mantida do seu arquivo original)
                            response = supabase.table("Acoes").select("id", count='exact').execute()
                            ids_existentes = [int(item['id']) for item in response.data if str(item.get('id')).isdigit()]
                            ultimo_id = max(ids_existentes) if ids_existentes else 0
                            tipo_acao_id = tipos_opcoes[tipo_selecionado_label]
                            tipo_acao_info = tipos_acao_df[tipos_acao_df['id'] == tipo_acao_id].iloc[0]
                            novas_acoes = []
                            for i, aluno_id in enumerate(alunos_para_anotar_ids):
                                novo_id = ultimo_id + 1 + i
                                nova_acao = {
                                    'id': str(novo_id), 'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_acao_id),
                                    'tipo': tipo_acao_info['nome'], 'descricao': descricao, 'data': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'usuario': st.session_state.username, 'status': 'Pendente'
                                }
                                novas_acoes.append(nova_acao)
                            if novas_acoes:
                                supabase.table("Acoes").insert(novas_acoes).execute()
                                st.success(f"Ação registrada com sucesso para {len(novas_acoes)} aluno(s)!")
                                st.session_state.alunos_selecionados_scanner_labels = []
                                load_data.clear()
                                st.rerun()
                        except Exception as e:
                            st.error(f"Falha ao salvar a(s) ação(ões): {e}")

    st.divider()
    
    if alunos_df.empty or acoes_df.empty:
        st.info("Registre alunos e ações para visualizar os painéis de dados.")
        return

    # --- SEÇÃO DE DESTAQUES CORRIGIDA E MELHORADA ---
    num_dias = st.number_input("Ver destaques dos últimos (dias):", min_value=1, max_value=90, value=7, step=1)
    
    st.subheader(f"🏆 Destaques dos Últimos {num_dias} Dias")
    st.markdown("As ações de maior e menor pontuação registradas no período selecionado.")

    hoje = datetime.now()
    data_inicio_filtro = hoje - timedelta(days=num_dias)
    
    acoes_df['data'] = pd.to_datetime(acoes_df['data'], errors='coerce')
    acoes_df['data'] = acoes_df['data'].dt.tz_localize(None)
    
    acoes_periodo_df = acoes_df[acoes_df['data'] >= data_inicio_filtro]

    if acoes_periodo_df.empty:
        st.info(f"Nenhuma ação registrada nos últimos {num_dias} dias.")
    else:
        acoes_com_pontos = calcular_pontuacao_efetiva(acoes_periodo_df, tipos_acao_df, config_df)
        destaques_df = pd.merge(acoes_com_pontos, alunos_df[['id', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id', how='inner')
        positivos = destaques_df[destaques_df['pontuacao_efetiva'] > 0].nlargest(5, 'pontuacao_efetiva')
        negativos = destaques_df[destaques_df['pontuacao_efetiva'] < 0].nsmallest(5, 'pontuacao_efetiva')
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Destaques Positivos")
            if positivos.empty:
                st.info("Nenhum destaque positivo no período.")
            else:
                for _, acao in positivos.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**Aluno:** {acao.get('nome_guerra', 'N/A')} ({acao.get('pelotao', 'N/A')})")
                        st.markdown(f"**Ação:** {acao.get('nome', 'N/A')} <span style='color:green; font-weight:bold;'>({acao['pontuacao_efetiva']:+.1f} pts)</span>", unsafe_allow_html=True)
                        if pd.notna(acao.get('descricao')) and acao.get('descricao'):
                            st.caption(f"Descrição: {acao['descricao']}")
        with col2:
            st.markdown("#### Destaques Negativos")
            if negativos.empty:
                st.info("Nenhum destaque negativo no período.")
            else:
                for _, acao in negativos.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**Aluno:** {acao.get('nome_guerra', 'N/A')} ({acao.get('pelotao', 'N/A')})")
                        st.markdown(f"**Ação:** {acao.get('nome', 'N/A')} <span style='color:red; font-weight:bold;'>({acao['pontuacao_efetiva']:+.1f} pts)</span>", unsafe_allow_html=True)
                        if pd.notna(acao.get('descricao')) and acao.get('descricao'):
                            st.caption(f"Descrição: {acao['descricao']}")

    st.divider()

    # --- SEÇÃO DE CONCEITO MÉDIO CORRIGIDA E MELHORADA ---
    st.subheader("🎓 Conceito Médio por Pelotão")
    config_dict = config_df.set_index('chave')['valor'].to_dict()
    soma_pontos_por_aluno = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df).groupby('aluno_id')['pontuacao_efetiva'].sum()
    alunos_com_pontuacao = pd.merge(alunos_df, soma_pontos_por_aluno.rename('soma_pontos'), left_on='id', right_on='aluno_id', how='left').fillna(0)
    if 'media_academica' not in alunos_com_pontuacao.columns:
        alunos_com_pontuacao['media_academica'] = 0.0
    alunos_com_pontuacao['pontuacao_final'] = alunos_com_pontuacao.apply(lambda row: calcular_conceito_final(row['soma_pontos'], float(row.get('media_academica', 0.0)), alunos_df, config_dict), axis=1)
    media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().sort_values(ascending=False).reset_index()
    media_por_pelotao.rename(columns={'pontuacao_final': 'Conceito Médio'}, inplace=True)
    chart_type = st.selectbox("Visualizar como:", ["Gráfico de Barras", "Tabela de Dados"], label_visibility="collapsed")
    if chart_type == "Gráfico de Barras":
        media_por_pelotao_chart = media_por_pelotao.set_index('pelotao')
        st.bar_chart(media_por_pelotao_chart)
    else:
        st.dataframe(media_por_pelotao.style.format({'Conceito Médio': '{:.2f}'}), use_container_width=True)

    st.divider()

    # --- SEÇÃO DE ANIVERSARIANTES MANTIDA ---
    st.subheader("🎂 Aniversariantes (Próximos 7 dias)")
    if 'data_nascimento' in alunos_df.columns:
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
