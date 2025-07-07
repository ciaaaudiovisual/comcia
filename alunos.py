import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
import math
import re 

# ==============================================================================
# FUNÇÃO DE APOIO PARA IMPORTAÇÃO
# ==============================================================================
def create_csv_template():
    """Cria um template CSV em memória para o utilizador baixar."""
    template_data = {
        'numero_interno': ['101', '102'],
        'nome_guerra': ['JOKER', 'PENGUIN'],
        'nome_completo': ['Jack Napier', 'Oswald Cobblepot'],
        'pelotao': ['Alfa', 'Bravo'],
        'especialidade': ['Infantaria', 'Artilharia'],
        'nip': ['12345678', '87654321'],
        'url_foto': ['http://exemplo.com/foto1.png', 'http://exemplo.com/foto2.png'],
        'media_academica': [8.5, 7.9],
        'data_nascimento': ['1990-04-01', '1988-11-25'],
        'endereco': ['Rua das Flores, 123', 'Av. Central, 456'],
        'telefone_contato': ['21999998888', '21988887777'],
        'contato_emergencia_nome': ['Martha Wayne', 'Alfred Pennyworth'],
        'contato_emergencia_numero': ['21977776666', '21966665555'],
        'numero_armario': ['A-15', 'B-07']
    }
    df = pd.DataFrame(template_data)
    return df.to_csv(index=False, sep=';').encode('utf-8')

# ==============================================================================
# FUNÇÕES DE CÁLCULO
# ==============================================================================
def calcular_pontuacao_efetiva(acoes_df: pd.DataFrame, tipos_acao_df: pd.DataFrame, config_df: pd.DataFrame) -> pd.DataFrame:
    if acoes_df.empty or tipos_acao_df.empty:
        return pd.DataFrame()
        
    if 'pontuacao' not in tipos_acao_df.columns:
        st.error("ERRO CRÍTICO: A coluna 'pontuacao' não existe na tabela 'Tipos_Acao'.")
        return pd.DataFrame()

    acoes_copy = acoes_df.copy()
    tipos_copy = tipos_acao_df.copy()

    tipos_copy['pontuacao'] = pd.to_numeric(tipos_copy['pontuacao'], errors='coerce').fillna(0)
    acoes_copy['tipo_acao_id'] = acoes_copy['tipo_acao_id'].astype(str)
    tipos_copy['id'] = tipos_copy['id'].astype(str)
    
    acoes_com_pontos = pd.merge(acoes_copy, tipos_copy[['id', 'pontuacao', 'nome']], left_on='tipo_acao_id', right_on='id', how='left')
    
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    fator_adaptacao = float(config_dict.get('fator_adaptacao', 0.25))
    try:
        inicio_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_inicio')).date()
        fim_adaptacao = pd.to_datetime(config_dict.get('periodo_adaptacao_fim')).date()
    except Exception:
        inicio_adaptacao, fim_adaptacao = None, None

    def aplicar_fator(row):
        pontuacao = row.get('pontuacao', 0.0)
        data_convertida = pd.to_datetime(row['data'], errors='coerce')
        if pd.isna(data_convertida):
            return pontuacao
        
        data_acao = data_convertida.date()

        if pontuacao >= 0 or not inicio_adaptacao: return pontuacao
        
        if inicio_adaptacao <= data_acao <= fim_adaptacao:
            return pontuacao * fator_adaptacao
        return pontuacao
        
    acoes_com_pontos['pontuacao_efetiva'] = acoes_com_pontos.apply(aplicar_fator, axis=1)
    return acoes_com_pontos

