import streamlit as st
import requests
import pandas as pd
import base64
from auth import check_permission
import json

# --- Configurações da API ---
# Estes valores serão lidos do seu ficheiro de segredos (secrets.toml)
API_URL = st.secrets.get("google_sheets_api", {}).get("url", "URL_NAO_CONFIGURADA")
API_KEY = st.secrets.get("google_sheets_api", {}).get("key", "CHAVE_NAO_CONFIGURADA")

def call_api(payload):
    """Função central para chamar a API do Google Apps Script."""
    try:
        payload['apiKey'] = API_KEY
        response = requests.post(API_URL, json=payload)
        response.raise_for_status()  # Lança um erro para códigos de status ruins (4xx ou 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Erro: A resposta da API não é um JSON válido. Verifique a URL e a implementação do Apps Script.")
        st.code(response.text, language='text')
        return None

def relatorio_pernoite_tab():
    """Renderiza a aba para o Relatório de Pernoite."""
    st.subheader("Gerar Relatório de Pernoite em PDF")

    dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]
    dia_selecionado = st.selectbox("Selecione o dia da semana:", dias_semana)

    if st.button("Gerar PDF", type="primary"):
        with st.spinner("A gerar o relatório em PDF, por favor aguarde..."):
            payload = {
                "action": "get_pernoite_pdf",
                "dia": dia_selecionado
            }
            response_data = call_api(payload)

            if response_data and response_data.get("status") == "success":
                st.session_state.pdf_data = response_data
                st.success("Relatório em PDF gerado com sucesso!")
            elif response_data:
                st.error(f"Falha ao gerar o PDF: {response_data.get('message')}")

    if 'pdf_data' in st.session_state and st.session_state.pdf_data:
        pdf_info = st.session_state.pdf_data
        pdf_bytes = base64.b64decode(pdf_info['pdf_base64'])
        st.download_button(
            label=f"📥 Baixar {pdf_info['filename']}",
            data=pdf_bytes,
            file_name=pdf_info['filename'],
            mime="application/pdf"
        )

def consolidado_diario_tab():
    """Renderiza a aba para o Consolidado Diário."""
    st.subheader("Visualizar Consolidado Diário por Semana")

    # Busca as semanas disponíveis ao carregar a aba
    if 'available_weeks' not in st.session_state:
        with st.spinner("A buscar semanas disponíveis..."):
            payload = {"action": "get_available_weeks"}
            response_data = call_api(payload)
            if response_data and response_data.get("status") == "success":
                st.session_state.available_weeks = response_data.get("weeks", [])
            else:
                st.session_state.available_weeks = []
                st.error("Não foi possível carregar a lista de semanas.")

    if not st.session_state.get('available_weeks'):
        st.warning("Nenhuma semana encontrada na planilha.")
        return
        
    semana_selecionada = st.selectbox("Selecione a semana:", st.session_state.available_weeks)

    if st.button("Buscar Dados", type="primary"):
        with st.spinner(f"A buscar dados para a {semana_selecionada}..."):
            payload = {
                "action": "get_consolidado_data",
                "semana": semana_selecionada
            }
            response_data = call_api(payload)

            if response_data and response_data.get("status") == "success":
                st.session_state.consolidado_data = response_data.get("data", [])
            elif response_data:
                st.session_state.consolidado_data = []
                st.error(f"Falha ao buscar dados: {response_data.get('message')}")

    if 'consolidado_data' in st.session_state and st.session_state.consolidado_data:
        data = st.session_state.consolidado_data
        # Converte para DataFrame do Pandas para melhor exibição
        df = pd.DataFrame(data[1:], columns=data[0])
        st.dataframe(df, use_container_width=True, hide_index=True)

def show_rancho_pernoite():
    """Função principal que renderiza a página."""
    st.title("📅 Relatórios de Rancho e Pernoite")
    
    if not check_permission('acesso_pagina_rancho_pernoite'):
        st.error("Acesso negado.")
        return

    if API_URL == "URL_NAO_CONFIGURADA" or API_KEY == "CHAVE_NAO_CONFIGURADA":
        st.error("A API do Google Sheets não está configurada. Por favor, adicione a URL e a Chave de API aos segredos do Streamlit.")
        return

    tab1, tab2 = st.tabs(["Relatório de Pernoite", "Consolidado Diário"])

    with tab1:
        relatorio_pernoite_tab()

    with tab2:
        consolidado_diario_tab()
