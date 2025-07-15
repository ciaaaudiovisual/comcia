import streamlit as st
import pandas as pd
from datetime import datetime, timedelta # Importar timedelta para cálculos de data
from database import load_data, init_supabase_client
[cite_start]from aluno_selection_components import render_alunos_filter_and_selection # Importa o componente de seleção de alunos [cite: 1]

# ==============================================================================
# FUNÇÃO AUXILIAR PARA FORMATAÇÃO SEGURA DE DATAS
# ==============================================================================
def safe_strftime(date_obj, fmt='%d/%m/%y'):
    """
    Formata um objeto de data/hora de forma segura. Retorna 'N/A' se for nulo,
    inválido ou não puder ser formatado.
    """
    [cite_start]if pd.isna(date_obj): # Verifica se é NaN (incluindo NaT do Pandas) [cite: 1]
        return "N/A"
    # [cite_start]Aceita datetime.date, datetime.datetime ou pandas.Timestamp [cite: 1]
    if isinstance(date_obj, (datetime.date, datetime.datetime, pd.Timestamp)): 
        try:
            # [cite_start]Converte para Timestamp do pandas para formatação consistente [cite: 1]
            return pd.to_datetime(date_obj).strftime(fmt) 
        [cite_start]except Exception: # Captura qualquer erro de formatação [cite: 1]
            return "N/A"
    [cite_start]return "N/A" # Retorna N/A para outros tipos de objeto [cite: 1]

# ==============================================================================
# DIÁLOGO DE EDIÇÃO
# ==============================================================================
@st.dialog("Editar Dados de Saúde")
def edit_saude_dialog(acao_id, dados_acao_atual, supabase):
    """
    Abre um formulário para editar os detalhes de saúde e o aluno de uma ação específica.
    """
    [cite_start]alunos_df = load_data("Alunos") [cite: 1]
    
    st.write(f"Editando evento para: **{dados_acao_atual.get('nome_guerra', 'N/A')}**")
    st.caption(f"Ação: {dados_acao_atual.get('tipo', 'N/A')} em {pd.to_datetime(dados_acao_atual.get('data')).strftime('%d/%m/%Y')}")

    with st.form("edit_saude_form"):
        st.divider()
        
        st.markdown("##### Corrigir Aluno (se necessário)")
        [cite_start]opcoes_alunos = pd.Series(alunos_df.id.values, index=alunos_df.nome_guerra).to_dict() [cite: 1]
        [cite_start]nomes_alunos_lista = list(opcoes_alunos.keys()) [cite: 1]
        [cite_start]aluno_atual_id = dados_acao_atual.get('aluno_id') [cite: 1]
        aluno_atual_nome = ""
        [cite_start]if pd.notna(aluno_atual_id): [cite: 1]
            [cite_start]aluno_info = alunos_df[alunos_df['id'] == aluno_atual_id] [cite: 1]
            [cite_start]if not aluno_info.empty: [cite: 1]
                [cite_start]aluno_atual_nome = aluno_info.iloc[0]['nome_guerra'] [cite: 1]
        [cite_start]indice_aluno_atual = nomes_alunos_lista.index(aluno_atual_nome) if aluno_atual_nome in nomes_alunos_lista else 0 [cite: 1]
        [cite_start]aluno_selecionado_nome = st.selectbox("Selecione o aluno correto:", options=nomes_alunos_lista, index=indice_aluno_atual) [cite: 1]
        
        st.divider()
        st.markdown("##### Controle de Dispensa Médica")
        
        [cite_start]esta_dispensado_atual = dados_acao_atual.get('esta_dispensado', False) [cite: 1]
        [cite_start]if pd.isna(esta_dispensado_atual): [cite: 1]
            [cite_start]esta_dispensado_atual = False [cite: 1]
            
        [cite_start]dispensado = st.toggle("Aluno está Dispensado?", value=bool(esta_dispensado_atual)) [cite: 1]
        
        data_inicio_dispensa = None
        data_fim_dispensa = None
        tipo_dispensa = ""

        if dispensado:
            [cite_start]start_date_val = dados_acao_atual.get('periodo_dispensa_inicio') [cite: 1]
            [cite_start]end_date_val = dados_acao_atual.get('periodo_dispensa_fim') [cite: 1]
            [cite_start]data_inicio_atual = pd.to_datetime(start_date_val).date() if pd.notna(start_date_val) else datetime.now().date() [cite: 1]
            [cite_start]data_fim_atual = pd.to_datetime(end_date_val).date() if pd.notna(end_date_val) else datetime.now().date() [cite: 1]

            [cite_start]col_d1, col_d2 = st.columns(2) [cite: 1]
            [cite_start]data_inicio_dispensa = col_d1.date_input("Início da Dispensa", value=data_inicio_atual) [cite: 1]
            [cite_start]data_fim_dispensa = col_d2.date_input("Fim da Dispensa", value=data_fim_atual) [cite: 1]
            
            [cite_start]tipos_dispensa_opcoes = ["", "Total", "Parcial", "Para Esforço Físico", "Outro"] [cite: 1]
            [cite_start]tipo_dispensa_atual = dados_acao_atual.get('tipo_dispensa', '') [cite: 1]
            [cite_start]if pd.isna(tipo_dispensa_atual): [cite: 1]
                [cite_start]tipo_dispensa_atual = "" [cite: 1]
            [cite_start]if tipo_dispensa_atual not in tipos_dispensa_opcoes: [cite: 1]
                [cite_start]tipos_dispensa_opcoes.append(tipo_dispensa_atual) [cite: 1]
            [cite_start]tipo_dispensa = st.selectbox("Tipo de Dispensa", options=tipos_dispensa_opcoes, index=tipos_dispensa_opcoes.index(tipo_dispensa_atual)) [cite: 1]

        st.divider()
        [cite_start]nova_descricao = st.text_area("Comentários/Observações (Opcional)", value=dados_acao_atual.get('descricao', '')) [cite: 1]

        [cite_start]if st.form_submit_button("Salvar Alterações"): [cite: 1]
            [cite_start]novo_aluno_id = opcoes_alunos[aluno_selecionado_nome] [cite: 1]
            dados_para_atualizar = {
                'aluno_id': novo_aluno_id,
                'esta_dispensado': dispensado,
                [cite_start]'periodo_dispensa_inicio': data_inicio_dispensa.isoformat() if dispensado and data_inicio_dispensa else None, [cite: 1]
                [cite_start]'periodo_dispensa_fim': data_fim_dispensa.isoformat() if dispensado and data_fim_dispensa else None, [cite: 1]
                [cite_start]'tipo_dispensa': tipo_dispensa if dispensado else None, [cite: 1]
                [cite_start]'descricao': nova_descricao [cite: 1]
            }
            
            try:
                [cite_start]supabase.table("Acoes").update(dados_para_atualizar).eq("id", acao_id).execute() [cite: 1]
                [cite_start]st.success("Dados de saúde atualizados com sucesso!") [cite: 1]
                [cite_start]load_data.clear() # Limpa o cache para recarregar dados atualizados [cite: 1]
            except Exception as e:
                [cite_start]st.error(f"Erro ao salvar as alterações: {e}") [cite: 1]

