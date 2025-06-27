# ficheiro: programacao.py

import streamlit as st
import pandas as pd
from datetime import datetime, time
from database import load_data, save_data

def show_programacao():
    st.title("Programação de Eventos")

    # Carrega os dados da programação
    programacao_df = load_data("Sistema_Acoes_Militares", "Programacao")

    # --- SUGESTÃO IMPLEMENTADA: Filtros Avançados ---
    st.subheader("Filtros")
    filtro_status = st.radio(
        "Ver eventos:",
        ["A Realizar", "Concluídos", "Todos"],
        horizontal=True,
        index=0  # Padrão para "A Realizar"
    )

    # Garante que a coluna 'concluida' seja booleana
    if not programacao_df.empty:
        programacao_df['concluida'] = programacao_df['concluida'].apply(
            lambda x: str(x).strip().lower() in ['true', '1', 't', 'y', 'yes', 'sim']
        )

    # Aplica o filtro de status
    if filtro_status == "A Realizar":
        df_filtrado = programacao_df[~programacao_df['concluida']]
    elif filtro_status == "Concluídos":
        df_filtrado = programacao_df[programacao_df['concluida']]
    else:
        df_filtrado = programacao_df
    
    st.divider()

    # Formulário para adicionar novo evento (dentro de um expander)
    with st.expander("➕ Adicionar Novo Evento"):
        with st.form("novo_evento_form", clear_on_submit=True):
            st.subheader("Detalhes do Evento")
            
            cols_data = st.columns(2)
            nova_data = cols_data[0].date_input("Data do Evento", datetime.now())
            novo_horario = cols_data[1].time_input("Horário", time(8, 0))
            
            nova_descricao = st.text_input("Descrição do Evento*")
            
            cols_info = st.columns(3)
            novo_local = cols_info[0].text_input("Local")
            novo_responsavel = cols_info[1].text_input("Responsável")
            nova_obs = cols_info[2].text_input("Observações")
            
            submitted = st.form_submit_button("Adicionar Evento")
            if submitted:
                if not nova_descricao:
                    st.warning("A descrição é obrigatória para adicionar um evento.")
                else:
                    # Lógica para gerar novo ID
                    if 'id' not in programacao_df.columns or programacao_df.empty:
                        novo_id = 1
                    else:
                        ids_numericos = pd.to_numeric(programacao_df['id'], errors='coerce').dropna()
                        novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                    
                    novo_evento = pd.DataFrame([{
                        'id': str(novo_id),
                        'data': nova_data.strftime('%Y-%m-%d'),
                        'horario': novo_horario.strftime('%H:%M'),
                        'descricao': nova_descricao,
                        'local': novo_local,
                        'responsavel': novo_responsavel,
                        'obs': nova_obs,
                        'concluida': False
                    }])
                    
                    programacao_df_atualizado = pd.concat([programacao_df, novo_evento], ignore_index=True)
                    
                    if save_data("Sistema_Acoes_Militares", "Programacao", programacao_df_atualizado):
                        st.success("Evento adicionado com sucesso!")
                        st.rerun()
                    else:
                        st.error("Falha ao salvar o novo evento.")

    # --- SUGESTÃO IMPLEMENTADA: Agrupamento por Data ---
    st.header("Agenda")
    if df_filtrado.empty:
        st.info(f"Nenhum evento na categoria '{filtro_status}' encontrado.")
    else:
        # Garante que a data é do tipo datetime para ordenação
        df_filtrado['data'] = pd.to_datetime(df_filtrado['data'], errors='coerce')
        df_filtrado = df_filtrado.sort_values(by=['data', 'horario'], ascending=True)

        # Agrupa os eventos por data para exibição organizada
        for data_evento, eventos_do_dia in df_filtrado.groupby(df_filtrado['data'].dt.date):
            # Usando uma biblioteca para traduzir o dia da semana seria ideal, mas strftime é universal
            st.subheader(f"🗓️ {data_evento.strftime('%d/%m/%Y')}") 
            
            for _, evento in eventos_do_dia.iterrows():
                col_check, col_desc, col_delete = st.columns([1, 10, 1])
                
                with col_check:
                    status_atual = evento['concluida']
                    # Chave única para o checkbox
                    novo_status = st.checkbox("", value=status_atual, key=f"check_{evento['id']}")
                    if novo_status != status_atual:
                        programacao_df.loc[programacao_df['id'] == evento['id'], 'concluida'] = novo_status
                        if save_data("Sistema_Acoes_Militares", "Programacao", programacao_df):
                            st.rerun()
                        else:
                            st.error("Não foi possível atualizar o estado do evento.")

                with col_desc:
                    text_style = "text-decoration: line-through; opacity: 0.6;" if evento['concluida'] else ""
                    cor_horario = "green" if evento['concluida'] else "blue"
                    st.markdown(f"""
                        <div style="{text_style}">
                            <span style="color:{cor_horario};"><b>{evento.get('horario', '')}</b></span> - <b>{evento.get('descricao', '')}</b>
                            <br>
                            <small><b>Local:</b> {evento.get('local', 'N/A')} | <b>Responsável:</b> {evento.get('responsavel', 'N/A')} | <b>Obs:</b> <i>{evento.get('obs', '')}</i></small>
                        </div>
                        """, unsafe_allow_html=True)

                with col_delete:
                    # Chave única para o botão de exclusão
                    if st.button("🗑️", key=f"delete_{evento['id']}", help="Excluir este evento"):
                        df_para_salvar = programacao_df[programacao_df['id'] != evento['id']]
                        if save_data("Sistema_Acoes_Militares", "Programacao", df_para_salvar):
                            st.success(f"Evento '{evento['descricao']}' excluído.")
                            st.rerun()
                        else:
                            st.error("Falha ao excluir o evento.")
            st.divider()