import streamlit as st
import pandas as pd
from datetime import datetime, timedelta # Importa timedelta
# Adiciona a importação de load_data e init_supabase_client do arquivo database
from database import load_data, init_supabase_client 
from aluno_selection_components import render_alunos_filter_and_selection # Importa o componente de seleção de alunos

# ==============================================================================
# FUNÇÃO AUXILIAR PARA FORMATAÇÃO SEGURA DE DATAS
# ==============================================================================
def safe_strftime(date_obj, fmt='%d/%m/%y'):
    """
    Formata um objeto de data/hora de forma segura. Retorna 'N/A' se for nulo,
    inválido ou não puder ser formatado.
    """
    # Debugging print para inspecionar o objeto recebido
    # print(f"DEBUG safe_strftime: Received date_obj type: {type(date_obj)}, value: {date_obj}")

    if pd.isna(date_obj): # Verifica se é NaN (incluindo NaT do Pandas)
        return "N/A"

    # Acesso defensivo a pd.Timestamp para evitar AttributeError se não estiver disponível
    pd_timestamp_type = getattr(pd, 'Timestamp', None)

    # Constrói a tupla de tipos válidos dinamicamente
    valid_date_types = (datetime.date, datetime.datetime)
    if pd_timestamp_type: # Adiciona pd.Timestamp apenas se estiver disponível
        valid_date_types += (pd_timestamp_type,)

    if isinstance(date_obj, valid_date_types):
        try:
            # Converte para Timestamp do pandas para formatação consistente
            return pd.to_datetime(date_obj).strftime(fmt) 
        except Exception as e: # Captura qualquer erro de formatação ou strftime
            # print(f"DEBUG safe_strftime: Error during formatting: {e}")
            return "N/A"
    else:
        # Debugging print para objetos que não são tipos de data reconhecidos
        # print(f"DEBUG safe_strftime: Object is not a recognized date type. Type: {type(date_obj)}")
        return "N/A" # Retorna N/A para outros tipos de objeto

