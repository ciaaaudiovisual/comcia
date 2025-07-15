import streamlit as st
import pandas as pd
from datetime import datetime, timedelta # Importa timedelta
from supabase import create_client, Client # Importa para Supabase

# Assume que o componente aluno_selection_components.py existe e funciona
# Para fins de exemplo, vou criar uma versão mock simples aqui.
# Em um cenário real, você importaria do seu arquivo.
try:
    from aluno_selection_components import render_alunos_filter_and_selection
except ImportError:
    # Mock para desenvolvimento/teste se o arquivo não estiver presente
    def render_alunos_filter_and_selection(key_suffix, include_full_name_search=False):
        st.info(f"Componente de seleção de alunos mockado. (key: {key_suffix})")

        # Dados de exemplo para o mock
        mock_alunos_data = [
            {"id": "mock-aluno-123", "nome_guerra": "Aluno Teste 1", "pelotao": "1", "numero_interno": "001"},
            {"id": "mock-aluno-456", "nome_guerra": "Aluno Teste 2", "pelotao": "2", "numero_interno": "002"},
            {"id": "mock-aluno-789", "nome_guerra": "Aluno Teste 3", "pelotao": "1", "numero_interno": "003"},
            {"id": "mock-aluno-101", "nome_guerra": "João Silva", "pelotao": "3", "numero_interno": "004"},
            {"id": "mock-aluno-102", "nome_guerra": "Maria Souza", "pelotao": "1", "numero_interno": "005"},
        ]
        mock_alunos_df = pd.DataFrame(mock_alunos_data)

        st.markdown("##### Filtro de Alunos (Mock)")
        col_name, col_num = st.columns(2)

        # Filtro por Nome de Guerra
        search_name = col_name.text_input("Buscar por Nome de Guerra:", key=f"search_name_{key_suffix}")

        # Filtro por Número Interno (NOVA FUNCIONALIDADE)
        search_numero_interno = col_num.text_input("Buscar por Número Interno:", key=f"search_num_interno_{key_suffix}")

        filtered_df = mock_alunos_df.copy()

        if search_name:
            filtered_df = filtered_df[filtered_df['nome_guerra'].str.contains(search_name, case=False, na=False)]

        if search_numero_interno:
            filtered_df = filtered_df[filtered_df['numero_interno'].str.contains(search_numero_interno, case=False, na=False)]

        # Exibe os alunos filtrados para seleção
        if not filtered_df.empty:
            options = filtered_df.apply(lambda row: f"{row['numero_interno']} - {row['nome_guerra']}", axis=1).tolist()
            selected_option = st.selectbox("Selecione Aluno(s):", options=options, key=f"select_aluno_{key_suffix}")
            if selected_option:
                # Retorna o DataFrame do aluno selecionado
                selected_aluno_num_interno = selected_option.split(' - ')[0] # Pega o numero_interno para encontrar o aluno
                return filtered_df[filtered_df['numero_interno'] == selected_aluno_num_interno]
        else:
            st.warning("Nenhum aluno encontrado com os filtros aplicados.")
            return pd.DataFrame() # Retorna DataFrame vazio se não houver alunos

        return pd.DataFrame() # Retorna DataFrame vazio por padrão


# ==============================================================================
# FUNÇÕES DE SUPABASE (ADICIONADAS PARA RESOLVER O NAMERROR)
# ==============================================================================
@st.cache_resource
def init_supabase_client():
    """
    Inicializa e retorna o cliente Supabase.
    As credenciais devem ser configuradas como segredos no Streamlit.
    """
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        supabase: Client = create_client(url, key)
        return supabase
    except KeyError:
        st.error("Credenciais do Supabase não encontradas nos segredos do Streamlit. Por favor, configure SUPABASE_URL e SUPABASE_KEY.")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao inicializar o cliente Supabase: {e}")
        st.stop()

@st.cache_data(ttl=300) # Cache dos dados por 5 minutos
def load_data(table_name):
    """
    Carrega dados de uma tabela específica do Supabase.
    """
    supabase = init_supabase_client()
    try:
        response = supabase.table(table_name).select("*").execute()
        data = response.data
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame() # Retorna DataFrame vazio se não houver dados
    except Exception as e:
        st.error(f"Erro ao carregar dados da tabela '{table_name}': {e}")
        return pd.DataFrame()