def calcular_conceito_final(soma_pontos_acoes: float, media_academica_aluno: float, todos_alunos_df: pd.DataFrame, config_dict: dict) -> float:
    linha_base = float(config_dict.get('linha_base_conceito', 8.5))
    impacto_max_acoes = float(config_dict.get('impacto_max_acoes', 1.5))
    peso_academico = float(config_dict.get('peso_academico', 1.0))

    impacto_acoes = max(-impacto_max_acoes, min(soma_pontos_acoes, impacto_max_acoes))
    impacto_academico = 0.0
    
    if 'media_academica' in todos_alunos_df.columns and not todos_alunos_df.empty:
        medias_validas = pd.to_numeric(todos_alunos_df['media_academica'], errors='coerce').dropna()
        if not medias_validas.empty and medias_validas.max() > medias_validas.min():
            media_min_turma = medias_validas.min()
            media_max_turma = medias_validas.max()
            if (media_max_turma - media_min_turma) > 0:
                fator_normalizado = (media_academica_aluno - media_min_turma) / (media_max_turma - media_min_turma)
                impacto_academico = fator_normalizado * peso_academico
    
    conceito_final = linha_base + impacto_acoes + impacto_academico
    return max(0.0, min(conceito_final, 10.0))

# ==============================================================================
# DIÁLOGOS
# ==============================================================================

@st.dialog("Registrar Nova Ação")
def registrar_acao_dialog(aluno_id, aluno_nome, supabase):
    st.write(f"Aluno: **{aluno_nome}**")
    tipos_acao_df = load_data("Tipos_Acao")
    if tipos_acao_df.empty:
        st.error("Não há tipos de ação cadastrados."); return
    
    with st.form("nova_acao_dialog_form"):
        tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
        sorted_tipos_df = tipos_acao_df.sort_values('nome')
        positivas_df = sorted_tipos_df[sorted_tipos_df['pontuacao'] > 0]
        neutras_df = sorted_tipos_df[sorted_tipos_df['pontuacao'] == 0]
        negativas_df = sorted_tipos_df[sorted_tipos_df['pontuacao'] < 0]
        opcoes_finais, tipos_opcoes_map = [], {}
        if not positivas_df.empty:
            opcoes_finais.append("--- AÇÕES POSITIVAS ---")
            for _, r in positivas_df.iterrows():
                label = f"{r['nome']} ({r['pontuacao']:.1f} pts)"
                opcoes_finais.append(label); tipos_opcoes_map[label] = r
        if not neutras_df.empty:
            opcoes_finais.append("--- AÇÕES NEUTRAS ---")
            for _, r in neutras_df.iterrows():
                label = f"{r['nome']} (0.0 pts)"
                opcoes_finais.append(label); tipos_opcoes_map[label] = r
        if not negativas_df.empty:
            opcoes_finais.append("--- AÇÕES NEGATIVAS ---")
            for _, r in negativas_df.iterrows():
                label = f"{r['nome']} ({r['pontuacao']:.1f} pts)"
                opcoes_finais.append(label); tipos_opcoes_map[label] = r
        
        tipo_selecionado_str = st.selectbox("Tipo de Ação", options=opcoes_finais)
        descricao = st.text_area("Descrição/Justificativa (Opcional)")
        data = st.date_input("Data da Ação", value=datetime.now())
        
        if st.form_submit_button("Registrar"):
            if not tipo_selecionado_str or tipo_selecionado_str.startswith("---"):
                st.warning("Por favor, selecione um tipo de ação válido."); return
            try:
                tipo_info = tipos_opcoes_map[tipo_selecionado_str]
                nova_acao = {
                    'aluno_id': str(aluno_id), 
                    'tipo_acao_id': str(tipo_info['id']),
                    'tipo': tipo_info['nome'], 
                    'descricao': descricao, 
                    'data': data.strftime('%Y-%m-%d'),
                    'usuario': st.session_state.username, 
                    'status': 'Pendente'
                }
                supabase.table("Acoes").insert(nova_acao).execute()
                st.success("Ação registrada com sucesso!"); load_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Falha ao registrar a ação: {e}")

