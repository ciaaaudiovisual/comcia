import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission

# --- Funções de Callback e Diálogos ---

def on_delete_action(action_id, supabase):
    """Callback para excluir uma ação."""
    try:
        supabase.table("Acoes").delete().eq('id', action_id).execute()
        st.toast("Ação excluída com sucesso!", icon="🗑️")
        load_data.clear() # Limpa o cache para recarregar os dados
    except Exception as e:
        st.error(f"Erro ao excluir a ação: {e}")

@st.dialog("✏️ Editar Ação")
def edit_action_dialog(action, tipos_acao_df, supabase):
    """Diálogo para editar os detalhes de uma ação."""
    st.write(f"Editando ação para: **{action.get('nome_guerra', 'N/A')}**")
    
    with st.form(key=f"edit_form_revisao_{action['id_acao']}"):
        # Carrega as opções de tipo de ação
        opcoes_tipo_acao = tipos_acao_df['nome'].unique().tolist()
        try:
            # Tenta encontrar o índice da ação atual para pré-selecionar
            index_acao_atual = opcoes_tipo_acao.index(action['tipo'])
        except (ValueError, KeyError):
            index_acao_atual = 0

        novo_tipo_acao = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao_atual)
        
        # Converte a data atual para um objeto de data, com fallback para a data de hoje
        try:
            data_atual = pd.to_datetime(action['data']).date()
        except (ValueError, TypeError):
            data_atual = datetime.now().date()
        
        nova_data = st.date_input("Data da Ação", value=data_atual)
        nova_descricao = st.text_area("Descrição/Justificativa", value=action.get('descricao', ''))

        if st.form_submit_button("Salvar Alterações"):
            try:
                tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == novo_tipo_acao].iloc[0]
                update_data = {
                    'tipo_acao_id': str(tipo_acao_info['id']),
                    'tipo': novo_tipo_acao,
                    'data': nova_data.strftime('%Y-%m-%d'),
                    'descricao': nova_descricao
                }
                supabase.table("Acoes").update(update_data).eq('id', action['id_acao']).execute()
                st.toast("Ação atualizada com sucesso!", icon="✅")
                load_data.clear()
                st.rerun() # Recarrega a página para refletir a alteração
            except Exception as e:
                st.error(f"Erro ao salvar as alterações: {e}")

# --- Função Principal da Página ---

def show_revisao_geral():
    st.title("Revisão Geral de Lançamentos")
    st.caption("Uma visão completa de todas as ações registradas no sistema.")

    # 1. Verificação de Permissão
    if not check_permission('acesso_pagina_revisao_geral'):
        st.error("Acesso negado. Apenas administradores podem visualizar esta página.")
        return

    supabase = init_supabase_client()

    # 2. Carregamento e Junção dos Dados
    with st.spinner("Carregando e processando todos os lançamentos..."):
        acoes_df = load_data("Acoes")
        alunos_df = load_data("Alunos")
        tipos_acao_df = load_data("Tipos_Acao")

        if acoes_df.empty or alunos_df.empty or tipos_acao_df.empty:
            st.warning("Dados insuficientes (ações, alunos ou tipos de ação) para exibir a revisão.")
            return

        # Garante que as colunas de ID são do tipo string para o merge
        acoes_df['aluno_id'] = acoes_df['aluno_id'].astype(str)
        alunos_df['id'] = alunos_df['id'].astype(str)
        acoes_df['tipo_acao_id'] = acoes_df['tipo_acao_id'].astype(str)
        tipos_acao_df['id'] = tipos_acao_df['id'].astype(str)

        # Adiciona a pontuação às ações
        df_merged = pd.merge(acoes_df, tipos_acao_df[['id', 'pontuacao']], left_on='tipo_acao_id', right_on='id', how='left', suffixes=('_acao', '_tipo'))
        df_merged['pontuacao'] = pd.to_numeric(df_merged['pontuacao'], errors='coerce').fillna(0)
        
        # Adiciona os dados dos alunos
        df_final = pd.merge(df_merged, alunos_df[['id', 'numero_interno', 'nome_guerra']], left_on='aluno_id', right_on='id', how='left', suffixes=('_acao', '_aluno'))
        df_final.rename(columns={'id_acao': 'id'}, inplace=True, errors='ignore') # Renomeia id_acao para id se existir
        
    # 3. Filtro de Ações
    filtro_tipo = st.radio(
        "Filtrar por tipo de ação:",
        ["Todas", "Positivas", "Negativas", "Neutras"],
        horizontal=True,
        key="filtro_revisao_geral"
    )

    df_filtrado = df_final.copy()
    if filtro_tipo == "Positivas":
        df_filtrado = df_filtrado[df_filtrado['pontuacao'] > 0]
    elif filtro_tipo == "Negativas":
        df_filtrado = df_filtrado[df_filtrado['pontuacao'] < 0]
    elif filtro_tipo == "Neutras":
        df_filtrado = df_filtrado[df_filtrado['pontuacao'] == 0]

    # Ordena pelos mais recentes por padrão
    df_filtrado['data'] = pd.to_datetime(df_filtrado['data'], errors='coerce')
    df_filtrado.sort_values(by='data', ascending=False, inplace=True)

    st.divider()
    st.subheader(f"Exibindo {len(df_filtrado)} Lançamentos")

    # 4. Lista de Lançamentos
    for _, action in df_filtrado.iterrows():
        action_id = action['id']
        cols = st.columns([2, 5, 2, 1, 1])
        
        with cols[0]:
            st.markdown(f"**{action.get('numero_interno', 'S/N')} - {action.get('nome_guerra', 'Aluno Apagado')}**")
        
        with cols[1]:
            st.caption(action.get('descricao', 'Sem descrição.'))

        with cols[2]:
            st.caption(f"Por: {action.get('usuario', 'N/A')}")
        
        with cols[3]:
            if st.button("✏️", key=f"edit_{action_id}", help="Editar esta ação"):
                edit_action_dialog(action, tipos_acao_df, supabase)

        with cols[4]:
            st.button("🗑️", key=f"delete_{action_id}", help="Excluir esta ação", on_click=on_delete_action, args=(action_id, supabase))
