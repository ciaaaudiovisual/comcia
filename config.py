import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission, get_permissions_rules

# --- LISTA MESTRA DE FUNCIONALIDADES CONTROLÁVEIS ---
FEATURES_LIST = [
    ('acesso_pagina_configuracoes', 'Acesso à Página de Configurações', 'admin'),
    ('acesso_pagina_relatorios', 'Acesso à Página de Relatórios', 'admin,comcia,supervisor'),
    ('acesso_pagina_lancamentos_faia', 'Acesso à Página de Lançamentos FAIA', 'admin,comcia,supervisor'),
    ('pode_gerenciar_usuarios', 'Pode Adicionar/Excluir Usuários', 'admin'),
    ('pode_gerenciar_tipos_acao', 'Pode Adicionar/Editar/Excluir Tipos de Ação', 'admin'),
    ('pode_editar_aluno', 'Pode Editar Dados de Alunos', 'admin,supervisor'),
    ('pode_importar_alunos', 'Pode Importar Alunos em Massa', 'admin'),
    ('pode_importar_eventos', 'Pode Importar Eventos em Massa', 'admin'),
    ('pode_escanear_cracha', 'Pode Usar o Scanner de Crachás', 'admin,comcia,compel,supervisor'),
    ('pode_excluir_evento_programacao', 'Pode Excluir Eventos da Programação', 'admin,supervisor'),
    ('pode_finalizar_evento_programacao', 'Pode Finalizar Eventos (Status Concluído)', 'admin,comcia,supervisor'),
    ('pode_excluir_lancamento_faia', 'Pode Excluir Lançamentos na tela da FAIA', 'admin,supervisor'),
    ('pode_ver_conceito_final', 'Pode Visualizar o Conceito Final do Aluno', 'admin,supervisor,comcia'),
]

# ==============================================================================
# FUNÇÕES DE CALLBACK E DIÁLOGOS
# ==============================================================================

# --- FUNÇÃO RENOMEADA PARA CORRIGIR O NameError ---
def on_visibility_change(acao_id, supabase):
    """Atualiza a visibilidade da ação nos gráficos."""
    novo_status = st.session_state[f"visible_{acao_id}"]
    try:
        supabase.table("Tipos_Acao").update({'exibir_no_grafico': novo_status}).eq("id", acao_id).execute()
        load_data.clear()
        st.toast("Visibilidade atualizada.")
    except Exception as e:
        st.error(f"Falha ao atualizar visibilidade: {e}")

@st.dialog("Editar Detalhes da Ação")
def edit_tipo_acao_dialog(tipo_acao, supabase):
    """Diálogo para editar NOME e DESCRIÇÃO. A pontuação é editada na tela principal."""
    st.write(f"Editando: **{tipo_acao['nome']}**")
    with st.form("edit_tipo_acao_form"):
        novo_nome = st.text_input("Nome da Ação*", value=tipo_acao.get('nome', ''))
        nova_descricao = st.text_input("Descrição", value=tipo_acao.get('descricao', ''))

        if st.form_submit_button("Salvar Alterações"):
            if not novo_nome:
                st.warning("O nome da ação é obrigatório.")
                return
            try:
                supabase.table("Tipos_Acao").update({
                    "nome": novo_nome,
                    "descricao": nova_descricao
                }).eq("id", tipo_acao['id']).execute()
                st.success("Tipo de Ação atualizado!")
                load_data.clear()
            except Exception as e:
                st.error(f"Falha ao salvar as alterações: {e}")

def on_pontuacao_change(tipo_acao_id, pontuacao_atual, delta, supabase):
    """Altera a pontuação de um tipo de ação em 0.1 para mais ou para menos."""
    nova_pontuacao = round(pontuacao_atual + delta, 1)
    try:
        supabase.table("Tipos_Acao").update({'pontuacao': nova_pontuacao}).eq('id', tipo_acao_id).execute()
        load_data.clear()
    except Exception as e:
        st.error(f"Falha ao alterar a pontuação: {e}")

def on_delete_tipo_acao_click(tipo_acao_id, supabase):
    """Callback para exclusão segura de um tipo de ação."""
    acoes_df = load_data("Acoes")
    if not acoes_df.empty and str(tipo_acao_id) in acoes_df['tipo_acao_id'].astype(str).values:
        st.error("Não é possível excluir: este tipo de ação já está em uso.")
    else:
        try:
            supabase.table("Tipos_Acao").delete().eq('id', str(tipo_acao_id)).execute()
            st.success("Tipo de Ação excluído.")
            load_data.clear()
        except Exception as e:
            st.error(f"Falha ao excluir o Tipo de Ação: {e}")

