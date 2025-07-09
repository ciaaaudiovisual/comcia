import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from streamlit_webrtc import webrtc_streamer, WebRtcMode, AudioProcessorBase
import numpy as np
import io

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
    
    # Dicionário de gatilhos melhorado, baseado na análise de dados reais
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

# Placeholder para a função de transcrição de áudio
def transcrever_audio_para_texto(audio_bytes: bytes) -> str:
    """
    SIMULAÇÃO: Numa implementação real, esta função enviaria os bytes de áudio 
    para um modelo de Speech-to-Text (como o Whisper) e retornaria o texto.
    """
    st.info("Simulação: O áudio foi capturado e seria transcrito aqui.")
    # Retornamos um texto fixo para fins de demonstração do fluxo
    return "O aluno GIDEÃO apresentou-se com o uniforme incompleto. Elogio o aluno PEREIRA pela sua atitude proativa."

# ==============================================================================
# PÁGINA PRINCIPAL DA ABA DE IA
# ==============================================================================
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    st.caption("Descreva as ocorrências em texto ou use o microfone para gravar um relato por voz.")

    supabase = init_supabase_client()
    
    # Inicializa o estado da sessão
    if 'sugestoes_ia' not in st.session_state:
        st.session_state.sugestoes_ia = []
    if 'texto_transcrito' not in st.session_state:
        st.session_state.texto_transcrito = ""

    # Carrega dados essenciais
    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    # --- Interface de Entrada com Opção de Voz ---
    st.subheader("Passo 1: Forneça o Relato")

    # Classe para processar o stream de áudio do componente webrtc
    class AudioProcessor(AudioProcessorBase):
        def __init__(self):
            self._audio_buffer = io.BytesIO()

        def recv(self, frame: np.ndarray, format: str) -> np.ndarray:
            self._audio_buffer.write(frame.tobytes())
            return frame

        def get_audio_bytes(self):
            return self._audio_buffer.getvalue()

    # Widget do webrtc para gravar áudio
    webrtc_ctx = webrtc_streamer(
        key="audio-recorder",
        mode="AUDIO_ONLY", # <--- CORREÇÃO: Usando texto simples
        audio_processor_factory=AudioProcessor,
        media_stream_constraints={"audio": True, "video": False},
    )

    st.write("Clique em 'start' para gravar, e 'stop' para parar e transcrever.")

    # Lógica para processar o áudio quando a gravação para
    if not webrtc_ctx.state.playing and webrtc_ctx.audio_processor:
        audio_bytes = webrtc_ctx.audio_processor.get_audio_bytes()
        if audio_bytes:
            with st.spinner("A transcrever o áudio... (simulação)"):
                texto_resultante = transcrever_audio_para_texto(audio_bytes)
                st.session_state.texto_transcrito = texto_resultante
                st.rerun()

    # Área de texto, pré-preenchida com a transcrição se houver
    texto_do_dia = st.text_area(
        "Relato para análise:", 
        height=150, 
        value=st.session_state.texto_transcrito,
        placeholder="Ex: O aluno GIDEÃO chegou atrasado na formatura..."
    )

    if st.button("Analisar Texto", type="primary"):
        if texto_do_dia:
            with st.spinner("A IA está a analisar o texto..."):
                sugestoes = processar_texto_com_regras(texto_do_dia, alunos_df, tipos_acao_df)
                st.session_state.sugestoes_ia = sugestoes
                st.session_state.texto_transcrito = texto_do_dia # Mantém o texto na caixa
                if not sugestoes:
                    st.warning("Nenhuma ação ou aluno conhecido foi identificado no texto.")
        else:
            st.warning("Por favor, insira um texto para ser analisado.")

    st.divider()

    # --- Interface de Saída (Formulários de Confirmação e Edição) ---
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

                # Campos editáveis pré-preenchidos pela IA
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
