import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva
from io import BytesIO
import zipfile

# ==============================================================================
# DIÁLOGOS E POPUPS
# ==============================================================================
@st.dialog("Sucesso!")
def show_success_dialog(message):
    st.success(message)
    if st.button("OK"):
        st.rerun()

@st.dialog("Pré-visualização da FAIA")
def preview_faia_dialog(aluno_info, acoes_aluno_df):
    st.header(f"FAIA de: {aluno_info.get('nome_guerra', 'N/A')}")
    texto_relatorio = formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df)
    st.text_area("Conteúdo do Relatório:", value=texto_relatorio, height=300)
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','N/A')}.txt"
    st.download_button(label="✅ Baixar Relatório .TXT", data=texto_relatorio.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")

# ==============================================================================
# FUNÇÕES DE APOIO E NOVAS FUNÇÕES DE AÇÃO EM MASSA
# ==============================================================================
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
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
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

def render_export_section(df_acoes_geral, alunos_df, pelotao_selecionado, aluno_selecionado):
    if not check_permission('pode_exportar_relatorio_faia'):
        return
    with st.container(border=True):
        st.subheader("📥 Exportar Relatórios FAIA")
        if aluno_selecionado != "Nenhum":
            st.info(f"Pré-visualize e exporte o relatório individual para {aluno_selecionado}. Serão incluídas apenas as ações com status 'Lançado'.")
            aluno_info_df = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado]
            if not aluno_info_df.empty:
                aluno_info = aluno_info_df.iloc[0]
                acoes_do_aluno = df_acoes_geral[df_acoes_geral['aluno_id'] == str(aluno_info['id'])]
                if st.button(f"👁️ Pré-visualizar e Exportar FAIA de {aluno_selecionado}"):
                    preview_faia_dialog(aluno_info, acoes_do_aluno)
            else:
                st.warning(f"Aluno '{aluno_selecionado}' não encontrado.")
        elif pelotao_selecionado != "Todos":
            st.info(f"A exportação gerará um arquivo .ZIP com os relatórios de todos os alunos do pelotão '{pelotao_selecionado}'. Serão incluídas apenas as ações com status 'Lançado'.")
            alunos_do_pelotao = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]
            with st.expander(f"Ver os {len(alunos_do_pelotao)} alunos que serão incluídos no .ZIP"):
                for _, aluno_info in alunos_do_pelotao.iterrows():
                    st.write(f"- {aluno_info.get('numero_interno', 'SN')} - {aluno_info.get('nome_guerra', 'N/A')}")
            if st.button(f"Gerar e Baixar .ZIP para {pelotao_selecionado}"):
                with st.spinner("Gerando relatórios..."):
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for _, aluno_info in alunos_do_pelotao.iterrows():
                            acoes_do_aluno = df_acoes_geral[df_acoes_geral['aluno_id'] == str(aluno_info['id'])]
                            conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
                            nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','S-N')}.txt"
                            zip_file.writestr(nome_arquivo, conteudo_txt)
                    st.download_button(label="Clique para baixar o .ZIP", data=zip_buffer.getvalue(), file_name=f"relatorios_FAIA_{pelotao_selecionado}.zip", mime="application/zip", use_container_width=True)
        else:
            st.warning("Selecione um pelotão ou um aluno específico nos filtros para habilitar a exportação.")

