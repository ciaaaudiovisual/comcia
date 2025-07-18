import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
import zipfile
from io import BytesIO

# Tenta importar o componente real de seleção de alunos.
# Se falhar, usa uma versão mock para desenvolvimento/teste.
try:
    from aluno_selection_components import render_alunos_filter_and_selection
except ImportError:
    # Mock para desenvolvimento/teste se o arquivo não estiver presente
    def render_alunos_filter_and_selection(key_suffix, include_full_name_search=False):
        st.info(f"Componente de seleção de alunos mockado. (key: {key_suffix})")
        mock_alunos_data = [
            {"id": "mock-aluno-123", "nome_guerra": "Aluno Teste 1", "pelotao": "1", "numero_interno": "001"},
            {"id": "mock-aluno-456", "nome_guerra": "Aluno Teste 2", "pelotao": "2", "numero_interno": "002"},
        ]
        mock_alunos_df = pd.DataFrame(mock_alunos_data)
        st.markdown("##### Filtro de Alunos (Mock)")
        search_name = st.text_input("Buscar por Nome de Guerra:", key=f"search_name_{key_suffix}")
        filtered_df = mock_alunos_df[mock_alunos_df['nome_guerra'].str.contains(search_name, case=False, na=False)] if search_name else mock_alunos_df
        if not filtered_df.empty:
            options = filtered_df.apply(lambda row: f"{row['numero_interno']} - {row['nome_guerra']}", axis=1).tolist()
            selected_option = st.selectbox("Selecione Aluno(s):", options=options, key=f"select_aluno_{key_suffix}")
            if selected_option:
                selected_aluno_num_interno = selected_option.split(' - ')[0]
                return filtered_df[filtered_df['numero_interno'] == selected_aluno_num_interno]
        return pd.DataFrame()


@st.cache_resource
def init_supabase_client():
    url, key = None, None
    try:
        url, key = st.secrets.supabase.url, st.secrets.supabase.key
    except AttributeError:
        try:
            url, key = st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"]
        except KeyError:
            st.error("Credenciais do Supabase não encontradas. Configure em secrets.toml.")
            st.stop()
    return create_client(url, key)

@st.cache_data(ttl=300)
def load_data(table_name):
    supabase = init_supabase_client()
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()


@st.dialog("✏️ Editar Ação")
def edit_acao_dialog(acao_selecionada, tipos_acao_df, supabase):
    st.write(f"Editando ação para: **{acao_selecionada.get('nome_guerra', 'N/A')}**")
    # CORREÇÃO: Usa o id correto da ação (id_acao) para a chave do formulário
    with st.form(key=f"edit_form_{acao_selecionada['id_acao']}"):
        opcoes_tipo_acao = tipos_acao_df['nome'].unique().tolist()
        index_acao_atual = opcoes_tipo_acao.index(acao_selecionada['tipo']) if acao_selecionada.get('tipo') in opcoes_tipo_acao else 0
        novo_tipo_acao = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao_atual)
        data_atual = pd.to_datetime(acao_selecionada.get('data', datetime.now())).date()
        nova_data = st.date_input("Data da Ação", value=data_atual)
        nova_descricao = st.text_area("Descrição/Justificativa", value=acao_selecionada.get('descricao', ''))
        if st.form_submit_button("Salvar Alterações"):
            try:
                tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == novo_tipo_acao].iloc[0]
                update_data = {'tipo_acao_id': str(tipo_acao_info['id']), 'tipo': novo_tipo_acao, 'data': nova_data.strftime('%Y-%m-%d'), 'descricao': nova_descricao}
                # CORREÇÃO: Usa o id correto da ação (id_acao) para a query
                supabase.table("Acoes").update(update_data).eq('id', acao_selecionada['id_acao']).execute()
                st.toast("Ação atualizada com sucesso!", icon="✅"); load_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar as alterações: {e}")

def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
    texto = [
        "============================================================",
        f"FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)\n",
        f"Pelotão: {aluno_info.get('pelotao', 'N/A')}",
        f"Aluno: {aluno_info.get('nome_completo', 'N/A')}",
        f"Nome de Guerra: {aluno_info.get('nome_guerra', 'N/A')}",
        f"Numero Interno: {aluno_info.get('numero_interno', 'N/A')}",
        "\n------------------------------------------------------------",
        "LANÇAMENTOS (STATUS 'LANÇADO') EM ORDEM CRONOLÓGICA:",
        "------------------------------------------------------------\n"
    ]
    acoes_lancadas = acoes_aluno_df[acoes_aluno_df['status'] == 'Lançado']
    if acoes_lancadas.empty:
        texto.append("Nenhum lançamento com status 'Lançado' encontrado para este aluno.")
    else:
        for _, acao in acoes_lancadas.sort_values(by='data').iterrows():
            texto.extend([
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y')}",
                f"Tipo: {acao.get('tipo', 'Tipo Desconhecido')}",
                f"Descrição: {acao.get('descricao', '')}",
                f"Registrado por: {acao.get('usuario', 'N/A')}",
                "\n-----------------------------------\n"
            ])
    texto.extend([
        "\n============================================================",
        f"Fim do Relatório - Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "============================================================"
    ])
    return "\n".join(texto)

