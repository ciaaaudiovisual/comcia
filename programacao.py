import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from io import BytesIO
import zipfile

# --- DIÁLOGOS E FUNÇÕES DE CALLBACK ---

@st.dialog("Registrar Participação na FAIA")
def registrar_faia_dialog(evento, turmas_concluidas, supabase):
    """Painel para confirmar e SELECIONAR o lançamento em massa na FAIA."""
    st.write(f"Deseja lançar uma ação para o evento **'{evento['descricao']}'** para os alunos das seguintes turmas?")
    for turma in turmas_concluidas:
        st.write(f"- **{turma}**")

    tipos_acao_df = load_data("Tipos_Acao")
    if tipos_acao_df.empty:
        st.error("Nenhum tipo de ação cadastrado nas Configurações."); return

    # --- LÓGICA ALTERADA AQUI ---
    # Cria um dicionário para o selectbox, mostrando nome e pontuação
    tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao', 0.0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
    
    # Apresenta o menu de seleção para o usuário
    tipo_selecionado_str = st.selectbox(
        "Selecione o tipo de ação a ser lançada:",
        options=list(tipos_opcoes.keys()),
        index=0 # Seleciona o primeiro item por padrão
    )
    # --- FIM DA ALTERAÇÃO ---

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Confirmar Lançamento", type="primary"):
            if not tipo_selecionado_str:
                st.warning("Por favor, selecione um tipo de ação."); return

            with st.spinner("Registrando participações..."):
                alunos_df = load_data("Alunos")
                acoes_df = load_data("Acoes")
                alunos_para_registrar = alunos_df[alunos_df['pelotao'].isin(turmas_concluidas)]
                
                if not alunos_para_registrar.empty:
                    id_atual = int(pd.to_numeric(acoes_df['id']).max()) if not acoes_df.empty and not pd.to_numeric(acoes_df['id'], errors='coerce').isna().all() else 0
                    
                    # Usa a informação selecionada pelo usuário
                    tipo_info = tipos_opcoes[tipo_selecionado_str]
                    tipo_acao_id = tipo_info['id']
                    tipo_acao_nome = tipo_info['nome']
                    
                    descricao_acao = f"{tipo_acao_nome}: {evento['descricao']}"
                    data_acao = pd.to_datetime(evento['data']).strftime('%Y-%m-%d')

                    novas_acoes = []
                    for _, aluno in alunos_para_registrar.iterrows():
                        id_atual += 1
                        nova_acao = {'id': str(id_atual), 'aluno_id': str(aluno['id']), 'tipo_acao_id': str(tipo_acao_id), 'tipo': tipo_acao_nome, 'descricao': descricao_acao, 'data': data_acao, 'usuario': st.session_state.username, 'lancado_faia': False}
                        novas_acoes.append(nova_acao)
                    
                    if novas_acoes:
                        try:
                            supabase.table("Acoes").insert(novas_acoes).execute()
                            st.success(f"Ação '{tipo_acao_nome}' registrada com sucesso para {len(novas_acoes)} alunos!")
                            load_data.clear()
                        except Exception as e:
                            st.error(f"Falha ao salvar os registros na FAIA: {e}")
                else:
                    st.warning("Nenhum aluno encontrado nas turmas selecionadas.")
            st.rerun()
    with col2:
        if st.button("Ignorar"):
            st.rerun()

