import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
import math

# --- FUNÇÃO HELPER DE CÁLCULO DE PONTUAÇÃO (Sem alterações) ---
def calcular_pontuacao_efetiva(acoes_df: pd.DataFrame, tipos_acao_df: pd.DataFrame, config_df: pd.DataFrame) -> pd.DataFrame:
    if acoes_df.empty or tipos_acao_df.empty:
        return pd.DataFrame()
        
    if 'pontuacao' not in tipos_acao_df.columns:
        return pd.DataFrame()

    acoes_copy = acoes_df.copy()
    tipos_copy = tipos_acao_df.copy()

    tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
    acoes_copy['tipo_acao_id'] = acoes_copy['tipo_acao_id'].astype(str)
    tipos_copy['id'] = tipos_copy['id'].astype(str)
    
    acoes_com_pontos = pd.merge(acoes_copy, tipos_copy[['id', 'pontuacao', 'nome']], left_on='tipo_acao_id', right_on='id', how='left')
    
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    fator_adaptacao = float(config_dict.get('fator_adaptacao', 0.25))
    try:
        inicio_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_inicio')).date()
        fim_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_fim')).date()
    except Exception:
        inicio_adaptacao, fim_adaptacao = None, None

    def aplicar_fator(row):
        pontuacao = row.get('pontuacao', 0.0)
        data_convertida = pd.to_datetime(row['data'], errors='coerce')
        if pd.isna(data_convertida):
            return pontuacao
        
        data_acao = data_convertida.date()

        if pontuacao >= 0 or not inicio_adaptacao: return pontuacao
        
        if inicio_adaptacao <= data_acao <= fim_adaptacao:
            return pontuacao * fator_adaptacao
        return pontuacao
        
    acoes_com_pontos['pontuacao_efetiva'] = acoes_com_pontos.apply(aplicar_fator, axis=1)
    return acoes_com_pontos

# --- FUNÇÃO PARA CALCULAR O CONCEITO FINAL (Sem alterações) ---
def calcular_conceito_final(soma_pontos_acoes: float, media_academica_aluno: float, todos_alunos_df: pd.DataFrame, config_dict: dict) -> float:
    linha_base = float(config_dict.get('linha_base_conceito', 8.5))
    impacto_max_acoes = float(config_dict.get('impacto_max_acoes', 1.5))
    peso_academico = float(config_dict.get('peso_academico', 1.0))

    impacto_acoes = max(-impacto_max_acoes, min(soma_pontos_acoes, impacto_max_acoes))
    impacto_academico = 0.0
    
    if 'media_academica' in todos_alunos_df.columns and not todos_alunos_df.empty:
        medias_validas = pd.to_numeric(todos_alunos_df['media_academica'], errors='coerce').dropna()
        if not medias_validas.empty and medias_validas.max() > medias_validas.min():
            media_min_turma = medias_validas.min()
            media_max_turma = medias_validas.max()
            if (media_max_turma - media_min_turma) > 0:
                fator_normalizado = (media_academica_aluno - media_min_turma) / (media_max_turma - media_min_turma)
                impacto_academico = fator_normalizado * peso_academico
    
    conceito_final = linha_base + impacto_acoes + impacto_academico
    return max(0.0, min(conceito_final, 10.0))