def bulk_update_status(ids_to_update, new_status, supabase):
    if not ids_to_update:
        st.warning("Nenhuma ação foi selecionada."); return
    try:
        supabase.table("Acoes").update({'status': new_status}).in_('id', ids_to_update).execute()
        st.toast(f"{len(ids_to_update)} ações foram atualizadas para '{new_status}'!", icon="✅")
        st.session_state.action_selection = {}; st.session_state.select_all_toggle = False
        load_data.clear(); st.rerun()
    except Exception as e:
        st.error(f"Erro ao atualizar ações em massa: {e}")

try:
    from auth import check_permission
except ImportError:
    def check_permission(permission_name): return True
try:
    from alunos import calcular_pontuacao_efetiva
except ImportError:
    def calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df):
        if not acoes_df.empty and not tipos_acao_df.empty:
            acoes_df['tipo_acao_id'] = acoes_df['tipo_acao_id'].astype(str)
            tipos_acao_df['id'] = tipos_acao_df['id'].astype(str)
            merged_df = pd.merge(acoes_df, tipos_acao_df[['id', 'pontuacao', 'tipo']], left_on='tipo_acao_id', right_on='id', how='left', suffixes=('_acao', '_tipo'))
            merged_df['pontuacao_efetiva'] = pd.to_numeric(merged_df['pontuacao'], errors='coerce').fillna(0)
            return merged_df
        return acoes_df

