# rancho_pernoite.py

import streamlit as st
import pandas as pd
import base64
from auth import check_permission
import json
import requests # Certifique-se de que a biblioteca requests está instalada

# --- Configurações da API ---
API_URL = st.secrets.get("google_sheets_api", {}).get("url", "URL_NAO_CONFIGURADA")
API_KEY = st.secrets.get("google_sheets_api", {}).get("key", "CHAVE_NAO_CONFIGURADA")

def call_api(payload):
    """Função central para chamar a API do Google Apps Script."""
    try:
        payload['apiKey'] = API_KEY
        response = requests.post(API_URL, json=payload, timeout=30) # Aumentado o timeout
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API: {e}")
        return None
    except json.JSONDecodeError:
        st.error(f"Erro: A resposta da API não é um JSON válido. Verifique o URL e o script. Resposta recebida: {response.text}")
        return None

def relatorio_pernoite_tab():
    """Renderiza a aba para o Relatório de Pernoite com as novas funcionalidades."""
    st.subheader("Gerar Relatório de Pernoite em PDF")

    # Carrega as semanas disponíveis ao iniciar
    if 'available_weeks' not in st.session_state:
        with st.spinner("A buscar semanas disponíveis..."):
            response = call_api({"action": "get_available_weeks"})
            if response and response.get("status") == "success":
                st.session_state.available_weeks = response.get("weeks", [])
            else:
                st.session_state.available_weeks = []
                st.error("Não foi possível carregar a lista de semanas.")

    if not st.session_state.get('available_weeks'):
        st.warning("Nenhuma semana encontrada para gerar relatórios.")
        return

    # 1. SELEÇÃO DA SEMANA
    semana_selecionada = st.selectbox(
        "Primeiro, selecione a semana para a qual deseja gerar os relatórios:",
        st.session_state.available_weeks
    )

    # 2. ÁREA PARA INSERIR CABEÇALHO
    st.markdown("---")
    cabecalho_pdf = st.text_input(
        "Cabeçalho Personalizado para o PDF (Opcional)",
        placeholder="Ex: RELATÓRIO DE PERNOITE - CURSO DE FORMAÇÃO 2025"
    )
    st.markdown("---")


    if semana_selecionada:
        dias_semana = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]

        # 3. DIAS DA SEMANA EXPANSÍVEIS
        for dia in dias_semana:
            with st.expander(f"▶️ {dia}"):
                col1, col2 = st.columns([2, 1])

                with col1:
                    st.markdown(f"**Pré-visualização dos militares em pernoite na {dia}:**")
                    # Lógica para mostrar a pré-visualização
                    if st.button(f"Carregar Pré-visualização de {dia}", key=f"preview_{dia}"):
                        with st.spinner(f"A buscar dados de {dia}..."):
                            payload = {"action": "get_pernoite_data", "semana": semana_selecionada, "dia": dia}
                            response = call_api(payload)
                            if response and response.get("status") == "success":
                                pernoite_data = response.get("data", [])
                                st.session_state[f"pernoite_data_{dia}"] = pernoite_data
                            else:
                                st.error(f"Falha ao buscar dados: {response.get('message', 'Erro desconhecido')}")

                    if f"pernoite_data_{dia}" in st.session_state:
                        pernoite_data = st.session_state[f"pernoite_data_{dia}"]
                        if pernoite_data:
                            df_pernoite = pd.DataFrame(pernoite_data, columns=["Pelotão/Militar"])
                            st.dataframe(df_pernoite, hide_index=True, use_container_width=True)
                            # 4. QUANTITATIVO DE ALUNOS
                            st.info(f"**Total em pernoite neste dia: {len(df_pernoite)}**")
                        else:
                            st.info("Nenhum militar em pernoite para este dia.")

                with col2:
                    st.write("") # Espaçamento
                    # 5. BOTÃO DE EXPORTAÇÃO INDIVIDUAL POR DIA
                    if st.button(f"📥 Gerar PDF de {dia}", key=f"pdf_{dia}", type="primary", use_container_width=True):
                        with st.spinner(f"A gerar o PDF para {dia}, por favor aguarde..."):
                            payload = {
                                "action": "get_pernoite_pdf",
                                "semana": semana_selecionada,
                                "dia": dia,
                                "cabecalho": cabecalho_pdf
                            }
                            response_data = call_api(payload)

                            if response_data and response_data.get("status") == "success":
                                pdf_bytes = base64.b64decode(response_data['pdf_base64'])
                                st.download_button(
                                    label=f"✅ Baixar {response_data['filename']}",
                                    data=pdf_bytes,
                                    file_name=response_data['filename'],
                                    mime="application/pdf",
                                    key=f"download_{dia}"
                                )
                            elif response_data:
                                st.error(f"Falha ao gerar o PDF: {response_data.get('message')}")


def consolidado_diario_tab():
    """Renderiza a aba para o Consolidado Diário."""
    st.subheader("Visualizar Consolidado Diário por Semana")

    if 'available_weeks' not in st.session_state or not st.session_state.available_weeks:
        st.warning("Lista de semanas não carregada. Verifique a aba de Pernoite primeiro ou recarregue a página.")
        return

    semana_selecionada = st.selectbox("Selecione a semana:", st.session_state.available_weeks, key="consolidado_week_select")

    if st.button("Buscar Dados", type="primary"):
        with st.spinner(f"A buscar dados para a {semana_selecionada}..."):
            payload = {"action": "get_consolidado_data", "semana": semana_selecionada}
            response_data = call_api(payload)

            if response_data and response_data.get("status") == "success":
                dados = response_data.get("data", [])
                if dados and len(dados) > 1:
                    df = pd.DataFrame(dados[1:], columns=dados[0])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    st.success("Dados carregados com sucesso!")
                else:
                    st.info("Não foram encontrados dados de refeições para a semana selecionada.")
            elif response_data:
                st.error(f"Falha ao buscar dados: {response_data.get('message', 'Erro desconhecido')}")


def show_rancho_pernoite():
    """Função principal que renderiza a página."""
    st.title("📅 Relatórios de Rancho e Pernoite")

    if not check_permission('acesso_pagina_rancho_pernoite'):
        st.error("Acesso negado."); return

    if API_URL == "URL_NAO_CONFIGURADA" or API_KEY == "CHAVE_NAO_CONFIGURADA":
        st.error("A API do Google Sheets não está configurada nos segredos do Streamlit."); return

    tab1, tab2 = st.tabs(["Relatório de Pernoite", "Consolidado Diário"])
    with tab1:
        relatorio_pernoite_tab()
    with tab2:
        consolidado_diario_tab()
