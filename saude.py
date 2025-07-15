import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client

# ==============================================================================
# DIÁLOGO DE EDIÇÃO (Sem alterações nesta versão)
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

    st.subheader("Filtro de Eventos")
    
    todos_tipos_nomes = sorted(tipos_acao_df['nome'].unique().tolist())
    
    # --- MODIFICAÇÃO 1: Lista padrão de filtros atualizada com a capitalização correta ---
    tipos_saude_padrao = ["ENFERMARIA", "HOSPITAL", "NAS", "DISPENSA MÉDICA", "SAÚDE"]
    
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

    # --- MODIFICAÇÃO 2: Adicionado 'numero_interno' ao merge para exibição ---
    acoes_com_nomes_df = pd.merge(
        acoes_saude_df,
        alunos_df[['id', 'nome_guerra', 'pelotao', 'numero_interno']],
        left_on='aluno_id',
        right_on='id',
        how='left'
    )
    acoes_com_nomes_df['nome_guerra'].fillna('N/A', inplace=True)
    
    acoes_com_nomes_df['data'] = pd.to_datetime(acoes_com_nomes_df['data'])
    acoes_com_nomes_df = acoes_com_nomes_df.sort_values(by="data", ascending=False)
    
    st.divider()
    
    st.subheader("Histórico de Eventos de Saúde")
    
    for index, acao in acoes_com_nomes_df.iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 2, 1])
            
            with col1:
                # --- MODIFICAÇÃO 3: Exibição alterada para "Número - Nome de Guerra" ---
                st.markdown(f"##### {acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}")
                st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}")
                st.caption(f"Data do Registro: {acao['data'].strftime('%d/%m/%Y')}")
                if acao.get('descricao'):
                    st.caption(f"Observação: {acao.get('descricao')}")
            
            with col2:
                if acao.get('esta_dispensado'):
                    inicio_str = pd.to_datetime(acao.get('periodo_dispensa_inicio')).strftime('%d/%m/%y') if pd.notna(acao.get('periodo_dispensa_inicio')) else "N/A"
                    fim_str = pd.to_datetime(acao.get('periodo_dispensa_fim')).strftime('%d/%m/%y') if pd.notna(acao.get('periodo_dispensa_fim')) else "N/A"
                    
                    data_fim = pd.to_datetime(acao.get('periodo_dispensa_fim')).date() if pd.notna(acao.get('periodo_dispensa_fim')) else None
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
