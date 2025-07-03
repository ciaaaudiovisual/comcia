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
# FUNÇÕES DE CALLBACK (APENAS PARA AÇÕES EM MASSA)
# ==============================================================================
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
            supabase.table("Acoes").update({'status': 'Lançado'}).in_('id', batch_ids).execute()
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
        f"FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)\n",
        f"Pelotão: {aluno_info.get('pelotao', 'N/A')}",
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
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
                f"Descrição: {acao.get('descricao', '')}",
                f"Registrado por: {acao.get('usuario', 'N/A')}",
                f"Status: {acao.get('status', 'N/A')}",
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
                positivas_df, neutras_df, negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome'), tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')
                opcoes_finais, tipos_opcoes_map = [], {}
                if not positivas_df.empty:
                    opcoes_finais.append("--- AÇÕES POSITIVAS ---"); [opcoes_finais.append(f"{r['nome']} ({r['pontuacao']:.1f} pts)") or tipos_opcoes_map.update({f"{r['nome']} ({r['pontuacao']:.1f} pts)": r}) for _, r in positivas_df.iterrows()]
                if not neutras_df.empty:
                    opcoes_finais.append("--- AÇÕES NEUTRAS ---"); [opcoes_finais.append(f"{r['nome']} (0.0 pts)") or tipos_opcoes_map.update({f"{r['nome']} (0.0 pts)": r}) for _, r in neutras_df.iterrows()]
                if not negativas_df.empty:
                    opcoes_finais.append("--- AÇÕES NEGATIVAS ---"); [opcoes_finais.append(f"{r['nome']} ({r['pontuacao']:.1f} pts)") or tipos_opcoes_map.update({f"{r['nome']} ({r['pontuacao']:.1f} pts)": r}) for _, r in negativas_df.iterrows()]
                tipo_selecionado_str = c1.selectbox("Tipo de Ação", opcoes_finais)
                data = c2.date_input("Data e Hora da Ação", datetime.now())
                descricao = st.text_area("Descrição/Justificativa (Opcional)")
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
                            nova_acao = {'id': str(novo_id), 'aluno_id': str(st.session_state.selected_student_id_gestao), 'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.isoformat(), 'usuario': st.session_state.username, 'status': 'Pendente'}
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação registrada para {aluno_selecionado['nome_guerra']}!"); load_data.clear(); st.rerun()
                        except Exception as e: st.error(f"Erro ao registrar ação: {e}")
        else:
            st.info("⬅️ Busque e selecione um aluno acima para registrar uma nova ação.")
    
    st.divider()
    st.subheader("Fila de Revisão e Ações")

    c1, c2, c3, c4 = st.columns(4)
    filtro_pelotao = c1.selectbox("Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
    filtro_status = c2.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
    opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
    filtro_tipo_acao = c3.selectbox("Filtrar por Ação", opcoes_tipo_acao)
    ordenar_por = c4.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.DataFrame()
    if not acoes_com_pontos.empty:
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='inner')
    
    if not df_display.empty:
        if filtro_pelotao != "Todos": df_display = df_display[df_display['pelotao'] == filtro_pelotao]
        if filtro_status != "Todos": df_display = df_display[df_display['status'] == filtro_status]
        if filtro_tipo_acao != "Todos": df_display = df_display[df_display['nome'] == filtro_tipo_acao]
        if ordenar_por == "Mais Antigos": df_display = df_display.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)": df_display = df_display.sort_values(by="nome_guerra", ascending=True)
        else: df_display = df_display.sort_values(by="data", ascending=False) 

    if df_display.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        df_display.drop_duplicates(subset=['id'], keep='first', inplace=True)
        for _, acao in df_display.iterrows():
            with st.container(border=True):
                info_col, actions_col = st.columns([7, 3])
                with info_col:
                    cor = "green" if acao['pontuacao_efetiva'] > 0 else "red" if acao['pontuacao_efetiva'] < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')
                    st.markdown(f"**{acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}** em {data_formatada}")
                    st.markdown(f"**Ação:** {acao['nome']} <span style='color:{cor}; font-weight:bold;'>({acao['pontuacao_efetiva']:+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao['descricao']}" if acao['descricao'] else "Sem descrição.")
                
                with actions_col:
                    status_atual = acao.get('status', 'Pendente')
                    can_launch = check_permission('acesso_pagina_lancamentos_faia')
                    can_delete = check_permission('pode_excluir_lancamento_faia')

                    if status_atual == 'Lançado':
                        st.success("✅ Lançado")
                    elif status_atual == 'Arquivado':
                        st.warning("🗄️ Arquivado")
                    elif status_atual == 'Pendente' and can_launch:
                        with st.form(f"launch_form_{acao['id']}"):
                            if st.form_submit_button("🚀 Lançar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', acao['id']).execute()
                                load_data.clear(); st.rerun()
                    
                    if status_atual != 'Arquivado' and can_delete:
                        with st.form(f"archive_form_{acao['id']}"):
                            if st.form_submit_button("🗑️ Arquivar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Arquivado'}).eq('id', acao['id']).execute()
                                load_data.clear(); st.rerun()
