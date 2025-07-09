import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from st_audiorec import st_audiorec
import requests
import google.generativeai as genai
import json

# URL da API do modelo Whisper no Hugging Face
API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"

# ==============================================================================
# FUNÇÕES DAS IAs (Sem alterações)
# ==============================================================================

def transcrever_audio_para_texto(audio_bytes: bytes) -> str:
    try:
        api_key = st.secrets["huggingface"]["api_key"]
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "audio/wav"}
        response = requests.post(API_URL, headers=headers, data=audio_bytes)
        if response.status_code == 200:
            resultado = response.json()
            texto_transcrito = resultado.get("text", "")
            st.toast("Áudio transcrito!", icon="🎤")
            return texto_transcrito.strip()
        else:
            st.error(f"Erro na API de transcrição (Whisper): {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar com a API de transcrição: {e}")
        return ""

def analisar_relato_com_gemini(texto: str, alunos_df: pd.DataFrame, tipos_acao_df: pd.DataFrame) -> list:
    try:
        api_key = st.secrets["google_ai"]["api_key"]
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini. Verifique seus segredos. Detalhe: {e}")
        return []

    lista_nomes_alunos = ", ".join(alunos_df['nome_guerra'].unique().tolist())
    lista_tipos_acao = ", ".join(tipos_acao_df['nome'].unique().tolist())
    data_de_hoje = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
    Você é um assistente para um sistema de gestão de alunos militares. Sua tarefa é analisar o relato de um supervisor e extrair as ações disciplinares ou elogios em um formato JSON.

    - A data de hoje é {data_de_hoje}. Use esta data para todas as ações.
    - A lista de alunos válidos é: [{lista_nomes_alunos}]. Corresponda os nomes do texto a esta lista.
    - A lista de tipos de ação válidos é: [{lista_tipos_acao}]. Associe as ocorrências do texto ao tipo de ação mais apropriado.
    - Para cada ação encontrada, crie um objeto com "nome_guerra", "tipo_acao", e "descricao". A descrição deve ser a sentença completa onde a ação foi encontrada.
    - Retorne um objeto JSON com uma chave "acoes", que é uma lista destes objetos. Se nada for encontrado, retorne uma lista vazia.

    Texto para análise: "{texto}"
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        sugestoes_dict = json.loads(json_response_text)
        sugestoes = sugestoes_dict.get('acoes', [])
        
        nomes_para_ids = pd.Series(alunos_df.id.values, index=alunos_df.nome_guerra).to_dict()
        for sugestao in sugestoes:
            sugestao['aluno_id'] = nomes_para_ids.get(sugestao['nome_guerra'])
            sugestao['data'] = datetime.strptime(data_de_hoje, '%Y-%m-%d').date()
        return sugestoes
    except Exception as e:
        st.error(f"A IA (Gemini) não conseguiu processar o texto. Detalhe do erro: {e}")
        return []

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA (REFORMULADA COM INTERFACE DE CHAT)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    st.caption("Envie um relato por texto ou voz e a IA irá preparar os rascunhos das ações para você.")

    supabase = init_supabase_client()

    # Inicializa o histórico do chat no estado da sessão
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar a registar as ocorrências de hoje?"}]

    # Carrega dados essenciais uma única vez
    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    # Exibe as mensagens do histórico
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            # Se o conteúdo for uma lista (nossas sugestões), renderiza de forma especial
            if isinstance(message["content"], list):
                st.info("Encontrei as seguintes ações. Por favor, revise e lance individualmente.")
                for i, sugestao in enumerate(message["content"]):
                    with st.form(key=f"form_sugestao_{i}", border=True):
                        # ... (código do formulário de edição)
                        if not sugestao.get('aluno_id'):
                            st.error(f"Erro: Não foi possível encontrar o ID do aluno '{sugestao.get('nome_guerra')}'.")
                            continue
                        
                        st.markdown(f"**Sugestão para: {sugestao['nome_guerra']}**")
                        try:
                            index_acao = opcoes_tipo_acao.index(sugestao['tipo_acao'])
                        except ValueError:
                            index_acao = 0

                        tipo_acao_selecionada = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao, key=f"tipo_{i}")
                        data_acao = st.date_input("Data", value=sugestao['data'], key=f"data_{i}")
                        descricao_acao = st.text_area("Descrição", value=sugestao['descricao'], height=100, key=f"desc_{i}")
                        
                        if st.form_submit_button("✅ Lançar Ação"):
                            # Lógica de inserção no banco de dados
                            tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao_selecionada].iloc[0]
                            nova_acao = {
                                'aluno_id': sugestao['aluno_id'], 'tipo_acao_id': str(tipo_acao_info['id']),
                                'tipo': tipo_acao_selecionada, 'descricao': descricao_acao,
                                'data': data_acao.strftime('%Y-%m-%d'), 'usuario': st.session_state['username'],
                                'status': 'Pendente'
                            }
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação para {sugestao['nome_guerra']} lançada!")
                            # Idealmente, aqui você removeria a sugestão da lista e daria um st.rerun()
            else:
                st.markdown(message["content"])

    # --- ÁREA DE ENTRADA (VOZ E TEXTO) ---
    st.markdown("---")
    st.write("🎤 **Grave seu relato de voz:**")
    audio_bytes = st_audiorec()

    # Processamento automático do áudio
    if audio_bytes:
        with st.spinner("Transcrição em andamento..."):
            texto_transcrito = transcrever_audio_para_texto(audio_bytes)
            if texto_transcrito:
                st.session_state.messages.append({"role": "user", "content": f"(Relato por voz) {texto_transcrito}"})
                with st.spinner("Gemini está a analisar o texto..."):
                    sugestoes = analisar_relato_com_gemini(texto_transcrito, alunos_df, tipos_acao_df)
                    st.session_state.messages.append({"role": "assistant", "content": sugestoes or "Não encontrei ações válidas no relato."})
                st.rerun()

    # Processamento automático do texto
    prompt_texto = st.chat_input("Ou digite seu relato aqui...")
    if prompt_texto:
        st.session_state.messages.append({"role": "user", "content": prompt_texto})
        with st.spinner("Gemini está a analisar o texto..."):
            sugestoes = analisar_relato_com_gemini(prompt_texto, alunos_df, tipos_acao_df)
            st.session_state.messages.append({"role": "assistant", "content": sugestoes or "Não encontrei ações válidas no relato."})
        st.rerun()
