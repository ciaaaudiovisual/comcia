import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from st_audiorec import st_audiorec
import google.generativeai as genai
import json

# ==============================================================================
# NOVA FUNÇÃO DE IA "TUDO EM UM" COM GEMINI 1.5
# ==============================================================================
def analisar_audio_com_gemini(audio_bytes: bytes, alunos_df: pd.DataFrame, tipos_acao_df: pd.DataFrame) -> list:
    """
    Envia o ÁUDIO diretamente para a API do Gemini e pede para transcrever e 
    extrair as ações em um único passo.
    """
    try:
        api_key = st.secrets["google_ai"]["api_key"]
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini. Verifique seus segredos. Detalhe: {e}")
        return []

    # Prepara o contexto para a IA
    nomes_validos = [str(nome) for nome in alunos_df['nome_guerra'].dropna().unique()]
    lista_nomes_alunos = ", ".join(nomes_validos)
    lista_tipos_acao = ", ".join(tipos_acao_df['nome'].unique().tolist())
    data_de_hoje = datetime.now().strftime('%Y-%m-%d')

    # Prompt instruindo a IA a analisar o ÁUDIO fornecido
    prompt = f"""
    Você é um assistente para um sistema de gestão de alunos militares. Sua tarefa é analisar o RELATO EM ÁUDIO de um supervisor, transcrevê-lo, identificar os alunos e as ações (positivas ou negativas) e estruturar essa informação em um formato JSON.

    **Instruções Críticas:**
    1.  **Contexto:** A data de hoje é {data_de_hoje}. A lista oficial de alunos é: [{lista_nomes_alunos}]. A lista oficial de tipos de ação é: [{lista_tipos_acao}].
    2.  **Extração:** Ouça o áudio, identifique o "nome_guerra" do aluno, o "tipo_acao" mais apropriado da lista oficial, e a "descricao" (a sentença completa onde a ocorrência foi mencionada).
    3.  **Formato de Saída:** Sua resposta deve ser **APENAS** um objeto JSON com uma chave "acoes", contendo uma lista de objetos. Cada objeto deve ter os campos "nome_guerra", "tipo_acao", e "descricao".

    **Exemplo de Saída JSON Esperada para um áudio contendo "elogio o aluno PEREIRA":**
    {{
      "acoes": [
        {{
          "nome_guerra": "PEREIRA",
          "tipo_acao": "Elogio Individual",
          "descricao": "Elogio o aluno PEREIRA."
        }}
      ]
    }}
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # --- CORREÇÃO APLICADA AQUI ---
        # 1. Cria a "parte" de áudio como um dicionário, em vez de fazer upload
        audio_part = {
            "mime_type": "audio/wav",
            "data": audio_bytes
        }

        # 2. Envia o prompt de texto E a parte de áudio diretamente para o modelo
        response = model.generate_content([prompt, audio_part])
        
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        sugestoes_dict = json.loads(json_response_text)
        sugestoes = sugestoes_dict.get('acoes', [])
        
        nomes_para_ids = pd.Series(alunos_df.id.values, index=alunos_df.nome_guerra).to_dict()
        for sugestao in sugestoes:
            sugestao['aluno_id'] = nomes_para_ids.get(sugestao['nome_guerra'])
            sugestao['data'] = datetime.strptime(data_de_hoje, '%Y-%m-%d').date()
        
        st.toast("Relato em áudio analisado com sucesso!", icon="✨")
        return sugestoes

    except Exception as e:
        st.error(f"A IA (Gemini) não conseguiu processar o áudio. Detalhe do erro: {e}")
        return []
# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA (LÓGICA SIMPLIFICADA)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA (Gemini 1.5)")
    
    if st.button("🧹 Iniciar Novo Relato"):
        st.session_state.sugestoes_ativas = []
        st.rerun()

    supabase = init_supabase_client()

    if "sugestoes_ativas" not in st.session_state:
        st.session_state.sugestoes_ativas = []

    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())
    
    st.info("Grave um relato de voz. O Gemini irá ouvir, transcrever e analisar as ações automaticamente.")
    
    # --- ÁREA DE ENTRADA DE VOZ ---
    audio_bytes = st_audiorec()

    # Processamento automático e direto do áudio com o Gemini
    if audio_bytes:
        with st.spinner("Gemini está a ouvir e a analisar o seu relato... (Isso pode levar alguns segundos)"):
            sugestoes = analisar_audio_com_gemini(audio_bytes, alunos_df, tipos_acao_df)
            st.session_state.sugestoes_ativas.extend(sugestoes)
        st.rerun()

    # --- ÁREA DE TRABALHO: Formulários para ações ativas ---
    if st.session_state.sugestoes_ativas:
        st.markdown("---")
        st.subheader("Ações Sugeridas para Revisão")

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
                    
                    st.session_state.sugestoes_ativas.pop(i)
                    st.rerun()
