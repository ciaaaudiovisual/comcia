import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from st_audiorec import st_audiorec
import os
import time


def show_assistente_ia():
    st.success("Arquivo importado com sucesso!")
# ==============================================================================
# "IA" A CUSTO ZERO: FUNÇÕES DE PROCESSAMENTO DE TEXTO
# ==============================================================================

def processar_texto_com_regras(texto: str, alunos_df: pd.DataFrame, tipos_acao_df: pd.DataFrame) -> list:
    """
    Processa um texto usando regras e palavras-chave para extrair ações e IDs.
    """
    sugestoes = []
    sentencas = texto.split('.')
    
    nomes_alunos_map = pd.Series(alunos_df.id.values, index=alunos_df.nome_guerra).to_dict()
    
    gatilhos_acoes = {
        'Atraso na Formação': ['atraso', 'atrasado', 'tarde', 'apresentou-se', 'formatura'],
        'Dispensa Médica': ['dispensa', 'médica', 'dispensado', 'atestado', 'licença', 'nas'],
        'Elogio Individual': ['elogio', 'parabéns', 'destacou-se', 'excelente', 'desempenho'],
        'Falta': ['falta', 'faltou', 'ausente', 'não compareceu', 'ausência'],
        'Falta de Punição': ['punição', 'falta', 'não cumpriu', 'advertência', 'repreensão'],
        'Formato de Presença': ['presença', 'instrução', 'verificação', 'formatura', 'atividade'],
        'Não Tirou Serviço': ['serviço', 'não tirou', 'faltou ao serviço', 'escala'],
        'Punição de Advertência': ['advertência', 'advertido', 'repreensão', 'punição'],
        'Punição de Repreensão': ['repreensão', 'repreendido', 'punição'],
        'Serviço de Dia': ['serviço', 'escala', 'guarnição', 'dia'],
        'Uniforme Incompleto': ['uniforme', 'incompleto', 'cobertura', 'coturno', 'farda']
    }

    for sentenca in sentencas:
        if not sentenca.strip():
            continue

        aluno_encontrado_id = None
        aluno_encontrado_nome = None
        acao_encontrada = None

        for nome, aluno_id in nomes_alunos_map.items():
            if nome.lower() in sentenca.lower():
                aluno_encontrado_id = aluno_id
                aluno_encontrado_nome = nome
                break
        
        if aluno_encontrado_id:
            for tipo_acao, gatilhos in gatilhos_acoes.items():
                for gatilho in gatilhos:
                    if gatilho in sentenca.lower():
                        acao_encontrada = tipo_acao
                        break
                if acao_encontrada:
                    break
        
        if aluno_encontrado_id and acao_encontrada:
            sugestao = {
                'aluno_id': str(aluno_encontrado_id),
                'nome_guerra': aluno_encontrado_nome,
                'tipo_acao': acao_encontrada,
                'descricao': sentenca.strip() + '.',
                'data': datetime.now().date()
            }
            sugestoes.append(sugestao)
            
    return sugestoes

def transcrever_audio_para_texto(caminho_do_arquivo: str) -> str:
    """
    SIMULAÇÃO: Numa implementação real, esta função usaria um modelo de Speech-to-Text 
    (como o Whisper) para processar o ARQUIVO DE ÁUDIO.
    """
    if not os.path.exists(caminho_do_arquivo):
        st.error("Arquivo de áudio não encontrado.")
        return ""
        
    st.toast("Arquivo de áudio recebido. Iniciando transcrição...", icon="📂")
    
    # Simula o tempo de processamento da IA lendo o arquivo
    with open(caminho_do_arquivo, 'rb') as f:
        # Em um caso real, você passaria `f` ou o caminho do arquivo para o modelo de IA
        audio_data = f.read()

    time.sleep(2) 
    st.toast("Áudio transcrito com sucesso!", icon="✅")
    return "O aluno GIDEÃO apresentou-se com o uniforme incompleto. Elogio o aluno PEREIRA pela sua atitude proativa."

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA (VERSÃO ROBUSTA COM ARQUIVO)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    st.caption("Use o microfone para gravar um relato por voz. O áudio será salvo e processado.")

    supabase = init_supabase_client()
    
    # Inicializa o estado da sessão
    if 'sugestoes_ia' not in st.session_state:
        st.session_state.sugestoes_ia = []
    if 'texto_transcrito' not in st.session_state:
        st.session_state.texto_transcrito = ""
    if 'caminho_audio' not in st.session_state:
        st.session_state.caminho_audio = ""

    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    # --- PASSO 1: GRAVAÇÃO E ARMAZENAMENTO DO ÁUDIO ---
    st.subheader("Passo 1: Grave o Relato de Voz")

    # Uso do st_audiorec
    # Este componente renderiza um gravador de áudio e retorna os bytes do arquivo .wav
    audio_bytes = st_audiorec()

    if audio_bytes:
        st.info("Áudio gravado! Processando o ficheiro...")
        
        # Define um diretório para salvar as gravações
        pasta_gravacoes = "gravacoes"
        if not os.path.exists(pasta_gravacoes):
            os.makedirs(pasta_gravacoes)

        # Cria um nome de arquivo único com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        caminho_do_arquivo = os.path.join(pasta_gravacoes, f"relato_{timestamp}.wav")

        # Salva o arquivo de áudio no servidor
        with open(caminho_do_arquivo, "wb") as f:
            f.write(audio_bytes)
        
        st.session_state.caminho_audio = caminho_do_arquivo

        # Mostra o player de áudio para o usuário ouvir o que gravou
        st.audio(audio_bytes, format='audio/wav')
        
        # Inicia a transcrição automaticamente
        with st.spinner("A IA está a transcrever o áudio... (simulação)"):
            texto_resultante = transcrever_audio_para_texto(st.session_state.caminho_audio)
            st.session_state.texto_transcrito = texto_resultante
        
        # Força um rerun para atualizar a área de texto com a transcrição
        st.rerun()

    # --- PASSO 2: ANÁLISE DO TEXTO TRANSCRITO ---
    st.subheader("Passo 2: Analise o Texto")
    
    texto_do_dia = st.text_area(
        "Texto transcrito (pode editar antes de analisar):", 
        height=150, 
        value=st.session_state.texto_transcrito,
        placeholder="O texto gravado aparecerá aqui."
    )

    if st.button("Analisar Texto", type="primary"):
        if texto_do_dia:
            with st.spinner("A IA está a analisar o texto..."):
                sugestoes = processar_texto_com_regras(texto_do_dia, alunos_df, tipos_acao_df)
                st.session_state.sugestoes_ia = sugestoes
                if not sugestoes:
                    st.warning("Nenhuma ação ou aluno conhecido foi identificado no texto.")
        else:
            st.warning("Não há texto para ser analisado.")

    st.divider()

    # --- PASSO 3: REVISÃO E LANÇAMENTO ---
    if st.session_state.sugestoes_ia:
        st.subheader("Passo 3: Revise e Lance as Ações Sugeridas")
        
        for i, sugestao in enumerate(list(st.session_state.sugestoes_ia)):
            with st.form(key=f"form_sugestao_{i}", border=True):
                st.markdown(f"**Sugestão de Lançamento #{i+1}**")

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