def on_delete_user_click(user_to_delete, supabase):
    """Callback para exclusão de usuário."""
    try:
        st.info("Funcionalidade de exclusão de usuário (Supabase Auth) requer chaves de administrador e não está implementada nesta versão.")
    except Exception as e:
        st.error(f"Erro ao remover perfil: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL E RENDERIZAÇÃO DAS ABAS
# ==============================================================================

def show_config_gerais(supabase):
    st.subheader("Configurações Gerais")
    config_df = load_data("Config")
    
    defaults = {'linha_base_conceito': 8.5, 'impacto_max_acoes': 1.5, 'peso_academico': 1.0, 'periodo_adaptacao_inicio': datetime.now().date(), 'periodo_adaptacao_fim': datetime.now().date(), 'fator_adaptacao': 0.25}
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}

    def get_config_value(key, default, cast_type=float):
        try:
            return cast_type(config_dict.get(key, default))
        except (ValueError, TypeError):
            return default

    linha_base = get_config_value('linha_base_conceito', defaults['linha_base_conceito'])
    impacto_acoes = get_config_value('impacto_max_acoes', defaults['impacto_max_acoes'])
    peso_academico = get_config_value('peso_academico', defaults['peso_academico'])
    adapt_inicio = pd.to_datetime(config_dict.get('periodo_adaptacao_inicio', defaults['periodo_adaptacao_inicio'])).date()
    adapt_fim = pd.to_datetime(config_dict.get('periodo_adaptacao_fim', defaults['periodo_adaptacao_fim'])).date()
    fator_adaptacao = get_config_value('fator_adaptacao', defaults['fator_adaptacao'])

    with st.form("editar_config"):
        st.subheader("Parâmetros do Conceito Final")
        st.caption("Fórmula: `Conceito = Linha de Base + Impacto das Ações + Impacto Acadêmico`")
        c1, c2, c3 = st.columns(3)
        nova_linha_base = c1.number_input("Linha de Base do Conceito", value=linha_base, step=0.1, format="%.2f", help="Nota de partida para um aluno mediano.")
        novo_impacto_acoes = c2.number_input("Impacto Máximo das Ações (+/-)", value=impacto_acoes, step=0.1, format="%.2f", help="Limite de pontos que as anotações podem influenciar no conceito final.")
        novo_peso_academico = c3.number_input("Peso Máximo Acadêmico", value=peso_academico, step=0.1, format="%.2f", help="Bônus máximo de pontos para o aluno com a melhor média.")
        
        st.divider()
        st.subheader("Parâmetros do Período de Adaptação")
        st.caption("As pontuações negativas das ações serão multiplicadas por este fator durante o período.")
        c4, c5, c6 = st.columns(3)
        novo_periodo_inicio = c4.date_input("Início do Período de Adaptação", value=adapt_inicio)
        novo_periodo_fim = c5.date_input("Fim do Período de Adaptação", value=adapt_fim)
        novo_fator = c6.slider("Fator de Adaptação", 0.0, 1.0, fator_adaptacao, 0.05)

        if st.form_submit_button("Salvar Todas as Configurações"):
            novas_configs = [
                {'chave': 'linha_base_conceito', 'valor': str(nova_linha_base)},
                {'chave': 'impacto_max_acoes', 'valor': str(novo_impacto_acoes)},
                {'chave': 'peso_academico', 'valor': str(novo_peso_academico)},
                {'chave': 'periodo_adaptacao_inicio', 'valor': novo_periodo_inicio.strftime('%Y-%m-%d')},
                {'chave': 'periodo_adaptacao_fim', 'valor': novo_periodo_fim.strftime('%Y-%m-%d')},
                {'chave': 'fator_adaptacao', 'valor': str(novo_fator)}
            ]
            try:
                supabase.table("Config").upsert(novas_configs).execute()
                st.success("Configurações salvas com sucesso!")
                load_data.clear()
            except Exception as e:
                st.error(f"Falha ao salvar configurações: {e}")

