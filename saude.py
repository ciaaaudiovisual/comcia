import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client

# ==============================================================================
# DIÁLOGO DE EDIÇÃO
# ==============================================================================
@st.dialog("Editar Dados de Saúde")
def edit_saude_dialog(acao_id, dados_acao_atual, supabase):
    """
    Abre um formulário para editar os detalhes de saúde de uma ação específica.
    """
    st.write(f"Editando evento para: **{dados_acao_atual.get('nome_guerra', 'N/A')}**")
    st.caption(f"Ação: {dados_acao_atual.get('tipo', 'N/A')} em {pd.to_datetime(dados_acao_atual.get('data')).strftime('%d/%m/%Y')}")

    with st.form("edit_saude_form"):
        # --- CAMPOS DO FORMULÁRIO ---
        st.divider()
        st.markdown("##### Controle de Dispensa Médica")

        # Converte o valor do banco (que pode ser None) para um booleano
        esta_dispensado_atual = dados_acao_atual.get('esta_dispensado', False)
        if pd.isna(esta_dispensado_atual):
            esta_dispensado_atual = False
            
        dispensado = st.toggle("Gerou dispensa médica?", value=bool(esta_dispensado_atual))
        
        # Campos que aparecem se a dispensa estiver ativa
        if dispensado:
            # Converte as datas do banco para objetos de data, com um padrão se forem nulas
            try:
                data_inicio_atual = pd.to_datetime(dados_acao_atual.get('periodo_dispensa_inicio')).date()
            except (TypeError, ValueError):
                data_inicio_atual = datetime.now().date()

            try:
                data_fim_atual = pd.to_datetime(dados_acao_atual.get('periodo_dispensa_fim')).date()
            except (TypeError, ValueError):
                data_fim_atual = datetime.now().date()

            col_d1, col_d2 = st.columns(2)
            data_inicio_dispensa = col_d1.date_input("Início da Dispensa", value=data_inicio_atual)
            data_fim_dispensa = col_d2.date_input("Fim da Dispensa", value=data_fim_atual)
            
            # Opções de dispensa
            tipos_dispensa_opcoes = ["", "Total", "Parcial", "Para Esforço Físico", "Outro"]
            tipo_dispensa_atual = dados_acao_atual.get('tipo_dispensa', '')
            
            # Garante que o valor atual esteja na lista de opções
            if tipo_dispensa_atual not in tipos_dispensa_opcoes:
                tipos_dispensa_opcoes.append(tipo_dispensa_atual)

            tipo_dispensa = st.selectbox(
                "Tipo de Dispensa", 
                options=tipos_dispensa_opcoes,
                index=tipos_dispensa_opcoes.index(tipo_dispensa_atual) if tipo_dispensa_atual in tipos_dispensa_opcoes else 0
            )

        # --- BOTÃO DE SALVAR ---
        if st.form_submit_button("Salvar Alterações"):
            dados_para_atualizar = {}
            if dispensado:
                dados_para_atualizar = {
                    'esta_dispensado': True,
                    'periodo_dispensa_inicio': data_inicio_dispensa.isoformat(),
                    'periodo_dispensa_fim': data_fim_dispensa.isoformat(),
                    'tipo_dispensa': tipo_dispensa
                }
            else:
                dados_para_atualizar = {
                    'esta_dispensado': False,
                    'periodo_dispensa_inicio': None,
                    'periodo_dispensa_fim': None,
                    'tipo_dispensa': None
                }
            
            try:
                supabase.table("Acoes").update(dados_para_atualizar).eq("id", acao_id).execute()
                st.success("Dados de saúde atualizados com sucesso!")
                load_data.clear() # Limpa o cache para forçar o recarregamento dos dados
            except Exception as e:
                st.error(f"Erro ao salvar as alterações: {e}")


# ==============================================================================
# PÁGINA PRINCIPAL DO MÓDULO DE SAÚDE
# ==============================================================================
def show_saude():
    st.title("⚕️ Módulo de Saúde")
    st.markdown("Controle centralizado de eventos de saúde e dispensas médicas.")
    
    supabase = init_supabase_client()
    
    # Carrega os dados necessários
    try:
        acoes_df = load_data("Acoes")
        alunos_df = load_data("Alunos")
        tipos_acao_df = load_data("Tipos_Acao")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # --- 1. Filtro Dinâmico de Tipos de Ação ---
    st.subheader("Filtro de Eventos")
    
    # Pega todos os nomes de tipos de ação disponíveis
    todos_tipos_nomes = tipos_acao_df['nome'].unique().tolist()
    
    # Define uma lista padrão de tipos de saúde para pré-selecionar
    tipos_saude_padrao = ["Enfermaria", "Hospital", "NAS", "DISPENÇA MÉDICA", "SAÚDE"]
    
    # Garante que apenas os tipos que realmente existem na base de dados sejam pré-selecionados
    tipos_selecionados_default = [tipo for tipo in tipos_saude_padrao if tipo in todos_tipos_nomes]
    
    tipos_selecionados = st.multiselect(
        "Selecione os tipos de evento para exibir:",
        options=todos_tipos_nomes,
        default=tipos_selecionados_default
    )
    
    if not tipos_selecionados:
        st.warning("Selecione pelo menos um tipo de evento para continuar.")
        return
        
    acoes_saude_df = acoes_df[acoes_df['tipo'].isin(tipos_selecionados)].copy()
    
    if acoes_saude_df.empty:
        st.info("Nenhum evento encontrado para os tipos selecionados.")
        return

    # Junta com os nomes dos alunos
    acoes_com_nomes_df = pd.merge(
        acoes_saude_df,
        alunos_df[['id', 'nome_guerra', 'pelotao']],
        left_on='aluno_id',
        right_on='id',
        how='left'
    )
    acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)
    
    # Ordena pelos eventos mais recentes
    acoes_com_nomes_df['data'] = pd.to_datetime(acoes_com_nomes_df['data'])
    acoes_com_nomes_df = acoes_com_nomes_df.sort_values(by="data", ascending=False)
    
    st.divider()
    
    # --- 2. Exibição dos Eventos com Botão de Edição ---
    st.subheader("Histórico de Eventos de Saúde")
    
    for index, acao in acoes_com_nomes_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                st.markdown(f"##### {acao.get('nome_guerra', 'N/A')} ({acao.get('pelotao', 'N/A')})")
                st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}")
                st.caption(f"Data do Registro: {acao['data'].strftime('%d/%m/%Y')}")
                if acao.get('descricao'):
                    st.caption(f"Observação: {acao.get('descricao')}")
            
            with col2:
                if acao.get('esta_dispensado'):
                    inicio_str = pd.to_datetime(acao.get('periodo_dispensa_inicio')).strftime('%d/%m/%y') if pd.notna(acao.get('periodo_dispensa_inicio')) else "N/A"
                    fim_str = pd.to_datetime(acao.get('periodo_dispensa_fim')).strftime('%d/%m/%y') if pd.notna(acao.get('periodo_dispensa_fim')) else "N/A"
                    
                    st.error(f"**DISPENSADO**", icon="⚕️")
                    st.markdown(f"**Período:** {inicio_str} a {fim_str}")
                    st.caption(f"Tipo: {acao.get('tipo_dispensa', 'Não especificado')}")
                else:
                    st.success("**SEM DISPENSA**", icon="✅")
            
            with col3:
                # Botão para abrir o diálogo de edição
                if st.button("✏️ Editar", key=f"edit_{acao['id']}"):
                    edit_saude_dialog(acao['id'], acao, supabase)
