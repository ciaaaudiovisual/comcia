import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission, get_permissions_rules

# --- LISTA MESTRA DE FUNCIONALIDADES (COM A VÍRGULA CORRIGIDA) ---
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
    ('pode_editar_lancamento_faia', 'Pode Editar Lançamentos na Fila', 'admin,supervisor'),
    ('acesso_pagina_revisao_geral', 'Acesso à Página de Revisão Geral', 'admin'),
    ('acesso_pagina_geracao_documentos', 'Acesso à Página de Geração de Documentos', 'admin,supervisor,comcia'),
    ('acesso_pagina_rancho_pernoite', 'Acesso aos Relatórios de Rancho', 'admin,comcia,rancho_viewer'), 
    ('acesso_pagina_auxilio_transporte', 'Acesso à Página de Auxílio Transporte', 'admin'),
    ('acesso_pagina_pernoite', 'Acesso à Página de Controle de Pernoite', 'admin,comcia,supervisor'),
]

# ==============================================================================
# FUNÇÕES DE CALLBACK E DIÁLOGOS
# ==============================================================================

def on_visibility_change(acao_id, supabase):
    novo_status = st.session_state[f"visible_{acao_id}"]
    try:
        supabase.table("Tipos_Acao").update({'exibir_no_grafico': novo_status}).eq("id", acao_id).execute()
        load_data.clear()
        st.toast("Visibilidade atualizada.")
    except Exception as e:
        st.error(f"Falha ao atualizar visibilidade: {e}")

@st.dialog("Editar Detalhes da Ação")
def edit_tipo_acao_dialog(tipo_acao, supabase):
    st.write(f"Editando: **{tipo_acao['nome']}**")
    with st.form("edit_tipo_acao_form"):
        novo_nome = st.text_input("Nome da Ação*", value=tipo_acao.get('nome', ''))
        nova_pontuacao = st.number_input("Pontuação", value=float(tipo_acao.get('pontuacao', 0.0)), step=0.01, format="%.2f")
        nova_descricao = st.text_input("Descrição", value=tipo_acao.get('descricao', ''))
        if st.form_submit_button("Salvar Alterações"):
            if not novo_nome:
                st.warning("O nome da ação é obrigatório."); return
            try:
                update_data = {"nome": novo_nome, "descricao": nova_descricao, "pontuacao": nova_pontuacao}
                supabase.table("Tipos_Acao").update(update_data).eq("id", tipo_acao['id']).execute()
                st.success("Tipo de Ação atualizado!"); load_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Falha ao salvar as alterações: {e}")

def on_delete_tipo_acao_click(tipo_acao_id, supabase):
    acoes_df = load_data("Acoes")
    if not acoes_df.empty and str(tipo_acao_id) in acoes_df['tipo_acao_id'].astype(str).values:
        st.error("Não é possível excluir: este tipo de ação já está em uso.")
    else:
        try:
            supabase.table("Tipos_Acao").delete().eq('id', str(tipo_acao_id)).execute()
            st.success("Tipo de Ação excluído."); load_data.clear(); st.rerun()
        except Exception as e:
            st.error(f"Falha ao excluir o Tipo de Ação: {e}")

def on_delete_user_click(user_to_delete, supabase):
    st.warning("A funcionalidade de exclusão de usuário não está implementada por razões de segurança.")

def render_acao_item(row, supabase):
    with st.container(border=True):
        st.markdown(f"**{row['nome']}**"); st.caption(row.get('descricao', 'Sem descrição.'))
        col_score, col_visibility, col_actions = st.columns([2, 1, 1])
        with col_score:
            st.metric(label="Pontuação", value=f"{float(row.get('pontuacao', 0.0)):+.2f}")
        with col_visibility:
            st.checkbox("Visível", value=row.get('exibir_no_grafico', True), key=f"visible_{row['id']}", on_change=on_visibility_change, args=(row['id'], supabase), help="Exibir nos gráficos")
        with col_actions:
            c1, c2 = st.columns(2)
            if c1.button("✏️", key=f"e_{row['id']}", help="Editar", use_container_width=True):
                edit_tipo_acao_dialog(row, supabase)
            if c2.button("🗑️", key=f"d_{row['id']}", help="Excluir", on_click=on_delete_tipo_acao_click, args=(row['id'], supabase), use_container_width=True):
                pass

