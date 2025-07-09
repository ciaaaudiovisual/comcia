import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import numpy as np
import io
import time

# ==============================================================================
# "IA" A CUSTO ZERO: FUNÇÕES DE PROCESSAMENTO DE TEXTO
# (Mantive suas funções originais aqui, sem alterações)
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

def transcrever_audio_para_texto(audio_bytes: bytes) -> str:
    """
    SIMULAÇÃO: Numa implementação real, esta função enviaria os bytes de áudio 
    para um modelo de Speech-to-Text (como o Whisper) e retornaria o texto.
    """
    # Se não houver bytes de áudio, não faz nada
    if not audio_bytes:
        return ""
    st.toast("Iniciando transcrição...", icon="🎤")
    time.sleep(2) # Simula o tempo de processamento da IA
    st.toast("Áudio transcrito com sucesso!", icon="✅")
    return "O aluno GIDEÃO apresentou-se com o uniforme incompleto. Elogio o aluno PEREIRA pela sua atitude proativa."

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA (VERSÃO CORRIGIDA)
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    st.caption("Descreva as ocorrências em texto ou use o microfone para gravar um relato por voz.")

    supabase = init_supabase_client()
    
    # Inicializa o estado da sessão de forma robusta
    if 'sugestoes_ia' not in st.session_state:
        st.session_state.sugestoes_ia = []
    if 'texto_transcrito' not in st.session_state:
        st.session_state.texto_transcrito = ""
    if 'gravando' not in st.session_state:
        st.session_state.gravando = False
    # <--- MUDANÇA 1: Inicializa um buffer de áudio no session_state
    if "audio_buffer" not in st.session_state:
        st.session_state.audio_buffer = []

    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    st.subheader("Passo 1: Forneça o Relato")

    status_indicator = st.empty()

    # <--- MUDANÇA 2: Simplificamos o AudioProcessor para apenas guardar os frames no session_state
    class AudioFrameHandler(AudioProcessorBase):
        def recv(self, frame: np.ndarray, format: str) -> np.ndarray:
            # Armazena cada frame de áudio como bytes na lista do session_state
            st.session_state.audio_buffer.append(frame.tobytes())
            return frame

    webrtc_ctx = webrtc_streamer(
        key="audio-recorder",
        mode=WebRtcMode.SENDONLY,
        audio_processor_factory=AudioFrameHandler, # <--- Usando o novo processador
        media_stream_constraints={"audio": True, "video": False},
    )
    
    # <--- MUDANÇA 3: Lógica de controle e processamento centralizada
    if webrtc_ctx.state.playing and not st.session_state.gravando:
        # O usuário clicou em "start"
        st.session_state.gravando = True
        # Limpa o buffer de gravações anteriores
        st.session_state.audio_buffer = [] 
        st.rerun()

    elif not webrtc_ctx.state.playing and st.session_state.gravando:
        # O usuário clicou em "stop"
        status_indicator.info("Áudio capturado. Processando...")
        
        # Junta todos os pedaços de áudio do buffer
        if st.session_state.audio_buffer:
            audio_bytes = b"".join(st.session_state.audio_buffer)
            
            with st.spinner("A transcrever o áudio... (simulação)"):
                texto_resultante = transcrever_audio_para_texto(audio_bytes)
                st.session_state.texto_transcrito = texto_resultante
        
        # Reseta os estados para a próxima gravação
        st.session_state.gravando = False
        st.session_state.audio_buffer = [] # Limpa o buffer após o uso
        st.rerun()

    # Atualiza a mensagem de status com base no estado
    if st.session_state.gravando:
        status_indicator.info("🔴 Gravando... Clique no botão 'stop' acima para parar.")
    
    # O resto do código permanece o mesmo...
    texto_do_dia = st.text_area(
        "Relato para análise:", 
        height=150, 
        value=st.session_state.texto_transcrito,
        placeholder="O texto gravado aparecerá aqui, ou pode digitar diretamente."
    )

    if st.button("Analisar Texto", type="primary"):
        if texto_do_dia:
            with st.spinner("A IA está a analisar o texto..."):
                sugestoes = processar_texto_com_regras(texto_do_dia, alunos_df, tipos_acao_df)
                st.session_state.sugestoes_ia = sugestoes
                st.session_state.texto_transcrito = texto_do_dia
                if not sugestoes:
                    st.warning("Nenhuma ação ou aluno conhecido foi identificado no texto.")
        else:
            st.warning("Por favor, insira um texto para ser analisado.")

    st.divider()

    if st.session_state.sugestoes_ia:
        st.subheader("Passo 2: Revise e Lance as Ações Sugeridas")
        st.info("Verifique e edite os dados abaixo antes de lançar cada ação individualmente.")

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
