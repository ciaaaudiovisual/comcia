import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
import time
from io import BytesIO
import xlsxwriter

# ==============================================================================
# DIÁLOGOS E FUNÇÕES DE CALLBACK
# ==============================================================================

@st.dialog("Alterar Data e Horário do Evento")
def edit_event_dialog(evento, supabase):
    """Diálogo para editar a data e o horário de um evento existente."""
    st.write(f"Editando evento: **{evento['descricao']}**")
    with st.form("edit_event_form"):
        try:
            current_date = pd.to_datetime(evento['data']).date()
        except:
            current_date = datetime.now().date()
        
        current_time = evento.get('horario', '08:00')

        cols = st.columns(2)
        new_date = cols[0].date_input("Nova Data", value=current_date)
        new_time = cols[1].text_input("Novo Horário", value=current_time)

        if st.form_submit_button("Salvar Alterações"):
            try:
                update_data = {
                    "data": new_date.strftime('%Y-%m-%d'),
                    "horario": new_time
                }
                supabase.table("Programacao").update(update_data).eq("id", evento['id']).execute()
                st.success("Evento atualizado com sucesso!")
                load_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Falha ao atualizar o evento: {e}")

@st.dialog("Finalizar Evento e Lançar na FAIA")
def registrar_faia_dialog(evento, turmas_concluidas, supabase):
    """Popup para finalizar o evento e, opcionalmente, lançar uma ação na FAIA."""
    st.write(f"Finalizando o evento **'{evento['descricao']}'** para os alunos das seguintes turmas:")
    for turma in turmas_concluidas:
        st.write(f"- **{turma}**")
    st.divider()
    st.write("Se desejar, pode lançar uma ação para estes alunos.")

    tipos_acao_df = load_data("Tipos_Acao")
    if tipos_acao_df.empty:
        st.error("Nenhum tipo de ação cadastrado."); return

    # Filtra apenas ações neutras (pontuação 0)
    tipos_acao_df['pontuacao'] = pd.to_numeric(tipos_acao_df['pontuacao'], errors='coerce').fillna(0)
    acoes_neutras_df = tipos_acao_df[tipos_acao_df['pontuacao'] == 0].sort_values('nome')
    
    if acoes_neutras_df.empty:
        st.warning("Nenhuma ação do tipo 'Neutra' (pontuação 0) encontrada nas configurações.")
    
    tipos_opcoes = {f"{tipo['nome']}": tipo for _, tipo in acoes_neutras_df.iterrows()}
    opcoes_labels = list(tipos_opcoes.keys())

    # Procura por uma opção que contenha "presença em instrução" para ser o padrão
    default_index = 0
    try:
        default_option = next(s for s in opcoes_labels if "presença em instrução" in s.lower())
        default_index = opcoes_labels.index(default_option)
    except StopIteration:
        default_index = 0

    tipo_selecionado_str = st.selectbox(
        "Selecione o tipo de ação a ser lançada:",
        options=opcoes_labels,
        index=default_index
    )
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apenas FINALIZAR", type="secondary"):
            try:
                update_data = {"status": 'Concluído', "concluido_por": st.session_state.username, "data_conclusao": datetime.now().strftime('%d/%m/%Y %H:%M')}
                supabase.table("Programacao").update(update_data).eq("id", evento['id']).execute()
                st.toast("Evento finalizado com sucesso!"); load_data.clear()
            except Exception as e:
                st.error(f"Falha ao finalizar o evento: {e}")
            st.rerun()
            
    with col2:
        if st.button("FINALIZAR E LANÇAR NA FAIA", type="primary"):
            if not tipo_selecionado_str:
                st.warning("Por favor, selecione um tipo de ação."); return

            with st.spinner("Finalizando evento e registrando participações..."):
                update_data = {"status": 'Concluído', "concluido_por": st.session_state.username, "data_conclusao": datetime.now().strftime('%d/%m/%Y %H:%M')}
                supabase.table("Programacao").update(update_data).eq("id", evento['id']).execute()

                alunos_df = load_data("Alunos")
                acoes_df = load_data("Acoes")
                alunos_para_registrar = alunos_df[alunos_df['pelotao'].isin(turmas_concluidas)]
                
                if not alunos_para_registrar.empty:
                    response = supabase.table("Acoes").select("id", count='exact').execute()
                    ids_existentes = [int(item['id']) for item in response.data if str(item.get('id')).isdigit()]
                    id_atual = max(ids_existentes) if ids_existentes else 0
                    
                    tipo_info = tipos_opcoes[tipo_selecionado_str]
                    tipo_acao_id = tipo_info['id']
                    tipo_acao_nome = tipo_info['nome']
                    
                    descricao_acao = f"{tipo_acao_nome}: {evento['descricao']}"
                    data_acao = pd.to_datetime(evento['data']).strftime('%Y-%m-%d')

                    novas_acoes = []
                    for _, aluno in alunos_para_registrar.iterrows():
                        id_atual += 1
                        nova_acao = {
                            'id': str(id_atual), 
                            'aluno_id': str(aluno['id']), 
                            'tipo_acao_id': str(tipo_acao_id), 
                            'tipo': tipo_acao_nome, 
                            'descricao': descricao_acao, 
                            'data': data_acao, 
                            'usuario': st.session_state.username, 
                            'status': 'Lançado' # Define o status como Lançado diretamente
                        }
                        novas_acoes.append(nova_acao)
                                        
                    if novas_acoes:
                        try:
                            supabase.table("Acoes").insert(novas_acoes).execute()
                            st.success(f"Ação '{tipo_acao_nome}' registrada para {len(novas_acoes)} alunos!")
                            load_data.clear()
                            time.sleep(2)
                        except Exception as e:
                            st.error(f"Falha ao salvar os registros na FAIA: {e}")
                            time.sleep(2)
                else:
                    st.warning("Nenhum aluno encontrado nas turmas selecionadas para lançar na FAIA.")
                    time.sleep(2)
            st.rerun()