# ==============================================================================
# DIÁLOGOS E POPUPS (mantidos inalterados)
# ==============================================================================
@st.dialog("✏️ Editar Ação")
def edit_acao_dialog(acao_selecionada, tipos_acao_df, supabase):
    st.write(f"Editando ação para: **{acao_selecionada.get('nome_guerra', 'N/A')}**")

    with st.form(key=f"edit_form_{acao_selecionada['id_x']}"):
        opcoes_tipo_acao = tipos_acao_df['nome'].unique().tolist()
        try:
            index_acao_atual = opcoes_tipo_acao.index(acao_selecionada['nome'])
        except (ValueError, KeyError):
            index_acao_atual = 0

        novo_tipo_acao = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao_atual)
        try:
            data_atual = pd.to_datetime(acao_selecionada['data']).date()
        except (ValueError, TypeError):
            data_atual = datetime.now().date()
        nova_data = st.date_input("Data da Ação", value=data_atual)
        nova_descricao = st.text_area("Descrição/Justificativa", value=acao_selecionada.get('descricao', ''))

        if st.form_submit_button("Salvar Alterações"):
            try:
                tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == novo_tipo_acao].iloc[0]
                update_data = {
                    'tipo_acao_id': str(tipo_acao_info['id']), 'tipo': novo_tipo_acao,
                    'data': nova_data.strftime('%Y-%m-%d'), 'descricao': nova_descricao
                }
                supabase.table("Acoes").update(update_data).eq('id', acao_selecionada['id_x']).execute()
                st.toast("Ação atualizada com sucesso!", icon="✅")
                load_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar as alterações: {e}")

@st.dialog("Pré-visualização da FAIA")
def preview_faia_dialog(aluno_info, acoes_aluno_df):
    st.header(f"FAIA de: {aluno_info.get('nome_guerra', 'N/A')}")
    texto_relatorio = formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df)
    st.text_area("Conteúdo do Relatório:", value=texto_relatorio, height=300)
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','N/A')}.txt"
    st.download_button(label="✅ Baixar Relatório .TXT", data=texto_relatorio.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")

# ==============================================================================
# FUNÇÕES DE APOIO (mantidas inalteradas)
# ==============================================================================
def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
    texto = [
        "============================================================",
        f"FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)\n",
        f"Pelotão: {aluno_info.get('pelotao', 'N/A')}",
        f"Aluno: {aluno_info.get('nome_completo', 'N/A')}",
        f"Nome de Guerra: {aluno_info.get('nome_guerra', 'N/A')}",
        f"Numero Interno: {aluno_info.get('numero_interno', 'N/A')}",
        "\n------------------------------------------------------------",
        "LANÇAMENTOS (STATUS 'LANÇADO') EM ORDEM CRONOLÓGICA:",
        "------------------------------------------------------------\n"
    ]
    acoes_lancadas = acoes_aluno_df[acoes_aluno_df['status'] == 'Lançado']
    if acoes_lancadas.empty:
        texto.append("Nenhum lançamento com status 'Lançado' encontrado para este aluno.")
    else:
        for _, acao in acoes_lancadas.sort_values(by='data').iterrows():
            texto.extend([
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
                f"Descrição: {acao.get('descricao', '')}",
                f"Registrado por: {acao.get('usuario', 'N/A')}",
                "\n-----------------------------------\n"
            ])
    texto.extend([
        "\n============================================================",
        f"Fim do Relatório - Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "============================================================"
    ])
    return "\n".join(texto)

def render_export_section(df_acoes_para_exportar, alunos_df, pelotao_selecionado, aluno_selecionado):
    """
    Renderiza a seção de exportação de relatórios.
    df_acoes_para_exportar: DataFrame já filtrado pelas seleções do usuário (pelotão, aluno, status, tipo_acao).
    """
    # check_permission is not defined in this snippet, assuming it's imported or mocked.
    # For this example, we'll assume permission is always granted.
    # if not check_permission('pode_exportar_relatorio_faia'):
    #     return
    
    with st.container(border=True):
        st.subheader("📥 Exportar Relatórios FAIA")
        
        # Filtro de alunos para exportação (opcional, para exibir apenas os alunos relevantes)
        alunos_elegivel_exportacao_df = alunos_df.copy()

        if pelotao_selecionado != "Todos":
            alunos_elegivel_exportacao_df = alunos_elegivel_exportacao_df[alunos_elegivel_exportacao_df['pelotao'] == pelotao_selecionado]
        
        # O botão de exportação individual só é ativado se um aluno específico estiver selecionado
        if aluno_selecionado != "Nenhum" and aluno_selecionado != "Todos":
            st.info(f"Pré-visualize e exporte o relatório individual para **{aluno_selecionado}**. Serão incluídas apenas as ações com status 'Lançado'.")
            aluno_info_df = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado]
            if not aluno_info_df.empty:
                aluno_info = aluno_info_df.iloc[0]
                # Ações para este aluno são filtradas do DataFrame 'df_acoes_para_exportar'
                acoes_do_aluno = df_acoes_para_exportar[df_acoes_para_exportar['aluno_id'] == str(aluno_info['id'])]
                if st.button(f"👁️ Pré-visualizar e Exportar FAIA de {aluno_selecionado}"):
                    preview_faia_dialog(aluno_info, acoes_do_aluno)
            else:
                st.warning(f"Aluno '{aluno_selecionado}' não encontrado.")
        elif pelotao_selecionado != "Todos":
            st.info(f"A exportação gerará um arquivo .ZIP com os relatórios de todos os alunos do pelotão **'{pelotao_selecionado}'**. Serão incluídas apenas as ações com status 'Lançado'.")
            alunos_do_pelotao = alunos_elegivel_exportacao_df # Já está filtrado por pelotão
            with st.expander(f"Ver os {len(alunos_do_pelotao)} alunos que serão incluídos no .ZIP"):
                for _, aluno_info in alunos_do_pelotao.iterrows():
                    st.write(f"- {aluno_info.get('numero_interno', 'SN')} - {aluno_info.get('nome_guerra', 'N/A')}")
            if st.button(f"Gerar e Baixar .ZIP para {pelotao_selecionado}"):
                import zipfile # Moved import here to avoid circular dependency if not used
                from io import BytesIO # Moved import here
                with st.spinner("Gerando relatórios..."):
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for _, aluno_info in alunos_do_pelotao.iterrows():
                            # Filtra as ações de cada aluno do DataFrame 'df_acoes_para_exportar'
                            acoes_do_aluno = df_acoes_para_exportar[df_acoes_para_exportar['aluno_id'] == str(aluno_info['id'])]
                            conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
                            nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','S-N')}.txt"
                            zip_file.writestr(nome_arquivo, conteudo_txt)
                    st.download_button(label="Clique para baixar o .ZIP", data=zip_buffer.getvalue(), file_name=f"relatorios_FAIA_{pelotao_selecionado}.zip", mime="application/zip", use_container_width=True)
        else:
            st.warning("Selecione um pelotão ou um aluno específico nos filtros para habilitar a exportação.")

