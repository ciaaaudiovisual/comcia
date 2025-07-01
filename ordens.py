import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission

# ==============================================================================
# DIÁLOGO DE EDIÇÃO (Sem alterações)
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

# ==============================================================================
# FUNÇÕES DE CALLBACK (MODIFICADAS)
# ==============================================================================
def on_set_status_click(item_id, new_status, supabase):
    """Atualiza o status de um item para Pendente, Em Andamento ou Concluída."""
    update_data = {'status': new_status}
    
    if new_status == 'Concluída':
        update_data['data_conclusao'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        update_data['concluida_por'] = st.session_state.username
    else:
        # Limpa os dados de conclusão se for reaberto ou movido para outro estado
        update_data['data_conclusao'] = None
        update_data['concluida_por'] = None

    try:
        supabase.table("Tarefas").update(update_data).eq('id', item_id).execute()
        st.toast(f"Item movido para '{new_status}'!")
        load_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

def on_delete_click(item_id, supabase):
    """Exclui um item da Parada Diária."""
    try:
        supabase.table("Tarefas").delete().eq('id', item_id).execute()
        st.success("Item excluído com sucesso.")
        load_data.clear()
        st.rerun()
    except Exception as e:
        st.error(f"Erro ao excluir: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL (MODIFICADA)
# ==============================================================================
def show_parada_diaria():
    st.title("Parada Diária")
    st.caption("Controle unificado de itens e tarefas pendentes.")
    supabase = init_supabase_client()

    parada_diaria_df = load_data("Tarefas")
    usuarios_df = load_data("Users")
    
    with st.expander("➕ Adicionar Novo Item à Parada Diária"):
        with st.form("novo_item_parada", clear_on_submit=True):
            texto = st.text_area("Descrição do Item*")
            opcoes_responsavel = ["Não Atribuído"] + sorted(usuarios_df['username'].unique().tolist())
            responsavel = st.selectbox("Atribuir a:", opcoes_responsavel)
            
            if st.form_submit_button("Adicionar Item"):
                if texto:
                    try:
                        ids_numericos = pd.to_numeric(parada_diaria_df['id'], errors='coerce').dropna()
                        novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                        novo_item = {
                            'id': str(novo_id), 'texto': texto, 'status': 'Pendente',
                            'responsavel': None if responsavel == "Não Atribuído" else responsavel,
                            'data_criacao': datetime.now().strftime('%Y-%m-%d'),
                        }
                        supabase.table("Tarefas").insert(novo_item).execute()
                        st.success("Item adicionado!")
                        load_data.clear(); st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar item: {e}")
                else:
                    st.warning("A descrição do item é obrigatória.")

    st.divider()
    st.subheader("Lista de Itens")
    
    # --- FILTROS ATUALIZADOS ---
    col1, col2 = st.columns(2)
    with col1:
        filtro_status = st.multiselect("Filtrar por Status:", 
                                       options=["Pendente", "Em Andamento", "Concluída"], 
                                       default=["Pendente", "Em Andamento"])
    with col2:
        opcoes_filtro_resp = ["Todos"] + sorted(parada_diaria_df['responsavel'].dropna().unique().tolist())
        filtro_resp = st.multiselect("Filtrar por Responsável:", opcoes_filtro_resp, default=["Todos"])

    # Lógica de filtragem
    filtered_df = parada_diaria_df
    if filtro_status:
        filtered_df = filtered_df[filtered_df['status'].isin(filtro_status)]
    if "Todos" not in filtro_resp:
        filtered_df = filtered_df[filtered_df['responsavel'].isin(filtro_resp)]
    
    # --- LAYOUT DOS CARDS MELHORADO ---
    if filtered_df.empty:
        st.info("Nenhum item encontrado para os filtros selecionados.")
    else:
        filtered_df['data_criacao'] = pd.to_datetime(filtered_df['data_criacao'], errors='coerce')
        filtered_df_sorted = filtered_df.sort_values('data_criacao', ascending=False)
        
        for _, item in filtered_df_sorted.iterrows():
            with st.container(border=True):
                status_atual = item.get('status', 'Pendente')
                
                # Cores e ícones para cada status
                status_map = {
                    'Pendente': ('🔵 Pendente', 'rgba(0, 100, 255, 0.1)'),
                    'Em Andamento': ('🟠 Em Andamento', 'rgba(255, 165, 0, 0.1)'),
                    'Concluída': ('✅ Concluída', 'rgba(0, 255, 0, 0.1)')
                }
                status_display, status_color = status_map.get(status_atual, ('⚪ Desconhecido', 'grey'))

                # Layout do card em colunas
                col_info, col_actions = st.columns([3, 1])

                with col_info:
                    st.markdown(f"<span style='background-color:{status_color}; padding: 3px 8px; border-radius: 5px;'>{status_display}</span>", unsafe_allow_html=True)
                    st.markdown(f"**{item['texto']}**")
                    responsavel_text = f"**Responsável:** {item.get('responsavel') or 'Não atribuído'}"
                    st.caption(responsavel_text)

                with col_actions:
                    st.write("") # Espaçamento
                    # Botões de status contextuais
                    if status_atual == 'Pendente':
                        st.button("▶️ Iniciar", on_click=on_set_status_click, args=(item['id'], 'Em Andamento', supabase), key=f"start_{item['id']}", use_container_width=True)
                    elif status_atual == 'Em Andamento':
                        st.button("✅ Concluir", on_click=on_set_status_click, args=(item['id'], 'Concluída', supabase), key=f"finish_{item['id']}", use_container_width=True)
                    
                    # Botões de gerenciamento para Admins
                    if st.session_state.get('role') == 'admin':
                        if status_atual == 'Concluída':
                           st.button("↩️ Reabrir", on_click=on_set_status_click, args=(item['id'], 'Pendente', supabase), key=f"reopen_{item['id']}", use_container_width=True)
                        
                        btn_c1, btn_c2 = st.columns(2)
                        with btn_c1:
                            if st.button("✏️", key=f"edit_{item['id']}", help="Editar item"):
                                edit_item_dialog(item, supabase)
                        with btn_c2:
                            st.button("🗑️", key=f"delete_{item['id']}", help="Excluir item", on_click=on_delete_click, args=(item['id'], supabase))