# ==============================================================================
# DIÁLOGO DE EDIÇÃO
# ==============================================================================
@st.dialog("Editar Dados de Saúde")
def edit_saude_dialog(acao_id, dados_acao_atual, supabase):
    """
    Abre um formulário para editar os detalhes de saúde e o aluno de uma ação específica.
    """
    alunos_df = load_data("Alunos")
    
    st.write(f"Editando evento para: **{dados_acao_atual.get('nome_guerra', 'N/A')}**")
    st.caption(f"Ação: {dados_acao_atual.get('tipo', 'N/A')} em {pd.to_datetime(dados_acao_atual.get('data')).strftime('%d/%m/%Y')}")

    with st.form("edit_saude_form"):
        st.divider()
        
        st.markdown("##### Corrigir Aluno (se necessário)")
        opcoes_alunos = pd.Series(alunos_df.id.values, index=alunos_df.nome_guerra).to_dict()
        nomes_alunos_lista = list(opcoes_alunos.keys())
        aluno_atual_id = dados_acao_atual.get('aluno_id')
        aluno_atual_nome = ""
        if pd.notna(aluno_atual_id):
            aluno_info = alunos_df[alunos_df['id'] == aluno_atual_id]
            if not aluno_info.empty:
                aluno_atual_nome = aluno_info.iloc[0]['nome_guerra']
        indice_aluno_atual = nomes_alunos_lista.index(aluno_atual_nome) if aluno_atual_nome in nomes_alunos_lista else 0
        aluno_selecionado_nome = st.selectbox("Selecione o aluno correto:", options=nomes_alunos_lista, index=indice_aluno_atual)
        
        st.divider()
        st.markdown("##### Controle de Dispensa Médica")
        
        esta_dispensado_atual = dados_acao_atual.get('esta_dispensado', False)
        if pd.isna(esta_dispensado_atual):
            esta_dispensado_atual = False
            
        dispensado = st.toggle("Aluno está Dispensado?", value=bool(esta_dispensado_atual))
        
        data_inicio_dispensa = None
        data_fim_dispensa = None
        tipo_dispensa = ""

        if dispensado:
            start_date_val = dados_acao_atual.get('periodo_dispensa_inicio')
            end_date_val = dados_acao_atual.get('periodo_dispensa_fim')
            data_inicio_atual = pd.to_datetime(start_date_val).date() if pd.notna(start_date_val) else datetime.now().date()
            data_fim_atual = pd.to_datetime(end_date_val).date() if pd.notna(end_date_val) else datetime.now().date()

            col_d1, col_d2 = st.columns(2)
            data_inicio_dispensa = col_d1.date_input("Início da Dispensa", value=data_inicio_atual)
            data_fim_dispensa = col_d2.date_input("Fim da Dispensa", value=data_fim_atual)
            
            tipos_dispensa_opcoes = ["", "Total", "Parcial", "Para Esforço Físico", "Outro"]
            tipo_dispensa_atual = dados_acao_atual.get('tipo_dispensa', '')
            if pd.isna(tipo_dispensa_atual):
                tipo_dispensa_atual = ""
            if tipo_dispensa_atual not in tipos_dispensa_opcoes:
                tipos_dispensa_opcoes.append(tipo_dispensa_atual)
            tipo_dispensa = st.selectbox("Tipo de Dispensa", options=tipos_dispensa_opcoes, index=tipos_dispensa_opcoes.index(tipo_dispensa_atual))

        st.divider()
        nova_descricao = st.text_area("Comentários/Observações (Opcional)", value=dados_acao_atual.get('descricao', ''))

        if st.form_submit_button("Salvar Alterações"):
            novo_aluno_id = opcoes_alunos[aluno_selecionado_nome]
            dados_para_atualizar = {
                'aluno_id': novo_aluno_id,
                'esta_dispensado': dispensado,
                'periodo_dispensa_inicio': data_inicio_dispensa.isoformat() if dispensado and data_inicio_dispensa else None,
                'periodo_dispensa_fim': data_fim_dispensa.isoformat() if dispensado and data_fim_dispensa else None,
                'tipo_dispensa': tipo_dispensa if dispensado else None,
                'descricao': nova_descricao
            }
            
            try:
                supabase.table("Acoes").update(dados_para_atualizar).eq("id", acao_id).execute()
                st.success("Dados de saúde atualizados com sucesso!")
                load_data.clear() # Limpa o cache para recarregar dados atualizados
            except Exception as e:
                st.error(f"Erro ao salvar as alterações: {e}")