def bulk_update_status(ids_to_update, new_status, supabase):
    """Função para atualizar o status de múltiplas ações em massa."""
    if not ids_to_update:
        st.warning("Nenhuma ação foi selecionada.")
        return
    try:
        supabase.table("Acoes").update({'status': new_status}).in_('id', ids_to_update).execute()
        st.toast(f"{len(ids_to_update)} ações foram atualizadas para '{new_status}' com sucesso!", icon="✅")
        st.session_state.action_selection = {}
        st.session_state.select_all_toggle = False
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar ações em massa: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_gestao_acoes():
    st.title("Lançamentos de Ações dos Alunos")
    supabase = init_supabase_client()

    # Carregamento inicial dos dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    # O formulário de registro não é relevante para o diagnóstico da lista
    with st.expander("➕ Registrar Nova Ação", expanded=True):
        st.info("O formulário de registro está temporariamente oculto para focar no diagnóstico da lista.")
        pass

    st.divider()
    st.subheader("Filtros de Visualização")
    
    # Os filtros não mudam
    col_filtros1, col_filtros2 = st.columns(2)
    with col_filtros1:
        filtro_pelotao = st.selectbox("1. Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
        filtro_aluno = st.selectbox("2. Filtrar Aluno (Opcional)", ["Nenhum"] + sorted([str(nome) for nome in alunos_df['nome_guerra'].unique() if pd.notna(nome)]))
    with col_filtros2:
        filtro_status = st.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
        filtro_tipo_acao = st.selectbox("Filtrar por Tipo de Ação", ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist()))

    ordenar_por = st.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])

    # ======================================================================
    # --- INÍCIO DO CÓDIGO DE DIAGNÓSTICO EM ETAPAS ---
    # ======================================================================
    st.divider()
    st.warning("INFORMAÇÕES DE DIAGNÓSTICO (pode remover depois)")

    # --- ETAPA 1: DADOS BRUTOS ---
    st.info("ETAPA 1: DADOS BRUTOS CARREGADOS DA TABELA 'ACOES'")
    st.write(f"Total de linhas carregadas de 'Acoes': **{acoes_df.shape[0]}**")
    st.write("Contagem de status diretamente do banco:")
    st.dataframe(acoes_df['status'].value_counts(dropna=False))

    # --- ETAPA 2: APÓS CALCULAR PONTOS ---
    st.info("ETAPA 2: DADOS APÓS A JUNÇÃO COM 'TIPOS_ACAO'")
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    st.write(f"Total de linhas após calcular pontos: **{acoes_com_pontos.shape[0]}**")
    st.write("Contagem de status nesta etapa:")
    st.dataframe(acoes_com_pontos['status'].value_counts(dropna=False))

    # --- ETAPA 3: APÓS JUNTAR COM ALUNOS ---
    st.info("ETAPA 3: DADOS APÓS A JUNÇÃO COM 'ALUNOS'")
    df_display = pd.DataFrame()
    if not acoes_com_pontos.empty and not alunos_df.empty:
        acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
        alunos_df['id'] = alunos_df['id'].astype(str)
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id', how='left')
    st.write(f"Total de linhas após juntar com alunos: **{df_display.shape[0]}**")
    st.write("Contagem de status final (antes do filtro da tela):")
    st.dataframe(df_display['status'].value_counts(dropna=False))

    st.warning("FIM DO DIAGNÓSTICO")
    # ======================================================================

    # Lógica de filtragem final (sem alterações)
    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'].fillna('') == filtro_pelotao]
        if filtro_aluno != "Nenhum":
            aluno_id_filtrado = str(alunos_df[alunos_df['nome_guerra'] == filtro_aluno]['id'].iloc[0])
            df_filtrado_final = df_filtrado_final[df_filtrado_final['aluno_id'] == aluno_id_filtrado]
        if filtro_status != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['status'].fillna('') == filtro_status]
        if filtro_tipo_acao != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['nome'].fillna('') == filtro_tipo_acao]
    
    st.divider()
    
    st.subheader("Filtros de Visualização")
    
    col_filtros1, col_filtros2 = st.columns(2)
    with col_filtros1:
        filtro_pelotao = st.selectbox("1. Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
        alunos_filtrados_pelotao = alunos_df[alunos_df['pelotao'] == filtro_pelotao] if filtro_pelotao != "Todos" else alunos_df
        nomes_unicos = alunos_filtrados_pelotao['nome_guerra'].unique()
        nomes_validos = [str(nome) for nome in nomes_unicos if pd.notna(nome)]
        opcoes_alunos = ["Nenhum"] + sorted(nomes_validos)
        filtro_aluno = st.selectbox("2. Filtrar Aluno (Opcional)", opcoes_alunos)
    
    with col_filtros2:
        filtro_status = st.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
        opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
        filtro_tipo_acao = st.selectbox("Filtrar por Tipo de Ação", opcoes_tipo_acao)

    ordenar_por = st.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.DataFrame()

    if not acoes_com_pontos.empty and not alunos_df.empty:
        acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
        alunos_df['id'] = alunos_df['id'].astype(str)
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='left')
        df_display['nome_guerra'].fillna('N/A (Aluno Apagado)', inplace=True)

    # --- BLOCO DE DIAGNÓSTICO TEMPORÁRIO ---
    st.warning("DIAGNÓSTICO FINAL (pode remover depois)")
    st.write(f"Tabela combinada (df_display) criada com {len(df_display)} linhas.")
    if not df_display.empty:
        st.write("Contagem de cada status encontrado na lista:")
        status_counts = df_display['status'].value_counts(dropna=False)
        st.dataframe(status_counts)
        st.write("Amostra dos 5 primeiros registros para análise completa:")
        st.dataframe(df_display.head())
    st.warning("FIM DO DIAGNÓSTICO")

    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'].fillna('') == filtro_pelotao]
        if filtro_aluno != "Nenhum":
            aluno_id_filtrado_df = alunos_df[alunos_df['nome_guerra'] == filtro_aluno]
            if not aluno_id_filtrado_df.empty:
                aluno_id_filtrado = str(aluno_id_filtrado_df['id'].iloc[0])
                df_filtrado_final = df_filtrado_final[df_filtrado_final['aluno_id'] == aluno_id_filtrado]
        if filtro_status != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['status'].fillna('') == filtro_status]
        if filtro_tipo_acao != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['nome'].fillna('') == filtro_tipo_acao]
        
        if ordenar_por == "Mais Antigos":
            df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)":
            df_filtrado_final = df_filtrado_final.sort_values(by="nome_guerra", ascending=True)
        else:
            df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=False)

    st.divider()

    st.subheader("Fila de Revisão e Ações")

    if df_filtrado_final.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        with st.container(border=True):
            col_botoes1, col_botoes2, col_check = st.columns([2, 2, 3])
            
            ids_visiveis = df_filtrado_final['id_x'].dropna().tolist()
            selected_ids = [acao_id for acao_id, is_selected in st.session_state.action_selection.items() if is_selected and acao_id in ids_visiveis]
            
            with col_botoes1:
                st.button(f"🚀 Lançar Selecionados ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Lançado', supabase), disabled=not selected_ids, use_container_width=True)
            with col_botoes2:
                st.button(f"🗄️ Arquivar Selecionados ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Arquivado', supabase), disabled=not selected_ids, use_container_width=True)

            def toggle_all_visible():
                new_state = st.session_state.get('select_all_toggle', False)
                for acao_id in ids_visiveis:
                    st.session_state.action_selection[acao_id] = new_state
            
            with col_check:
                st.checkbox("Marcar/Desmarcar todos os visíveis", key='select_all_toggle', on_change=toggle_all_visible)
        
        st.write("") 

        df_filtrado_final.drop_duplicates(subset=['id_x'], keep='first', inplace=True)
        for _, acao in df_filtrado_final.iterrows():
            acao_id = acao['id_x']
            with st.container(border=True):
                col_check_ind, col_info, col_actions = st.columns([1, 6, 3])
                
                with col_check_ind:
                    st.session_state.action_selection[acao_id] = st.checkbox(" ", value=st.session_state.action_selection.get(acao_id, False), key=f"select_{acao_id}", label_visibility="collapsed")

                with col_info:
                    cor = "green" if acao.get('pontuacao_efetiva', 0) > 0 else "red" if acao.get('pontuacao_efetiva', 0) < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')
                    st.markdown(f"**{acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A (Aluno Apagado)')}** em {data_formatada}")
                    st.markdown(f"**Ação:** {acao.get('nome','N/A')} <span style='color:{cor}; font-weight:bold;'>({acao.get('pontuacao_efetiva', 0):+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao.get('descricao')}" if pd.notna(acao.get('descricao')) else "Sem descrição.")
                
                with col_actions:
                    status_atual = acao.get('status', 'Pendente')
                    can_launch = check_permission('acesso_pagina_lancamentos_faia')
                    can_delete = check_permission('pode_excluir_lancamento_faia')

                    if status_atual == 'Lançado':
                        st.success("✅ Lançado")
                    elif status_atual == 'Arquivado':
                        st.warning("🗄️ Arquivado")
                    elif status_atual == 'Pendente' and can_launch:
                        with st.form(f"launch_form_{acao_id}"):
                            if st.form_submit_button("🚀 Lançar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', acao_id).execute()
                                load_data.clear(); st.rerun()
                    
                    if status_atual != 'Arquivado' and can_delete:
                        with st.form(f"archive_form_{acao_id}"):
                            if st.form_submit_button("🗑️ Arquivar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Arquivado'}).eq('id', acao_id).execute()
                                load_data.clear(); st.rerun()

    st.divider()
    render_export_section(acoes_com_pontos, alunos_df, filtro_pelotao, filtro_aluno)