@st.dialog("Histórico de Ações")
def historico_dialog(aluno, acoes_df, tipos_acao_df, config_df):
    st.header(f"Histórico de: {aluno.get('nome_guerra', 'N/A')}")
    
    if not acoes_df.empty and 'aluno_id' in acoes_df.columns:
        acoes_do_aluno_todas = acoes_df[acoes_df['aluno_id'].astype(str) == str(aluno['id'])]
        acoes_do_aluno = acoes_do_aluno_todas[acoes_do_aluno_todas['status'] == 'Lançado']
    else:
        acoes_do_aluno = pd.DataFrame()
        
    if acoes_do_aluno.empty:
        st.info("Nenhuma ação com status 'Lançado' encontrada no histórico.")
    else:
        historico_com_pontos = calcular_pontuacao_efetiva(acoes_do_aluno.copy(), tipos_acao_df, config_df)
        if not historico_com_pontos.empty:
            for _, acao in historico_com_pontos.sort_values("data", ascending=False).iterrows():
                pontos = acao.get('pontuacao_efetiva', 0.0)
                data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                cor_ponto = "green" if pontos > 0 else "red" if pontos < 0 else "gray"
                
                st.markdown(f"""
                <div style="border-bottom: 1px solid #e0e0e0; padding-bottom: 5px; margin-bottom: 5px;">
                    <b>{data_formatada} - {acao.get('nome', 'N/A')}</b> 
                    (<span style='color:{cor_ponto};'>{pontos:+.1f} pts</span>)
                    <br>
                    <small><i>{acao.get('descricao', 'Sem descrição.')}</i></small>
                </div>
                """, unsafe_allow_html=True)

