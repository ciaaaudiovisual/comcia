import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission

# ==============================================================================
# DIÁLOGO DE EDIÇÃO
# ==============================================================================

@st.dialog("Editar Item da Parada Diária")
def edit_item_dialog(item_data, supabase):
    """Exibe um formulário para editar um item existente."""
    st.write(f"Editando item: **{item_data.get('texto', '')[:50]}...**")
    
    usuarios_df = load_data("Users")
    opcoes_responsavel = ["Não Atribuído"]
    if not usuarios_df.empty:
        opcoes_responsavel.extend(sorted(usuarios_df['username'].unique().tolist()))
    
    # Define o índice do responsável atual para o selectbox
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
# FUNÇÕES DE CALLBACK
# ==============================================================================

def on_status_change(item_id, supabase, key_name):
    """Atualiza o status de um item (Pendente/Concluída)."""
    novo_status_bool = st.session_state[key_name]
    
    update_data = {
        'status': 'Concluída' if novo_status_bool else 'Pendente',
        'data_conclusao': datetime.now().strftime('%Y-%m-%d %H:%M') if novo_status_bool else None,
        'concluida_por': st.session_state.username if novo_status_bool else None
    }
    
    try:
        # O nome da tabela no backend continua "Tarefas"
        supabase.table("Tarefas").update(update_data).eq('id', item_id).execute()
        st.toast("Status atualizado!")
        load_data.clear()
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
# PÁGINA PRINCIPAL
# ==============================================================================

def show_parada_diaria():
    """Função principal que renderiza a página unificada 'Parada Diária'."""
    st.title("Parada Diária")
    st.caption("Controle unificado de itens e tarefas pendentes.")
    supabase = init_supabase_client()

    # Carrega os dados. A tabela no backend permanece "Tarefas" por consistência.
    parada_diaria_df = load_data("Tarefas")
    usuarios_df = load_data("Users")
    
    # Formulário para adicionar novos itens
    with st.expander("➕ Adicionar Novo Item à Parada Diária"):
        with st.form("novo_item_parada", clear_on_submit=True):
            texto = st.text_area("Descrição do Item*")
            
            opcoes_responsavel = ["Não Atribuído"]
            if not usuarios_df.empty:
                opcoes_responsavel.extend(sorted(usuarios_df['username'].unique().tolist()))
            
            responsavel = st.selectbox("Atribuir a:", opcoes_responsavel)
            
            if st.form_submit_button("Adicionar Item"):
                if texto:
                    try:
                        novo_item = {
                            'texto': texto,
                            'status': 'Pendente',
                            'responsavel': None if responsavel == "Não Atribuído" else responsavel,
                            'data_criacao': datetime.now().strftime('%Y-%m-%d'),
                        }
                        supabase.table("Tarefas").insert(novo_item).execute()
                        st.success("Item adicionado!")
                        load_data.clear()
                    except Exception as e:
                        st.error(f"Erro ao salvar item: {e}")
                else:
                    st.warning("A descrição do item é obrigatória.")

    st.divider()

    # Filtros para a lista de itens
    st.subheader("Lista de Itens")
    col1, col2 = st.columns(2)
    with col1:
        filtro_status = st.multiselect("Filtrar por Status:", ["Pendente", "Concluída"], default=["Pendente"])
    with col2:
        opcoes_filtro_resp = ["Todos"] + sorted(parada_diaria_df['responsavel'].dropna().unique().tolist())
        filtro_resp = st.multiselect("Filtrar por Responsável:", opcoes_filtro_resp, default=["Todos"])

    # Lógica de filtragem
    filtered_df = parada_diaria_df
    if filtro_status:
        filtered_df = filtered_df[filtered_df['status'].isin(filtro_status)]
    if "Todos" not in filtro_resp:
        mask = filtered_df['responsavel'].isin(filtro_resp)
        filtered_df = filtered_df[mask]
    
    # Exibição dos itens
    if filtered_df.empty:
        st.info("Nenhum item encontrado para os filtros selecionados.")
    else:
        filtered_df['data_criacao'] = pd.to_datetime(filtered_df['data_criacao'], errors='coerce')
        filtered_df_sorted = filtered_df.sort_values('data_criacao', ascending=False)
        
        for _, item in filtered_df_sorted.iterrows():
            with st.container(border=True):
                is_done = (item['status'] == 'Concluída')
                
                # Colunas para Checkbox, Informação e Botões de Ação
                col_check, col_info, col_actions = st.columns([1, 8, 2])
                
                with col_check:
                    st.checkbox(
                        "Concluído", 
                        value=is_done, 
                        key=f"check_item_{item['id']}", 
                        on_change=on_status_change, 
                        args=(item['id'], supabase, f"check_item_{item['id']}"),
                        label_visibility="collapsed"
                    )
                
                with col_info:
                    text_style = "text-decoration: line-through; opacity: 0.6;" if is_done else ""
                    st.markdown(f"<p style='{text_style}'>{item['texto']}</p>", unsafe_allow_html=True)
                    
                    responsavel_text = f"Responsável: {item.get('responsavel') or 'Não atribuído'}"
                    data_criacao_fmt = f"Criado em: {item['data_criacao'].strftime('%d/%m/%Y')}" if pd.notna(item.get('data_criacao')) else ""
                    
                    if is_done and item.get('concluida_por'):
                        concluido_text = f"Concluído por: {item['concluida_por']}"
                        st.caption(f"✓ {responsavel_text} | {concluido_text}")
                    else:
                        st.caption(f"👤 {responsavel_text} | 🗓️ {data_criacao_fmt}")

                with col_actions:
                    # Botões de Editar e Excluir (visíveis para admin)
                    if st.session_state.get('role') == 'admin':
                        sub_c1, sub_c2 = st.columns(2)
                        with sub_c1:
                            if st.button("✏️", key=f"edit_item_{item['id']}", help="Editar este item"):
                                edit_item_dialog(item, supabase)
                        with sub_c2:
                            st.button("🗑️", key=f"del_item_{item['id']}", help="Excluir este item", on_click=on_delete_click, args=(item['id'], supabase))
