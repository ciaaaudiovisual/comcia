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
    st.download_button(label="✅ Exportar Relatório", data=texto_relatorio.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")

# ==============================================================================
# FUNÇÕES DE CALLBACK
# ==============================================================================
def on_launch_click(acao, supabase):
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
    try:
        supabase.table("Acoes").update({'lancado_faia': True}).in_('id', selected_ids).execute()
        st.session_state.action_selection = {}
        load_data.clear()
        show_success_dialog(f"{len(selected_ids)} ações foram lançadas na FAIA com sucesso!")
    except Exception as e:
        st.error(f"Ocorreu um erro ao lançar as ações em massa: {e}")

# ==============================================================================
# FUNÇÕES DE APOIO
# ==============================================================================
def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
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
    st.title("Gestão de Ações dos Alunos")
    supabase = init_supabase_client()

    if 'action_selection' not in st.session_state: st.session_state.action_selection = {}
    if 'search_results_df_gestao' not in st.session_state: st.session_state.search_results_df_gestao = pd.DataFrame()
    if 'selected_student_id_gestao' not in st.session_state: st.session_state.selected_student_id_gestao = None

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    with st.expander("➕ Registrar Nova Ação", expanded=True):
        with st.form("search_form"):
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
                if busca_num_interno:
                    df_busca = df_busca[df_busca['numero_interno'].astype(str).str.contains(busca_num_interno, na=False)]
                if busca_nome_guerra:
                    df_busca = df_busca[df_busca['nome_guerra'].str.contains(busca_nome_guerra, case=False, na=False)]
                if busca_nip and 'nip' in df_busca.columns:
                    df_busca = df_busca[df_busca['nip'].astype(str).str.contains(busca_nip, na=False)]
                if busca_nome_completo and 'nome_completo' in df_busca.columns:
                    df_busca = df_busca[df_busca['nome_completo'].str.contains(busca_nome_completo, case=False, na=False)]
                
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
                if not acoes_df.empty and 'tipo_acao_id' in acoes_df.columns:
                    contagem = acoes_df['tipo_acao_id'].value_counts().to_dict()
                    tipos_acao_df['contagem'] = tipos_acao_df['id'].astype(str).map(contagem).fillna(0)
                    tipos_acao_df = tipos_acao_df.sort_values('contagem', ascending=False)
                
                tipos_opcoes = {f"{t['nome']} ({float(t.get('pontuacao', 0)):.1f} pts)": t for _, t in tipos_acao_df.iterrows()}
                tipo_selecionado_str = c1.selectbox("Tipo de Ação", tipos_opcoes.keys())
                data = c2.date_input("Data", datetime.now())
                descricao = st.text_area("Descrição/Justificativa (Opcional)")

                lancar_direto = st.checkbox("🚀 Lançar diretamente na FAIA") if check_permission('acesso_pagina_lancamentos_faia') else False
                confirmacao_registro = st.checkbox("Confirmo que os dados estão corretos para o registo.")

                if st.form_submit_button("Registrar Ação"):
                    if not confirmacao_registro:
                        st.warning("Por favor, confirme que os dados estão corretos.")
                    else:
                        try:
                            tipo_info = tipos_opcoes[tipo_selecionado_str]
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

    # --- INÍCIO DA MODIFICAÇÃO ---
    with st.form(key="filter_form"):
        c1, c2, c3, c4 = st.columns(4) # Adicionada uma coluna extra
        filtro_pelotao = c1.selectbox("Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
        filtro_status_lancamento = c2.selectbox("Filtrar Status", ["Todos", "A Lançar", "Lançados"])
        
        # Novo filtro por tipo de ação
        opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
        filtro_tipo_acao = c3.selectbox("Filtrar por Ação", opcoes_tipo_acao)

        ordenar_por = c4.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])
        
        st.form_submit_button("🔎 Aplicar Filtros")

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='inner')
    
    if filtro_pelotao != "Todos": df_display = df_display[df_display['pelotao'] == filtro_pelotao]
    if filtro_status_lancamento == "A Lançar": df_display = df_display[df_display['lancado_faia'] == False]
    elif filtro_status_lancamento == "Lançados": df_display = df_display[df_display['lancado_faia'] == True]

    # Nova lógica de filtro por tipo de ação
    if filtro_tipo_acao != "Todos":
        # A coluna com o nome da ação é 'nome' após o merge em calcular_pontuacao_efetiva
        df_display = df_display[df_display['nome'] == filtro_tipo_acao]

    if ordenar_por == "Mais Antigos": df_display = df_display.sort_values(by="data", ascending=True)
    elif ordenar_por == "Aluno (A-Z)": df_display = df_display.sort_values(by="nome_guerra", ascending=True)
    else: df_display = df_display.sort_values(by="data", ascending=False)

    with st.container():
        nomes_unicos = df_display['nome_guerra'].unique()
        nomes_validos = sorted([str(nome) for nome in nomes_unicos if pd.notna(nome)])
        aluno_para_exportar = st.selectbox("Selecione um Aluno para Gerar Relatório:", ["Nenhum"] + nomes_validos)
        
        if aluno_para_exportar != "Nenhum":
            if st.button("👁️ Visualizar FAIA para Exportar"):
                aluno_info = df_display[df_display['nome_guerra'] == aluno_para_exportar].iloc[0]
                acoes_do_aluno = df_display[df_display['nome_guerra'] == aluno_para_exportar]
                preview_faia_dialog(aluno_info, acoes_do_aluno)

    acoes_pendentes_visiveis = df_display[df_display['lancado_faia'] == False]
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
