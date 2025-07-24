# previa_rancho.py
import streamlit as st
import pandas as pd
import requests

# --- Configurações da API ---
# É recomendado que a URL e a Chave fiquem nos segredos do Streamlit (secrets.toml)
API_URL = st.secrets.get("google_sheets_api", {}).get("url", "URL_NAO_CONFIGURADA")
API_KEY = st.secrets.get("google_sheets_api", {}).get("key", "CHAVE_NAO_CONFIGURADA")

def call_api(payload):
    """Função central para chamar a API do Google Apps Script."""
    try:
        # Adiciona a chave da API ao corpo da requisição
        payload['apiKey'] = API_KEY
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()  # Lança um erro para respostas com status 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Erro de conexão com a API do Google Sheets: {e}")
        return None
    except Exception as e:
        st.error(f"Ocorreu um erro inesperado: {e}")
        return None

@st.cache_data
def convert_df_to_csv(df):
    """Converte um DataFrame para CSV, otimizado com cache."""
    # Importante: O cache evita a reconversão a cada interação do usuário
    return df.to_csv(index=False).encode('utf-8')

def show_previa_rancho():
    """Página principal do módulo de Prévia de Rancho."""
    st.title("🥩 Prévia de Rancho (via Google Sheets)")

    if API_URL == "URL_NAO_CONFIGURADA" or API_KEY == "CHAVE_NAO_CONFIGURADA":
        st.error("A API do Google Sheets não está configurada nos segredos (secrets.toml) do Streamlit.")
        return

    # 1. Carregar semanas disponíveis
    with st.spinner("Buscando semanas disponíveis..."):
        response = call_api({"action": "get_available_weeks"})
        if response and response.get("status") == "success":
            available_weeks = response.get("weeks", [])
        else:
            available_weeks = []
            st.error("Não foi possível carregar a lista de semanas do Google Sheets.")

    if not available_weeks:
        st.warning("Nenhuma semana encontrada na planilha de respostas.")
        return
    
    # 2. Seleção da semana pelo usuário
    st.subheader("Selecione a semana para ver o consolidado")
    semana_selecionada = st.selectbox("Selecione a semana:", available_weeks)

    if st.button("Buscar Dados da Prévia", type="primary"):
        with st.spinner(f"Buscando dados para a semana '{semana_selecionada}'..."):
            payload = {"action": "get_consolidado_data", "semana": semana_selecionada}
            response_data = call_api(payload)

            if response_data and response_data.get("status") == "success":
                dados = response_data.get("data", [])
                if dados and len(dados) > 1:
                    # Cria o DataFrame e o exibe
                    df = pd.DataFrame(dados[1:], columns=dados[0])
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    
                    # --- NOVO: Botão de Download ---
                    csv = convert_df_to_csv(df)
                    
                    st.download_button(
                       label="📥 Exportar para CSV",
                       data=csv,
                       file_name=f'consolidado_rancho_{semana_selecionada}.csv',
                       mime='text/csv',
                    )
                    st.info("Abra o arquivo CSV no Excel ou Google Sheets para salvar como PDF.")

                else:
                    st.info("Não foram encontrados dados de refeições para a semana selecionada.")
            elif response_data:
                st.error(f"Falha ao buscar dados: {response_data.get('message', 'Erro desconhecido')}")

# Ponto de entrada para executar a aplicação
if __name__ == "__main__":
    show_previa_rancho()

