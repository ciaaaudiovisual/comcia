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
# FUNÇÕES DE APOIO E AÇÕES EM MASSA
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
            data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
            texto.extend([
                f"Data: {data_formatada}",
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

    if 'action_selection' not in st.session_state:
        st.session_state.action_selection = {}

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    with st.expander("➕ Registrar Nova Ação", expanded=False):
        # Esta secção foi restaurada com base no seu código original e com a lógica de ID corrigida.
        with st.form("novo_lancamento_restaurado"):
            st.subheader("Registrar Nova Ação")
            alunos_opcoes_dict = {f"Nº: {aluno.get('numero_interno', 'S/N')} | {aluno['nome_guerra']}": aluno['id'] for _, aluno in alunos_df.sort_values('numero_interno').iterrows()}
            aluno_selecionado_label = st.selectbox("Selecione o Aluno", options=list(alunos_opcoes_dict.keys()))

            tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao', 0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação", tipos_opcoes.keys())
            
            data = st.date_input("Data da Ação", datetime.now())
            descricao = st.text_area("Descrição/Justificativa")

            if st.form_submit_button("Registrar Ação"):
                if not all([aluno_selecionado_label, tipo_selecionado_str, descricao]):
                    st.warning("Todos os campos são obrigatórios.")
                else:
                    try:
                        # --- LÓGICA DE GERAÇÃO DE ID ROBUSTA ---
                        response = supabase.table("Acoes").select("id", count='exact').execute()
                        ids_existentes = [int(item['id']) for item in response.data if str(item.get('id')).isdigit()]
                        novo_id = max(ids_existentes) + 1 if ids_existentes else 1

                        aluno_id = alunos_opcoes_dict[aluno_selecionado_label]
                        tipo_info = tipos_opcoes[tipo_selecionado_str]
                        
                        nova_acao = {
                            'id': str(novo_id),
                            'aluno_id': aluno_id,
                            'tipo_acao_id': tipo_info['id'],
                            'tipo': tipo_info['nome'],
                            'descricao': descricao,
                            'data': data.strftime('%Y-%m-%d'),
                            'usuario': st.session_state.username,
                            'status': 'Pendente' # O status padrão é pendente
                        }
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.success(f"Ação '{tipo_info['nome']}' registrada com sucesso!")
                        load_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar a ação: {e}")
    
    st.divider()
    
    st.subheader("Filtros e Exportação")
    
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
    if not acoes_com_pontos.empty:
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='inner')
    
    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'] == filtro_pelotao]
        if filtro_aluno != "Nenhum":
            aluno_id_filtrado = alunos_df[alunos_df['nome_guerra'] == filtro_aluno].iloc[0]['id']
            df_filtrado_final = df_filtrado_final[df_filtrado_final['aluno_id'] == aluno_id_filtrado]
        if filtro_status != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['status'] == filtro_status]
        if filtro_tipo_acao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['nome'] == filtro_tipo_acao]
        
        if ordenar_por == "Mais Antigos": df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)": df_filtrado_final = df_filtrado_final.sort_values(by="nome_guerra", ascending=True)
        else: df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=False) 

    st.divider()
    render_export_section(acoes_com_pontos, alunos_df, filtro_pelotao, filtro_aluno)
    st.divider()

    st.subheader("Fila de Revisão e Ações")

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
                for acao_id in df_filtrado_final['id'].unique(): # Correção para usar 'id'
                    st.session_state.action_selection[acao_id] = new_state
            
            with col_check:
                st.checkbox("Marcar/Desmarcar todos os visíveis", key='select_all_toggle', on_change=toggle_all_visible)
        
        st.write("")
        
        df_filtrado_final.drop_duplicates(subset=['id'], keep='first', inplace=True) # Correção para usar 'id'
        for _, acao in df_filtrado_final.iterrows():
            acao_id = acao['id']
            with st.container(border=True):
                col_check_ind, col_info, col_actions = st.columns([1, 6, 3])
                
                with col_check_ind:
                    st.session_state.action_selection[acao_id] = st.checkbox(" ", value=st.session_state.action_selection.get(acao_id, False), key=f"select_{acao_id}", label_visibility="collapsed")

                with col_info:
                    cor = "green" if acao['pontuacao_efetiva'] > 0 else "red" if acao['pontuacao_efetiva'] < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
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
                        with st.form(f"launch_form_{acao_id}", clear_on_submit=True):
                            if st.form_submit_button("🚀 Lançar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', acao_id).execute()
                                load_data.clear(); st.rerun()
                    
                    if status_atual != 'Arquivado' and can_delete:
                        with st.form(f"archive_form_{acao_id}", clear_on_submit=True):
                            if st.form_submit_button("🗑️ Arquivar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Arquivado'}).eq('id', acao_id).execute()
                                load_data.clear(); st.rerun()