def show_config_usuarios(supabase):
    st.subheader("Gestão de Usuários")
    usuarios_df = load_data("Users")

    if check_permission('pode_gerenciar_usuarios'):
        with st.expander("➕ Adicionar Novo Usuário"):
            with st.form("novo_usuario", clear_on_submit=True):
                st.info("O login no Supabase usa E-mail. O 'Nome de Usuário' é para exibição interna.")
                email = st.text_input("E-mail do Usuário*")
                password = st.text_input("Senha Temporária*", type="password")
                username = st.text_input("Nome de Usuário (para exibição)*")
                nome = st.text_input("Nome Completo")
                role = st.selectbox("Tipo de Permissão*", ["admin", "comcia", "compel", "supervisor"])
                
                if st.form_submit_button("Adicionar Usuário"):
                    if not all([email, password, username]):
                        st.error("E-mail, Senha e Nome de Usuário são obrigatórios.")
                    else:
                        try:
                            res = supabase.auth.sign_up({"email": email, "password": password})
                            if res.user:
                                new_user_id = res.user.id
                                supabase.table("Users").insert({
                                    "id": new_user_id, "username": username, "nome": nome, "role": role
                                }).execute()
                                st.success(f"Usuário {username} criado!")
                                load_data.clear()
                            else:
                                st.error("Falha ao criar o usuário no sistema de autenticação.")
                        except Exception as e:
                            st.error(f"Erro ao criar usuário: {e}")

    st.divider()
    st.subheader("Usuários Cadastrados")
    if not usuarios_df.empty:
        for _, u in usuarios_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{u.get('nome','N/A')}** (`{u.get('username')}`)")
                c2.write(f"Permissão: {u.get('role')}")
                if check_permission('pode_gerenciar_usuarios') and u['username'] != st.session_state.get('username'):
                    with c3:
                        st.button("🗑️", key=f"del_user_{u['id']}", on_click=on_delete_user_click, args=(u, supabase), help="Excluir este usuário")
    else:
        st.info("Nenhum usuário cadastrado.")

def show_config_tipos_acao(supabase):
    st.subheader("Gestão de Tipos de Ação")
    if not check_permission('pode_gerenciar_tipos_acao'):
        st.warning("Você não tem permissão para gerenciar os tipos de ação."); return
        
    tipos_acao_df = load_data("Tipos_Acao")
    
    with st.expander("➕ Adicionar Novo Tipo de Ação"):
        with st.form("novo_tipo_acao", clear_on_submit=True):
            nome = st.text_input("Nome da Ação*")
            descricao = st.text_input("Descrição")
            pontuacao = st.number_input("Pontuação Inicial*", value=0.0, step=0.1, format="%.1f")
            
            if st.form_submit_button("Adicionar Tipo"):
                if not nome: st.warning("O nome da ação é obrigatório.")
                else:
                    ids = pd.to_numeric(tipos_acao_df['id'], errors='coerce').dropna()
                    novo_id = int(ids.max()) + 1 if not ids.empty else 1
                    novo_tipo = {'id': str(novo_id), 'nome': nome, 'descricao': descricao, 'pontuacao': pontuacao, 'exibir_no_grafico': True}
                    try:
                        supabase.table("Tipos_Acao").insert(novo_tipo).execute()
                        st.success("Tipo de ação adicionado!"); load_data.clear()
                    except Exception as e: st.error(f"Erro ao adicionar: {e}")

    st.divider()
    st.subheader("Tipos de Ação Cadastrados")

    if not tipos_acao_df.empty:
        col_header1, col_header2, col_header3, col_header4 = st.columns([5, 2, 2, 2])
        col_header1.markdown("**Ação**")
        col_header2.markdown("<p style='text-align: center;'><b>Ajuste de Pontos</b></p>", unsafe_allow_html=True)
        col_header3.markdown("<p style='text-align: center;'><b>Visível no Gráfico</b></p>", unsafe_allow_html=True)
        col_header4.markdown("<p style='text-align: center;'><b>Opções</b></p>", unsafe_allow_html=True)

        for _, row in tipos_acao_df.sort_values('nome').iterrows():
            pontuacao_atual = float(row.get('pontuacao', 0.0))
            
            col_info, col_score_ctrl, col_visibility, col_actions = st.columns([5, 2, 2, 2])
            
            with col_info:
                st.markdown(f"**{row['nome']}**")
                st.caption(row.get('descricao', 'Sem descrição.'))
            
            with col_score_ctrl:
                sub_c1, sub_c2, sub_c3 = st.columns([1, 1, 1])
                sub_c1.button("➖", key=f"minus_{row['id']}", on_click=on_pontuacao_change, args=(row['id'], pontuacao_atual, -0.1, supabase), use_container_width=True)
                cor = 'red' if pontuacao_atual < 0 else 'green' if pontuacao_atual > 0 else 'gray'
                sub_c2.markdown(f"<p style='font-size: 1.25rem; text-align: center; color: {cor}; margin: 0; font-weight: 500; padding-top: 5px;'>{pontuacao_atual:+.1f}</p>", unsafe_allow_html=True)
                sub_c3.button("➕", key=f"plus_{row['id']}", on_click=on_pontuacao_change, args=(row['id'], pontuacao_atual, 0.1, supabase), use_container_width=True)
            
            with col_visibility:
                st.checkbox(
                    "Exibir",
                    value=row.get('exibir_no_grafico', True),
                    key=f"visible_{row['id']}",
                    on_change=on_visibility_change,
                    args=(row['id'], supabase),
                    label_visibility="collapsed"
                )

            with col_actions:
                sub_b1, sub_b2 = st.columns(2)
                if sub_b1.button("✏️", key=f"e_{row['id']}", help="Editar nome/descrição", use_container_width=True):
                    edit_tipo_acao_dialog(row, supabase)
                sub_b2.button("🗑️", key=f"d_{row['id']}", help="Excluir", on_click=on_delete_tipo_acao_click, args=(row['id'], supabase), use_container_width=True)
            
            st.markdown("---") 