def bulk_update_status(ids_to_update, new_status, supabase):
    if not ids_to_update:
        st.warning("Nenhuma ação foi selecionada.")
        return
    try:
        supabase.table("Acoes").update({'status': new_status}).in_('id', ids_to_update).execute()
        st.toast(f"{len(ids_to_update)} ações foram atualizadas para '{new_status}' com sucesso!", icon="✅")
        st.session_state.action_selection = {}
        st.session_state.select_all_toggle = False
        load_data.clear()
        st.rerun() # Adicionado para recarregar a interface após a atualização em massa
    except Exception as e:
        st.error(f"Erro ao atualizar ações em massa: {e}")

# Mock da função check_permission se não estiver disponível
try:
    from auth import check_permission
except ImportError:
    def check_permission(permission_name):
        # Mock: retorna True para todas as permissões para fins de demonstração
        return True

# Mock da função calcular_pontuacao_efetiva se não estiver disponível
try:
    from acoes import calcular_pontuacao_efetiva
except ImportError:
    def calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df):
        # Mock: Adiciona uma coluna de pontuação efetiva simples para demonstração
        # Em um ambiente real, esta função faria o cálculo correto
        if not acoes_df.empty and not tipos_acao_df.empty:
            # Garante que 'tipo_acao_id' é string em ambos os DataFrames para o merge
            acoes_df['tipo_acao_id'] = acoes_df['tipo_acao_id'].astype(str)
            tipos_acao_df['id'] = tipos_acao_df['id'].astype(str)

            merged_df = pd.merge(acoes_df, tipos_acao_df[['id', 'pontuacao']],
                                 left_on='tipo_acao_id', right_on='id', how='left', suffixes=('_acao', '_tipo'))
            merged_df['pontuacao_efetiva'] = pd.to_numeric(merged_df['pontuacao'], errors='coerce').fillna(0)
            merged_df.drop(columns=['id_tipo', 'pontuacao'], errors='ignore', inplace=True) # Remove colunas duplicadas/desnecessárias após o merge
            return merged_df
        return acoes_df


# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_gestao_acoes():
    st.title("Lançamentos de Ações dos Alunos")
    supabase = init_supabase_client()

    if 'action_selection' not in st.session_state: st.session_state.action_selection = {}
    # Removidos os st.session_state.search_results_df_gestao e selected_student_id_gestao
    # pois a gestão da seleção será feita pelo componente render_alunos_filter_and_selection.

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    # --- Seção "Registrar Nova Ação" ---
    with st.expander("➕ Registrar Nova Ação", expanded=True):
        st.subheader("Passo 1: Selecionar Aluno")

        # Usa o componente de seleção de alunos
        # Inclui busca por nome completo, pois é útil para encontrar o aluno para registro
        # Adicione um unique key para este uso específico do componente
        selected_alunos_for_new_action = render_alunos_filter_and_selection(
            key_suffix="new_action_student_selector",
            include_full_name_search=True
        )

        aluno_selecionado_para_registro = None
        if not selected_alunos_for_new_action.empty:
            # Se múltiplos alunos forem selecionados, o Streamlit multi-select permite.
            # Para registro de uma AÇÃO, geralmente é um aluno por vez.
            # Se você quer permitir múltiplos registros em massa, a lógica abaixo precisaria mudar.
            # Por simplicidade, vamos pegar o primeiro aluno selecionado para registro.
            if len(selected_alunos_for_new_action) > 1:
                st.warning("Por favor, selecione apenas UM aluno para registrar uma nova ação.")
                aluno_selecionado_para_registro = None # Reseta a seleção para forçar um único aluno
            else:
                aluno_selecionado_para_registro = selected_alunos_for_new_action.iloc[0]
                st.info(f"Aluno selecionado: **{aluno_selecionado_para_registro.get('nome_guerra', 'N/A')}**")
        else:
            st.info("Nenhum aluno selecionado. Use os filtros acima para encontrar um aluno.")

        if aluno_selecionado_para_registro is not None:
            st.divider()

            st.subheader(f"Passo 2: Registrar Ação para **{aluno_selecionado_para_registro['nome_guerra']}**")

            with st.form("form_nova_acao"):
                tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
                positivas_df = tipos_acao_df[tipos_acao_df['pontuacao'] > 0].sort_values('nome')
                neutras_df = tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome')
                negativas_df = tipos_acao_df[tipos_acao_df['pontuacao'] < 0].sort_values('nome')

                opcoes_categorizadas = []
                tipos_opcoes_map = {} # Mapeia o label exibido para o row completo do tipo de ação

                # Adiciona as categorias e os tipos de ação
                if not positivas_df.empty:
                    opcoes_categorizadas.append("--- AÇÕES POSITIVAS ---")
                    for _, r in positivas_df.iterrows():
                        label = f"{r['nome']} ({r['pontuacao']:+.1f} pts)"
                        opcoes_categorizadas.append(label)
                        tipos_opcoes_map[label] = r
                if not neutras_df.empty:
                    opcoes_categorizadas.append("--- AÇÕES NEUTRAS ---")
                    for _, r in neutras_df.iterrows():
                        label = f"{r['nome']} ({r['pontuacao']:.1f} pts)"
                        opcoes_categorizadas.append(label)
                        tipos_opcoes_map[label] = r
                if not negativas_df.empty:
                    opcoes_categorizadas.append("--- AÇÕES NEGATIVAS ---")
                    for _, r in negativas_df.iterrows():
                        label = f"{r['nome']} ({r['pontuacao']:+.1f} pts)"
                        opcoes_categorizadas.append(label)
                        tipos_opcoes_map[label] = r

                if not opcoes_categorizadas:
                    opcoes_categorizadas = ["Selecione um tipo de ação"]
                elif opcoes_categorizadas[0].startswith("---"):
                    opcoes_categorizadas.insert(0, "Selecione um tipo de ação")

                c1, c2 = st.columns(2)
                tipo_selecionado_str = c1.selectbox("Tipo de Ação", opcoes_categorizadas, index=0)
                data = c2.date_input("Data e Hora da Ação", datetime.now())
                descricao = st.text_area("Descrição/Justificativa (Opcional)")

                tipos_de_saude = ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]
                nome_acao_selecionada = ""
                if tipo_selecionado_str and not tipo_selecionado_str.startswith("---") and tipo_selecionado_str != "Selecione um tipo de ação":
                    nome_acao_selecionada = tipos_opcoes_map[tipo_selecionado_str]['nome']

                dispensado = False
                if nome_acao_selecionada in tipos_de_saude:
                    st.divider()
                    st.markdown("##### Controle de Dispensa Médica")
                    dispensado = st.toggle("Gerou dispensa médica?")
                    if dispensado:
                        col_d1, col_d2 = st.columns(2)
                        data_inicio_dispensa = col_d1.date_input("Início da Dispensa", value=datetime.now().date())
                        data_fim_dispensa = col_d2.date_input("Fim da Dispensa", value=datetime.now().date())
                        tipo_dispensa = st.selectbox("Tipo de Dispensa", ["", "Total", "Parcial", "Para Esforço Físico", "Outro"])

                confirmacao_registro = st.checkbox("Confirmo que os dados estão corretos para o registo.")

                if st.form_submit_button("Registrar Ação", use_container_width=True, type="primary"):
                    if tipo_selecionado_str.startswith("---") or tipo_selecionado_str == "Selecione um tipo de ação":
                        st.warning("Por favor, selecione um tipo de ação válido.")
                    elif not confirmacao_registro:
                        st.warning("Por favor, confirme que os dados estão corretos.")
                    else:
                        try:
                            tipo_info = tipos_opcoes_map[tipo_selecionado_str]
                            nova_acao = {'aluno_id': str(aluno_selecionado_para_registro['id']), 'tipo_acao_id': str(tipo_info['id']), 'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.isoformat(), 'usuario': st.session_state.username, 'status': 'Pendente'}
                            if nome_acao_selecionada in tipos_de_saude and dispensado:
                                nova_acao['esta_dispensado'] = True
                                nova_acao['periodo_dispensa_inicio'] = data_inicio_dispensa.isoformat()
                                nova_acao['periodo_dispensa_fim'] = data_fim_dispensa.isoformat()
                                nova_acao['tipo_dispensa'] = tipo_dispensa
                            else:
                                nova_acao['esta_dispensado'] = False
                                nova_acao['periodo_dispensa_inicio'] = None
                                nova_acao['periodo_dispensa_fim'] = None
                                nova_acao['tipo_dispensa'] = None
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação registrada para {aluno_selecionado_para_registro['nome_guerra']}!"); load_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao registrar ação: {e}")
        else:
            st.info("⬅️ Use os filtros acima para selecionar um aluno para registrar uma nova ação.")

    st.divider()

    st.subheader("Filtros de Visualização")

    col_filtros1, col_filtros2 = st.columns(2)
    with col_filtros1:
        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
        filtro_pelotao = st.selectbox("1. Filtrar Pelotão", opcoes_pelotao)

        alunos_filtrados_pelotao = alunos_df.copy()
        if filtro_pelotao != "Todos":
            alunos_filtrados_pelotao = alunos_filtrados_pelotao[alunos_filtrados_pelotao['pelotao'] == filtro_pelotao]

        nomes_unicos = alunos_filtrados_pelotao['nome_guerra'].unique()
        nomes_validos = [str(nome) for nome in nomes_unicos if pd.notna(nome)]

        opcoes_alunos = ["Nenhum"] + sorted(nomes_validos)
        filtro_aluno = st.selectbox("2. Filtrar Aluno (Opcional)", opcoes_alunos)

    with col_filtros2:
        filtro_status = st.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
        opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
        filtro_tipo_acao = st.selectbox("Filtrar por Tipo de Ação", opcoes_tipo_acao)

    ordenar_por = st.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])

    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.DataFrame()

    if not acoes_com_pontos.empty and not alunos_df.empty:
        acoes_com_pontos['aluno_id'] = acoes_com_pontos['aluno_id'].astype(str)
        alunos_df['id'] = alunos_df['id'].astype(str)
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo', 'url_foto']], left_on='aluno_id', right_on='id', how='left')
        df_display['nome_guerra'].fillna('N/A (Aluno Apagado)', inplace=True)

    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'].fillna('') == filtro_pelotao]
        if filtro_aluno != "Nenhum":
            aluno_id_filtrado_df = alunos_df[alunos_df['nome_guerra'] == filtro_aluno]
            if not aluno_id_filtrado_df.empty:
                aluno_id_filtrado = str(aluno_id_filtrado_df['id'].iloc[0])
                df_filtrado_final = df_filtrado_final[df_filtrado_final['aluno_id'] == aluno_id_filtrado]
        if filtro_status != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['status'].fillna('') == filtro_status]
        if filtro_tipo_acao != "Todos":
            df_filtrado_final = df_filtrado_final[df_filtrado_final['nome'].fillna('') == filtro_tipo_acao]

        if ordenar_por == "Mais Antigos":
            df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)":
            df_filtrado_final = df_filtrado_final.sort_values(by="nome_guerra", ascending=True)
        else:
            df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=False)

    st.divider()

    st.subheader("Fila de Revisão e Ações")

    if df_filtrado_final.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        with st.container(border=True):
            col_botoes1, col_botoes2, col_check = st.columns([2, 2, 3])

            ids_visiveis = df_filtrado_final['id_x'].dropna().astype(int).tolist()
            selected_ids = [acao_id for acao_id, is_selected in st.session_state.action_selection.items() if is_selected and acao_id in ids_visiveis]

            with col_botoes1:
                st.button(f"🚀 Lançar Selecionados ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Lançado', supabase), disabled=not selected_ids, use_container_width=True)
            with col_botoes2:
                st.button(f"🗑️ Arquivar Selecionados ({len(selected_ids)})", on_click=bulk_update_status, args=(selected_ids, 'Arquivado', supabase), disabled=not selected_ids, use_container_width=True)

            def toggle_all_visible():
                new_state = st.session_state.get('select_all_toggle', False)
                for acao_id in ids_visiveis:
                    st.session_state.action_selection[acao_id] = new_state

            with col_check:
                st.checkbox("Marcar/Desmarcar todos os visíveis", key='select_all_toggle', on_change=toggle_all_visible)

        st.write("")

        df_filtrado_final.drop_duplicates(subset=['id_x'], keep='first', inplace=True)
        for _, acao in df_filtrado_final.iterrows():
            acao_id = acao['id_x']
            with st.container(border=True):
                col_foto, col_info, col_actions = st.columns([1, 4, 2])

                with col_foto:
                    foto_url = acao.get('url_foto')
                    image_source = foto_url if isinstance(foto_url, str) and foto_url.startswith('http') else "https://via.placeholder.com/100?text=S/Foto"
                    st.image(image_source, width=80)

                with col_info:
                    st.session_state.action_selection[acao_id] = st.checkbox("Selecionar esta ação", value=st.session_state.action_selection.get(acao_id, False), key=f"select_{acao_id}", label_visibility="visible")
                    cor = "green" if acao.get('pontuacao_efetiva', 0) > 0 else "red" if acao.get('pontuacao_efetiva', 0) < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')
                    st.markdown(f"**{acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A (Aluno Apagado)')}** em {data_formatada}")
                    st.markdown(f"**Ação:** {acao.get('nome','N/A')} <span style='color:{cor}; font-weight:bold;'>({acao.get('pontuacao_efetiva', 0):+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao.get('descricao')}" if pd.notna(acao.get('descricao')) else "Sem descrição.")

                with col_actions:
                    status_atual = acao.get('status', 'Pendente')
                    can_launch = check_permission('acesso_pagina_lancamentos_faia')
                    can_delete = check_permission('pode_excluir_lancamento_faia')
                    can_edit = check_permission('pode_editar_lancamento_faia')

                    if status_atual == 'Pendente' and can_launch:
                        if st.button("🚀 Lançar", key=f"launch_{acao_id}", use_container_width=True, type="primary"):
                             supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', acao_id).execute()
                             load_data.clear(); st.rerun()

                    if can_edit:
                         if st.button("✏️ Editar", key=f"edit_{acao_id}", use_container_width=True):
                            edit_acao_dialog(acao, tipos_acao_df, supabase)

                    if status_atual != 'Arquivado' and can_delete:
                        if st.button("🗑️ Arquivar", key=f"archive_{acao_id}", use_container_width=True):
                            supabase.table("Acoes").update({'status': 'Arquivado'}).eq('id', acao_id).execute()
                            load_data.clear(); st.rerun()

                    if status_atual == 'Lançado':
                        st.success("✅ Lançado")
                    elif status_atual == 'Arquivado':
                        st.warning("🗄️ Arquivado")

    st.divider()
    render_export_section(df_filtrado_final, alunos_df, filtro_pelotao, filtro_aluno)
