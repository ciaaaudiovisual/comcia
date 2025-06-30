import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission

# ==============================================================================
# FUNÇÕES DE CALLBACK (CORRIGIDAS)
# ==============================================================================

def on_status_change(item_id, table_name, supabase):
    """Atualiza o status de uma tarefa ou ordem."""
    # A chave do widget é construída dinamicamente para ser única
    key_name = f"check_{table_name}_{item_id}"
    novo_status_bool = st.session_state[key_name]
    
    update_data = {
        'status': 'Concluída' if novo_status_bool else 'Pendente'
    }

    # Adiciona detalhes de conclusão apenas para a tabela de Tarefas
    if table_name == "Tarefas":
        update_data['data_conclusao'] = datetime.now().strftime('%d/%m/%Y %H:%M') if novo_status_bool else None
        update_data['concluida_por'] = st.session_state.username if novo_status_bool else None
    
    try:
        supabase.table(table_name).update(update_data).eq('id', item_id).execute()
        st.toast("Status atualizado!")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

def on_delete_click(item_id, table_name, supabase):
    """Exclui um item (tarefa ou ordem) do banco de dados."""
    try:
        supabase.table(table_name).delete().eq('id', item_id).execute()
        st.success("Item excluído com sucesso.")
        load_data.clear()
        # A chamada st.rerun() foi REMOVIDA daqui, pois é desnecessária em callbacks.
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")

# ==============================================================================
# FUNÇÕES DE RENDERIZAÇÃO DA PÁGINA
# ==============================================================================

def display_task_notifications():
    """Mostra notificações de tarefas pendentes para o usuário logado."""
    if 'username' not in st.session_state:
        return
        
    logged_in_user = st.session_state.username
    tarefas_df = load_data("Tarefas")
    if tarefas_df.empty or 'status' not in tarefas_df.columns:
        return

    # Filtra tarefas pendentes que são para "Todos" ou para o usuário específico
    tarefas_pendentes = tarefas_df[
        (tarefas_df['status'] != 'Concluída') &
        (
            (tarefas_df['responsavel'] == logged_in_user) |
            (tarefas_df['responsavel'] == 'Todos') |
            (pd.isna(tarefas_df['responsavel'])) |
            (tarefas_df['responsavel'] == '')
        )
    ]
    if not tarefas_pendentes.empty:
        with st.container(border=True):
            st.info(f"**Atenção, {logged_in_user}!** Você tem tarefas que requerem a sua atenção:", icon="📣")
            for _, tarefa in tarefas_pendentes.iterrows():
                responsavel = tarefa.get('responsavel') or 'Todos'
                st.markdown(f"📌 **{tarefa.get('texto', '')}** - *(Atribuída a: {responsavel})*")
        st.divider()

def show_ordens_diarias(supabase):
    """Renderiza a aba 'Ordens do Dia'."""
    st.subheader("Ordens do Dia")
    ordens_df = load_data("Ordens_Diarias")
    if 'status' not in ordens_df.columns:
        ordens_df['status'] = 'Pendente'

    filtro_status = st.radio("Filtrar ordens:", ["Pendentes", "Concluídas", "Todas"], horizontal=True, index=0, key="filtro_ordens")
    
    if filtro_status == "Pendentes":
        df_filtrado = ordens_df[ordens_df['status'] == 'Pendente']
    elif filtro_status == "Concluídas":
        df_filtrado = ordens_df[ordens_df['status'] == 'Concluída']
    else:
        df_filtrado = ordens_df

    if st.session_state.get("role") == "admin":
        with st.expander("➕ Registrar Nova Ordem"):
            with st.form("nova_ordem_form", clear_on_submit=True):
                texto = st.text_area("Texto da Ordem")
                if st.form_submit_button("Salvar Ordem"):
                    if texto:
                        try:
                            # CORREÇÃO: Removida a criação manual de ID.
                            nova_ordem = {
                                'data': datetime.now().strftime('%Y-%m-%d'),
                                'texto': texto,
                                'autor_id': st.session_state.username,
                                'status': 'Pendente'
                            }
                            supabase.table("Ordens_Diarias").insert(nova_ordem).execute()
                            st.success("Ordem registrada!")
                            load_data.clear()
                        except Exception as e:
                            st.error(f"Erro ao salvar ordem: {e}")
                    else:
                        st.warning("O texto da ordem não pode estar vazio.")

    st.divider()
    st.subheader("Lista de Ordens")
    if df_filtrado.empty:
        st.info(f"Nenhuma ordem na categoria '{filtro_status}'.")
    else:
        df_filtrado['data'] = pd.to_datetime(df_filtrado['data'], errors='coerce').dt.date
        df_filtrado_sorted = df_filtrado.sort_values('data', ascending=False)
        for _, ordem in df_filtrado_sorted.iterrows():
            col_check, col_desc, col_del = st.columns([1, 10, 1])
            with col_check:
                st.checkbox("Lida", value=(ordem['status'] == 'Concluída'), key=f"check_Ordens_Diarias_{ordem['id']}", on_change=on_status_change, args=(ordem['id'], "Ordens_Diarias", supabase))
            with col_desc:
                text_style = "text-decoration: line-through; opacity: 0.7;" if ordem['status'] == 'Concluída' else ""
                data_formatada = ordem['data'].strftime('%d/%m/%Y') if pd.notna(ordem['data']) else "Data Inválida"
                st.markdown(f"<div style='{text_style}'><b>Ordem de {data_formatada}</b> por <i>{ordem['autor_id']}</i><p style='white-space: pre-wrap;'>{ordem['texto']}</p></div>", unsafe_allow_html=True)
            with col_del:
                if st.session_state.get("role") == "admin":
                    st.button("🗑️", key=f"del_ordem_{ordem['id']}", on_click=on_delete_click, args=(ordem['id'], "Ordens_Diarias", supabase))
            st.divider()