def show_config_permissoes(supabase):
    st.subheader("Gestão de Permissões por Perfil")
    st.info("O perfil 'admin' sempre tem acesso total e não pode ser editado aqui.")
    permissions_df = get_permissions_rules()
    
    perfis_disponiveis = ["comcia", "compel", "supervisor"] 
    with st.form("permissions_form"):
        for _, feature in pd.DataFrame(FEATURES_LIST, columns=['key','name','default']).iterrows():
            st.markdown(f"**{feature['name']}**")
            rule = permissions_df[permissions_df['feature_key'] == feature['key']]
            current_roles = []
            if not rule.empty:
                roles_str = rule.iloc[0].get('allowed_roles', '')
                if pd.notna(roles_str):
                    current_roles = [r.strip() for r in roles_str.split(',') if r]
            
            default_for_widget = [role for role in current_roles if role in perfis_disponiveis]
            st.multiselect("Perfis com acesso:", options=perfis_disponiveis, default=default_for_widget, key=f"perm_{feature['key']}")
            st.divider()
            
        if st.form_submit_button("Salvar Todas as Permissões"):
            novas_permissoes = []
            for feature_key, feature_name, _ in FEATURES_LIST:
                selected_roles = st.session_state[f"perm_{feature_key}"]
                final_roles = set(selected_roles)
                default_roles_str = next((f[2] for f in FEATURES_LIST if f[0] == feature_key), '')
                if 'admin' in default_roles_str:
                    final_roles.add('admin')
                
                novas_permissoes.append({
                    "feature_key": feature_key, 
                    "feature_name": feature_name, 
                    "allowed_roles": ",".join(sorted(list(final_roles)))
                })
            
            try:
                supabase.table("Permissions").upsert(novas_permissoes, on_conflict='feature_key').execute()
                get_permissions_rules.clear()
                st.success("Permissões salvas com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar permissões: {e}")

def show_config():
    st.title("Configurações do Sistema")
    supabase = init_supabase_client()

    if not check_permission('acesso_pagina_configuracoes'):
        st.error("Acesso negado. Você não tem permissão para acessar esta página.")
        return
    
    tab_list = ["⚙️ Gerais", "👥 Usuários", "🏆 Tipos de Ação"]
    if st.session_state.get('role') == 'admin':
        tab_list.append("🔒 Permissões")
    tabs = st.tabs(tab_list)
    
    with tabs[0]:
        show_config_gerais(supabase)
    with tabs[1]:
        show_config_usuarios(supabase)
    with tabs[2]:
        show_config_tipos_acao(supabase)
    if "🔒 Permissões" in tab_list:
        with tabs[3]:
            show_config_permissoes(supabase)
