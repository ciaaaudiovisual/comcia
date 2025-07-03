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
# FUNÇÕES DE CALLBACK
# ==============================================================================
def on_launch_click(acao, supabase):
    try:
        supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', acao['id']).execute()
        load_data.clear()
        alunos_df = load_data("Alunos")
        aluno_info_query = alunos_df[alunos_df['id'] == str(acao['aluno_id'])]
        if not aluno_info_query.empty:
            aluno_info = aluno_info_query.iloc[0]
            msg = f"A ação '{acao['nome']}' para o aluno {aluno_info.get('nome_guerra', 'N/A')} foi lançada na FAIA com sucesso!"
            show_success_dialog(msg)
        else:
            show_success_dialog("Ação lançada na FAIA com sucesso!")
    except Exception as e:
        st.error(f"Ocorreu um erro ao lançar a ação: {e}")

def on_delete_action_click(action_id, supabase):
    try:
        supabase.table("Acoes").delete().eq('id', action_id).execute()
        st.toast("Ação excluída com sucesso!")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir a ação: {e}")

def launch_selected_actions(selected_ids, supabase):
    if not selected_ids:
        st.warning("Nenhuma ação foi selecionada.")
        return
    BATCH_SIZE = 50
    total_items = len(selected_ids)
    progress_bar = st.progress(0, text="Iniciando lançamento em massa...")
    try:
        processed_count = 0
        for i in range(0, total_items, BATCH_SIZE):
            batch_ids = selected_ids[i:i + BATCH_SIZE]
            progress_text = f"Processando lote {i//BATCH_SIZE + 1}... ({processed_count}/{total_items})"
            progress_bar.progress(i / total_items, text=progress_text)
            supabase.table("Acoes").update({'status': 'Lançado'}).in_('id', batch_ids).execute()
            processed_count += len(batch_ids)
        progress_bar.progress(1.0, text="Lançamento concluído!")
        st.session_state.action_selection = {}
        st.session_state.select_all_toggle = False
        load_data.clear()
        show_success_dialog(f"{processed_count} de {total_items} ações foram lançadas na FAIA com sucesso!")
    except Exception as e:
        st.error(f"Ocorreu um erro durante o lançamento em massa: {e}")
        progress_bar.empty()

