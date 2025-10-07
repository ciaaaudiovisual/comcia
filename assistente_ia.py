import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission # <-- CORREÇÃO: Importa a função de permissão
import google.generativeai as genai
import json
import time
from io import BytesIO
import PyPDF2
import numpy as np

# ==============================================================================
# FUNÇÕES DE BACKEND PARA INDEXAÇÃO E BUSCA (RAG)
# ==============================================================================

# Função para ler texto de um PDF
def ler_pdf(ficheiro_bytes: BytesIO) -> str:
    leitor_pdf = PyPDF2.PdfReader(ficheiro_bytes)
    texto = ""
    for pagina in leitor_pdf.pages:
        texto += pagina.extract_text()
    return texto

# Função para quebrar o texto em pedaços (chunks)
def dividir_em_chunks(texto: str, chunk_size=1000, overlap=100):
    chunks = []
    for i in range(0, len(texto), chunk_size - overlap):
        chunks.append(texto[i:i + chunk_size])
    return chunks

# Função principal de indexação
def indexar_documento(nome_ficheiro: str, ficheiro_bytes: BytesIO, supabase, progress_bar):
    try:
        st.info(f"A ler o conteúdo do ficheiro: {nome_ficheiro}...")
        texto_completo = ler_pdf(ficheiro_bytes)
        
        st.info("A dividir o documento em pedaços...")
        chunks = dividir_em_chunks(texto_completo)
        
        st.info(f"Encontrados {len(chunks)} pedaços. A criar 'impressões digitais' (embeddings)...")
        
        total_chunks = len(chunks)
        for i, chunk in enumerate(chunks):
            # Chama a API do Gemini para criar o embedding
            response = genai.embed_content(model='models/text-embedding-004', content=chunk)
            embedding = response['embedding']
            
            # Insere o chunk e o seu embedding no Supabase
            supabase.table('document_chunks').insert({
                'document_name': nome_ficheiro,
                'chunk_text': chunk,
                'embedding': embedding
            }).execute()

            # Respeita o limite da API para não causar erros
            time.sleep(1) # Pausa de 1 segundo entre cada chamada
            progress_bar.progress((i + 1) / total_chunks, text=f"A processar pedaço {i+1}/{total_chunks}")

        st.success(f"Documento '{nome_ficheiro}' indexado com sucesso!")
        return True
    except Exception as e:
        st.error(f"Ocorreu um erro durante a indexação: {e}")
        return False

# Função para buscar os chunks relevantes
def buscar_chunks_relevantes(pergunta: str, supabase, top_k=3):
    # Cria o embedding para a pergunta do utilizador
    response = genai.embed_content(model='models/text-embedding-004', content=pergunta)
    pergunta_embedding = response['embedding']
    
    # Executa a busca por similaridade de vetores no Supabase
    # Nota: O Supabase precisa de uma "RPC Function" para busca de vetores.
    # O comando para criar a função no SQL Editor do Supabase é:
    # CREATE OR REPLACE FUNCTION match_document_chunks (
    #   query_embedding vector(768),
    #   match_threshold float,
    #   match_count int
    # )
    # RETURNS TABLE (
    #   id uuid,
    #   document_name text,
    #   chunk_text text,
    #   similarity float
    # )
    # AS $$
    #   SELECT
    #     dc.id,
    #     dc.document_name,
    #     dc.chunk_text,
    #     1 - (dc.embedding <=> query_embedding) as similarity
    #   FROM document_chunks dc
    #   WHERE 1 - (dc.embedding <=> query_embedding) > match_threshold
    #   ORDER BY similarity DESC
    #   LIMIT match_count;
    # $$ LANGUAGE sql;

    resultados = supabase.rpc('match_document_chunks', {
        'query_embedding': pergunta_embedding,
        'match_threshold': 0.5, # Limiar de similaridade
        'match_count': top_k
    }).execute()
    
    return resultados.data

# Função para gerar a resposta final com base no contexto
def gerar_resposta_com_contexto(pergunta: str, chunks_relevantes: list):
    contexto = "\n\n---\n\n".join([chunk['chunk_text'] for chunk in chunks_relevantes])
    
    prompt = f"""
    Você é um assistente especialista. Responda à pergunta do utilizador baseando-se **exclusivamente** no contexto fornecido abaixo. Se a resposta não estiver no contexto, diga "A informação não foi encontrada nos documentos disponíveis."

    **Contexto:**
    {contexto}

    **Pergunta:**
    {pergunta}
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    return response.text


# ==============================================================================
# PÁGINA PRINCIPAL DO ASSISTENTE IA (COM ABAS)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente de Conhecimento")
    
    supabase = init_supabase_client()
    try:
        api_key = st.secrets["google_ai"]["api_key"]
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Erro ao configurar a API do Gemini. Verifique os segredos: {e}")
        return

    # Cria as abas
    tab_consulta, tab_gestao = st.tabs(["Consultar Documentos", "Gerir Documentos"])

    # --- ABA DE CONSULTA PARA TODOS OS UTILIZADORES ---
    with tab_consulta:
        st.subheader("Faça uma pergunta sobre os regulamentos")
        
        if "chat_messages" not in st.session_state:
            st.session_state.chat_messages = [{"role": "assistant", "content": "Olá! Em que posso ajudar com base nos documentos?"}]

        for message in st.session_state.chat_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt_texto = st.chat_input("Qual é a sua dúvida?")
        if prompt_texto:
            st.session_state.chat_messages.append({"role": "user", "content": prompt_texto})
            with st.chat_message("user"):
                st.markdown(prompt_texto)
            
            with st.chat_message("assistant"):
                with st.spinner("A consultar a base de conhecimento..."):
                    chunks = buscar_chunks_relevantes(prompt_texto, supabase)
                    if not chunks:
                        resposta = "Não encontrei informações relevantes nos documentos para responder à sua pergunta."
                    else:
                        resposta = gerar_resposta_com_contexto(prompt_texto, chunks)
                st.markdown(resposta)
            
            st.session_state.chat_messages.append({"role": "assistant", "content": resposta})

    # --- ABA DE GESTÃO APENAS PARA ADMINS ---
    with tab_gestao:
        st.subheader("Gestão da Base de Conhecimento")
        if check_permission('pode_gerenciar_usuarios'): # Usando uma permissão de admin existente como exemplo
            
            # Secção de Upload e Indexação
            st.markdown("#### Carregar e Indexar Novo Documento")
            uploaded_file = st.file_uploader("Escolha um ficheiro PDF", type="pdf")
            if uploaded_file is not None:
                if st.button(f"Indexar Ficheiro: {uploaded_file.name}"):
                    progress_bar = st.progress(0, text="A iniciar a indexação...")
                    indexar_documento(uploaded_file.name, BytesIO(uploaded_file.getvalue()), supabase, progress_bar)
                    st.success("Processo de indexação concluído!")

            st.divider()

            # Secção para ver documentos já indexados
            st.markdown("#### Documentos na Memória da IA")
            try:
                documentos_db = supabase.table('document_chunks').select('document_name').execute()
                if documentos_db.data:
                    nomes_unicos = sorted(list(set(item['document_name'] for item in documentos_db.data)))
                    for nome in nomes_unicos:
                        st.write(f"📄 {nome}")
                else:
                    st.info("Nenhum documento foi indexado ainda.")
            except Exception as e:
                st.warning(f"Não foi possível listar os documentos. A tabela 'document_chunks' existe? Erro: {e}")

        else:
            st.error("Apenas administradores podem aceder a esta secção.")