def show_gestao_acoes():
    st.title("Gestão de Lançamentos de Ações dos Alunos")
    supabase = init_supabase_client()
    if 'action_selection' not in st.session_state: st.session_state.action_selection = {}

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    with st.expander("➕ Registrar Nova Ação", expanded=True):
        st.subheader("Passo 1: Selecionar Aluno")
        selected_alunos = render_alunos_filter_and_selection(key_suffix="new_action", include_full_name_search=True)
        aluno_selecionado = None
        if not selected_alunos.empty:
            if len(selected_alunos) > 1:
                st.warning("Por favor, selecione apenas UM aluno para registrar uma nova ação.")
            else:
                aluno_selecionado = selected_alunos.iloc[0]
                st.info(f"Aluno selecionado: **{aluno_selecionado.get('nome_guerra', 'N/A')}**")
        if aluno_selecionado is not None:
            st.divider()
            st.subheader(f"Passo 2: Registrar Ação para **{aluno_selecionado['nome_guerra']}**")
            with st.form("form_nova_acao"):
                tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df.get('pontuacao', 0), errors='coerce').fillna(0)
                positivas_df, neutras_df, negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')
                opcoes_categorizadas, tipos_opcoes_map = [], {}
                for df, categoria in [(positivas_df, "POSITIVAS"), (neutras_df, "NEUTRAS"), (negativas_df, "NEGATIVAS")]:
                    if not df.empty:
                        opcoes_categorizadas.append(f"--- AÇÕES {categoria} ---")
                        for _, r in df.iterrows():
                            label = f"{r['nome']} ({r['pontuacao']:+.1f} pts)"; opcoes_categorizadas.append(label); tipos_opcoes_map[label] = r
                c1, c2 = st.columns(2)
                tipo_selecionado_str = c1.selectbox("Tipo de Ação", opcoes_categorizadas)
                data = c2.date_input("Data da Ação", datetime.now())
                descricao = st.text_area("Descrição/Justificativa")
                if st.form_submit_button("Registrar Ação", use_container_width=True, type="primary"):
                    if tipo_selecionado_str.startswith("---"):
                        st.warning("Selecione um tipo de ação válido.")
                    else:
                        try:
                            tipo_info = tipos_opcoes_map[tipo_selecionado_str]
                            nova_acao = {'aluno_id': str(aluno_selecionado['id']), 'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.isoformat(), 'usuario': st.session_state.get('username', 'sistema'), 'status': 'Pendente'}
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação registrada!"); load_data.clear(); st.rerun()
                        except Exception as e: st.error(f"Erro ao registrar: {e}")

    st.divider()
    st.subheader("Filtros de Visualização")
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
        filtro_pelotao = st.selectbox("1. Filtrar Pelotão", opcoes_pelotao)
        alunos_filtrados_pelotao = alunos_df[alunos_df['pelotao'] == filtro_pelotao] if filtro_pelotao != "Todos" else alunos_df
        opcoes_alunos = ["Todos"] + sorted([str(n) for n in alunos_filtrados_pelotao['nome_guerra'].unique() if pd.notna(n)])
        filtro_aluno = st.selectbox("2. Filtrar Aluno", opcoes_alunos)
    with col_f2:
        filtro_status = st.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
        opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
        filtro_tipo_acao = st.selectbox("Filtrar Tipo de Ação", opcoes_tipo_acao)
    ordenar_por = st.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.merge(acoes_com_pontos, alunos_df, left_on='aluno_id', right_on='id', how='left', suffixes=('_acao', '_aluno')) if not acoes_com_pontos.empty else pd.DataFrame()
    if 'nome_guerra' in df_display: df_display['nome_guerra'].fillna('N/A (Aluno Apagado)', inplace=True)

    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'].fillna('') == filtro_pelotao]
        if filtro_aluno != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['nome_guerra'].fillna('') == filtro_aluno]
        if filtro_status != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['status'].fillna('') == filtro_status]
        if filtro_tipo_acao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['tipo'].fillna('') == filtro_tipo_acao]

        # --- LÓGICA DE ORDENAÇÃO CORRIGIDA ---
        df_filtrado_final['data'] = pd.to_datetime(df_filtrado_final['data'], errors='coerce')
        if ordenar_por == "Mais Recentes":
            df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=False)
        elif ordenar_por == "Mais Antigos":
            df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)":
            df_filtrado_final = df_filtrado_final.sort_values(by="nome_guerra", ascending=True)
        # --- FIM DA CORREÇÃO ---

    st.divider()
    st.subheader(f"Fila de Revisão ({len(df_filtrado_final)} ações)")
    if df_filtrado_final.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        # CORREÇÃO: Usar 'id_acao' que é o nome correto da coluna de ID após o merge.
        ids_visiveis = [int(i) for i in df_filtrado_final['id_acao'].dropna().unique()]
        with st.container(border=True):
            col_b1, col_b2, col_c1 = st.columns([2, 2, 3])
            selected_ids = [acao_id for acao_id, is_selected in st.session_state.action_selection.items() if is_selected and acao_id in ids_visiveis]
            with col_b1:
                st.button(f"🚀 Lançar ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Lançado', supabase), disabled=not selected_ids, use_container_width=True)
            with col_b2:
                st.button(f"🗑️ Arquivar ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Arquivado', supabase), disabled=not selected_ids, use_container_width=True)
            def toggle_all_visible():
                new_state = not st.session_state.get('select_all_toggle', False)
                st.session_state.select_all_toggle = new_state
                for acao_id in ids_visiveis: st.session_state.action_selection[acao_id] = new_state
            with col_c1:
                st.checkbox("Marcar/Desmarcar todos", key='select_all_toggle_disp', on_change=toggle_all_visible, value=st.session_state.get('select_all_toggle', False))

        st.write("")
        # CORREÇÃO: Usar 'id_acao' para remover duplicatas
        df_to_display = df_filtrado_final.drop_duplicates(subset=['id_acao'], keep='first')
        for _, acao in df_to_display.iterrows():
            # CORREÇÃO: Usar 'id_acao' para todas as operações
            acao_id = int(acao['id_acao'])
            with st.container(border=True):
                col_foto, col_info, col_actions = st.columns([1, 4, 2])
                with col_foto:
                    st.image(acao.get('url_foto') or "https://via.placeholder.com/100?text=S/Foto", width=80)
                with col_info:
                    st.checkbox("Selecionar", key=f"select_{acao_id}", value=st.session_state.action_selection.get(acao_id, False), label_visibility="collapsed")
                    cor = "green" if acao.get('pontuacao_efetiva', 0) > 0 else "red" if acao.get('pontuacao_efetiva', 0) < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M') if pd.notna(acao['data']) else "Data Inválida"
                    st.markdown(f"**{acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}** em {data_formatada}")
                    st.markdown(f"**Ação:** {acao.get('tipo','N/A')} <span style='color:{cor}; font-weight:bold;'>({acao.get('pontuacao_efetiva', 0):+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao.get('descricao')}" if pd.notna(acao.get('descricao')) else "Sem descrição.")
                with col_actions:
                    status_atual = acao.get('status', 'Pendente')
                    if status_atual == 'Pendente' and check_permission('acesso_pagina_lancamentos_faia'):
                        st.button("🚀 Lançar", key=f"launch_{acao_id}", on_click=lambda id=acao_id: (supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', id).execute(), st.rerun()), use_container_width=True, type="primary")
                    if check_permission('pode_editar_lancamento_faia'):
                        st.button("✏️ Editar", key=f"edit_{acao_id}", on_click=edit_acao_dialog, args=(acao, tipos_acao_df, supabase), use_container_width=True)
                    if status_atual != 'Arquivado' and check_permission('pode_excluir_lancamento_faia'):
                        st.button("🗑️ Arquivar", key=f"archive_{acao_id}", on_click=lambda id=acao_id: (supabase.table("Acoes").update({'status': 'Arquivado'}).eq('id', id).execute(), st.rerun()), use_container_width=True)
                    if status_atual == 'Lançado': st.success("✅ Lançado")
                    elif status_atual == 'Arquivado': st.warning("🗄️ Arquivado")
