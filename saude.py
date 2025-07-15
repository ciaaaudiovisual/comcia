# saude.py
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data
from aluno_selection_components import render_alunos_filter_and_selection # Importe o novo nome

def show_saude(): # Renomeado para show_saude para consistência com outros arquivos
    st.title("⚕️ Módulo de Saúde")
    st.markdown("Controle centralizado de eventos de saúde e dispensas médicas.")

    # --- Componente Padronizado de Seleção de Alunos ---
    # Não precisamos da busca por nome completo/NIP aqui, então include_full_name_search=False
    selected_alunos_df = render_alunos_filter_and_selection(key_suffix="saude_module", include_full_name_search=False)

    if selected_alunos_df.empty:
        st.info("Selecione alunos para visualizar os dados de saúde.")
        return # Sai da função se nenhum aluno for selecionado

    st.divider()
    st.subheader("Filtros Específicos de Saúde")

    col_filter_saude1, col_filter_saude2 = st.columns(2)
    with col_filter_saude1:
        # Filtro por Dispensa Médica
        dispensa_medica_options = ["Todos", "Com Dispensa Ativa", "Com Dispensa Vencida", "Sem Dispensa"]
        selected_dispensa = st.selectbox(
            "Status de Dispensa Médica:",
            options=dispensa_medica_options,
            key="dispensa_medica_filter"
        )
    
    with col_filter_saude2:
        # Filtro por Tipos de Ação (saúde)
        tipos_acao_df = load_data("Tipos_Acao") # Carrega tipos de ação para o filtro
        todos_tipos_nomes = sorted(tipos_acao_df['nome'].unique().tolist())
        tipos_saude_padrao = ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"] #
        selected_types_default = [tipo for tipo in tipos_saude_padrao if tipo in todos_tipos_nomes]
        
        selected_types = st.multiselect(
            "Filtrar por Tipo de Evento:",
            options=todos_tipos_nomes,
            default=selected_types_default,
            key="saude_event_types_filter"
        )

    # Filtro por Período (Data Range)
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
    acoes_df = load_data("Acoes")
    if acoes_df is None or acoes_df.empty:
        st.warning("Não há dados de ações para exibir. Verifique a tabela 'Acoes'.")
        return

    # 1. Filtra as ações pelos tipos selecionados
    acoes_saude_df = acoes_df[acoes_df['tipo'].isin(selected_types)].copy()

    # 2. Filtra as ações pelos alunos selecionados do componente
# saude.py (APENAS O TRECHO ONDE O ERRO OCORRE)

    # 4. Adiciona informações do aluno às ações para exibição e filtro de dispensa
    # SOLUÇÃO: Converter as colunas 'aluno_id' e 'id' para string ANTES DO MERGE
    acoes_saude_df['aluno_id'] = acoes_saude_df['aluno_id'].astype(str)
    selected_alunos_df['id'] = selected_alunos_df['id'].astype(str) # Garante que o ID do aluno também é string

    acoes_com_nomes_df = pd.merge(
        acoes_saude_df,
        selected_alunos_df[['id', 'nome_guerra', 'pelotao', 'numero_interno']],
        left_on='aluno_id',
        right_on='id',
        how='left'
    )
    acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)
    acoes_com_nomes_df = acoes_com_nomes_df.sort_values(by="data", ascending=False)

    # 5. Aplica filtro de dispensa médica (AGORA MAIS ROBUSTO)
    if selected_dispensa != "Todos":
        hoje = datetime.now().date()
        
        # Garante que as colunas de data sejam datetime.date
        acoes_com_nomes_df['periodo_dispensa_inicio'] = pd.to_datetime(acoes_com_nomes_df['periodo_dispensa_inicio'], errors='coerce').dt.date
        acoes_com_nomes_df['periodo_dispensa_fim'] = pd.to_datetime(acoes_com_nomes_df['periodo_dispensa_fim'], errors='coerce').dt.date

        if selected_dispensa == "Com Dispensa Ativa":
            # Está dispensado E a data de fim é >= hoje
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == True) &
                (acoes_com_nomes_df['periodo_dispensa_fim'].notna()) & # Garante que a data não é nula
                (acoes_com_nomes_df['periodo_dispensa_fim'] >= hoje)
            ]
        elif selected_dispensa == "Com Dispensa Vencida":
            # Está dispensado E a data de fim é < hoje
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == True) &
                (acoes_com_nomes_df['periodo_dispensa_fim'].notna()) &
                (acoes_com_nomes_df['periodo_dispensa_fim'] < hoje)
            ]
        elif selected_dispensa == "Sem Dispensa":
            # Não está dispensado OU (está dispensado mas sem período definido ou com período expirado)
            acoes_com_nomes_df = acoes_com_nomes_df[
                (acoes_com_nomes_df['esta_dispensado'] == False) |
                (acoes_com_nomes_df['periodo_dispensa_fim'].isna()) | # Sem data de fim definida
                (acoes_com_nomes_df['periodo_dispensa_fim'] < hoje) # Ou vencida
            ]
    
    st.divider()
    
    st.subheader("Histórico de Eventos de Saúde")
    
    if acoes_com_nomes_df.empty:
        st.info("Nenhum evento de saúde encontrado para os filtros aplicados.")
        return

    for index, acao in acoes_com_nomes_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"##### {acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}")
                st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}")
                st.caption(f"Data do Registro: {acao['data'].strftime('%d/%m/%Y')}")
                if acao.get('descricao'):
                    st.caption(f"Observação: {acao.get('descricao')}")
            
            with col2:
                if acao.get('esta_dispensado'):
                    inicio_str = acao['periodo_dispensa_inicio'].strftime('%d/%m/%y') if pd.notna(acao['periodo_dispensa_inicio']) else "N/A"
                    fim_str = acao['periodo_dispensa_fim'].strftime('%d/%m/%y') if pd.notna(acao['periodo_dispensa_fim']) else "N/A"
                    
                    data_fim = acao['periodo_dispensa_fim']
                    hoje = datetime.now().date()
                    
                    if data_fim and data_fim < hoje:
                        st.warning("**DISPENSA VENCIDA**", icon="⌛")
                    else:
                        st.error("**DISPENSADO**", icon="⚕️")
                    
                    st.markdown(f"**Período:** {inicio_str} a {fim_str}")
                    st.caption(f"Tipo: {acao.get('tipo_dispensa', 'Não especificado')}")
                else:
                    st.success("**SEM DISPENSA**", icon="✅")
            
            with col3:
                id_da_acao = acao['id_x'] 
                if st.button("✏️ Editar", key=f"edit_{id_da_acao}"):
                    # Chame o diálogo de edição
                    # Você precisará ter a função edit_saude_dialog importada ou definida aqui
                    # Por enquanto, mantendo o import original para não quebrar outros arquivos
                    from saude import edit_saude_dialog # Importa localmente para evitar circular
                    edit_saude_dialog(id_da_acao, acao, supabase)
