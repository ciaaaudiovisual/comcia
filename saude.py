import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data, init_supabase_client
from aluno_selection_components import render_alunos_filter_and_selection # Importe o novo nome

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
                load_data.clear()
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

    # --- Componente Padronizado de Seleção de Alunos ---
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
            key="dispensa_medica_filter",
            index=0 # ALTERADO: Padrão para 'Todos'
        )
    
    with col_filter_saude2:
        # Filtro por Tipos de Ação (saúde)
        todos_tipos_nomes = sorted(tipos_acao_df['nome'].unique().tolist())
        
        selected_types = st.multiselect(
            "Filtrar por Tipo de Evento:",
            options=todos_tipos_nomes,
            default=todos_tipos_nomes, # ALTERADO: Seleciona todos os tipos por padrão
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
    if acoes_df is None or acoes_df.empty:
        st.warning("Não há dados de ações para exibir. Verifique a tabela 'Acoes'.")
        return

    # 1. Filtra as ações pelos tipos selecionados
    acoes_saude_df = acoes_df[acoes_df['tipo'].isin(selected_types)].copy()

    # 2. Filtra as ações pelos alunos selecionados do componente
    # SOLUÇÃO DO ValueError: Converter as colunas 'aluno_id' e 'id' para string ANTES DO MERGE
    acoes_saude_df['aluno_id'] = acoes_saude_df['aluno_id'].astype(str)
    selected_alunos_df['id'] = selected_alunos_df['id'].astype(str) # Garante que o ID do aluno também é string

    # 3. Filtra as ações pelo período de registro
    acoes_saude_df['data'] = pd.to_datetime(acoes_saude_df['data'], errors='coerce').dt.date
    acoes_saude_df = acoes_saude_df[
        (acoes_saude_df['data'] >= start_date_event) &
        (acoes_saude_df['data'] <= end_date_event)
    ]
    
    # 4. Adiciona informações do aluno às ações para exibição e filtro de dispensa
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
                # Exibição alterada para "Número - Nome de Guerra"
                st.markdown(f"##### {acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}")
                st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}")
                st.caption(f"Data do Registro: {acao['data'].strftime('%d/%m/%Y')}")
                if acao.get('descricao'):
                    st.caption(f"Observação: {acao.get('descricao')}")
            
            with col2:
                if acao.get('esta_dispensado'):
                    # Pega os valores da série ou DataFrame
                    inicio_dt = acao['periodo_dispensa_inicio']
                    fim_dt = acao['periodo_dispensa_fim']

                    # Adicionado pd.api.types.is_datetime64_any_dtype para robustez na formatação
                    inicio_str = inicio_dt.strftime('%d/%m/%y') if pd.notna(inicio_dt) and pd.api.types.is_datetime64_any_dtype(inicio_dt) else "N/A"
                    fim_str = fim_dt.strftime('%d/%m/%y') if pd.notna(fim_dt) and pd.api.types.is_datetime64_any_dtype(fim_dt) else "N/A"
                    
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
                    edit_saude_dialog(id_da_acao, acao, supabase)
