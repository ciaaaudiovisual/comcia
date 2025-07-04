# saude.py

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data

def show_saude():
    st.title("⚕️ Módulo de Saúde")
    st.markdown("Controle centralizado de eventos de saúde e dispensas médicas.")
    
    # Carrega os dados necessários
    try:
        acoes_df = load_data("Acoes")
        alunos_df = load_data("Alunos")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # --- 1. Filtro de Ações de Saúde ---
    tipos_de_saude = ["Enfermaria", "Hospital", "NAS"] # Adicione outros tipos se necessário
    
    if 'tipo' not in acoes_df.columns:
        st.error("A tabela 'Acoes' não contém a coluna 'tipo'. Impossível filtrar eventos de saúde.")
        return
        
    acoes_saude_df = acoes_df[acoes_df['tipo'].isin(tipos_de_saude)].copy()
    
    if acoes_saude_df.empty:
        st.info("Nenhum evento de saúde (Enfermaria, Hospital, NAS) foi registrado ainda.")
        return

    # Junta com os nomes dos alunos para fácil identificação
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
    
    # --- 2. Exibição dos Eventos de Saúde ---
    st.subheader("Histórico de Eventos de Saúde")
    
    for _, acao in acoes_com_nomes_df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.markdown(f"##### {acao.get('nome_guerra', 'N/A')} ({acao.get('pelotao', 'N/A')})")
                st.markdown(f"**Evento:** {acao.get('tipo', 'N/A')}")
                st.caption(f"Data do Registro: {acao['data'].strftime('%d/%m/%Y')}")
                if acao.get('descricao'):
                    st.caption(f"Observação: {acao.get('descricao')}")
            
            with col2:
                # Verifica se o aluno está dispensado nesta ação específica
                if acao.get('esta_dispensado'):
                    inicio_str = pd.to_datetime(acao.get('periodo_dispensa_inicio')).strftime('%d/%m/%y') if pd.notna(acao.get('periodo_dispensa_inicio')) else "N/A"
                    fim_str = pd.to_datetime(acao.get('periodo_dispensa_fim')).strftime('%d/%m/%y') if pd.notna(acao.get('periodo_dispensa_fim')) else "N/A"
                    
                    st.error(f"**DISPENSADO**", icon="⚕️")
                    st.markdown(f"**Período:** {inicio_str} a {fim_str}")
                    st.caption(f"Tipo: {acao.get('tipo_dispensa', 'Não especificado')}")
                else:
                    st.success("**SEM DISPENSA**", icon="✅")