# ==============================================================================
# PÁGINA PRINCIPAL DO MÓDULO DE SAÚDE
# ==============================================================================
def show_saude():
    st.title("⚕️ Módulo de Saúde")
    st.markdown("Controle centralizado de eventos de saúde e dispensas médicas.")
    
    supabase = init_supabase_client()
    
    try:
        acoes_df = load_data("Acoes")
        alunos_df = load_data("Alunos")
        tipos_acao_df = load_data("Tipos_Acao")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # --- Seção "Adicionar Novo Registro de Saúde" ---
    with st.expander("➕ Adicionar Novo Registro de Saúde", expanded=False):
        st.subheader("Registrar Nova Ação de Saúde")
        
        # 1. Seleção do Aluno (usando o componente padronizado)
        st.markdown("##### Selecione o Aluno")
        selected_alunos_for_new_record = render_alunos_filter_and_selection(
            key_suffix="new_health_record_student_selector", 
            include_full_name_search=True
        )

        aluno_selecionado_para_registro = None
        if not selected_alunos_for_new_record.empty:
            if len(selected_alunos_for_new_record) > 1:
                st.warning("Por favor, selecione apenas UM aluno para registrar um novo evento de saúde.")
            else:
                aluno_selecionado_para_registro = selected_alunos_for_new_record.iloc[0]
                st.info(f"Aluno selecionado: **{aluno_selecionado_para_registro.get('nome_guerra', 'N/A')}**")
        else:
            st.info("Use os filtros acima para selecionar um aluno para registrar um novo evento de saúde.")

        # 2. Formulário de Registro (aparece apenas se um aluno for selecionado)
        if aluno_selecionado_para_registro is not None:
            st.divider()
            st.markdown(f"##### Detalhes do Registro para **{aluno_selecionado_para_registro['nome_guerra']}**")
            
            with st.form("new_health_record_form"):
                # Tipos de Ação de Saúde (filtrados para relevância)
                # Definindo tipos_saude_padrao aqui para ser acessível
                tipos_saude_padrao = ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]
                tipos_saude_disponiveis = [t for t in tipos_saude_padrao if t in tipos_acao_df['nome'].unique().tolist()]
                if not tipos_saude_disponiveis:
                    st.warning("Nenhum tipo de ação de saúde padrão encontrado. Cadastre-os em 'Configurações > Tipos de Ação'.")
                    st.stop() # Para a execução do formulário se não houver tipos

                tipo_acao_saude_selecionado = st.selectbox(
                    "Tipo de Evento de Saúde:",
                    options=tipos_saude_disponiveis,
                    key="new_health_record_type"
                )
                
                col_date_new, col_empty_new = st.columns([1, 1])
                data_registro_new = col_date_new.date_input("Data do Registro:", value=datetime.now().date())
                
                descricao_new = st.text_area("Observações/Comentários:", height=100)

                st.divider()
                st.markdown("##### Controle de Dispensa Médica")
                dispensado_new = st.toggle("Aluno está Dispensado?", key="new_health_record_dispensed_toggle")
                
                data_inicio_dispensa_new = None
                data_fim_dispensa_new = None
                tipo_dispensa_new = ""

                if dispensado_new:
                    col_d1_new, col_d2_new = st.columns(2)
                    data_inicio_dispensa_new = col_d1_new.date_input("Início da Dispensa", value=datetime.now().date(), key="new_health_record_disp_start")
                    data_fim_dispensa_new = col_d2_new.date_input("Fim da Dispensa", value=datetime.now().date() + timedelta(days=7), key="new_health_record_disp_end")
                    
                    tipos_dispensa_opcoes = ["", "Total", "Parcial", "Para Esforço Físico", "Outro"]
                    tipo_dispensa_new = st.selectbox("Tipo de Dispensa", options=tipos_dispensa_opcoes, key="new_health_record_disp_type")

                if st.form_submit_button("Registrar Novo Evento", type="primary"):
                    # Encontra o ID do tipo de ação selecionado
                    tipo_info_df = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao_saude_selecionado]
                    if tipo_info_df.empty:
                        st.error("Tipo de evento de saúde selecionado não encontrado na base de dados.")
                        st.stop()
                    tipo_acao_id_new = str(tipo_info_df.iloc[0]['id'])

                    # Dados para inserção
                    new_health_record_data = {
                        'aluno_id': str(aluno_selecionado_para_registro['id']),
                        'tipo_acao_id': tipo_acao_id_new,
                        'tipo': tipo_acao_saude_selecionado,
                        'descricao': descricao_new,
                        'data': data_registro_new.isoformat(),
                        'usuario': st.session_state.username, # Assume que o usuário logado está disponível
                        'status': 'Lançado', # Eventos de saúde podem ser lançados diretamente
                        'esta_dispensado': dispensado_new,
                        'periodo_dispensa_inicio': data_inicio_dispensa_new.isoformat() if dispensado_new and data_inicio_dispensa_new else None,
                        'periodo_dispensa_fim': data_fim_dispensa_new.isoformat() if dispensado_new and data_fim_dispensa_new else None,
                        'tipo_dispensa': tipo_dispensa_new if dispensado_new else None
                    }
                    
                    try:
                        supabase.table("Acoes").insert(new_health_record_data).execute()
                        st.success(f"Registro de saúde para {aluno_selecionado_para_registro['nome_guerra']} adicionado com sucesso!")
                        load_data.clear() # Limpa o cache para recarregar os dados
                        st.rerun() # Recarrega a página para mostrar o novo registro
                    except Exception as e:
                        st.error(f"Erro ao registrar novo evento de saúde: {e}")
        else:
            st.info("Selecione um aluno acima para habilitar o formulário de registro.")

    st.divider()
    # --- Fim da Seção "Adicionar Novo Registro de Saúde" ---


    # --- Filtros de Visualização do Histórico (mantidos e aprimorados) ---
    st.subheader("Filtro de Eventos de Saúde Existentes") # Título mais claro para esta seção de filtros

    # Componente de seleção de alunos para o histórico (agora opcional para mostrar todos)
    selected_alunos_for_history_filter = render_alunos_filter_and_selection(key_suffix="saude_history_filter", include_full_name_search=False)

    # Lógica para exibir todos os alunos se nenhum for selecionado no filtro de histórico
    if selected_alunos_for_history_filter.empty:
        # Se o usuário não selecionou nenhum aluno específico no filtro de histórico,
        # consideramos todos os alunos para a exibição dos últimos lançamentos.
        alunos_para_filtragem_historico = alunos_df.copy() 
        st.info("Nenhum aluno selecionado para o histórico. Exibindo eventos de **todos** os alunos.")
    else:
        # Se o usuário selecionou alunos, filtramos por eles.
        alunos_para_filtragem_historico = selected_alunos_for_history_filter
 

    col_filter_saude1, col_filter_saude2 = st.columns(2)
    with col_filter_saude1:
        # Filtro por Dispensa Médica (mantido conforme original)
        dispensa_medica_options = ["Todos", "Com Dispensa Ativa", "Com Dispensa Vencida", "Sem Dispensa"]
        selected_dispensa = st.selectbox(
            "Status de Dispensa Médica:",
            options=dispensa_medica_options,
            key="dispensa_medica_filter",
            index=0 # Padrão para 'Todos'
        )
    
    with col_filter_saude2:
        # Filtro por Tipos de Ação (saúde) (mantido conforme original)
        todos_tipos_nomes = sorted(tipos_acao_df['nome'].unique().tolist())
        
        # Tipos padrão de saúde para seleção inicial no multiselect
        # Definindo tipos_saude_padrao aqui também para ser acessível
        tipos_saude_padrao = ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]
        
        selected_types = st.multiselect(
            "Filtrar por Tipo de Evento:",
            options=todos_tipos_nomes,
            default=[t for t in tipos_saude_padrao if t in todos_tipos_nomes], # Seleciona tipos de saúde relevantes por padrão
            key="saude_event_types_filter"
        )
    
    if not selected_types:
        st.warning("Selecione pelo menos um tipo de evento para continuar.")
        return

    # Filtro por Período (Data Range) (reintroduzido para os "últimos registros")
    st.markdown("##### Filtrar por Período de Registro:")
    today = datetime.now().date()
    default_start_date = today - timedelta(days=90) # Últimos 90 dias como padrão

    col_date1, col_date2 = st.columns(2)
    with col_date1:
        start_date_event = st.date_input(
            "Data de Início do Registro:",
            value=default_start_date,
            key="saude_start_date_event"
        )
    with col_date2:
        end_date_event = st.date_input(
            "Data de Fim do Registro:",
            value=today,
            key="saude_end_date_event"
        )

    if start_date_event > end_date_event:
        st.error("A data de início do registro não pode ser posterior à data de fim.")
        return

    # --- Carregar e Filtrar Dados de Ações (de saúde) ---
    if acoes_df is None or acoes_df.empty:
        st.info("Não há dados de ações para exibir. Verifique a tabela 'Acoes'.")
        return

    # 1. Filtra as ações pelos tipos selecionados
    acoes_saude_df = acoes_df[acoes_df['tipo'].isin(selected_types)].copy()

    # 2. Filtra as ações pelos alunos selecionados (ou todos os alunos se nenhum selecionado)
    acoes_saude_df['aluno_id'] = acoes_saude_df['aluno_id'].astype(str)
    alunos_para_filtragem_historico['id'] = alunos_para_filtragem_historico['id'].astype(str)

    alunos_ids_para_filtragem = alunos_para_filtragem_historico['id'].tolist()
    acoes_saude_df = acoes_saude_df[acoes_saude_df['aluno_id'].isin(alunos_ids_para_filtragem)]

    # 3. Filtra as ações pelo período de registro
    acoes_saude_df['data'] = pd.to_datetime(acoes_saude_df['data'], errors='coerce').dt.date
    acoes_saude_df = acoes_saude_df[
        (acoes_saude_df['data'] >= start_date_event) &
        (acoes_saude_df['data'] <= end_date_event)
    ]
    
    # 4. Adiciona informações do aluno às ações para exibição e filtro de dispensa
    acoes_com_nomes_df = pd.merge(
        acoes_saude_df,
        alunos_para_filtragem_historico[['id', 'nome_guerra', 'pelotao', 'numero_interno']],
        left_on='aluno_id',
        right_on='id',
        how='left',
        suffixes=('_acao', '_aluno') # Adiciona sufixos para diferenciar colunas 'id'
    )
    acoes_com_nomes_df['nome_guerra'].fillna('N/A (Aluno Removido)', inplace=True)
    acoes_com_nomes_df = acoes_com_nomes_df.sort_values(by="data", ascending=False) # Ordena pelos mais recentes
    
    # 5. Aplica filtro de dispensa médica
    if selected_dispensa != "Todos":
        hoje = datetime.now().date()
        
        # Garante que as colunas de data da dispensa sejam datetime.date para comparações
        acoes_com_nomes_df['periodo_dispensa_inicio'] = pd.to_datetime(acoes_com_nomes_df['periodo_dispensa_inicio'], errors='coerce').dt.date
        acoes_com_nomes_df['periodo_dispensa_fim'] = pd.to_datetime(acoes_com_nomes_df['periodo_dispensa_fim'], errors='coerce').dt.date

        if selected_dispensa == "Com Dispensa Ativa":
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == True) &
                (acoes_com_nomes_df['periodo_dispensa_fim'].notna()) & 
                (acoes_com_nomes_df['periodo_dispensa_fim'] >= hoje)
            ]
        elif selected_dispensa == "Com Dispensa Vencida":
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == True) &
                (acoes_com_nomes_df['periodo_dispensa_fim'].notna()) & 
                (acoes_com_nomes_df['periodo_dispensa_fim'] < hoje)
            ]
        elif selected_dispensa == "Sem Dispensa":
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == False) | # Não está dispensado
                (acoes_com_nomes_df['periodo_dispensa_fim'].isna()) | # Ou está dispensado mas sem data de fim (irregular/indefinido)
                (acoes_com_nomes_df['periodo_dispensa_fim'] < hoje) # Ou a dispensa já venceu
            ]
    
    st.divider()
    
    st.subheader("Histórico de Eventos de Saúde")
    
    if acoes_com_nomes_df.empty:
        st.info("Nenhum evento de saúde encontrado para os filtros aplicados.")
        return

    # Exibe os eventos de saúde
    for index, acao in acoes_com_nomes_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"##### {acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}")
                st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}")
                # Usa safe_strftime para formatar a data do registro
                st.caption(f"Data do Registro: {safe_strftime(acao['data'], '%d/%m/%Y')}")
                if acao.get('descricao'):
                    st.caption(f"Observação: {acao.get('descricao')}")
            
            with col2:
                if acao.get('esta_dispensado'):
                    # Usa safe_strftime para as datas de dispensa
                    inicio_str = safe_strftime(acao.get('periodo_dispensa_inicio'), '%d/%m/%y')
                    fim_str = safe_strftime(acao.get('periodo_dispensa_fim'), '%d/%m/%y')
                    
                    data_fim_obj = acao.get('periodo_dispensa_fim') # Pode ser pd.NaT ou datetime.date
                    hoje = datetime.now().date()
                    
                    # Verifica o status da dispensa: Converte para date para comparar com 'hoje'
                    if pd.notna(data_fim_obj) and pd.to_datetime(data_fim_obj).date() < hoje: 
                        st.warning("**DISPENSA VENCIDA**", icon="⌛")
                    else:
                        st.error("**DISPENSADO**", icon="⚕️")
                    
                    st.markdown(f"**Período:** {inicio_str} a {fim_str}")
                    st.caption(f"Tipo: {acao.get('tipo_dispensa', 'Não especificado')}")
                else:
                    st.success("**SEM DISPENSA**", icon="✅")
            
            with col3:
                # O ID da ação agora é 'id_acao' devido ao sufixo no merge
                id_da_acao = acao['id_acao']
                if st.button("✏️ Editar", key=f"edit_saude_{id_da_acao}"):
                    edit_saude_dialog(id_da_acao, acao, supabase)