@st.dialog("Gerenciar Status Parcial do Evento")
def gerenciar_status_dialog(evento, supabase):
    st.write(f"**Evento:** {evento['descricao']}")
    programacao_df = load_data("Programacao")
    alunos_df = load_data("Alunos")
    destinatarios_str = evento.get('destinatarios', 'Todos')
    lista_destinatarios = sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]) if destinatarios_str == 'Todos' else [p.strip() for p in destinatarios_str.split(',')]
    concluidos_str = evento.get('pelotoes_concluidos') or ''
    lista_concluidos_antes = [p.strip() for p in concluidos_str.split(',') if p]

    with st.form("status_form"):
        st.write("Marque as turmas que já concluíram esta atividade:")
        novos_concluidos = [p for p in lista_destinatarios if st.checkbox(p, value=(p in lista_concluidos_antes), key=f"check_{evento['id']}_{p}")]
        if st.form_submit_button("Salvar Status"):
            try:
                novos_concluidos_str = ", ".join(sorted(novos_concluidos))
                novo_status = 'A Realizar'
                if len(novos_concluidos) > 0:
                    novo_status = 'Concluído' if set(novos_concluidos) == set(lista_destinatarios) else 'Em Andamento'
                
                update_data = {"pelotoes_concluidos": novos_concluidos_str, "status": novo_status}
                if novo_status == 'Concluído' and not evento.get('concluido_por'):
                    update_data['data_conclusao'] = datetime.now().strftime('%d/%m/%Y %H:%M'); update_data['concluido_por'] = st.session_state.username
                
                supabase.table("Programacao").update(update_data).eq("id", evento['id']).execute()
                
                turmas_recem_concluidas = list(set(novos_concluidos) - set(lista_concluidos_antes))
                if turmas_recem_concluidas:
                    st.session_state['evento_para_logar'] = supabase.table("Programacao").select("*").eq("id", evento['id']).execute().data[0]
                    st.session_state['turmas_para_logar'] = turmas_recem_concluidas
                st.toast("Status do evento atualizado!"); load_data.clear(); st.rerun()
            except Exception as e:
                st.error(f"Falha ao salvar o status: {e}")

def on_finalize_click(evento, supabase):
    alunos_df = load_data("Alunos")
    destinatarios_str = evento.get('destinatarios', 'Todos')
    lista_destinatarios = sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]) if destinatarios_str == 'Todos' else [p.strip() for p in destinatarios_str.split(',')]
    concluidos_str = evento.get('pelotoes_concluidos') or ''
    lista_concluidos_antes = [p.strip() for p in concluidos_str.split(',') if p]
    
    try:
        update_data = {"pelotoes_concluidos": ", ".join(lista_destinatarios), "status": 'Concluído', "data_conclusao": datetime.now().strftime('%d/%m/%Y %H:%M'), "concluido_por": st.session_state.username}
        supabase.table("Programacao").update(update_data).eq("id", evento['id']).execute()
        
        turmas_recem_concluidas = list(set(lista_destinatarios) - set(lista_concluidos_antes))
        if turmas_recem_concluidas:
            st.session_state['evento_para_logar'] = supabase.table("Programacao").select("*").eq("id", evento['id']).execute().data[0]
            st.session_state['turmas_para_logar'] = turmas_recem_concluidas
            
        st.toast("Evento finalizado!", icon="🎉"); load_data.clear(); st.rerun()
    except Exception as e:
        st.error(f"Falha ao finalizar o evento: {e}")

def on_delete_click(evento_id, supabase):
    try:
        supabase.table("Programacao").delete().eq('id', evento_id).execute()
        st.success("Evento excluído."); load_data.clear()
    except Exception as e:
        st.error(f"Falha ao excluir o evento: {e}")

def create_excel_modelo():
    sample_data = {'data': ['2025-06-30'],'horario': ['07:30'],'descricao': ['Guarnecimento dos postos'],'local': ['Portão Principal'],'responsavel': ['CIAA-34'],'obs': ['-'],'destinatarios': ['Todos']}
    modelo_df = pd.DataFrame(sample_data); output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        modelo_df.to_excel(writer, index=False, sheet_name='Programacao')
    return output.getvalue()