@st.dialog("Informações do Aluno")
def informacoes_dialog(aluno, supabase):
    st.header(f"Informações de: {aluno.get('nome_guerra', 'N/A')}")

    def format_whatsapp_link(numero):
        if not numero or not isinstance(numero, str):
            return None
        numero_limpo = re.sub(r'\D', '', numero)
        if len(numero_limpo) >= 10:
             return f"https://wa.me/55{numero_limpo}"
        return None

    with st.form(key=f"info_edit_form_{aluno['id']}"):
        tab_pessoal, tab_contato, tab_academico, tab_outros = st.tabs(["Pessoal", "Contato", "Acadêmico", "Outros"])

        with tab_pessoal:
            st.subheader("Dados Pessoais")
            new_nome_completo = st.text_input("Nome Completo", value=aluno.get('nome_completo', ''))
            new_nome_guerra = st.text_input("Nome de Guerra", value=aluno.get('nome_guerra', ''))
            new_numero_interno = st.text_input("Número Interno", value=aluno.get('numero_interno', ''))
            new_nip = st.text_input("NIP", value=aluno.get('nip', ''))
            new_pelotao = st.text_input("Pelotão", value=aluno.get('pelotao', ''))
            new_especialidade = st.text_input("Especialidade", value=aluno.get('especialidade', ''))
            new_url_foto = st.text_input("URL da Foto", value=aluno.get('url_foto', ''))

        with tab_contato:
            st.subheader("Informações de Contato")
            new_telefone_contato = st.text_input("Telefone de Contato", value=aluno.get('telefone_contato', ''))
            link_whatsapp = format_whatsapp_link(new_telefone_contato)
            if link_whatsapp:
                st.markdown(f"[Chamar no WhatsApp]({link_whatsapp})", unsafe_allow_html=True)

            new_endereco = st.text_area("Endereço", value=aluno.get('endereco', ''))
            
            st.divider()

            st.subheader("Contato de Emergência")
            new_contato_emergencia_nome = st.text_input("Nome do Contato de Emergência", value=aluno.get('contato_emergencia_nome', ''))
            new_contato_emergencia_numero = st.text_input("Telefone de Emergência", value=aluno.get('contato_emergencia_numero', ''))
            link_emergencia = format_whatsapp_link(new_contato_emergencia_numero)
            if link_emergencia:
                st.markdown(f"[Chamar Contato de Emergência]({link_emergencia})", unsafe_allow_html=True)
        
        with tab_academico:
            st.subheader("Dados Acadêmicos")
            new_media_academica = st.number_input("Média Acadêmica Final", value=float(aluno.get('media_academica', 0.0)), min_value=0.0, max_value=10.0, step=0.1, format="%.2f")

        with tab_outros:
            st.subheader("Outras Informações")
            new_numero_armario = st.text_input("Número do Armário", value=aluno.get('numero_armario', ''))

        if st.form_submit_button("Salvar Alterações"):
            if check_permission('pode_editar_aluno'):
                dados_update = {
                    'media_academica': new_media_academica, 'nome_completo': new_nome_completo,
                    'nome_guerra': new_nome_guerra, 'numero_interno': new_numero_interno, 
                    'pelotao': new_pelotao, 'especialidade': new_especialidade, 'url_foto': new_url_foto,
                    'nip': new_nip, 'endereco': new_endereco, 'telefone_contato': new_telefone_contato,
                    'contato_emergencia_nome': new_contato_emergencia_nome,
                    'contato_emergencia_numero': new_contato_emergencia_numero,
                    'numero_armario': new_numero_armario
                }
                try:
                    supabase.table("Alunos").update(dados_update).eq("id", aluno['id']).execute()
                    st.success("Dados atualizados com sucesso!"); load_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Erro ao atualizar os dados: {e}")
            else:
                st.warning("Você não tem permissão para editar dados.")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_alunos():
    st.title("Gestão de Alunos")
    supabase = init_supabase_client()
    if 'page_num' not in st.session_state: st.session_state.page_num = 1
    def reset_page(): st.session_state.page_num = 1

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    novas_colunas = {
        'media_academica': 0.0, 'endereco': '', 'telefone_contato': '',
        'contato_emergencia_nome': '', 'contato_emergencia_numero': '', 'numero_armario': ''
    }
    for col, default_value in novas_colunas.items():
        if col not in alunos_df.columns:
            alunos_df[col] = default_value

    if tipos_acao_df.empty:
        st.error("ERRO CRÍTICO: Tabela 'Tipos_Acao' não encontrada. Cadastre os tipos de ação primeiro."); st.stop()

    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    
    if not acoes_df.empty:
        acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
        soma_pontos_por_aluno = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
        
        # CORREÇÃO: Garante que ambas as chaves são do tipo string ANTES do mapeamento
        # Isso protege o código independentemente do tipo de dado que vem do BD.
        alunos_df['id'] = alunos_df['id'].astype(str)
        soma_pontos_por_aluno.index = soma_pontos_por_aluno.index.astype(str)
        
        alunos_df['soma_pontos_acoes'] = alunos_df['id'].map(soma_pontos_por_aluno)
    else:
        alunos_df['soma_pontos_acoes'] = 0

    alunos_df['soma_pontos_acoes'] = alunos_df['soma_pontos_acoes'].fillna(0)
    
    alunos_df['conceito_final_calculado'] = alunos_df.apply(
        lambda row: calcular_conceito_final(
            row['soma_pontos_acoes'],
            float(row.get('media_academica', 0.0)),
            alunos_df,
            config_dict
        ),
        axis=1
    )

    st.subheader("Filtros e Ordenação")
    col1, col2 = st.columns(2)
    with col1:
        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
        pelotao_selecionado = st.selectbox("Filtrar por Pelotão:", opcoes_pelotao, on_change=reset_page)
        opcoes_especialidade = ["Todas"] + sorted([e for e in alunos_df['especialidade'].unique() if pd.notna(e)])
        especialidade_selecionada = st.selectbox("Filtrar por Especialidade:", opcoes_especialidade, on_change=reset_page)
    with col2:
        search = st.text_input("Buscar por nome, número ou NIP...", key="search_aluno", on_change=reset_page)
        sort_option = st.selectbox(
            "Ordenar por:",
            ["Padrão (Nº Interno)", "Maior Conceito", "Menor Conceito"],
            key="sort_aluno", on_change=reset_page
        )

    filtered_df = alunos_df.copy()
    if pelotao_selecionado != "Todos": filtered_df = filtered_df[filtered_df['pelotao'] == pelotao_selecionado]
    if especialidade_selecionada != "Todas": filtered_df = filtered_df[filtered_df['especialidade'] == especialidade_selecionada]
    if search:
        search_lower = search.lower()
        mask_nome_guerra = filtered_df['nome_guerra'].str.lower().str.contains(search_lower, na=False)
        mask_num_interno = filtered_df['numero_interno'].astype(str).str.lower().str.contains(search_lower, na=False)
        mask_nome_completo = filtered_df['nome_completo'].str.lower().str.contains(search_lower, na=False)
        mask_nip = filtered_df['nip'].astype(str).str.lower().str.contains(search_lower, na=False)
        filtered_df = filtered_df[mask_nome_guerra | mask_num_interno | mask_nome_completo | mask_nip]

    if sort_option == "Maior Conceito":
        filtered_df = filtered_df.sort_values(by='conceito_final_calculado', ascending=False)
    elif sort_option == "Menor Conceito":
        filtered_df = filtered_df.sort_values(by='conceito_final_calculado', ascending=True)
    else:
        filtered_df['numero_interno_num'] = pd.to_numeric(filtered_df['numero_interno'], errors='coerce')
        filtered_df = filtered_df.sort_values(by='numero_interno_num', ascending=True)
    st.divider()

    if check_permission('pode_importar_alunos'):
        with st.expander("➕ Opções de Cadastro"):
            st.subheader("Adicionar Novo Aluno")
            with st.form("add_aluno_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                numero_interno = c1.text_input("Número Interno*")
                nome_guerra = c2.text_input("Nome de Guerra*")
                nome_completo = st.text_input("Nome Completo")
                c3, c4 = st.columns(2)
                pelotao = c3.text_input("Pelotão*")
                nip = c4.text_input("NIP")
                especialidade = st.text_input("Especialidade")
                if st.form_submit_button("Adicionar Aluno"):
                    if not all([numero_interno, nome_guerra, pelotao]):
                        st.warning("Número, Nome de Guerra e Pelotão são obrigatórios.")
                    else:
                        try:
                            novo_aluno = {
                                'numero_interno': numero_interno, 
                                'nome_guerra': nome_guerra, 'nome_completo': nome_completo, 
                                'pelotao': pelotao, 'especialidade': especialidade, 'nip': nip
                            }
                            supabase.table("Alunos").insert(novo_aluno).execute()
                            st.success(f"Aluno {nome_guerra} adicionado!"); load_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao adicionar aluno: {e}")
            
            st.divider()
        
  
            st.subheader("Importar Alunos em Massa (CSV)")
            st.info("Use o modelo para garantir a formatação correta. A importação irá ATUALIZAR alunos existentes (pelo Nº Interno) e ADICIONAR novos.")
            csv_template = create_csv_template()
            st.download_button(label="Baixar Modelo CSV", data=csv_template, file_name="modelo_alunos.csv", mime="text/csv")
            uploaded_file = st.file_uploader("Escolha um ficheiro CSV", type="csv")
            if uploaded_file is not None:
                try:
                    new_alunos_df = pd.read_csv(uploaded_file, sep=';', dtype=str).fillna('')
                    
                    # Verifica apenas se o ficheiro tem colunas, sem exigir nomes específicos
                    if new_alunos_df.empty or len(new_alunos_df.columns) == 0:
                        st.error("Erro: O ficheiro CSV está vazio ou formatado incorretamente.")
                    else:
                        records_to_upsert = new_alunos_df.to_dict(orient='records')
                        with st.spinner("A processar e importar alunos..."):
                            # A chave 'numero_interno' é mantida pois é a regra de negócio da aplicação
                            supabase.table("Alunos").upsert(records_to_upsert, on_conflict='numero_interno').execute()
                        st.success(f"Importação concluída! {len(records_to_upsert)} registos foram processados.")
                        load_data.clear()
                        st.rerun()
                except Exception as e:
                    st.error(f"Ocorreu um erro ao processar o ficheiro: {e}")
                    st.warning("Verifique se o seu ficheiro CSV usa o separador ';' e a codificação UTF-8.")
    st.divider()
    
    ITEMS_PER_PAGE = 30
    total_items = len(filtered_df)
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
    if st.session_state.page_num > total_pages: st.session_state.page_num = total_pages
    start_idx = (st.session_state.page_num - 1) * ITEMS_PER_PAGE
    end_idx = start_idx + ITEMS_PER_PAGE
    paginated_df = filtered_df.iloc[start_idx:end_idx]
    st.subheader(f"Alunos Exibidos ({len(paginated_df)} de {total_items})")

    if not paginated_df.empty:
        for _, aluno in paginated_df.iterrows():
            aluno_id = aluno['id']
            with st.container(border=True):
                col_img, col_info, col_actions = st.columns([1, 4, 1.2])
                
                soma_pontos_observacional = aluno['soma_pontos_acoes']
                conceito_final_aluno = aluno['conceito_final_calculado']

                with col_img:
                    foto_url = aluno.get('url_foto')
                    image_source = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else "https://via.placeholder.com/100?text=Sem+Foto"
                    st.image(image_source, width=100)
                
                with col_info:
                    st.markdown(f"**{aluno.get('nome_guerra', 'N/A')}** (`{aluno.get('numero_interno', 'N/A')}`) | **NIP:** `{aluno.get('nip', 'N/A')}`")
                    st.caption(f"Nome: {aluno.get('nome_completo', 'Não informado')}")
                    st.write(f"Pelotão: {aluno.get('pelotao', 'N/A')} | Especialidade: {aluno.get('especialidade', 'N/A')}")
                    cor_conceito = "green" if conceito_final_aluno >= 8.5 else "orange" if conceito_final_aluno >= 7.0 else "red"
                    
                    if check_permission('pode_ver_conceito_final'):
                        st.markdown(f"**Conceito Final:** <span style='color:{cor_conceito}; font-size: 1.2em; font-weight: bold;'>{conceito_final_aluno:.2f}</span> | **Pontuação Geral:** `{soma_pontos_observacional:+.2f} pts`", unsafe_allow_html=True)
                    else:
                        st.markdown(f"**Pontuação Geral:** `{soma_pontos_observacional:+.2f} pts`", unsafe_allow_html=True)

                with col_actions:
                    if st.button("➕ Ação", key=f"acao_{aluno_id}", use_container_width=True):
                        registrar_acao_dialog(aluno_id, aluno.get('nome_guerra', 'N/A'), supabase)
                    
                    if st.button("📜 Histórico", key=f"hist_{aluno_id}", use_container_width=True):
                        historico_dialog(aluno, acoes_df, tipos_acao_df, config_df)

                    if st.button("ℹ️ Informações", key=f"info_{aluno_id}", use_container_width=True):
                        informacoes_dialog(aluno, supabase)
    
    st.divider()
    if total_pages > 1:
        col_prev, col_page, col_next = st.columns([2, 1, 2])
        with col_prev:
            if st.button("⬅️ Anterior", use_container_width=True, disabled=(st.session_state.page_num <= 1)):
                st.session_state.page_num -= 1; st.rerun()
        with col_page:
            st.write(f"Página **{st.session_state.page_num} de {total_pages}**")
        with col_next:
            if st.button("Próxima ➡️", use_container_width=True, disabled=(st.session_state.page_num >= total_pages)):
                st.session_state.page_num += 1; st.rerun()