# ==============================================================================
# RENDERIZAÇÃO DAS ABAS
# ==============================================================================
def show_config_gerais(supabase):
    st.subheader("Configurações Gerais")
    config_df = load_data("Config")
    defaults = {'linha_base_conceito': 8.5, 'impacto_max_acoes': 1.5, 'peso_academico': 1.0, 'periodo_adaptacao_inicio': datetime.now().date(), 'periodo_adaptacao_fim': datetime.now().date(), 'fator_adaptacao': 0.25}
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    def get_config_value(key, default, cast_type=float):
        try: return cast_type(config_dict.get(key, default))
        except (ValueError, TypeError): return default
    linha_base = get_config_value('linha_base_conceito', defaults['linha_base_conceito'])
    impacto_acoes = get_config_value('impacto_max_acoes', defaults['impacto_max_acoes'])
    peso_academico = get_config_value('peso_academico', defaults['peso_academico'])
    adapt_inicio = pd.to_datetime(config_dict.get('periodo_adaptacao_inicio', defaults['periodo_adaptacao_inicio'])).date()
    adapt_fim = pd.to_datetime(config_dict.get('periodo_adaptacao_fim', defaults['periodo_adaptacao_fim'])).date()
    fator_adaptacao = get_config_value('fator_adaptacao', defaults['fator_adaptacao'])
    with st.form("editar_config"):
        st.subheader("Parâmetros do Conceito Final")
        c1, c2, c3 = st.columns(3)
        nova_linha_base = c1.number_input("Linha de Base", value=linha_base, step=0.1, format="%.2f")
        novo_impacto_acoes = c2.number_input("Impacto Máx. Ações", value=impacto_acoes, step=0.1, format="%.2f")
        novo_peso_academico = c3.number_input("Peso Máx. Acadêmico", value=peso_academico, step=0.1, format="%.2f")
        st.divider()
        st.subheader("Período de Adaptação")
        c4, c5, c6 = st.columns(3)
        novo_periodo_inicio = c4.date_input("Início", value=adapt_inicio)
        novo_periodo_fim = c5.date_input("Fim", value=adapt_fim)
        novo_fator = c6.slider("Fator de Adaptação", 0.0, 1.0, fator_adaptacao, 0.05)
        if st.form_submit_button("Salvar Configurações"):
            novas_configs = [
                {'chave': 'linha_base_conceito', 'valor': str(nova_linha_base)}, {'chave': 'impacto_max_acoes', 'valor': str(novo_impacto_acoes)},
                {'chave': 'peso_academico', 'valor': str(novo_peso_academico)}, {'chave': 'periodo_adaptacao_inicio', 'valor': novo_periodo_inicio.strftime('%Y-%m-%d')},
                {'chave': 'periodo_adaptacao_fim', 'valor': novo_periodo_fim.strftime('%Y-%m-%d')}, {'chave': 'fator_adaptacao', 'valor': str(novo_fator)}
            ]
            try:
                supabase.table("Config").upsert(novas_configs).execute()
                st.success("Configurações salvas!"); load_data.clear()
            except Exception as e:
                st.error(f"Falha ao salvar: {e}")

def show_config_usuarios(supabase):
    st.subheader("Gestão de Usuários")
    usuarios_df = load_data("Users")
    if check_permission('pode_gerenciar_usuarios'):
        with st.expander("➕ Adicionar Novo Usuário"):
            with st.form("novo_usuario", clear_on_submit=True):
                email = st.text_input("E-mail*"); password = st.text_input("Senha*", type="password")
                username = st.text_input("Nome de Usuário*"); nome = st.text_input("Nome Completo")
                role = st.selectbox("Permissão*", ["admin", "comcia", "compel", "supervisor", "rancho_viewer"])
                if st.form_submit_button("Adicionar"):
                    if not all([email, password, username]):
                        st.error("E-mail, Senha e Nome de Usuário são obrigatórios.")
                    else:
                        try:
                            res = supabase.auth.sign_up({"email": email, "password": password})
                            if res.user:
                                supabase.table("Users").insert({"id": res.user.id, "username": username, "nome": nome, "role": role}).execute()
                                st.success(f"Usuário {username} criado!"); load_data.clear()
                            else: st.error("Falha ao criar usuário na autenticação.")
                        except Exception as e: st.error(f"Erro ao criar usuário: {e}")
    st.divider()
    st.subheader("Usuários Cadastrados")
    if not usuarios_df.empty:
        for _, u in usuarios_df.iterrows():
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.write(f"**{u.get('nome','N/A')}** (`{u.get('username')}`)"); c2.write(f"Permissão: {u.get('role')}")
                if check_permission('pode_gerenciar_usuarios') and u['username'] != st.session_state.get('username'):
                    with c3: st.button("🗑️", key=f"del_user_{u['id']}", on_click=on_delete_user_click, args=(u, supabase), help="Excluir")
    else: st.info("Nenhum usuário cadastrado.")