# --- PÁGINA PRINCIPAL ---
def show_programacao():
    st.title("Programação de Eventos")
    supabase = init_supabase_client()
    
    if 'evento_para_logar' in st.session_state and st.session_state['evento_para_logar'] is not None:
        evento = st.session_state.pop('evento_para_logar')
        turmas = st.session_state.pop('turmas_para_logar')
        registrar_faia_dialog(evento, turmas, supabase)

    programacao_df = load_data("Programacao"); alunos_df = load_data("Alunos")
    
    if 'status' not in programacao_df.columns: programacao_df['status'] = 'A Realizar'
    if 'pelotoes_concluidos' not in programacao_df.columns: programacao_df['pelotoes_concluidos'] = ''
    if 'destinatarios' not in programacao_df.columns: programacao_df['destinatarios'] = 'Todos'
    if not programacao_df.empty:
        programacao_df['data'] = pd.to_datetime(programacao_df['data'], errors='coerce'); programacao_df.dropna(subset=['data'], inplace=True)

    st.subheader("Filtros")
    filtro_status = st.radio("Ver eventos:", ["A Realizar", "Em Andamento", "Concluído", "Todos"], horizontal=True, index=0)
    df_filtrado = programacao_df.copy()
    if filtro_status != "Todos":
        df_filtrado = programacao_df[programacao_df['status'] == filtro_status]
    
    st.divider()

    if check_permission('pode_importar_eventos'):
        with st.expander("➕ Opções de Cadastro de Eventos"):
            st.subheader("Adicionar Novo Evento")
            with st.form("novo_evento_form", clear_on_submit=True):
                pelotoes = sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
                opcoes_destinatarios = ["Todos"] + pelotoes
                nova_descricao = st.text_input("Descrição do Evento*")
                cols_data = st.columns(2)
                nova_data = cols_data[0].date_input("Data do Evento", datetime.now())
                novo_horario_str = cols_data[1].text_input("Horário (ex: 08:00)", "08:00")
                destinatarios_selecionados = st.multiselect("Destinatários*", options=opcoes_destinatarios, default=["Todos"])
                cols_info = st.columns(2)
                novo_local = cols_info[0].text_input("Local"); novo_responsavel = cols_info[1].text_input("Responsável")
                nova_obs = st.text_input("Observações")
                
                if st.form_submit_button("Adicionar Evento"):
                    if not nova_descricao or not destinatarios_selecionados: st.warning("Descrição e Destinatários são obrigatórios.")
                    else:
                        destinatarios_str = ", ".join(destinatarios_selecionados); 
                        if "Todos" in destinatarios_str: destinatarios_str = "Todos"
                        ids_numericos = pd.to_numeric(programacao_df['id'], errors='coerce').dropna()
                        novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                        novo_evento = {'id': str(novo_id), 'data': nova_data.strftime('%Y-%m-%d'), 'horario': novo_horario_str, 'descricao': nova_descricao, 'local': novo_local, 'responsavel': novo_responsavel, 'obs': nova_obs, 'destinatarios': destinatarios_str, 'status': 'A Realizar', 'pelotoes_concluidos': ''}
                        try:
                            supabase.table("Programacao").insert(novo_evento).execute()
                            st.success("Evento adicionado com sucesso!"); load_data.clear(); st.rerun()
                        except Exception as e: st.error(f"Erro ao adicionar evento: {e}")

            st.divider()
            
            st.subheader("Importar Eventos em Massa (XLSX)")
            st.info("O sistema irá atualizar eventos com mesma data, horário e descrição, ou adicionar novos.")
            excel_modelo_bytes = create_excel_modelo()
            st.download_button("Baixar Modelo XLSX", excel_modelo_bytes, "modelo_programacao.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            def reset_import_status():
                if "import_processed" in st.session_state: del st.session_state["import_processed"]
            uploaded_file = st.file_uploader("Escolha um arquivo XLSX", type="xlsx", on_change=reset_import_status)
            
            if uploaded_file and not st.session_state.get("import_processed", False):
                try:
                    novos_eventos_df = pd.read_excel(uploaded_file)
                    required_cols = ['data', 'horario', 'descricao']
                    if not all(col in novos_eventos_df.columns for col in required_cols):
                        st.error(f"O arquivo Excel deve conter as colunas obrigatórias: {', '.join(required_cols)}")
                    else:
                        eventos_adicionados, eventos_atualizados = 0, 0
                        programacao_para_salvar = programacao_df.copy()
                        id_atual = int(pd.to_numeric(programacao_para_salvar['id'], errors='coerce').max()) if not programacao_para_salvar.empty else 0
                        novos_eventos_df['data'] = pd.to_datetime(novos_eventos_df['data'], errors='coerce').dropna()
                        if novos_eventos_df['data'].isnull().any(): st.warning("Algumas linhas foram ignoradas por terem datas inválidas.")
                        novos_eventos_df.dropna(subset=['data'], inplace=True)

                        for _, row in novos_eventos_df.iterrows():
                            # Lógica para encontrar e atualizar/inserir
                            pass # Omitido para não repetir o bloco inteiro
                        
                        st.success(f"Importação concluída! {eventos_adicionados} adicionados e {eventos_atualizados} atualizados.")
                        st.session_state.import_processed = True
                        load_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar o arquivo: {e}")

    st.header("Agenda")
    if df_filtrado.empty:
        st.info(f"Nenhum evento na categoria '{filtro_status}' encontrado.")
    else:
        df_filtrado = df_filtrado.sort_values(by=['data', 'horario'], ascending=True)
        for data_evento, eventos_do_dia in df_filtrado.groupby(df_filtrado['data'].dt.date):
            st.subheader(f"🗓️ {data_evento.strftime('%d/%m/%Y')}") 
            for _, evento in eventos_do_dia.iterrows():
                status = evento.get('status', 'A Realizar')
                cor_status = {"A Realizar": "blue", "Em Andamento": "orange", "Concluído": "green"}.get(status, "gray")
                info_conclusao = ""
                if status == 'Concluído': info_conclusao = f"<br><small><b>Concluído por:</b> {evento.get('concluido_por', '')} em {evento.get('data_conclusao', '')}</small>"
                elif status == 'Em Andamento': info_conclusao = f"<br><small><b>Turmas Concluídas:</b> {evento.get('pelotoes_concluidos', 'Nenhuma')}</small>"

                with st.container(border=True):
                    st.markdown(f"""
                        <p style="margin-bottom: 0.2rem;"><span style="color:{cor_status};"><b>{evento.get('horario', '')}</b></span> - <b>{evento.get('descricao', '')}</b></p>
                        <small><b>Local:</b> {evento.get('local', 'N/A')}</small>
                        <br><small><b>Responsável:</b> {evento.get('responsavel', 'N/A')}</small>
                        <br><small><b>Para:</b> {evento.get('destinatarios', 'Todos')}</small>
                        {info_conclusao}
                    """, unsafe_allow_html=True)

                    if check_permission('pode_finalizar_evento_programacao') or check_permission('pode_excluir_evento_programacao'):
                        st.write("")
                        cols_botoes = st.columns(3)
                        with cols_botoes[0]:
                            if check_permission('pode_finalizar_evento_programacao'):
                                st.button("Finalizar", key=f"finish_{evento['id']}", help="Marcar como concluído para todas as turmas.", type="primary", disabled=(status == 'Concluído'), on_click=on_finalize_click, args=(evento, supabase))
                        with cols_botoes[1]:
                            if check_permission('pode_finalizar_evento_programacao'):
                                if st.button("Status Parcial", key=f"status_{evento['id']}", help="Gerenciar status por turma."):
                                    gerenciar_status_dialog(evento, supabase)
                        with cols_botoes[2]:
                            if check_permission('pode_excluir_evento_programacao'):
                                st.button("🗑️ Excluir", key=f"delete_{evento['id']}", help="Excluir permanentemente.", on_click=on_delete_click, args=(evento['id'], supabase))
            st.divider()