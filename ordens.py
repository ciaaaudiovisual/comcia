import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission

# ==============================================================================
# DIÁLOGOS DE EDIÇÃO E COMENTÁRIOS
# ==============================================================================
@st.dialog("Editar Item da Parada Diária")
def edit_item_dialog(item_data, supabase):
    st.write(f"Editando item: **{item_data.get('texto', '')[:50]}...**")
    
    usuarios_df = load_data("Users")
    opcoes_responsavel = ["Não Atribuído"]
    if not usuarios_df.empty:
        opcoes_responsavel.extend(sorted(usuarios_df['username'].unique().tolist()))
    
    responsavel_atual = item_data.get('responsavel') or "Não Atribuído"
    index_responsavel = opcoes_responsavel.index(responsavel_atual) if responsavel_atual in opcoes_responsavel else 0

    with st.form("edit_item_form"):
        novo_texto = st.text_area("Descrição do Item*", value=item_data.get('texto', ''))
        novo_responsavel = st.selectbox(
            "Atribuir a:", 
            options=opcoes_responsavel,
            index=index_responsavel
        )
        
        if st.form_submit_button("Salvar Alterações"):
            if not novo_texto:
                st.warning("A descrição não pode ficar vazia.")
                return
            
            try:
                update_data = {
                    'texto': novo_texto,
                    'responsavel': None if novo_responsavel == "Não Atribuído" else novo_responsavel
                }
                supabase.table("Tarefas").update(update_data).eq('id', item_data['id']).execute()
                st.success("Item atualizado com sucesso!")
                load_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao salvar as alterações: {e}")

# --- NOVO: Diálogo para adicionar/editar comentários ---
@st.dialog("Adicionar/Editar Comentário")
def comment_dialog(item_data, supabase):
    st.write(f"Comentários para: **{item_data.get('texto', '')[:50]}...**")
    
    with st.form("comment_form"):
        comentario_atual = item_data.get('comentarios', '')
        novo_comentario = st.text_area("Comentário:", value=comentario_atual, height=200)
        
        if st.form_submit_button("Salvar Comentário"):
            try:
                update_data = {'comentarios': novo_comentario}
                supabase.table("Tarefas").update(update_data).eq('id', item_data['id']).execute()
                st.success("Comentário salvo com sucesso!")
                load_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao salvar o comentário: {e}")

