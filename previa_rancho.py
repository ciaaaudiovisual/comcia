# previa_rancho.py

import streamlit as st
import pandas as pd
import json
import requests
from auth import check_permission

# --- Configurações da API ---
API_URL = st.secrets.get("google_sheets_api", {}).get("url", "URL_NAO_CONFIGURADA")
API_KEY = st.secrets.get("google_sheets_api", {}).get("key", "CHAVE_NAO_CONFIGURADA")

def call_api(payload):
    """Função central para chamar a API do Google Apps Script."""
    try:
        payload['apiKey'] = API_KEY
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Erro de conexão com a API do Google Sheets: {e}")
        return None

def show_previa_rancho():
    """Página principal do módulo de Prévia de Rancho."""
    st.title("🥩 Prévia de Rancho (via Google Sheets)")

    if API_URL == "URL_NAO_CONFIGURADA" or API_KEY == "CHAVE_NAO_CONFIGURADA":
        st.error("A API do Google Sheets não está configurada nos segredos do Streamlit."); return

    # Carrega as semanas disponíveis
    with st.spinner("A buscar semanas disponíveis..."):
        response = call_api({"action": "get_available_weeks"})
        if response and response.get("status") == "success":
            available_weeks = response.get("weeks", [])
        else:
            available_weeks = []
            st.error("Não foi possível carregar a lista de semanas do Google Sheets.")

    if not available_weeks:
        st.warning("Nenhuma semana encontrada na planilha de respostas."); return
    
    st.subheader("Selecione a semana para ver o consolidado")
    semana_selecionada = st.selectbox("Selecione a semana:", available_weeks)

    if st.button("Buscar Dados da Prévia", type="primary"):
        with st.spinner(f"A buscar dados para a {semana_selecionada}..."):
            payload = {"action": "get_consolidado_data", "semana": semana_selecionada}
            response_data = call_api(payload)

            if response_data and response_data.get("status") == "success":
                dados = response_data.get("data", [])
                if dados and len(dados) > 1:
                    df = pd.DataFrame(dados[1:], columns=dados[0])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.info("Não foram encontrados dados de refeições para a semana selecionada.")
            elif response_data:
                st.error(f"Falha ao buscar dados: {response_data.get('message', 'Erro desconhecido')}")
