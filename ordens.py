import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission

# --- NOVAS FUNÇÕES DE CALLBACK PARA SUPABASE ---

def on_status_change(item_id, table_name, supabase):
    """Atualiza o status de uma tarefa ou ordem."""
    novo_status_bool = st.session_state[f"check_{table_name}_{item_id}"]
    status_col_name = 'status'
    
    update_data = {
        status_col_name: 'Concluída' if novo_status_bool else 'Pendente'
    }

    # Adiciona detalhes de conclusão apenas para tarefas
    if table_name == "Tarefas":
        update_data['data_conclusao'] = datetime.now().strftime('%d/%m/%Y %H:%M') if novo_status_bool else ''
        update_data['concluida_por'] = st.session_state.username if novo_status_bool else ''
    
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
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")

# --- FUNÇÃO DE NOTIFICAÇÃO PRESERVADA ---
def display_task_notifications():
    if 'username' not in st.session_state: return
    logged_in_user = st.session_state.username
    tarefas_df = load_data("Tarefas")
    if tarefas_df.empty or 'status' not in tarefas_df.columns: return

    tarefas_pendentes = tarefas_df[
        (tarefas_df['status'] != 'Concluída') &
        (
            (tarefas_df['responsavel'] == logged_in_user) |
            (tarefas_df['responsavel'] == 'Todos') |
            (tarefas_df['responsavel'] == '') |
            (pd.isna(tarefas_df['responsavel']))
        )
    ]
    if not tarefas_pendentes.empty:
        with st.container(border=True):
            st.info(f"**Atenção, {logged_in_user}!** Você tem tarefas que requerem a sua atenção:", icon="📣")
            for _, tarefa in tarefas_pendentes.iterrows():
                responsavel = tarefa.get('responsavel', 'Não Atribuída')
                if responsavel == '': responsavel = 'Todos'
                responsavel_str = f"(Atribuída a: {responsavel})"
                st.markdown(f"📌 **{tarefa.get('texto', '')}** - *{responsavel_str}*")
        st.divider()

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_ordens_e_tarefas():
    st.title("Ordens Diárias e Tarefas")
    supabase = init_supabase_client()
    display_task_notifications()
    tab1, tab2 = st.tabs(["📝 Ordens do Dia", "✅ Tarefas"])
    with tab1:
        show_ordens_diarias(supabase)
    with tab2:
        show_tarefas(supabase)

# --- ABA DE ORDENS DO DIA ATUALIZADA ---
def show_ordens_diarias(supabase):
    st.subheader("Ordens do Dia")
    ordens_df = load_data("Ordens_Diarias")
    if 'status' not in ordens_df.columns: ordens_df['status'] = 'Pendente'

    filtro_status = st.radio("Filtrar ordens:", ["Pendentes", "Concluídas", "Todas"], horizontal=True, index=0)
    if filtro_status == "Pendentes": df_filtrado = ordens_df[ordens_df['status'] == 'Pendente']
    elif filtro_status == "Concluídas": df_filtrado = ordens_df[ordens_df['status'] == 'Concluída']
    else: df_filtrado = ordens_df

    if st.session_state.get("role") == "admin":
        with st.expander("➕ Registrar Nova Ordem"):
            with st.form("nova_ordem_form"):
                texto = st.text_area("Texto da Ordem")
                if st.form_submit_button("Salvar Ordem"):
                    if texto:
                        try:
                            ordens_all = load_data("Ordens_Diarias")
                            ids_numericos = pd.to_numeric(ordens_all['id'], errors='coerce').dropna()
                            novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                            nova_ordem = {'id': novo_id, 'data': datetime.now().strftime('%Y-%m-%d'), 'texto': texto, 'autor_id': st.session_state.username, 'status': 'Pendente'}
                            supabase.table("Ordens_Diarias").insert(nova_ordem).execute()
                            st.success("Ordem registrada!"); load_data.clear(); st.rerun()
                        except Exception as e: st.error(f"Erro ao salvar: {e}")
                    else: st.warning("O texto da ordem não pode estar vazio.")

    st.divider()
    st.subheader("Lista de Ordens")
    if df_filtrado.empty:
        st.info(f"Nenhuma ordem na categoria '{filtro_status}'.")
    else:
        df_filtrado['data'] = pd.to_datetime(df_filtrado['data'], errors='coerce')
        df_filtrado = df_filtrado.sort_values('data', ascending=False)
        for _, ordem in df_filtrado.iterrows():
            col_check, col_desc, col_del = st.columns([1, 10, 1])
            with col_check:
                st.checkbox("Lida", value=(ordem['status'] == 'Concluída'), key=f"check_Ordens_Diarias_{ordem['id']}", on_change=on_status_change, args=(ordem['id'], "Ordens_Diarias", supabase))
            with col_desc:
                text_style = "text-decoration: line-through; opacity: 0.7;" if ordem['status'] == 'Concluída' else ""
                st.markdown(f"<div style='{text_style}'><b>Ordem de {ordem['data'].strftime('%d/%m/%Y')}</b> por <i>{ordem['autor_id']}</i><p style='white-space: pre-wrap;'>{ordem['texto']}</p></div>", unsafe_allow_html=True)
            with col_del:
                if st.session_state.get("role") == "admin":
                    st.button("🗑️", key=f"del_ordem_{ordem['id']}", on_click=on_delete_click, args=(ordem['id'], "Ordens_Diarias", supabase))
            st.divider()