# ==============================================================================
# PÁGINA PRINCIPAL DO MÓDULO DE SAÚDE
# ==============================================================================
def show_saude():
    st.title("⚕️ Módulo de Saúde")
    st.markdown("Controle centralizado de eventos de saúde e dispensas médicas.")
    
    [cite_start]supabase = init_supabase_client() [cite: 1]
    
    try:
        [cite_start]acoes_df = load_data("Acoes") [cite: 1]
        [cite_start]alunos_df = load_data("Alunos") [cite: 1]
        [cite_start]tipos_acao_df = load_data("Tipos_Acao") [cite: 1]
    except Exception as e:
        [cite_start]st.error(f"Erro ao carregar dados: {e}") [cite: 1]
        return

    # --- Componente Padronizado de Seleção de Alunos (reintroduzido e essencial) ---
    [cite_start]selected_alunos_df = render_alunos_filter_and_selection(key_suffix="saude_module", include_full_name_search=False) [cite: 1]

    [cite_start]if selected_alunos_df.empty: [cite: 1]
        [cite_start]st.info("Selecione alunos para visualizar os dados de saúde.") [cite: 1]
        [cite_start]return # Sai da função se nenhum aluno for selecionado [cite: 1]

    st.divider()
    st.subheader("Filtros Específicos de Saúde")

    [cite_start]col_filter_saude1, col_filter_saude2 = st.columns(2) [cite: 1]
    with col_filter_saude1:
        # Filtro por Dispensa Médica (mantido conforme original)
        [cite_start]dispensa_medica_options = ["Todos", "Com Dispensa Ativa", "Com Dispensa Vencida", "Sem Dispensa"] [cite: 1]
        selected_dispensa = st.selectbox(
            "Status de Dispensa Médica:",
            options=dispensa_medica_options,
            key="dispensa_medica_filter",
            [cite_start]index=0 # Padrão para 'Todos' [cite: 1]
        )
    
    with col_filter_saude2:
        # Filtro por Tipos de Ação (saúde) (mantido conforme original)
        [cite_start]todos_tipos_nomes = sorted(tipos_acao_df['nome'].unique().tolist()) [cite: 1]
        
        # Tipos padrão de saúde para seleção inicial no multiselect
        [cite_start]tipos_saude_padrao = ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"] [cite: 1]
        
        selected_types = st.multiselect(
            "Filtrar por Tipo de Evento:",
            options=todos_tipos_nomes,
            [cite_start]default=[t for t in tipos_saude_padrao if t in todos_tipos_nomes], # Seleciona tipos de saúde relevantes por padrão [cite: 1]
            key="saude_event_types_filter"
        )
    
    [cite_start]if not selected_types: [cite: 1]
        [cite_start]st.warning("Selecione pelo menos um tipo de evento para continuar.") [cite: 1]
        return

    # Filtro por Período (Data Range) (reintroduzido para os "últimos registros")
    st.markdown("##### Filtrar por Período de Registro:")
    [cite_start]today = datetime.now().date() [cite: 1]
    [cite_start]default_start_date = today - timedelta(days=90) # Últimos 90 dias como padrão [cite: 1]

    [cite_start]col_date1, col_date2 = st.columns(2) [cite: 1]
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

    [cite_start]if start_date_event > end_date_event: [cite: 1]
        [cite_start]st.error("A data de início do registro não pode ser posterior à data de fim.") [cite: 1]
        return

    # --- Carregar e Filtrar Dados de Ações (de saúde) ---
    [cite_start]if acoes_df is None or acoes_df.empty: [cite: 1]
        [cite_start]st.warning("Não há dados de ações para exibir. Verifique a tabela 'Acoes'.") [cite: 1]
        return

    # 1. Filtra as ações pelos tipos selecionados
    [cite_start]acoes_saude_df = acoes_df[acoes_df['tipo'].isin(selected_types)].copy() [cite: 1]

    # 2. Filtra as ações pelos alunos selecionados do componente `render_alunos_filter_and_selection`
    # [cite_start]Garante que as colunas 'aluno_id' e 'id' são strings para a fusão/filtro [cite: 1]
    [cite_start]acoes_saude_df['aluno_id'] = acoes_saude_df['aluno_id'].astype(str) [cite: 1]
    [cite_start]selected_alunos_df['id'] = selected_alunos_df['id'].astype(str) [cite: 1]

    # Aplica o filtro de alunos: apenas ações de alunos que estão em selected_alunos_df
    [cite_start]alunos_ids_selecionados = selected_alunos_df['id'].tolist() [cite: 1]
    [cite_start]acoes_saude_df = acoes_saude_df[acoes_saude_df['aluno_id'].isin(alunos_ids_selecionados)] [cite: 1]

    # 3. Filtra as ações pelo período de registro
    [cite_start]acoes_saude_df['data'] = pd.to_datetime(acoes_saude_df['data'], errors='coerce').dt.date [cite: 1]
    acoes_saude_df = acoes_saude_df[
        [cite_start](acoes_saude_df['data'] >= start_date_event) & [cite: 1]
        [cite_start](acoes_saude_df['data'] <= end_date_event) [cite: 1]
    ]
    
    # 4. Adiciona informações do aluno às ações para exibição e filtro de dispensa
    acoes_com_nomes_df = pd.merge(
        acoes_saude_df,
        selected_alunos_df[['id', 'nome_guerra', 'pelotao', 'numero_interno']],
        left_on='aluno_id',
        right_on='id',
        how='left',
        [cite_start]suffixes=('_acao', '_aluno') # Adiciona sufixos para diferenciar colunas 'id' [cite: 1]
    )
    [cite_start]acoes_com_nomes_df['nome_guerra'].fillna('N/A (Aluno Removido)', inplace=True) [cite: 1]
    [cite_start]acoes_com_nomes_df = acoes_com_nomes_df.sort_values(by="data", ascending=False) # Ordena pelos mais recentes [cite: 1]
    
    # 5. Aplica filtro de dispensa médica
    [cite_start]if selected_dispensa != "Todos": [cite: 1]
        [cite_start]hoje = datetime.now().date() [cite: 1]
        
        # [cite_start]Garante que as colunas de data da dispensa sejam datetime.date para comparações [cite: 1]
        [cite_start]acoes_com_nomes_df['periodo_dispensa_inicio'] = pd.to_datetime(acoes_com_nomes_df['periodo_dispensa_inicio'], errors='coerce').dt.date [cite: 1]
        [cite_start]acoes_com_nomes_df['periodo_dispensa_fim'] = pd.to_datetime(acoes_com_nomes_df['periodo_dispensa_fim'], errors='coerce').dt.date [cite: 1]

        [cite_start]if selected_dispensa == "Com Dispensa Ativa": [cite: 1]
            acoes_com_nomes_df = acoes_com_nomes_df[
                [cite_start](acoes_com_nomes_df['esta_dispensado'] == True) & [cite: 1]
                [cite_start](acoes_com_nomes_df['periodo_dispensa_fim'].notna()) & [cite: 1]
                [cite_start](acoes_com_nomes_df['periodo_dispensa_fim'] >= hoje) [cite: 1]
            ]
        [cite_start]elif selected_dispensa == "Com Dispensa Vencida": [cite: 1]
            acoes_com_nomes_df = acoes_com_nomes_df[
                [cite_start](acoes_com_nomes_df['esta_dispensado'] == True) & [cite: 1]
                [cite_start](acoes_com_nomes_df['periodo_dispensa_fim'].notna()) & [cite: 1]
                [cite_start](acoes_com_nomes_df['periodo_dispensa_fim'] < hoje) [cite: 1]
            ]
        [cite_start]elif selected_dispensa == "Sem Dispensa": [cite: 1]
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == False) | # [cite_start]Não está dispensado [cite: 1]
                (acoes_com_nomes_df['periodo_dispensa_fim'].isna()) | # [cite_start]Ou está dispensado mas sem data de fim (irregular/indefinido) [cite: 1]
                [cite_start](acoes_com_nomes_df['periodo_dispensa_fim'] < hoje) # Ou a dispensa já venceu [cite: 1]
            ]
    
    st.divider()
    
    st.subheader("Histórico de Eventos de Saúde")
    
    [cite_start]if acoes_com_nomes_df.empty: [cite: 1]
        [cite_start]st.info("Nenhum evento de saúde encontrado para os filtros aplicados.") [cite: 1]
        return

    # Exibe os eventos de saúde
    [cite_start]for index, acao in acoes_com_nomes_df.iterrows(): [cite: 1]
        [cite_start]with st.container(border=True): [cite: 1]
            [cite_start]col1, col2, col3 = st.columns([3, 2, 1]) [cite: 1]
            
            with col1:
                [cite_start]st.markdown(f"##### {acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}") [cite: 1]
                [cite_start]st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}") [cite: 1]
                # [cite_start]Usa safe_strftime para formatar a data do registro [cite: 1]
                [cite_start]st.caption(f"Data do Registro: {safe_strftime(acao['data'], '%d/%m/%Y')}") [cite: 1]
                [cite_start]if acao.get('descricao'): [cite: 1]
                    [cite_start]st.caption(f"Observação: {acao.get('descricao')}") [cite: 1]
            
            with col2:
                [cite_start]if acao.get('esta_dispensado'): [cite: 1]
                    # [cite_start]Usa safe_strftime para as datas de dispensa [cite: 1]
                    [cite_start]inicio_str = safe_strftime(acao.get('periodo_dispensa_inicio'), '%d/%m/%y') [cite: 1]
                    [cite_start]fim_str = safe_strftime(acao.get('periodo_dispensa_fim'), '%d/%m/%y') [cite: 1]
                    
                    [cite_start]data_fim_obj = acao.get('periodo_dispensa_fim') # Pode ser pd.NaT ou datetime.date [cite: 1]
                    [cite_start]hoje = datetime.now().date() [cite: 1]
                    
                    # [cite_start]Verifica o status da dispensa: Converte para date para comparar com 'hoje' [cite: 1]
                    if pd.notna(data_fim_obj) and pd.to_datetime(data_fim_obj).date() < hoje: 
                        [cite_start]st.warning("**DISPENSA VENCIDA**", icon="⌛") [cite: 1]
                    else:
                        [cite_start]st.error("**DISPENSADO**", icon="⚕️") [cite: 1]
                    
                    [cite_start]st.markdown(f"**Período:** {inicio_str} a {fim_str}") [cite: 1]
                    [cite_start]st.caption(f"Tipo: {acao.get('tipo_dispensa', 'Não especificado')}") [cite: 1]
                else:
                    [cite_start]st.success("**SEM DISPENSA**", icon="✅") [cite: 1]
            
            with col3:
                # [cite_start]O ID da ação agora é 'id_acao' devido ao sufixo no merge [cite: 1]
                [cite_start]id_da_acao = acao['id_acao'] [cite: 1]
                [cite_start]if st.button("✏️ Editar", key=f"edit_saude_{id_da_acao}"): [cite: 1]
                    [cite_start]edit_saude_dialog(id_da_acao, acao, supabase) [cite: 1]
