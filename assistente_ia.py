import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from st_audiorec import st_audiorec
import requests
import google.generativeai as genai
import json

API_URL = "https://api-inference.huggingface.co/models/openai/whisper-base"

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
            return resultado.get("text", "").strip()
        else:
            st.error(f"Erro na API de transcrição: {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        st.error(f"Erro na API de transcrição: {e}")
        return ""

def analisar_relato_com_gemini(texto: str, alunos_df: pd.DataFrame, tipos_acao_df: pd.DataFrame) -> list:
    try:
        api_key = st.secrets["google_ai"]["api_key"]
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini: {e}")
        return []

    nomes_validos = [str(nome) for nome in alunos_df['nome_guerra'].dropna().unique()]
    lista_nomes_alunos = ", ".join(nomes_validos)
    lista_tipos_acao = ", ".join(tipos_acao_df['nome'].unique().tolist())
    data_de_hoje = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
    Sua tarefa é analisar o relato de um supervisor e extrair ações em um formato JSON.
    Contexto: Data de hoje é {data_de_hoje}. Alunos válidos: [{lista_nomes_alunos}]. Ações válidas: [{lista_tipos_acao}].
    Regras: Ignore nomes ou ações fora das listas. Sua resposta deve ser APENAS um objeto JSON com uma chave "acoes", contendo uma lista de objetos.
    Exemplo de Saída: {{"acoes": [{{"nome_guerra": "NOME", "tipo_acao": "TIPO", "descricao": "SENTENÇA"}}]}}
    Relato para Análise: "{texto}"
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
        st.error(f"A IA (Gemini) não conseguiu processar o texto: {e}")
        return []

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA (LÓGICA REFORMULADA)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    
    # --- NOVO: Botão de Limpeza com Lógica Aprimorada ---
    if st.button("🧹 Iniciar Novo Relato (Limpar Tudo)"):
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar a registar as ocorrências de hoje?"}]
        st.session_state.sugestoes_ativas = []
        st.rerun()

    supabase = init_supabase_client()

    # Inicializa os estados da sessão
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar a registar as ocorrências de hoje?"}]
    if "sugestoes_ativas" not in st.session_state:
        st.session_state.sugestoes_ativas = []

    # Carrega dados essenciais
    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    # --- Container para o Histórico do Chat ---
    chat_container = st.container(height=300, border=True)
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # --- ÁREA DE TRABALHO: Formulários para ações ativas ---
    if st.session_state.sugestoes_ativas:
        st.markdown("---")
        st.subheader("Ações Sugeridas para Revisão")
        st.info("Verifique e edite os dados abaixo antes de lançar cada ação individualmente.")

        # Itera sobre uma cópia para poder remover itens da lista original
        for i, sugestao in enumerate(list(st.session_state.sugestoes_ativas)):
            chave_unica = f"form_{sugestao.get('aluno_id')}_{sugestao.get('tipo_acao').replace(' ', '_')}_{i}"
            with st.form(key=chave_unica, border=True):
                if not sugestao.get('aluno_id'):
                    st.error(f"Erro: ID não encontrado para o aluno '{sugestao.get('nome_guerra')}'.")
                    continue
                
                st.markdown(f"**Sugestão para: {sugestao['nome_guerra']}**")
                try:
                    index_acao = opcoes_tipo_acao.index(sugestao['tipo_acao'])
                except ValueError:
                    index_acao = 0

                tipo_acao = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao, key=f"tipo_{chave_unica}")
                data_acao = st.date_input("Data", value=sugestao['data'], key=f"data_{chave_unica}")
                desc_acao = st.text_area("Descrição", value=sugestao['descricao'], height=100, key=f"desc_{chave_unica}")
                
                if st.form_submit_button("✅ Lançar Ação"):
                    nova_acao = {
                        'aluno_id': sugestao['aluno_id'], 'tipo_acao_id': str(tipos_acao_df[tipos_acao_df['nome'] == tipo_acao].iloc[0]['id']),
                        'tipo': tipo_acao, 'descricao': desc_acao, 'data': data_acao.strftime('%Y-%m-%d'),
                        'usuario': st.session_state['username'], 'status': 'Pendente'
                    }
                    supabase.table("Acoes").insert(nova_acao).execute()
                    st.toast(f"Ação para {sugestao['nome_guerra']} lançada!", icon="🎉")
                    
                    # CORREÇÃO: Remove o item da lista de sugestões ativas
                    st.session_state.sugestoes_ativas.pop(i)
                    st.rerun()

    # --- ÁREA DE ENTRADA (VOZ E TEXTO) ---
    st.markdown("---")
    audio_bytes = st_audiorec()

    # Processamento automático do áudio
    if audio_bytes:
        with st.spinner("Ouvindo e transcrevendo (Whisper)..."):
            texto = transcrever_audio_para_texto(audio_bytes)
            if texto:
                st.session_state.messages.append({"role": "user", "content": f"(Relato por voz) {texto}"})
                with st.spinner("Gemini está a analisar..."):
                    sugestoes = analisar_relato_com_gemini(texto, alunos_df, tipos_acao_df)
                    st.session_state.sugestoes_ativas.extend(sugestoes) # Adiciona às sugestões ativas
                    st.session_state.messages.append({"role": "assistant", "content": f"Análise concluída. Encontrei {len(sugestoes)} nova(s) sugestão(ões)."})
                st.rerun()

    # Processamento do texto do chat_input
    prompt_texto = st.chat_input("Digite ou grave seu relato aqui...")
    if prompt_texto:
        st.session_state.messages.append({"role": "user", "content": prompt_texto})
        with st.spinner("Gemini está a analisar..."):
            sugestoes = analisar_relato_com_gemini(prompt_texto, alunos_df, tipos_acao_df)
            st.session_state.sugestoes_ativas.extend(sugestoes) # Adiciona às sugestões ativas
            st.session_state.messages.append({"role": "assistant", "content": f"Análise concluída. Encontrei {len(sugestoes)} nova(s) sugestão(ões)."})
        st.rerun()