# --- ABA DE TAREFAS ATUALIZADA ---
def show_tarefas(supabase):
    st.subheader("Tarefas")
    tarefas_df = load_data("Tarefas")
    usuarios_df = load_data("Users")
    
    comcias = usuarios_df[usuarios_df['role'] == 'comcia']['username'].tolist() if not usuarios_df.empty else []
    opcoes_responsavel = ["Não Atribuído"] + comcias
    
    with st.form("nova_tarefa"):
        st.write("Adicionar Nova Tarefa")
        texto = st.text_input("Descrição da Tarefa")
        responsavel = st.selectbox("Atribuir a:", opcoes_responsavel)
        if st.form_submit_button("Adicionar"):
            if texto:
                try:
                    tarefas_all = load_data("Tarefas")
                    ids = pd.to_numeric(tarefas_all['id'], errors='coerce').dropna()
                    novo_id = int(ids.max()) + 1 if not ids.empty else 1
                    nova_tarefa = {'id': novo_id, 'texto': texto, 'status': 'Pendente', 'responsavel': "" if responsavel == "Não Atribuído" else responsavel, 'data_criacao': datetime.now().strftime('%Y-%m-%d'), 'data_conclusao': '', 'concluida_por': ''}
                    supabase.table("Tarefas").insert(nova_tarefa).execute()
                    st.success("Tarefa adicionada!"); load_data.clear(); st.rerun()
                except Exception as e: st.error(f"Erro ao salvar tarefa: {e}")

    if not tarefas_df.empty:
        col1, col2 = st.columns(2)
        filtro_status = col1.multiselect("Filtrar por Status:", ["Pendente", "Em Andamento", "Concluída"], default=["Pendente", "Em Andamento", "Concluída"])
        filtro_resp = col2.multiselect("Filtrar por Responsável:", ["Não atribuído"] + sorted(tarefas_df['responsavel'].dropna().unique().tolist()))
        
        filtered_df = tarefas_df
        if filtro_status: filtered_df = filtered_df[filtered_df['status'].isin(filtro_status)]
        if filtro_resp:
            mask = filtered_df['responsavel'].isin([r for r in filtro_resp if r != "Não atribuído"])
            if "Não atribuído" in filtro_resp: mask |= (filtered_df['responsavel'] == "")
            filtered_df = filtered_df[mask]
        
        filtered_df['data_criacao'] = pd.to_datetime(filtered_df['data_criacao'], errors='coerce')
        filtered_df = filtered_df.sort_values(['status', 'data_criacao'], ascending=[True, False])
        
        for _, tarefa in filtered_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([5, 3, 2])
                with c1:
                    st.write(tarefa['texto']); st.caption(f"Criada em: {tarefa.get('data_criacao')}")
                with c2:
                    st.write(f"Responsável: {tarefa.get('responsavel') or 'Não atribuído'}")
                    if tarefa['status'] == 'Concluída' and tarefa.get('concluida_por'):
                        st.caption(f"Concluída por: {tarefa['concluida_por']} em {tarefa['data_conclusao']}")
                with c3:
                    # Usando o mesmo callback de on_status_change
                    st.checkbox("Concluída", value=(tarefa['status']=='Concluída'), key=f"task_check_{tarefa['id']}", on_change=on_status_change, args=(tarefa['id'], "Tarefas", supabase))
                    if st.session_state.get('role') == 'admin':
                        st.button("Excluir", key=f"del_task_{tarefa['id']}", on_click=on_delete_click, args=(tarefa['id'], "Tarefas", supabase))
    else:
        st.info("Nenhuma tarefa registrada.")

# --- FUNÇÕES HELPER PRESERVADAS ---
def adicionar_como_tarefa(texto, responsavel, supabase):
    try:
        tarefas_all = load_data("Tarefas")
        ids = pd.to_numeric(tarefas_all['id'], errors='coerce').dropna()
        novo_id = int(ids.max()) + 1 if not ids.empty else 1
        nova_tarefa = {'id': novo_id, 'texto': texto, 'status': 'Pendente', 'responsavel': "" if responsavel == "Não atribuído" else responsavel, 'data_criacao': datetime.now().strftime('%Y-%m-%d')}
        supabase.table("Tarefas").insert(nova_tarefa).execute()
        load_data.clear(); return True
    except Exception: return False

def notificacoes_de_tarefas(tarefas_df):
    if tarefas_df.empty: return
    username = st.session_state.get("username")
    tarefas_pendentes = tarefas_df[tarefas_df['status'] != 'Concluída']
    tarefas_do_usuario = tarefas_pendentes[(tarefas_pendentes['responsavel'] == username) | (tarefas_pendentes['responsavel'] == '')]
    if not tarefas_do_usuario.empty:
        st.info(f"🔔 Você tem **{len(tarefas_do_usuario)}** tarefa(s) pendente(s).")