def show_config_tipos_acao(supabase):
    st.subheader("Gestão de Tipos de Ação")
    if not check_permission('pode_gerenciar_tipos_acao'):
        st.warning("Sem permissão para gerenciar os tipos de ação."); return
    tipos_acao_df = load_data("Tipos_Acao")
    if not tipos_acao_df.empty:
        tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
    with st.expander("➕ Adicionar Novo Tipo de Ação"):
        with st.form("novo_tipo_acao", clear_on_submit=True):
            nome = st.text_input("Nome da Ação*")
            descricao = st.text_input("Descrição")
            pontuacao = st.number_input("Pontuação*", value=0.00, step=0.01, format="%.2f")
            if st.form_submit_button("Adicionar"):
                if not nome: st.warning("O nome é obrigatório.")
                else:
                    ids_numericos = pd.to_numeric(tipos_acao_df['id'], errors='coerce').dropna()
                    novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                    novo_tipo = {'id': str(novo_id), 'nome': nome, 'descricao': descricao, 'pontuacao': pontuacao, 'exibir_no_grafico': True}
                    try:
                        supabase.table("Tipos_Acao").insert(novo_tipo).execute()
                        st.success("Tipo de ação adicionado!"); load_data.clear(); st.rerun()
                    except Exception as e: st.error(f"Erro ao adicionar: {e}")
    st.divider()
    st.subheader("Tipos de Ação Cadastrados")
    if tipos_acao_df.empty:
        st.info("Nenhum tipo de ação cadastrado."); return
    positivas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome')
    neutras_df = tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome')
    negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')
    col_pos, col_neu, col_neg = st.columns(3)
    with col_pos:
        st.subheader("✅ Positivas"); st.markdown("---")
        if positivas_df.empty: st.info("Nenhuma.")
        for _, row in positivas_df.iterrows(): render_acao_item(row, supabase)
    with col_neu:
        st.subheader("⚪ Neutras"); st.markdown("---")
        if neutras_df.empty: st.info("Nenhuma.")
        for _, row in neutras_df.iterrows(): render_acao_item(row, supabase)
    with col_neg:
        st.subheader("⚠️ Negativas"); st.markdown("---")
        if negativas_df.empty: st.info("Nenhuma.")
        for _, row in negativas_df.iterrows(): render_acao_item(row, supabase)

def show_config_permissoes(supabase):
    st.subheader("Gestão de Permissões por Perfil")
    st.info("O perfil 'admin' tem acesso total e não pode ser editado.")
    permissions_df = get_permissions_rules()
    perfis = ["comcia", "compel", "supervisor", "rancho_viewer"] 
    with st.form("permissions_form"):
        for _, feature in pd.DataFrame(FEATURES_LIST, columns=['key','name','default']).iterrows():
            st.markdown(f"**{feature['name']}**")
            rule = permissions_df[permissions_df['feature_key'] == feature['key']]
            current_roles = rule.iloc[0].get('allowed_roles', '').split(',') if not rule.empty and pd.notna(rule.iloc[0].get('allowed_roles')) else []
            default_for_widget = [role for role in current_roles if role in perfis]
            st.multiselect("Perfis com acesso:", options=perfis, default=default_for_widget, key=f"perm_{feature['key']}")
            st.divider()
        if st.form_submit_button("Salvar Permissões"):
            novas_permissoes = []
            for key, name, _ in FEATURES_LIST:
                selected = st.session_state[f"perm_{key}"]
                final = set(selected); final.add('admin')
                novas_permissoes.append({"feature_key": key, "feature_name": name, "allowed_roles": ",".join(sorted(list(final)))})
            try:
                supabase.table("Permissions").upsert(novas_permissoes, on_conflict='feature_key').execute()
                get_permissions_rules.clear(); st.success("Permissões salvas!")
            except Exception as e: st.error(f"Erro ao salvar: {e}")

# ==============================================================================
# FUNÇÃO PRINCIPAL DO FICHEIRO
# ==============================================================================
def show_config():
    st.title("Configurações do Sistema")
    supabase = init_supabase_client()
    if not check_permission('acesso_pagina_configuracoes'):
        st.error("Acesso negado."); return
    tab_list = ["🏆 Tipos de Ação", "⚙️ Gerais", "👥 Usuários"]
    if st.session_state.get('role') == 'admin':
        tab_list.append("🔒 Permissões")
    tabs = st.tabs(tab_list)
    tab_map = {
        "🏆 Tipos de Ação": show_config_tipos_acao,
        "⚙️ Gerais": show_config_gerais,
        "👥 Usuários": show_config_usuarios,
        "🔒 Permissões": show_config_permissoes
    }
    for i, title in enumerate(tab_list):
        if i < len(tabs):
            with tabs[i]:
                if title in tab_map:
                    tab_map[title](supabase)