# --- DIÁLOGO DE REGISTRO DE AÇÃO (Sem alterações) ---
@st.dialog("Registrar Nova Ação")
def registrar_acao_dialog(aluno_id, aluno_nome, supabase):
    st.write(f"Aluno: **{aluno_nome}**")
    tipos_acao_df = load_data("Tipos_Acao")
    if tipos_acao_df.empty:
        st.error("Não há tipos de ação cadastrados."); return
    with st.form("nova_acao_dialog_form"):
        tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao', 0.0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
        tipo_selecionado_str = st.selectbox("Tipo de Ação", options=list(tipos_opcoes.keys()))
        descricao = st.text_area("Descrição/Justificativa")
        data = st.date_input("Data da Ação", value=datetime.now())
        if st.form_submit_button("Registrar"):
            if not descricao or not tipo_selecionado_str:
                st.warning("Descrição e Tipo de Ação são obrigatórios."); return
            try:
                acoes_df = load_data("Acoes")
                tipo_info = tipos_opcoes[tipo_selecionado_str]
                ids = pd.to_numeric(acoes_df['id'], errors='coerce').dropna()
                novo_id = int(ids.max()) + 1 if not ids.empty else 1
                nova_acao = {'id': str(novo_id), 'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.strftime('%Y-%m-%d'), 'usuario': st.session_state.username}
                supabase.table("Acoes").insert(nova_acao).execute()
                st.success("Ação registrada com sucesso!"); load_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Falha ao registrar a ação: {e}")

# --- PÁGINA PRINCIPAL (MODIFICADA) ---
def show_alunos():
    st.title("Gestão de Alunos")
    supabase = init_supabase_client()
    if 'page_num' not in st.session_state: st.session_state.page_num = 1
    def reset_page(): st.session_state.page_num = 1

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    if 'media_academica' not in alunos_df.columns: alunos_df['media_academica'] = 0.0
    if tipos_acao_df.empty:
        st.error("ERRO CRÍTICO: Tabela 'Tipos_Acao' não encontrada. Cadastre os tipos de ação primeiro."); st.stop()

    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    
    # --- OTIMIZAÇÃO: Bloco de pré-cálculo de pontos e conceitos para todos os alunos ---
    soma_pontos_por_aluno = pd.DataFrame()
    if not acoes_df.empty:
        acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
        if not acoes_com_pontos.empty:
            soma_pontos_por_aluno = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum().reset_index()
            soma_pontos_por_aluno.rename(columns={'pontuacao_efetiva': 'soma_pontos_acoes'}, inplace=True)

    if not soma_pontos_por_aluno.empty:
        alunos_df = pd.merge(alunos_df, soma_pontos_por_aluno, left_on='id', right_on='aluno_id', how='left')
    else:
        alunos_df['soma_pontos_acoes'] = 0
    
    alunos_df['soma_pontos_acoes'] = alunos_df['soma_pontos_acoes'].fillna(0)

    alunos_df['conceito_final_calculado'] = alunos_df.apply(
        lambda row: calcular_conceito_final(
            row['soma_pontos_acoes'],
            float(row.get('media_academica', 0.0)),
            alunos_df,
            config_dict
        ),
        axis=1
    )
    # --- FIM DO BLOCO DE OTIMIZAÇÃO ---

    # Seção de Filtros, Busca e Ordenação
    st.subheader("Filtros e Ordenação")
    col1, col2 = st.columns(2)
    with col1:
        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
        pelotao_selecionado = st.selectbox("Filtrar por Pelotão:", opcoes_pelotao, on_change=reset_page)
        opcoes_especialidade = ["Todas"] + sorted([e for e in alunos_df['especialidade'].unique() if pd.notna(e)])
        especialidade_selecionada = st.selectbox("Filtrar por Especialidade:", opcoes_especialidade, on_change=reset_page)
    with col2:
        search = st.text_input("Buscar por nome ou número...", key="search_aluno", on_change=reset_page)
        # --- NOVO: Seletor de ordenação ---
        sort_option = st.selectbox(
            "Ordenar por:",
            ["Padrão (Nº Interno)", "Maior Conceito", "Menor Conceito"],
            key="sort_aluno",
            on_change=reset_page
        )

    # Lógica de filtragem
    filtered_df = alunos_df.copy()
    if pelotao_selecionado != "Todos": filtered_df = filtered_df[filtered_df['pelotao'] == pelotao_selecionado]
    if especialidade_selecionada != "Todas": filtered_df = filtered_df[filtered_df['especialidade'] == especialidade_selecionada]
    if search:
        search_lower = search.lower()
        mask = (filtered_df['nome_guerra'].str.lower().str.contains(search_lower, na=False) | 
                filtered_df['numero_interno'].astype(str).str.contains(search_lower, na=False) |
                filtered_df['nome_completo'].str.lower().str.contains(search_lower, na=False))
        filtered_df = filtered_df[mask]

    # --- NOVO: Lógica de ordenação ---
    if sort_option == "Maior Conceito":
        filtered_df = filtered_df.sort_values(by='conceito_final_calculado', ascending=False)
    elif sort_option == "Menor Conceito":
        filtered_df = filtered_df.sort_values(by='conceito_final_calculado', ascending=True)
    else: # Padrão (Nº Interno)
        # Garante que a coluna de número interno seja numérica para ordenação correta
        filtered_df['numero_interno_num'] = pd.to_numeric(filtered_df['numero_interno'], errors='coerce')
        filtered_df = filtered_df.sort_values(by='numero_interno_num', ascending=True)

    st.divider()

    # Expander de Cadastro
    if check_permission('pode_importar_alunos'):
        with st.expander("➕ Opções de Cadastro"):
            st.subheader("Adicionar Novo Aluno")
            with st.form("add_aluno_form", clear_on_submit=True):
                c1,c2 = st.columns(2); numero_interno = c1.text_input("Número Interno*"); nome_guerra = c2.text_input("Nome de Guerra*")
                nome_completo = st.text_input("Nome Completo")
                c3,c4 = st.columns(2); pelotao = c3.text_input("Pelotão*"); especialidade = c4.text_input("Especialidade")
                if st.form_submit_button("Adicionar Aluno"):
                    if not all([numero_interno, nome_guerra, pelotao]): st.warning("Número, Nome de Guerra e Pelotão são obrigatórios.")
                    else:
                        try:
                            ids = pd.to_numeric(alunos_df['id'], errors='coerce').dropna()
                            novo_id = int(ids.max()) + 1 if not ids.empty else 1
                            novo_aluno = {'id': str(novo_id), 'numero_interno': numero_interno, 'nome_guerra': nome_guerra, 'nome_completo': nome_completo, 'pelotao': pelotao, 'especialidade': especialidade}
                            supabase.table("Alunos").insert(novo_aluno).execute()
                            st.success(f"Aluno {nome_guerra} adicionado!"); load_data.clear(); st.rerun()
                        except Exception as e: st.error(f"Erro ao adicionar aluno: {e}")
            
            st.divider()
            st.subheader("Importar Alunos em Massa (CSV)")
            st.info("Funcionalidade de importação de CSV a ser implementada.")


    st.divider()
    
    # Lógica de Paginação
    ITEMS_PER_PAGE = 30
    total_items = len(filtered_df); total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
    if st.session_state.page_num > total_pages: st.session_state.page_num = total_pages
    start_idx = (st.session_state.page_num - 1) * ITEMS_PER_PAGE; end_idx = start_idx + ITEMS_PER_PAGE
    paginated_df = filtered_df.iloc[start_idx:end_idx]
    st.subheader(f"Alunos Exibidos ({len(paginated_df)} de {total_items})")

    # Loop de exibição
    if not paginated_df.empty:
        for _, aluno in paginated_df.iterrows():
            aluno_id = aluno['id']
            with st.container(border=True):
                col_img, col_info, col_actions = st.columns([1, 4, 1])
                
                soma_pontos_observacional = aluno['soma_pontos_acoes']
                conceito_final_aluno = aluno['conceito_final_calculado']

                with col_img:
                    st.image(aluno.get('url_foto', "https://via.placeholder.com/100?text=Sem+Foto"), width=100)
                
                with col_info:
                    st.markdown(f"**{aluno.get('nome_guerra', 'N/A')}** (`{aluno.get('numero_interno', 'N/A')}`)")
                    st.caption(f"Nome: {aluno.get('nome_completo', 'Não informado')}")
                    st.write(f"Pelotão: {aluno.get('pelotao', 'N/A')} | Especialidade: {aluno.get('especialidade', 'N/A')}")
                    cor_conceito = "green" if conceito_final_aluno >= 8.5 else "orange" if conceito_final_aluno >= 7.0 else "red"
                    
                    if check_permission('pode_ver_conceito_final'):
                        st.markdown(f"**Conceito Final:** <span style='color:{cor_conceito}; font-size: 1.2em; font-weight: bold;'>{conceito_final_aluno:.2f}</span> | **Pontuação Geral:** `{soma_pontos_observacional:+.2f} pts`", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**Pontuação Geral:** `{soma_pontos_observacional:+.2f} pts`", unsafe_allow_html=True)

                with col_actions:
                    if st.button("➕ Ação", key=f"acao_{aluno_id}"):
                        registrar_acao_dialog(aluno_id, aluno.get('nome_guerra', 'N/A'), supabase)
                    if st.button("👁️ Detalhes", key=f"detalhes_{aluno_id}"):
                        st.session_state.aluno_em_foco_id = aluno_id if st.session_state.get('aluno_em_foco_id') != aluno_id else None
                        st.rerun()

                # Painel de detalhes
                if st.session_state.get('aluno_em_foco_id') == aluno_id:
                    with st.container(border=True):
                        tab_ver, tab_editar = st.tabs(["Ver Histórico", "Editar Dados"])
                        with tab_ver:
                            st.subheader("Histórico de Ações")
                            acoes_do_aluno = acoes_df[acoes_df['aluno_id'].astype(str) == str(aluno_id)] if not acoes_df.empty and 'aluno_id' in acoes_df.columns else pd.DataFrame()
                            if acoes_do_aluno.empty: st.info("Nenhuma ação registrada.")
                            else:
                                historico_com_pontos = calcular_pontuacao_efetiva(acoes_do_aluno.copy(), tipos_acao_df, config_df)
                                if not historico_com_pontos.empty:
                                    for _, acao in historico_com_pontos.sort_values("data", ascending=False).iterrows():
                                        pontos = acao.get('pontuacao_efetiva', 0.0)
                                        cor = "green" if pontos > 0 else "red" if pontos < 0 else "gray"
                                        st.markdown(f"**{pd.to_datetime(acao['data']).strftime('%d/%m/%Y')} - {acao.get('nome', 'N/A')}** (`{pontos:+.1f} pts`): {acao.get('descricao','')}")
                        
                        with tab_editar:
                            if check_permission('pode_editar_aluno'):
                                st.subheader("Editar Dados do Aluno")
                                with st.form(key=f"edit_form_{aluno_id}"):
                                    st.subheader("Informações Acadêmicas")
                                    new_media_academica = st.number_input(
                                        "Média Acadêmica Final", 
                                        value=float(aluno.get('media_academica', 0.0)), 
                                        min_value=0.0, max_value=10.0, step=0.1, format="%.2f"
                                    )
                                    st.divider()
                                    
                                    st.subheader("Dados Pessoais")
                                    new_nome_completo = st.text_input("Nome Completo", value=aluno.get('nome_completo', ''))
                                    new_nome_guerra = st.text_input("Nome de Guerra", value=aluno.get('nome_guerra', ''))
                                    new_numero_interno = st.text_input("Número Interno", value=aluno.get('numero_interno', ''))
                                    new_pelotao = st.text_input("Pelotão", value=aluno.get('pelotao', ''))
                                    new_especialidade = st.text_input("Especialidade", value=aluno.get('especialidade', ''))
                                    new_url_foto = st.text_input("URL da Foto", value=aluno.get('url_foto', ''))
                                    
                                    if st.form_submit_button("Salvar Alterações"):
                                        dados_update = {
                                            'media_academica': new_media_academica, 
                                            'nome_completo': new_nome_completo,
                                            'nome_guerra': new_nome_guerra,
                                            'numero_interno': new_numero_interno, 
                                            'pelotao': new_pelotao,
                                            'especialidade': new_especialidade, 
                                            'url_foto': new_url_foto
                                        }
                                        try:
                                            supabase.table("Alunos").update(dados_update).eq("id", aluno_id).execute()
                                            st.success("Dados atualizados!")
                                            load_data.clear()
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Erro ao atualizar: {e}")
                            else:
                                st.info("Você não tem permissão para editar os dados do aluno.")
    
    st.divider()
    
    # Controles de Paginação
    if total_pages > 1:
        col_prev, col_page, col_next = st.columns([2, 1, 2])
        with col_prev:
            if st.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.page_num <= 1)):
                st.session_state.page_num -= 1; st.rerun()
        with col_page:
            st.write(f"Página **{st.session_state.page_num} de {total_pages}**")
        with col_next:
            if st.button("Próxima ➡️", use_container_width=True, disabled=(st.session_state.page_num >= total_pages)):
                st.session_state.page_num += 1; st.rerun()