@st.dialog("Gerenciar Status Parcial do Evento")
def gerenciar_status_dialog(evento, supabase):
    st.write(f"**Evento:** {evento['descricao']}")
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
                    update_data['data_conclusao'] = datetime.now().strftime('%d/%m/%Y %H:%M')
                    update_data['concluido_por'] = st.session_state.username
                
                supabase.table("Programacao").update(update_data).eq("id", evento['id']).execute()
                
                turmas_recem_concluidas = list(set(novos_concluidos) - set(lista_concluidos_antes))
                if turmas_recem_concluidas:
                    st.session_state['evento_para_logar'] = supabase.table("Programacao").select("*").eq("id", evento['id']).execute().data[0]
                    st.session_state['turmas_para_logar'] = turmas_recem_concluidas
                st.toast("Status do evento atualizado!")
                load_data.clear()
            except Exception as e:
                st.error(f"Falha ao salvar o status: {e}")

def on_delete_click(evento_id, supabase):
    try:
        supabase.table("Programacao").delete().eq('id', evento_id).execute()
        st.success("Evento excluído.")
        load_data.clear()
    except Exception as e:
        st.error(f"Falha ao excluir o evento: {e}")

def create_excel_modelo():
    sample_data = {'data': ['2025-07-01'],'horario': ['07:30'],'descricao': ['Guarnecimento dos postos'],'local': ['Portão Principal'],'responsavel': ['CIAA-34'],'obs': ['-'],'destinatarios': ['Todos']}
    modelo_df = pd.DataFrame(sample_data); output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        modelo_df.to_excel(writer, index=False, sheet_name='Programacao')
    return output.getvalue()

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_programacao():
    st.title("Programação de Eventos")
    supabase = init_supabase_client()
    
    if 'evento_para_logar' in st.session_state and st.session_state['evento_para_logar'] is not None:
        evento = st.session_state.pop('evento_para_logar')
        turmas = st.session_state.pop('turmas_para_logar')
        registrar_faia_dialog(evento, turmas, supabase)

    programacao_df = load_data("Programacao")
    alunos_df = load_data("Alunos")
    
    if 'status' not in programacao_df.columns: programacao_df['status'] = 'A Realizar'
    if not programacao_df.empty:
        programacao_df['data'] = pd.to_datetime(programacao_df['data'], errors='coerce')
        programacao_df.dropna(subset=['data'], inplace=True)

    st.info("Presença Diária 6:30 | 7:00 Café | 12:00 Almoço | 17:40 Jantar | 21:00 Ceia")
    
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
                novo_local = cols_info[0].text_input("Local")
                novo_responsavel = cols_info[1].text_input("Responsável")
                nova_obs = st.text_input("Observações")
                
                if st.form_submit_button("Adicionar Evento"):
                    if not nova_descricao or not destinatarios_selecionados: 
                        st.warning("Descrição e Destinatários são obrigatórios.")
                    else:
                        destinatarios_str = ", ".join(destinatarios_selecionados) 
                        if "Todos" in destinatarios_str: destinatarios_str = "Todos"
                        
                        ids_numericos = pd.to_numeric(programacao_df['id'], errors='coerce').dropna()
                        novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                        
                        novo_evento = {
                            'id': str(novo_id), 'data': nova_data.strftime('%Y-%m-%d'), 
                            'horario': novo_horario_str, 'descricao': nova_descricao, 
                            'local': novo_local, 'responsavel': novo_responsavel, 
                            'obs': nova_obs, 'destinatarios': destinatarios_str, 
                            'status': 'A Realizar', 'pelotoes_concluidos': ''
                        }
                        try:
                            supabase.table("Programacao").insert(novo_evento).execute()
                            st.success("Evento adicionado com sucesso!"); load_data.clear(); st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao adicionar evento: {e}")

            st.divider()
            
            st.subheader("Importar Eventos em Massa (XLSX)")
            st.info("O sistema irá atualizar eventos com mesma data, horário e descrição, ou adicionar novos.")
            excel_modelo_bytes = create_excel_modelo()
            st.download_button("Baixar Modelo XLSX", excel_modelo_bytes, "modelo_programacao.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            uploaded_file = st.file_uploader("Escolha um arquivo XLSX", type="xlsx")
            if uploaded_file:
                try:
                    with st.spinner("Processando o ficheiro..."):
                        df_import = pd.read_excel(uploaded_file)
                        required_cols = ['data', 'horario', 'descricao']
                        if not all(col in df_import.columns for col in required_cols):
                            st.error(f"O ficheiro deve conter as colunas obrigatórias: {', '.join(required_cols)}")
                        else:
                            registros_para_upsert = []
                            programacao_atual = load_data("Programacao")
                            
                            programacao_atual['data'] = pd.to_datetime(programacao_atual['data'], errors='coerce')
                            programacao_atual['horario'] = programacao_atual['horario'].astype(str).str.strip()
                            programacao_atual['descricao'] = programacao_atual['descricao'].astype(str).str.strip()
                            
                            ids_existentes = pd.to_numeric(programacao_atual['id'], errors='coerce').dropna()
                            id_atual = int(ids_existentes.max()) if not ids_existentes.empty else 0

                            for _, row in df_import.iterrows():
                                try:
                                    row_data = pd.to_datetime(row['data']).date()
                                except Exception:
                                    continue
                                    
                                row_horario = str(row.get('horario', '')).strip()
                                row_descricao = str(row.get('descricao', '')).strip()

                                match = programacao_atual[
                                    (programacao_atual['data'].dt.date == row_data) &
                                    (programacao_atual['horario'] == row_horario) &
                                    (programacao_atual['descricao'] == row_descricao)
                                ]
                                
                                if not match.empty:
                                    id_evento = match.iloc[0]['id']
                                    registro = row.to_dict()
                                    registro['id'] = id_evento
                                else:
                                    id_atual += 1
                                    registro = row.to_dict()
                                    registro['id'] = str(id_atual)
                                    registro['status'] = 'A Realizar'
                                    registro['pelotoes_concluidos'] = ''
                                
                                registro['data'] = row_data.strftime('%Y-%m-%d')
                                registros_para_upsert.append(registro)

                            if registros_para_upsert:
                                supabase.table("Programacao").upsert(registros_para_upsert, on_conflict='id').execute()
                                st.success(f"Importação concluída! {len(registros_para_upsert)} eventos foram processados.")
                                load_data.clear(); st.rerun()
                except Exception as e:
                    st.error(f"Erro ao processar o ficheiro: {e}")
            
    st.header("Agenda")
    
    if filtro_status not in ["Concluído", "Todos"]:
        conclusao_por_data = df_filtrado.groupby(df_filtrado['data'].dt.date)['status'].apply(lambda x: (x == 'Concluído').all())
        if not conclusao_por_data.empty:
            datas_para_mostrar = conclusao_por_data[~conclusao_por_data].index
            df_filtrado = df_filtrado[df_filtrado['data'].dt.date.isin(datas_para_mostrar)]

    if df_filtrado.empty:
        st.info(f"Nenhum evento na categoria '{filtro_status}' encontrado.")
    else:
        df_filtrado = df_filtrado.sort_values(by=['data', 'horario'], ascending=True)
        for data_evento, eventos_do_dia in df_filtrado.groupby(df_filtrado['data'].dt.date):
            
            with st.expander(f"🗓️ {data_evento.strftime('%d/%m/%Y')} - ({len(eventos_do_dia)} evento(s))"):
                for _, evento in eventos_do_dia.iterrows():
                    status = evento.get('status', 'A Realizar')
                    cor_status = {"A Realizar": "blue", "Em Andamento": "orange", "Concluído": "green"}.get(status, "gray")
                    info_conclusao = ""
                    if status == 'Concluído': 
                        info_conclusao = f"<br><small><b>Concluído por:</b> {evento.get('concluido_por', '')} em {evento.get('data_conclusao', '')}</small>"
                    elif status == 'Em Andamento': 
                        info_conclusao = f"<br><small><b>Turmas Concluídas:</b> {evento.get('pelotoes_concluidos', 'Nenhuma')}</small>"

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
                            cols_botoes = st.columns(4)
                            
                            with cols_botoes[0]:
                                if check_permission('pode_finalizar_evento_programacao'):
                                    if st.button("Finalizar", key=f"finish_{evento['id']}", help="Finalizar este evento para todas as turmas.", type="primary", disabled=(status == 'Concluído')):
                                        destinatarios_str = evento.get('destinatarios', 'Todos')
                                        turmas_evento = sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]) if destinatarios_str == 'Todos' else [p.strip() for p in destinatarios_str.split(',')]
                                        registrar_faia_dialog(evento, turmas_evento, supabase)
                            
                            with cols_botoes[1]:
                                if check_permission('pode_finalizar_evento_programacao'):
                                    if st.button("Feito Parcialmente", key=f"status_{evento['id']}", help="Gerenciar status por turma."):
                                        gerenciar_status_dialog(evento, supabase)
                            
                            with cols_botoes[2]:
                                if check_permission('pode_finalizar_evento_programacao'): 
                                    if st.button("✏️ Alterar", key=f"edit_{evento['id']}", help="Alterar data e horário"):
                                        edit_event_dialog(evento, supabase)

                            with cols_botoes[3]:
                                if check_permission('pode_excluir_evento_programacao'):
                                    st.button("🗑️ Excluir", key=f"delete_{evento['id']}", help="Excluir permanentemente.", on_click=on_delete_click, args=(evento['id'], supabase))
                    st.divider()