# ==============================================================================
# FUNÇÕES DE APOIO
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
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y')}",
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
            aluno_info = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado].iloc[0]
            acoes_do_aluno = df_acoes_geral[df_acoes_geral['aluno_id'] == aluno_info['id']]
            if st.button(f"👁️ Pré-visualizar e Exportar FAIA de {aluno_selecionado}"):
                preview_faia_dialog(aluno_info, acoes_do_aluno)
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
                            acoes_do_aluno = df_acoes_geral[df_acoes_geral['aluno_id'] == aluno_info['id']]
                            conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
                            nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','S-N')}.txt"
                            zip_file.writestr(nome_arquivo, conteudo_txt)
                    st.download_button(label="Clique para baixar o .ZIP", data=zip_buffer.getvalue(), file_name=f"relatorios_FAIA_{pelotao_selecionado}.zip", mime="application/zip", use_container_width=True)
        else:
            st.warning("Selecione um pelotão ou um aluno específico nos filtros para habilitar a exportação.")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_gestao_acoes():
    st.title("Lançamentos de Ações dos Alunos")
    supabase = init_supabase_client()

    if 'action_selection' not in st.session_state: st.session_state.action_selection = {}
    if 'search_results_df_gestao' not in st.session_state: st.session_state.search_results_df_gestao = pd.DataFrame()
    if 'selected_student_id_gestao' not in st.session_state: st.session_state.selected_student_id_gestao = None

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    with st.expander("➕ Registrar Nova Ação", expanded=True):
        with st.form("search_form_gestao"):
            st.subheader("Passo 1: Buscar Aluno")
            st.info("Preencha um ou mais campos e clique em 'Buscar'. A busca combinará todos os critérios.")
            c1, c2 = st.columns(2)
            busca_num_interno = c1.text_input("Nº Interno")
            busca_nome_guerra = c2.text_input("Nome de Guerra")
            c3, c4 = st.columns(2)
            busca_nip = c3.text_input("NIP")
            busca_nome_completo = c4.text_input("Nome Completo")
            if st.form_submit_button("🔎 Buscar Aluno"):
                df_busca = alunos_df.copy()
                if busca_num_interno: df_busca = df_busca[df_busca['numero_interno'].astype(str).str.contains(busca_num_interno, na=False)]
                if busca_nome_guerra: df_busca = df_busca[df_busca['nome_guerra'].str.contains(busca_nome_guerra, case=False, na=False)]
                if busca_nip and 'nip' in df_busca.columns: df_busca = df_busca[df_busca['nip'].astype(str).str.contains(busca_nip, na=False)]
                if busca_nome_completo and 'nome_completo' in df_busca.columns: df_busca = df_busca[df_busca['nome_completo'].str.contains(busca_nome_completo, case=False, na=False)]
                st.session_state.search_results_df_gestao = df_busca
                st.session_state.selected_student_id_gestao = None
        
        search_results_df = st.session_state.search_results_df_gestao
        if not search_results_df.empty:
            st.write("Resultados da busca:")
            search_results_df['label'] = search_results_df.apply(lambda r: f"{r.get('numero_interno', '')} - {r.get('nome_guerra', '')} ({r.get('pelotao', '')})", axis=1)
            opcoes_encontradas = pd.Series(search_results_df.id.values, index=search_results_df.label).to_dict()
            aluno_selecionado_label = st.radio("Selecione um aluno:", options=opcoes_encontradas.keys(), index=None)
            if aluno_selecionado_label: st.session_state.selected_student_id_gestao = str(opcoes_encontradas[aluno_selecionado_label])
        
        if st.session_state.selected_student_id_gestao:
            st.divider()
            aluno_selecionado = alunos_df[alunos_df['id'] == st.session_state.selected_student_id_gestao].iloc[0]
            st.subheader(f"Passo 2: Registrar Ação para {aluno_selecionado['nome_guerra']}")
            with st.form("form_nova_acao"):
                c1, c2 = st.columns(2)
                tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
                positivas_df, neutras_df, negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')
                opcoes_finais, tipos_opcoes_map = [], {}
                if not positivas_df.empty:
                    opcoes_finais.append("--- AÇÕES POSITIVAS ---"); [opcoes_finais.append(f"{r['nome']} ({r['pontuacao']:.1f} pts)") or tipos_opcoes_map.update({f"{r['nome']} ({r['pontuacao']:.1f} pts)": r}) for _, r in positivas_df.iterrows()]
                if not neutras_df.empty:
                    opcoes_finais.append("--- AÇÕES NEUTRAS ---"); [opcoes_finais.append(f"{r['nome']} (0.0 pts)") or tipos_opcoes_map.update({f"{r['nome']} (0.0 pts)": r}) for _, r in neutras_df.iterrows()]
                if not negativas_df.empty:
                    opcoes_finais.append("--- AÇÕES NEGATIVAS ---"); [opcoes_finais.append(f"{r['nome']} ({r['pontuacao']:.1f} pts)") or tipos_opcoes_map.update({f"{r['nome']} ({r['pontuacao']:.1f} pts)": r}) for _, r in negativas_df.iterrows()]
                tipo_selecionado_str = c1.selectbox("Tipo de Ação", opcoes_finais)
                data = c2.date_input("Data", datetime.now())
                descricao = st.text_area("Descrição/Justificativa (Opcional)")
                lancar_direto = st.checkbox("🚀 Lançar diretamente na FAIA") if check_permission('acesso_pagina_lancamentos_faia') else False
                confirmacao_registro = st.checkbox("Confirmo que os dados estão corretos para o registo.")
                if st.form_submit_button("Registrar Ação"):
                    if tipo_selecionado_str.startswith("---"): st.warning("Por favor, selecione um tipo de ação válido.")
                    elif not confirmacao_registro: st.warning("Por favor, confirme que os dados estão corretos.")
                    else:
                        try:
                            response = supabase.table("Acoes").select("id", count='exact').execute()
                            ids_existentes = [int(item['id']) for item in response.data if str(item.get('id')).isdigit()]
                            novo_id = max(ids_existentes) + 1 if ids_existentes else 1
                            tipo_info = tipos_opcoes_map[tipo_selecionado_str]
                            nova_acao = {'id': str(novo_id), 'aluno_id': str(st.session_state.selected_student_id_gestao), 'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.strftime('%Y-%m-%d'), 'usuario': st.session_state.username, 'status': 'Lançado' if lancar_direto else 'A Lançar'}
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação registrada para {aluno_selecionado['nome_guerra']}!"); load_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar ação: {e}")
        else:
            st.info("⬅️ Busque e selecione um aluno acima para registrar uma nova ação.")
    
    st.divider()
    st.subheader("Fila de Revisão e Ações")
    
    with st.form(key="filter_form"):
        col1, col2 = st.columns(2)
        filtro_pelotao = col1.selectbox("Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
        filtro_status = col2.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
        st.form_submit_button("🔎 Aplicar Filtros")

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.DataFrame()
    if not acoes_com_pontos.empty:
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='inner')
    
    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'] == filtro_pelotao]
        if filtro_status != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['status'] == filtro_status]
    
    st.divider()
    # --- SECÇÃO DE EXPORTAÇÃO RESTAURADA ---
    render_export_section(acoes_com_pontos, alunos_df, filtro_pelotao, "Nenhum") # O filtro de aluno individual é tratado dentro da função
    st.divider()

    st.subheader("Lista de Ações")
    if df_filtrado_final.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        with st.container(border=True):
            col_botoes1, col_botoes2, col_check = st.columns([2, 2, 3])
            selected_ids = [acao_id for acao_id, is_selected in st.session_state.action_selection.items() if is_selected]
            with col_botoes1:
                st.button(f"🚀 Lançar Selecionados ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Lançado', supabase), disabled=not selected_ids, use_container_width=True)
            with col_botoes2:
                st.button(f"🗄️ Arquivar Selecionados ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Arquivado', supabase), disabled=not selected_ids, use_container_width=True)
            def toggle_all_visible():
                new_state = st.session_state.get('select_all_toggle', False)
                for acao_id in df_filtrado_final['id_x']:
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
                    cor = "green" if acao['pontuacao_efetiva'] > 0 else "red" if acao['pontuacao_efetiva'] < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')
                    st.markdown(f"**{acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}** em {data_formatada}")
                    st.markdown(f"**Ação:** {acao['nome']} <span style='color:{cor}; font-weight:bold;'>({acao['pontuacao_efetiva']:+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao['descricao']}" if acao['descricao'] else "Sem descrição.")
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