def show_tarefas(supabase):
    """Renderiza a aba 'Tarefas'."""
    st.subheader("Tarefas")
    tarefas_df = load_data("Tarefas")
    usuarios_df = load_data("Users")
    
    opcoes_responsavel = ["Não Atribuído"]
    if not usuarios_df.empty and 'role' in usuarios_df.columns:
        # Pega qualquer usuário que possa ser um responsável (ex: comcia, supervisor, etc.)
        responsaveis = usuarios_df[usuarios_df['role'].isin(['comcia', 'supervisor', 'admin'])]['username'].tolist()
        opcoes_responsavel.extend(sorted(list(set(responsaveis))))

    with st.form("nova_tarefa", clear_on_submit=True):
        st.write("Adicionar Nova Tarefa")
        texto = st.text_input("Descrição da Tarefa*")
        responsavel = st.selectbox("Atribuir a:", opcoes_responsavel)
        if st.form_submit_button("Adicionar"):
            if texto:
                try:
                    # CORREÇÃO: Removida a criação manual de ID.
                    nova_tarefa = {
                        'texto': texto,
                        'status': 'Pendente',
                        'responsavel': None if responsavel == "Não Atribuído" else responsavel,
                        'data_criacao': datetime.now().strftime('%Y-%m-%d'),
                    }
                    supabase.table("Tarefas").insert(nova_tarefa).execute()
                    st.success("Tarefa adicionada!")
                    load_data.clear()
                except Exception as e:
                    st.error(f"Erro ao salvar tarefa: {e}")
            else:
                st.warning("A descrição da tarefa é obrigatória.")

    st.divider()
    st.subheader("Lista de Tarefas")
    if not tarefas_df.empty:
        # Lógica para filtrar e exibir tarefas
        col1, col2 = st.columns(2)
        filtro_status_tarefa = col1.multiselect("Filtrar por Status:", ["Pendente", "Concluída"], default=["Pendente"])
        
        opcoes_filtro_resp = ["Não atribuído"] + sorted(tarefas_df['responsavel'].dropna().unique().tolist())
        filtro_resp = col2.multiselect("Filtrar por Responsável:", opcoes_filtro_resp, default=[])

        filtered_df = tarefas_df
        if filtro_status_tarefa:
            filtered_df = filtered_df[filtered_df['status'].isin(filtro_status_tarefa)]
        if filtro_resp:
            mask = filtered_df['responsavel'].isin([r for r in filtro_resp if r != "Não atribuído"])
            if "Não atribuído" in filtro_resp:
                mask |= (pd.isna(filtered_df['responsavel'])) | (filtered_df['responsavel'] == '')
            filtered_df = filtered_df[mask]
        
        filtered_df['data_criacao'] = pd.to_datetime(filtered_df['data_criacao'], errors='coerce')
        filtered_df_sorted = filtered_df.sort_values('data_criacao', ascending=False)
        
        for _, tarefa in filtered_df_sorted.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([5, 3, 2])
                with c1:
                    st.write(tarefa['texto'])
                    data_criacao_fmt = pd.to_datetime(tarefa.get('data_criacao')).strftime('%d/%m/%Y') if pd.notna(tarefa.get('data_criacao')) else "N/A"
                    st.caption(f"Criada em: {data_criacao_fmt}")
                with c2:
                    st.write(f"Responsável: {tarefa.get('responsavel') or 'Não atribuído'}")
                    if tarefa['status'] == 'Concluída' and tarefa.get('concluida_por'):
                        st.caption(f"Concluída por: {tarefa['concluida_por']} em {tarefa['data_conclusao']}")
                with c3:
                    st.checkbox("Concluída", value=(tarefa['status']=='Concluída'), key=f"check_Tarefas_{tarefa['id']}", on_change=on_status_change, args=(tarefa['id'], "Tarefas", supabase))
                    if st.session_state.get('role') == 'admin':
                        st.button("🗑️", key=f"del_task_{tarefa['id']}", on_click=on_delete_click, args=(tarefa['id'], "Tarefas", supabase))
    else:
        st.info("Nenhuma tarefa registrada.")


def show_ordens_e_tarefas():
    """Função principal que renderiza a página inteira."""
    st.title("Ordens Diárias e Tarefas")
    supabase = init_supabase_client()
    display_task_notifications()
    tab1, tab2 = st.tabs(["📝 Ordens do Dia", "✅ Tarefas"])
    with tab1:
        show_ordens_diarias(supabase)
    with tab2:
        show_tarefas(supabase)
