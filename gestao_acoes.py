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
    st.header(f"FAIA de: {aluno_info['nome_guerra']}")
    texto_relatorio = formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df)
    st.text_area("Conteúdo do Relatório:", value=texto_relatorio, height=300)
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info['nome_guerra']}.txt"
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
            msg = f"A ação '{acao['nome']}' para o aluno {aluno_info['nome_guerra']} foi lançada na FAIA com sucesso!"
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

    # Inicialização dos estados da sessão
    if 'action_selection' not in st.session_state: st.session_state.action_selection = {}
    if 'search_query_gestao' not in st.session_state: st.session_state.search_query_gestao = ""
    if 'selected_student_id_gestao' not in st.session_state: st.session_state.selected_student_id_gestao = None

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    with st.expander("➕ Registrar Nova Ação", expanded=True):
        
        # --- NOVO COMPONENTE DE BUSCA INTERATIVA ---
        st.subheader("Passo 1: Encontre e Selecione o Aluno")
        
        def update_search():
            st.session_state.search_query_gestao = st.session_state.search_widget_gestao
            st.session_state.selected_student_id_gestao = None

        query = st.text_input(
            "Buscar por Nº Interno, Nome de Guerra ou NIP:", 
            key="search_widget_gestao",
            on_change=update_search,
            value=st.session_state.get('search_query_gestao', '')
        )

        search_results_df = pd.DataFrame()
        if query:
            search_lower = query.lower()
            mask = (
                alunos_df['nome_guerra'].str.lower().str.contains(search_lower, na=False) | 
                alunos_df['numero_interno'].astype(str).str.contains(search_lower, na=False) |
                (alunos_df['nip'].astype(str).str.contains(search_lower, na=False) if 'nip' in alunos_df.columns else False) |
                (alunos_df['nome_completo'].str.lower().str.contains(search_lower, na=False) if 'nome_completo' in alunos_df.columns else False)
            )
            search_results_df = alunos_df[mask]

        if not search_results_df.empty:
            search_results_df['label'] = search_results_df.apply(lambda row: f"{row.get('numero_interno', '')} - {row.get('nome_guerra', '(NOME PENDENTE)')}", axis=1)
            opcoes_encontradas = pd.Series(search_results_df.id.values, index=search_results_df.label).to_dict()
            
            aluno_selecionado_label = st.radio(
                "Resultados da busca (selecione um):", 
                options=opcoes_encontradas.keys(),
                key='selected_student_radio',
                index=None
            )
            if aluno_selecionado_label:
                st.session_state.selected_student_id_gestao = str(opcoes_encontradas[aluno_selecionado_label])
        elif query:
            st.warning("Nenhum aluno encontrado com os critérios de busca.")
            st.session_state.selected_student_id_gestao = None
        
        st.divider()

        # --- FORMULÁRIO DE REGISTO DE AÇÃO ---
        st.subheader("Passo 2: Registre os Detalhes da Ação")
        if st.session_state.selected_student_id_gestao:
            aluno_selecionado = alunos_df[alunos_df['id'] == st.session_state.selected_student_id_gestao].iloc[0]
            st.info(f"Ação para o aluno: **{aluno_selecionado.get('numero_interno', '')} - {aluno_selecionado.get('nome_guerra', '')}**")

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
                            st.session_state.selected_student_id_gestao = None
                            st.session_state.search_query_gestao = ""
                            load_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar ação: {e}")
        else:
            st.info("⬅️ Por favor, encontre e selecione um aluno no painel acima para continuar.")
    
    st.divider()
    # (O restante do código da página - filtros, lista de ações, etc. - permanece inalterado)
    pass
