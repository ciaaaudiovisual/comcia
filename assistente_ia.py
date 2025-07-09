import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from st_audiorec import st_audiorec
import requests
import google.generativeai as genai
import json

# URL da API do modelo Whisper no Hugging Face
WHISPER_API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v3"

# ==============================================================================
# "IA" A CUSTO ZERO: FUNÇÕES DE PROCESSAMENTO
# ==============================================================================

def transcrever_audio_para_texto(audio_bytes: bytes) -> str:
    """
    Envia os bytes de áudio para a API do Whisper no Hugging Face e retorna o texto.
    """
    try:
        api_key = st.secrets["huggingface"]["api_key"]
        # ADICIONA O CABEÇALHO "CONTENT-TYPE"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "audio/wav" 
        }
        
        # Faz a chamada para a API
        response = requests.post(API_URL, headers=headers, data=audio_bytes)
        
        if response.status_code == 200:
            resultado = response.json()
            texto_transcrito = resultado.get("text", "")
            st.toast("Áudio transcrito com sucesso pela IA!", icon="🎤")
            return texto_transcrito.strip()
        else:
            st.error(f"Erro na API de transcrição (Whisper): {response.status_code} - {response.text}")
            return ""
    except Exception as e:
        st.error(f"Ocorreu um erro ao conectar com a API de transcrição: {e}")
        return ""

def analisar_relato_com_gemini(texto: str, alunos_df: pd.DataFrame, tipos_acao_df: pd.DataFrame) -> list:
    """
    Envia o texto para a API do Gemini e pede para extrair as ações em formato JSON.
    """
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

    - A data de hoje é {data_de_hoje}. Use esta data para todas as ações, a menos que outra seja especificada no texto.
    - A lista de alunos válidos é: [{lista_nomes_alunos}]. Corresponda os nomes do texto a esta lista. Ignore nomes que não estão na lista.
    - A lista de tipos de ação válidos é: [{lista_tipos_acao}]. Associe as ocorrências do texto ao tipo de ação mais apropriado desta lista.
    - Para cada ação encontrada, crie um objeto com os campos "nome_guerra", "tipo_acao", e "descricao". A descrição deve ser a sentença completa onde a ação foi encontrada.
    - Retorne um objeto JSON que contenha uma chave "acoes", cujo valor é uma lista destes objetos.
    - Se não encontrar nenhuma ação válida, retorne uma lista de ações vazia.

    Texto para análise: "{texto}"
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        sugestoes_dict = json.loads(json_response_text)
        
        # Garante que sempre retornamos a lista de dentro do objeto JSON
        sugestoes = sugestoes_dict.get('acoes', [])
        
        # Adiciona o ID do aluno a cada sugestão encontrada
        nomes_para_ids = pd.Series(alunos_df.id.values, index=alunos_df.nome_guerra).to_dict()
        for sugestao in sugestoes:
            sugestao['aluno_id'] = nomes_para_ids.get(sugestao['nome_guerra'])
            sugestao['data'] = datetime.strptime(data_de_hoje, '%Y-%m-%d').date()

        return sugestoes

    except Exception as e:
        st.error(f"A IA (Gemini) não conseguiu processar o texto. Detalhe do erro: {e}")
        return []

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    st.caption("Grave um relato por voz ou digite diretamente na caixa de texto abaixo.")

    supabase = init_supabase_client()
    
    if 'sugestoes_ia' not in st.session_state: st.session_state.sugestoes_ia = []
    if 'texto_analise' not in st.session_state: st.session_state.texto_analise = ""

    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    st.subheader("Passo 1: Forneça o Relato")

    audio_bytes = st_audiorec()

    if audio_bytes:
        with st.spinner("A transcrever o áudio com a IA (Whisper)..."):
            texto_transcrito = transcrever_audio_para_texto(audio_bytes)
            st.session_state.texto_analise = texto_transcrito
    
    texto_do_dia = st.text_area(
        "Relato para análise:", 
        height=150, 
        value=st.session_state.texto_analise,
        key="text_area_analise"
    )

    if st.button("Analisar Texto com Gemini", type="primary"):
        texto_para_analisar = st.session_state.text_area_analise
        if texto_para_analisar:
            with st.spinner("A IA do Gemini está a analisar o texto..."):
                sugestoes = analisar_relato_com_gemini(texto_para_analisar, alunos_df, tipos_acao_df)
                st.session_state.sugestoes_ia = sugestoes
                if not sugestoes:
                    st.warning("Nenhuma ação ou aluno conhecido foi identificado no texto pela IA.")
        else:
            st.warning("Por favor, insira ou grave um texto para ser analisado.")

    st.divider()

    if st.session_state.sugestoes_ia:
        st.subheader("Passo 2: Revise e Lance as Ações Sugeridas")
        st.info("Verifique e edite os dados abaixo antes de lançar cada ação individualmente.")

        for i, sugestao in enumerate(list(st.session_state.sugestoes_ia)):
            with st.form(key=f"form_sugestao_{i}", border=True):
                st.markdown(f"**Sugestão de Lançamento #{i+1}**")
                
                if not sugestao.get('aluno_id'):
                    st.error(f"Erro: Não foi possível encontrar o ID do aluno '{sugestao.get('nome_guerra')}'. Esta ação não pode ser lançada.")
                    continue
                
                try:
                    index_acao = opcoes_tipo_acao.index(sugestao['tipo_acao'])
                except ValueError:
                    index_acao = 0

                aluno_nome = st.text_input("Aluno", value=sugestao['nome_guerra'], disabled=True)
                tipo_acao_selecionada = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao)
                data_acao = st.date_input("Data da Ação", value=sugestao['data'])
                descricao_acao = st.text_area("Descrição", value=sugestao['descricao'], height=100)
                
                if st.form_submit_button("✅ Lançar Esta Ação"):
                    try:
                        tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao_selecionada].iloc[0]
                        nova_acao = {
                            'aluno_id': sugestao['aluno_id'], 
                            'tipo_acao_id': str(tipo_acao_info['id']),
                            'tipo': tipo_acao_selecionada, 
                            'descricao': descricao_acao,
                            'data': data_acao.strftime('%Y-%m-%d'), 
                            'usuario': st.session_state['username'],
                            'status': 'Pendente'
                        }
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.success(f"Ação '{tipo_acao_selecionada}' lançada para {aluno_nome}!")
                        
                        st.session_state.sugestoes_ia.pop(i)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Ocorreu um erro ao lançar a ação: {e}")
