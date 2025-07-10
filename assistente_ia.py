import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from st_audiorec import st_audiorec
import requests
import google.generativeai as genai
import json

# URL da API do modelo Whisper (versão mais rápida)
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
    try:
        api_key = st.secrets["google_ai"]["api_key"]
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini. Verifique seus segredos. Detalhe: {e}")
        return []

    nomes_validos = [str(nome) for nome in alunos_df['nome_guerra'].dropna().unique()]
    lista_nomes_alunos = ", ".join(nomes_validos)
    
    lista_tipos_acao = ", ".join(tipos_acao_df['nome'].unique().tolist())
    data_de_hoje = datetime.now().strftime('%Y-%m-%d')

    prompt = f"""
    Você é um assistente para um sistema de gestão de alunos militares. Sua função é analisar relatos textuais de supervisores, identificar os alunos e as ações (positivas ou negativas) e estruturar essa informação em um formato JSON.

    **Instruções Críticas:**
    1.  **Contexto:** A data de hoje é {data_de_hoje}. A lista oficial de alunos é: [{lista_nomes_alunos}]. A lista oficial de tipos de ação é: [{lista_tipos_acao}].
    2.  **Extração:** Identifique o "nome_guerra" do aluno, o "tipo_acao" mais apropriado da lista oficial, e a "descricao" (a sentença completa onde a ocorrência foi mencionada).
    3.  **Regras:**
        - Ignore qualquer nome que não esteja na lista oficial de alunos.
        - Se uma ação não se encaixar perfeitamente em um tipo, não invente um. Deixe-a de fora.
        - Foque em extrair ações claras e diretas.
    4.  **Formato de Saída:** Sua resposta deve ser **APENAS** um objeto JSON com uma chave "acoes", contendo uma lista de objetos, um para cada ação encontrada. Não inclua texto ou explicações antes ou depois do JSON.

    **Exemplo 1 de Entrada:**
    "o aluno GIDEÃO chegou 10 minutos atrasado na formatura matinal."

    **Exemplo 1 de Saída JSON Esperada:**
    {{
      "acoes": [
        {{
          "nome_guerra": "GIDEÃO",
          "tipo_acao": "Atraso na Formação",
          "descricao": "o aluno GIDEÃO chegou 10 minutos atrasado na formatura matinal."
        }}
      ]
    }}

    **Exemplo 2 de Entrada:**
    "Elogio o militar PEREIRA pela excelente apresentação pessoal. Já o aluno COSTA estava com o uniforme incompleto."

    **Exemplo 2 de Saída JSON Esperada:**
    {{
      "acoes": [
        {{
          "nome_guerra": "PEREIRA",
          "tipo_acao": "Elogio Individual",
          "descricao": "Elogio o militar PEREIRA pela excelente apresentação pessoal."
        }},
        {{
          "nome_guerra": "COSTA",
          "tipo_acao": "Uniforme Incompleto",
          "descricao": "Já o aluno COSTA estava com o uniforme incompleto."
        }}
      ]
    }}

    **Relato Real para Análise:**
    "{texto}"
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
# PÁGINA PRINCIPAL DA ABA DE IA
# ==============================================================================
def show_assistente_ia():
    # --- NOVO: Título e Botão de Limpeza no Topo ---
    col1, col2 = st.columns([3, 1])
    with col1:
        st.title("🤖 Assistente IA")
    with col2:
        if st.button("🧹 Limpar Histórico", use_container_width=True):
            # Reinicia o estado do chat para o padrão
            st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar a registar as ocorrências de hoje?"}]
            st.rerun()

    st.caption("Envie um relato por texto ou voz e a IA irá preparar os rascunhos das ações para você.")

    supabase = init_supabase_client()
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Como posso ajudar a registar as ocorrências de hoje?"}]

    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    # Exibe o histórico do chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if isinstance(message["content"], list):
                st.info("Encontrei as seguintes ações. Por favor, revise e lance individualmente.")
                for i, sugestao in enumerate(message["content"]):
                    chave_unica = f"form_{sugestao.get('aluno_id')}_{sugestao.get('tipo_acao').replace(' ', '_')}_{i}"
                    with st.form(key=chave_unica, border=True):
                        if not sugestao.get('aluno_id'):
                            st.error(f"Erro: Não foi possível encontrar o ID do aluno '{sugestao.get('nome_guerra')}'.")
                            continue
                        
                        st.markdown(f"**Sugestão para: {sugestao['nome_guerra']}**")
                        try:
                            index_acao = opcoes_tipo_acao.index(sugestao['tipo_acao'])
                        except ValueError:
                            index_acao = 0

                        tipo_acao_selecionada = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao, key=f"tipo_{chave_unica}")
                        data_acao = st.date_input("Data", value=sugestao['data'], key=f"data_{chave_unica}")
                        descricao_acao = st.text_area("Descrição", value=sugestao['descricao'], height=100, key=f"desc_{chave_unica}")
                        
                        if st.form_submit_button("✅ Lançar Ação"):
                            tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao_selecionada].iloc[0]
                            nova_acao = {
                                'aluno_id': sugestao['aluno_id'], 'tipo_acao_id': str(tipo_acao_info['id']),
                                'tipo': tipo_acao_selecionada, 'descricao': descricao_acao,
                                'data': data_acao.strftime('%Y-%m-%d'), 'usuario': st.session_state['username'],
                                'status': 'Pendente'
                            }
                            supabase.table("Acoes").insert(nova_acao).execute()
                            st.success(f"Ação para {sugestao['nome_guerra']} lançada!")
            else:
                st.markdown(message["content"])

    # --- ÁREA DE ENTRADA (VOZ E TEXTO) ---
    st.markdown("---")
    st.write("🎤 **Grave seu relato de voz:**")
    audio_bytes = st_audiorec()

    if audio_bytes:
        with st.spinner("Ouvindo e transcrevendo (Whisper)... Isso pode levar alguns segundos."):
            texto_transcrito = transcrever_audio_para_texto(audio_bytes)
            if texto_transcrito:
                st.session_state.messages.append({"role": "user", "content": f"(Relato por voz) {texto_transcrito}"})
                with st.spinner("Gemini está a analisar o texto..."):
                    sugestoes = analisar_relato_com_gemini(texto_transcrito, alunos_df, tipos_acao_df)
                    st.session_state.messages.append({"role": "assistant", "content": sugestoes or "Não encontrei ações válidas no relato."})
                st.rerun()

    prompt_texto = st.chat_input("Ou digite seu relato aqui...")
    if prompt_texto:
        st.session_state.messages.append({"role": "user", "content": prompt_texto})
        with st.spinner("Gemini está a analisar o texto..."):
            sugestoes = analisar_relato_com_gemini(prompt_texto, alunos_df, tipos_acao_df)
            st.session_state.messages.append({"role": "assistant", "content": sugestoes or "Não encontrei ações válidas no relato."})
        st.rerun()
