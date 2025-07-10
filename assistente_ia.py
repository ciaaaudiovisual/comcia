import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
import google.generativeai as genai
import json

# ==============================================================================
# FUNÇÃO DA IA (GEMINI) - Analisa apenas texto
# ==============================================================================
def analisar_relato_com_gemini(texto: str, alunos_df: pd.DataFrame, tipos_acao_df: pd.DataFrame) -> list:
    """
    Envia o TEXTO para a API do Gemini e pede para extrair as ações em formato JSON.
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

    # Prompt focado em analisar o TEXTO fornecido
    prompt = f"""
    Você é um assistente para um sistema de gestão de alunos militares. Sua função é analisar relatos textuais de supervisores, identificar os alunos e as ações (positivas ou negativas) e estruturar essa informação em um formato JSON.

    **Instruções Críticas:**
    1.  **Contexto:** A data de hoje é {data_de_hoje}. A lista oficial de alunos é: [{lista_nomes_alunos}]. A lista oficial de tipos de ação é: [{lista_tipos_acao}].
    2.  **Extração:** Leia o texto, identifique o "nome_guerra" do aluno, o "tipo_acao" mais apropriado da lista oficial, e a "descricao" (a sentença completa onde a ocorrência foi mencionada).
    3.  **Formato de Saída:** Sua resposta deve ser **APENAS** um objeto JSON com uma chave "acoes", contendo uma lista de objetos.

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
        
        st.toast("Relato analisado com sucesso!", icon="✨")
        return sugestoes

    except Exception as e:
        st.error(f"A IA (Gemini) não conseguiu processar o texto. Detalhe do erro: {e}")
        return []

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA (INTERFACE DE TEXTO)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    
    if st.button("🧹 Iniciar Novo Relato (Limpar)"):
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Digite um relato para eu analisar."}]
        st.session_state.sugestoes_ativas = []
        st.rerun()

    supabase = init_supabase_client()

    # Inicializa os estados da sessão
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Olá! Digite um relato para eu analisar."}]
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

        for i, sugestao in enumerate(list(st.session_state.sugestoes_ativas)):
            chave_unica = f"form_{sugestao.get('aluno_id')}_{sugestao.get('tipo_acao').replace(' ', '_')}_{i}"
            with st.form(key=chave_unica, border=True):
                if not sugestao.get('aluno_id'):
                    st.error(f"Erro: ID não encontrado para o aluno '{sugestao.get('nome_guerra')}'.")
                    continue
                
                st.markdown(f"**Sugestão para: {sugestao['nome_guerra']}**")
                lista_nomes_alunos = [""] + sorted(alunos_df['nome_guerra'].dropna().unique().tolist())
                try:
                    index_aluno = lista_nomes_alunos.index(sugestao['nome_guerra'])
                except ValueError:
                    index_aluno = 0
                aluno_selecionado_nome = st.selectbox("Aluno (pode corrigir se necessário)", options=lista_nomes_alunos, index=index_aluno, key=f"aluno_{chave_unica}")

                try:
                    index_acao = opcoes_tipo_acao.index(sugestao['tipo_acao'])
                except ValueError:
                    index_acao = 0
                tipo_acao = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao, key=f"tipo_{chave_unica}")
                data_acao = st.date_input("Data", value=sugestao['data'], key=f"data_{chave_unica}")
                desc_acao = st.text_area("Descrição", value=sugestao['descricao'], height=100, key=f"desc_{chave_unica}")
                
                if st.form_submit_button("✅ Lançar Ação"):
                    if not aluno_selecionado_nome:
                        st.warning("Por favor, selecione um aluno antes de lançar.")
                    else:
                        aluno_info = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado_nome].iloc[0]
                        aluno_id_final = str(aluno_info['id'])
                        
                        nova_acao = {
                            'aluno_id': aluno_id_final, 
                            'tipo_acao_id': str(tipos_acao_df[tipos_acao_df['nome'] == tipo_acao].iloc[0]['id']),
                            'tipo': tipo_acao, 'descricao': desc_acao, 'data': data_acao.strftime('%Y-%m-%d'),
                            'usuario': st.session_state['username'], 'status': 'Pendente'
                        }
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.toast(f"Ação para {aluno_selecionado_nome} lançada!", icon="🎉")
                        
                        st.session_state.sugestoes_ativas.pop(i)
                        st.rerun()

    # --- ÁREA DE ENTRADA (Apenas Texto) ---
    st.markdown("---")
    prompt_texto = st.chat_input("Digite o relato aqui e pressione Enter...")
    if prompt_texto:
        st.session_state.messages.append({"role": "user", "content": prompt_texto})
        with st.spinner("Gemini está a analisar o seu relato..."):
            sugestoes = analisar_relato_com_gemini(prompt_texto, alunos_df, tipos_acao_df)
            st.session_state.sugestoes_ativas.extend(sugestoes)
            st.session_state.messages.append({"role": "assistant", "content": f"Análise concluída. Encontrei {len(sugestoes)} nova(s) sugestão(ões) para sua revisão."})
        st.rerun()