# ==============================================================================
# FUNÇÕES DE CALLBACK
# ==============================================================================
def on_set_status_click(item_id, new_status, supabase):
    update_data = {'status': new_status}
    
    if new_status == 'Concluída':
        update_data['data_conclusao'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        update_data['concluida_por'] = st.session_state.username
    else:
        update_data['data_conclusao'] = None
        update_data['concluida_por'] = None

    try:
        supabase.table("Tarefas").update(update_data).eq('id', item_id).execute()
        st.toast(f"Item movido para '{new_status}'!")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

def on_delete_click(item_id, supabase):
    try:
        supabase.table("Tarefas").delete().eq('id', item_id).execute()
        st.success("Item excluído com sucesso.")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_parada_diaria():
    st.title("Parada Diária")
    st.caption("Controle unificado de itens e tarefas pendentes.")
    supabase = init_supabase_client()

    parada_diaria_df = load_data("Tarefas")
    usuarios_df = load_data("Users")
    
    st.subheader("➕ Adicionar Novo Item")
    with st.form("novo_item_parada", clear_on_submit=True):
        texto = st.text_area("Descrição do Item*", placeholder="Escreva a descrição do novo item aqui...")
        
        # --- NOVO: Campo de comentários na criação ---
        comentarios = st.text_area("Comentários (opcional)", placeholder="Adicione observações iniciais aqui...")

        opcoes_responsavel = ["Não Atribuído"] + sorted(usuarios_df['username'].unique().tolist())
        responsavel = st.selectbox("Atribuir a:", opcoes_responsavel)
        
        if st.form_submit_button("Adicionar Item", use_container_width=True):
            if texto:
                try:
                    ids_numericos = pd.to_numeric(parada_diaria_df['id'], errors='coerce').dropna()
                    novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                    novo_item = {
                        'id': str(novo_id), 
                        'texto': texto, 
                        'status': 'Pendente',
                        'responsavel': None if responsavel == "Não Atribuído" else responsavel,
                        'data_criacao': datetime.now().strftime('%Y-%m-%d'),
                        'comentarios': comentarios # Adicionado ao novo item
                    }
                    supabase.table("Tarefas").insert(novo_item).execute()
                    st.success("Item adicionado!")
                    load_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar item: {e}")
            else:
                st.warning("A descrição do item é obrigatória.")

    st.divider()
    st.subheader("Lista de Itens")
    
    col1, col2 = st.columns(2)
    with col1:
        filtro_status = st.multiselect("Filtrar por Status:", 
                                       options=["Pendente", "Em Andamento", "Concluída"], 
                                       default=["Pendente", "Em Andamento"])
    with col2:
        opcoes_filtro_resp = ["Todos"] + sorted(parada_diaria_df['responsavel'].dropna().unique().tolist())
        filtro_resp = st.multiselect("Filtrar por Responsável:", opcoes_filtro_resp, default=["Todos"])

    filtered_df = parada_diaria_df
    if filtro_status:
        filtered_df = filtered_df[filtered_df['status'].isin(filtro_status)]
    if "Todos" not in filtro_resp:
        filtered_df = filtered_df[filtered_df['responsavel'].isin(filtro_resp)]
    
    if filtered_df.empty:
        st.info("Nenhum item encontrado para os filtros selecionados.")
    else:
        filtered_df['data_criacao'] = pd.to_datetime(filtered_df['data_criacao'], errors='coerce')
        filtered_df_sorted = filtered_df.sort_values('data_criacao', ascending=False)
        
        for _, item in filtered_df_sorted.iterrows():
            with st.container(border=True):
                status_atual = item.get('status', 'Pendente')
                status_map = {
                    'Pendente': '🔵 Pendente',
                    'Em Andamento': '🟠 Em Andamento',
                    'Concluída': '✅ Concluída'
                }
                status_display = status_map.get(status_atual, '⚪ Desconhecido')

                col_status, col_info, col_actions = st.columns([2, 5, 3])

                with col_status:
                    st.markdown(f"**Status**\n\n{status_display}")

                with col_info:
                    st.markdown(f"**Descrição**\n\n{item['texto']}")
                    responsavel_text = f"**Responsável:** {item.get('responsavel') or 'Não atribuído'}"
                    st.caption(responsavel_text)
                    
                    # --- NOVO: Exibição dos comentários ---
                    comentario_item = item.get('comentarios')
                    if comentario_item:
                        with st.expander("Ver Comentários"):
                            st.text(comentario_item)

                with col_actions:
                    st.markdown("**Ações**")
                    botoes_c1, botoes_c2 = st.columns(2)
                    
                    if status_atual == 'Pendente':
                        botoes_c1.button("▶️ Iniciar", on_click=on_set_status_click, args=(item['id'], 'Em Andamento', supabase), key=f"start_{item['id']}", use_container_width=True)
                    elif status_atual == 'Em Andamento':
                        botoes_c1.button("✅ Concluir", on_click=on_set_status_click, args=(item['id'], 'Concluída', supabase), key=f"finish_{item['id']}", use_container_width=True)
                    
                    # --- NOVO: Botão para adicionar/editar comentário ---
                    botoes_c2.button("💬", key=f"comment_{item['id']}", help="Adicionar/Editar Comentário", on_click=lambda i=item: comment_dialog(i, supabase), use_container_width=True)
                    
                    if st.session_state.get('role') == 'admin':
                        if status_atual == 'Concluída':
                           botoes_c1.button("↩️ Reabrir", on_click=on_set_status_click, args=(item['id'], 'Pendente', supabase), key=f"reopen_{item['id']}", use_container_width=True)
                        
                        btn_c1_admin, btn_c2_admin = st.columns(2)
                        btn_c1_admin.button("✏️", key=f"edit_{item['id']}", help="Editar item", on_click=lambda i=item: edit_item_dialog(i, supabase), use_container_width=True)
                        btn_c2_admin.button("🗑️", key=f"delete_{item['id']}", help="Excluir item", on_click=on_delete_click, args=(item['id'], supabase), use_container_width=True)
