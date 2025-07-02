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
    """Exibe um popup de sucesso que o utilizador precisa de fechar manualmente."""
    st.success(message)
    if st.button("OK"):
        st.rerun()

@st.dialog("Pré-visualização da FAIA")
def preview_faia_dialog(aluno_info, acoes_aluno_df):
    """Exibe o conteúdo da FAIA e o botão para exportar."""
    st.header(f"FAIA de: {aluno_info.get('nome_guerra', 'N/A')}")
    texto_relatorio = formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df)
    st.text_area("Conteúdo do Relatório:", value=texto_relatorio, height=300)
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','N/A')}.txt"
    st.download_button(label="✅ Exportar Relatório", data=texto_relatorio.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")

# ==============================================================================
# FUNÇÕES DE CALLBACK
# ==============================================================================
def on_launch_click(acao, supabase):
    """Callback para lançar UMA ÚNICA ação e mostrar o popup de sucesso."""
    try:
        supabase.table("Acoes").update({'lancado_faia': True}).eq('id', acao['id']).execute()
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
    """Callback para excluir uma ação específica."""
    try:
        supabase.table("Acoes").delete().eq('id', action_id).execute()
        st.toast("Ação excluída com sucesso!")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir a ação: {e}")

def launch_selected_actions(selected_ids, supabase):
    """Callback para lançar MÚLTIPLAS ações em lotes para evitar timeouts."""
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
            supabase.table("Acoes").update({'lancado_faia': True}).in_('id', batch_ids).execute()
            processed_count += len(batch_ids)
        progress_bar.progress(1.0, text="Lançamento concluído!")
        st.session_state.action_selection = {}
        load_data.clear()
        show_success_dialog(f"{processed_count} de {total_items} ações foram lançadas na FAIA com sucesso!")
    except Exception as e:
        st.error(f"Ocorreu um erro durante o lançamento em massa: {e}")
        progress_bar.empty()

# ==============================================================================
# FUNÇÕES DE APOIO
# ==============================================================================
def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
    """Formata os dados de um único aluno para uma string de texto."""
    texto = [
        "============================================================",
        "      FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)",
        "============================================================",
        f"\nPelotão: {aluno_info.get('pelotao', 'N/A')}",
        f"Aluno: {aluno_info.get('nome_completo', 'N/A')}",
        f"Nome de Guerra: {aluno_info.get('nome_guerra', 'N/A')}",
        f"Numero Interno: {aluno_info.get('numero_interno', 'N/A')}",
        "\n------------------------------------------------------------",
        "LANÇAMENTOS EM ORDEM CRONOLÓGICA:",
        "------------------------------------------------------------\n"
    ]
    if acoes_aluno_df.empty:
        texto.append("Nenhum lançamento encontrado para este aluno no período filtrado.")
    else:
        for _, acao in acoes_aluno_df.sort_values(by='data').iterrows():
            texto.extend([
                f"Data: {pd.to_datetime(acao['data']).strftime('%Y-%m-%d')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
                f"Descrição: {acao.get('descricao', '')}",
                f"Registrado por: {acao.get('usuario', 'N/A')}",
                f"Lançado na FAIA: {'Sim' if acao.get('lancado_faia') else 'Não'}",
                "\n-----------------------------------\n"
            ])
    texto.extend([
        "\n============================================================",
        f"Fim do Relatório - Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "============================================================"
    ])
    return "\n".join(texto)

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
            
            col1, col2 = st.columns(2)
            busca_num_interno = col1.text_input("Nº Interno (ex: 101)")
            busca_nome_guerra = col2.text_input("Nome de Guerra")
            
            col3, col4 = st.columns(2)
            busca_nip = col3.text_input("NIP (ex: 12345678)")
            busca_nome_completo = col4.text_input("Nome Completo")
            
            if st.form_submit_button("🔎 Buscar Aluno"):
                df_busca = alunos_df.copy()
                # Converte os termos de busca para maiúsculas para busca case-insensitive
                if busca_num_interno:
                    df_busca = df_busca[df_busca['numero_interno'].astype(str).str.upper().str.contains(busca_num_interno.upper(), na=False)]
                if busca_nome_guerra:
                    df_busca = df_busca[df_busca['nome_guerra'].str.upper().str.contains(busca_nome_guerra.upper(), case=False, na=False)]
                if busca_nip and 'nip' in df_busca.columns:
                    df_busca = df_busca[df_busca['nip'].astype(str).str.upper().str.contains(busca_nip.upper(), na=False)]
                if busca_nome_completo and 'nome_completo' in df_busca.columns:
                    df_busca = df_busca[df_busca['nome_completo'].str.upper().str.contains(busca_nome_completo.upper(), case=False, na=False)]
                
                st.session_state.search_results_df_gestao = df_busca
                st.session_state.selected_student_id_gestao = None

        search_results_df = st.session_state.search_results_df_gestao
        if not search_results_df.empty:
            st.write("Resultados da busca:")
            search_results_df['label'] = search_results_df.apply(lambda row: f"{row.get('numero_interno', '')} - {row.get('nome_guerra', '')} ({row.get('pelotao', '')})", axis=1)
            opcoes_encontradas = pd.Series(search_results_df.id.values, index=search_results_df.label).to_dict()
            
            aluno_selecionado_label = st.radio("Selecione um aluno:", options=opcoes_encontradas.keys(), index=None)
            if aluno_selecionado_label:
                st.session_state.selected_student_id_gestao = str(opcoes_encontradas[aluno_selecionado_label])
        
        if st.session_state.selected_student_id_gestao:
            st.divider()
            aluno_selecionado = alunos_df[alunos_df['id'] == st.session_state.selected_student_id_gestao].iloc[0]
            st.subheader(f"Passo 2: Registrar Ação para {aluno_selecionado['nome_guerra']}")

            with st.form("form_nova_acao"):
                c1, c2 = st.columns(2)
                
                tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
                positivas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome')
                neutras_df = tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome')
                negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')
                
                opcoes_finais = []
                tipos_opcoes_map = {}

                if not positivas_df.empty:
                    opcoes_finais.append("--- AÇÕES POSITIVAS ---")
                    for _, row in positivas_df.iterrows():
                        label = f"{row['nome']} ({row['pontuacao']:.1f} pts)"
                        opcoes_finais.append(label)
                        tipos_opcoes_map[label] = row
                if not neutras_df.empty:
                    opcoes_finais.append("--- AÇÕES NEUTRAS ---")
                    for _, row in neutras_df.iterrows():
                        label = f"{row['nome']} (0.0 pts)"
                        opcoes_finais.append(label)
                        tipos_opcoes_map[label] = row
                if not negativas_df.empty:
                    opcoes_finais.append("--- AÇÕES NEGATIVAS ---")
                    for _, row in negativas_df.iterrows():
                        label = f"{row['nome']} ({row['pontuacao']:.1f} pts)"
                        opcoes_finais.append(label)
                        tipos_opcoes_map[label] = row
                
                tipo_selecionado_str = c1.selectbox("Tipo de Ação", opcoes_finais)
                data = c2.date_input("Data", datetime.now())
                descricao = st.text_area("Descrição/Justificativa (Opcional)")

                lancar_direto = st.checkbox("🚀 Lançar diretamente na FAIA") if check_permission('acesso_pagina_lancamentos_faia') else False
                confirmacao_registro = st.checkbox("Confirmo que os dados estão corretos para o registo.")

                if st.form_submit_button("Registrar Ação"):
                    if tipo_selecionado_str.startswith("---"):
                        st.warning("Por favor, selecione um tipo de ação válido, não um cabeçalho de categoria.")
                    elif not confirmacao_registro:
                        st.warning("Por favor, confirme que os dados estão corretos.")
                    else:
                        try:
                            tipo_info = tipos_opcoes_map[tipo_selecionado_str]
                            ids = pd.to_numeric(acoes_df['id'], errors='coerce').dropna()
                            novo_id = int(ids.max()) + 1 if not ids.empty else 1
                            nova_acao = {
                                'id': str(novo_id), 'aluno_id': str(st.session_state.selected_student_id_gestao), 
                                'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 
                                'descricao': descricao, 'data': data.strftime('%Y-%m-%d'),
                                'usuario': st.session_state.username, 'lancado_faia': lancar_direto
                            }
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação registrada para {aluno_selecionado['nome_guerra']}!")
                            st.session_state.search_results_df_gestao = pd.DataFrame()
                            st.session_state.selected_student_id_gestao = None
                            load_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar ação: {e}")
        else:
            st.info("⬅️ Busque e selecione um aluno acima para registrar uma nova ação.")
    
    st.divider()
    st.subheader("Fila de Revisão e Ações Lançadas")

    with st.form(key="filter_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            filtro_pelotao = st.selectbox("Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
        with c2:
            filtro_status_lancamento = st.selectbox("Filtrar Status", ["Todos", "A Lançar", "Lançados"])
        with c3:
            ordenar_por = st.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])
        
        opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
        filtro_tipo_acao = st.selectbox("Filtrar por Ação", opcoes_tipo_acao)

        st.form_submit_button("🔎 Aplicar Filtros")

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    
    if acoes_com_pontos.empty or 'aluno_id' not in acoes_com_pontos.columns:
        df_display = pd.DataFrame()
    else:
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='inner')
    
    if not df_display.empty:
        if filtro_pelotao != "Todos": df_display = df_display[df_display['pelotao'] == filtro_pelotao]
        if filtro_status_lancamento == "A Lançar": df_display = df_display[df_display['lancado_faia'] == False]
        elif filtro_status_lancamento == "Lançados": df_display = df_display[df_display['lancado_faia'] == True]
        if filtro_tipo_acao != "Todos":
            df_display = df_display[df_display['nome'] == filtro_tipo_acao]

        if ordenar_por == "Mais Antigos": df_display = df_display.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)": df_display = df_display.sort_values(by="nome_guerra", ascending=True)
        else: df_display = df_display.sort_values(by="data", ascending=False) 

    with st.container():
        if not df_display.empty:
            nomes_unicos = df_display['nome_guerra'].unique()
            nomes_validos = sorted([str(nome) for nome in nomes_unicos if pd.notna(nome)])
            aluno_para_exportar = st.selectbox("Selecione um Aluno para Gerar Relatório:", ["Nenhum"] + nomes_validos)
            
            if aluno_para_exportar != "Nenhum":
                if st.button("👁️ Visualizar FAIA para Exportar"):
                    aluno_info = df_display[df_display['nome_guerra'] == aluno_para_exportar].iloc[0]
                    acoes_do_aluno = df_display[df_display['nome_guerra'] == aluno_para_exportar]
                    preview_faia_dialog(aluno_info, acoes_do_aluno)

    acoes_pendentes_visiveis = df_display[~df_display['lancado_faia']] if 'lancado_faia' in df_display else pd.DataFrame()
    if not acoes_pendentes_visiveis.empty and check_permission('acesso_pagina_lancamentos_faia'):
        st.write("---")
        col_massa1, col_massa2 = st.columns([1, 3])
        
        select_all = col_massa1.toggle("Marcar/Desmarcar Todas as Visíveis")
        for _, row in acoes_pendentes_visiveis.iterrows():
            st.session_state.action_selection[row['id']] = select_all
        
        selected_ids = [k for k, v in st.session_state.action_selection.items() if v]
        if selected_ids:
            col_massa2.button(f"🚀 Lançar {len(selected_ids)} Ações Selecionadas", type="primary", on_click=launch_selected_actions, args=(selected_ids, supabase))
    
    if df_display.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        df_display.drop_duplicates(subset=['id'], keep='first', inplace=True)
        for _, acao in df_display.iterrows():
            with st.container(border=True):
                is_launched = acao.get('lancado_faia', False)
                can_launch = check_permission('acesso_pagina_lancamentos_faia')
                can_delete = check_permission('pode_excluir_lancamento_faia')
                
                if not is_launched and can_launch:
                    cols = st.columns([1, 6, 3])
                    with cols[0]:
                        st.session_state.action_selection[acao['id']] = st.checkbox("Select", key=f"select_{acao['id']}", value=st.session_state.action_selection.get(acao['id'], False), label_visibility="collapsed")
                    info_col, actions_col = cols[1], cols[2]
                else:
                    info_col, actions_col = st.columns([7, 3])

                with info_col:
                    cor = "green" if acao['pontuacao_efetiva'] > 0 else "red" if acao['pontuacao_efetiva'] < 0 else "gray"
                    st.markdown(f"**{acao['nome_guerra']}** ({acao['pelotao']}) em {pd.to_datetime(acao['data']).strftime('%d/%m/%Y')}")
                    st.markdown(f"**Ação:** {acao['nome']} <span style='color:{cor}; font-weight:bold;'>({acao['pontuacao_efetiva']:+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao['descricao']}" if acao['descricao'] else "Sem descrição.")
                
                with actions_col:
                    if is_launched:
                        st.success("✅ Lançado")
                        if can_delete:
                            st.button("🗑️", key=f"delete_launched_{acao['id']}", on_click=on_delete_action_click, args=(acao['id'], supabase), use_container_width=True, help="Excluir lançamento")
                    else:
                        if can_launch and can_delete:
                            btn1, btn2 = st.columns(2)
                            btn1.button("Lançar", key=f"launch_{acao['id']}", on_click=on_launch_click, args=(acao, supabase), use_container_width=True)
                            btn2.button("🗑️", key=f"delete_pending_{acao['id']}", on_click=on_delete_action_click, args=(acao['id'], supabase), use_container_width=True, help="Excluir lançamento")
                        elif can_launch:
                            st.button("Lançar", key=f"launch_{acao['id']}", on_click=on_launch_click, args=(acao, supabase), use_container_width=True)
                        elif can_delete:
                            st.button("🗑️", key=f"delete_pending_{acao['id']}", on_click=on_delete_action_click, args=(acao['id'], supabase), use_container_width=True, help="Excluir lançamento")
