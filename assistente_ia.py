import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client

# Esta é a nossa "IA a custo zero". A mesma função que discutimos antes.
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


# Função principal que renderiza a página da IA
def show_assistente_ia():
    st.title("🤖 Assistente IA para Lançamentos")
    st.caption("Descreva as ocorrências do dia em texto corrido. A IA irá identificar os alunos, sugerir as ações e preparar um rascunho para seu lançamento.")

    supabase = init_supabase_client()
    
    # Inicializa o estado da sessão para guardar as sugestões
    if 'sugestoes_ia' not in st.session_state:
        st.session_state.sugestoes_ia = []

    # Carrega os dados necessários para a IA
    alunos_df = load_data("Alunos")
    tipos_acao_df = load_data("Tipos_Acao")
    opcoes_tipo_acao = sorted(tipos_acao_df['nome'].unique().tolist())

    # --- Interface de Entrada ---
    texto_do_dia = st.text_area("Insira o texto para análise aqui:", height=200, placeholder="Ex: O aluno GIDEÃO chegou atrasado na formatura. Elogio o aluno PEREIRA pela sua iniciativa...")

    if st.button("Analisar Texto", type="primary"):
        if texto_do_dia:
            with st.spinner("A IA está a analisar o texto..."):
                sugestoes = processar_texto_com_regras(texto_do_dia, alunos_df, tipos_acao_df)
                st.session_state.sugestoes_ia = sugestoes
                if not sugestoes:
                    st.warning("Nenhuma ação ou aluno conhecido foi identificado no texto.")
        else:
            st.warning("Por favor, insira um texto para ser analisado.")

    st.divider()

    # --- Interface de Saída (Formulários de Confirmação) ---
    if st.session_state.sugestoes_ia:
        st.subheader("Rascunhos Sugeridos para Lançamento")
        st.info("Verifique e edite os dados abaixo antes de lançar cada ação individualmente.")

        # Itera sobre uma cópia da lista para poder remover itens de forma segura
        for i, sugestao in enumerate(list(st.session_state.sugestoes_ia)):
            
            with st.form(key=f"form_sugestao_{i}", border=True):
                st.markdown(f"**Sugestão #{i+1}**")

                # Encontra o índice do tipo de ação sugerido para pré-selecionar no selectbox
                try:
                    index_acao = opcoes_tipo_acao.index(sugestao['tipo_acao'])
                except ValueError:
                    index_acao = 0 # Se não encontrar, seleciona o primeiro

                # --- Campos de Preenchimento Extendido ---
                aluno_nome = st.text_input("Aluno", value=sugestao['nome_guerra'], disabled=True)
                tipo_acao_selecionada = st.selectbox("Tipo de Ação", options=opcoes_tipo_acao, index=index_acao)
                data_acao = st.date_input("Data da Ação", value=sugestao['data'])
                descricao_acao = st.text_area("Descrição", value=sugestao['descricao'], height=150)
                
                # Botão de lançamento dentro do formulário
                if st.form_submit_button("✅ Lançar Esta Ação"):
                    # Lógica para inserir no banco de dados
                    try:
                        tipo_acao_info = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao_selecionada].iloc[0]
                        
                        nova_acao = {
                            'aluno_id': sugestao['aluno_id'],
                            'tipo_acao_id': str(tipo_acao_info['id']),
                            'tipo': tipo_acao_selecionada,
                            'descricao': descricao_acao,
                            'data': data_acao.strftime('%Y-%m-%d'),
                            'usuario': st.session_state.username,
                            'status': 'Pendente'
                        }
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.success(f"Ação '{tipo_acao_selecionada}' lançada para {aluno_nome}!")

                        # Remove a sugestão da lista e recarrega a página
                        st.session_state.sugestoes_ia.pop(i)
                        st.rerun()

                    except Exception as e:
                        st.error(f"Ocorreu um erro ao lançar a ação: {e}")
