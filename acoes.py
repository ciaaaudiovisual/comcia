import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva

# --- FUNÇÃO PRINCIPAL DA PÁGINA ---
def show_lancamentos_page():
    st.title("Lançamento de Ações")
    supabase = init_supabase_client()

    # Carregar dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df.empty or tipos_acao_df.empty:
        st.warning("Não há alunos ou tipos de ação cadastrados. Cadastre-os primeiro.")
        return

    # Formulário para novo lançamento
    st.subheader("Novo Lançamento")
    with st.form("novo_lancamento"):
        col1, col2 = st.columns(2)
        with col1:
            # --- LÓGICA DE BUSCA COM A NOVA ORDENAÇÃO ---
            if not alunos_df.empty:
                # Cria um dicionário que mapeia a string de exibição completa para o ID do aluno
                alunos_opcoes_dict = {
                    f"Nº: {aluno.get('numero_interno', 'S/N')} | {aluno['nome_guerra']} | NIP: {aluno.get('nip', 'S/N')} ({aluno.get('nome_completo', 'S/N')})": aluno['id']
                    for _, aluno in alunos_df.sort_values('numero_interno').iterrows()
                }
                alunos_opcoes_labels = list(alunos_opcoes_dict.keys())
            else:
                alunos_opcoes_dict = {}
                alunos_opcoes_labels = []

            aluno_selecionado_label = st.selectbox(
                "Selecione o Aluno (busque por nº, nome ou NIP)",
                options=alunos_opcoes_labels
            )
            # --- FIM DA LÓGICA DE BUSCA ---

            tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao', 0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação", tipos_opcoes.keys())

        with col2:
            data = st.date_input("Data", datetime.now())
            descricao = st.text_area("Descrição/Justificativa", height=100)

        if st.form_submit_button("Registrar Ação"):
            if not all([descricao, aluno_selecionado_label, tipo_selecionado_str]):
                st.error("Por favor, preencha todos os campos.")
            else:
                try:
                    # Recupera o ID do aluno a partir da label selecionada
                    aluno_id = alunos_opcoes_dict[aluno_selecionado_label]
                    tipo_info = tipos_opcoes[tipo_selecionado_str]
                    
                    ids_numericos = pd.to_numeric(acoes_df['id'], errors='coerce').dropna()
                    novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1

                    nova_acao = {
                        'id': str(novo_id),
                        'aluno_id': aluno_id,
                        'tipo_acao_id': tipo_info['id'],
                        'tipo': tipo_info['nome'],
                        'descricao': descricao,
                        'data': data.strftime('%Y-%m-%d'),
                        'usuario': st.session_state.username,
                        'lancado_faia': False
                    }
                    
                    supabase.table("Acoes").insert(nova_acao).execute()
                    st.success(f"Ação '{tipo_info['nome']}' registrada com sucesso!")
                    load_data.clear()
                    st.rerun()

                except Exception as e:
                    st.error(f"Erro ao salvar a ação: {e}")

    # Histórico de lançamentos recentes
    st.divider()
    st.subheader("Lançamentos Recentes")
    if acoes_df.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        acoes_recentes_df = acoes_df.copy()
        acoes_recentes_df['data'] = pd.to_datetime(acoes_recentes_df['data'], errors='coerce')
        acoes_recentes_df = acoes_recentes_df.sort_values('data', ascending=False).head(10)

        if not tipos_acao_df.empty:
            acoes_com_pontos = calcular_pontuacao_efetiva(acoes_recentes_df, tipos_acao_df, config_df)
            if not acoes_com_pontos.empty:
                acoes_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id')
                for _, acao in acoes_display.iterrows():
                    col1, col2, col3 = st.columns([2, 3, 1])
                    with col1:
                        st.write(f"**{pd.to_datetime(acao['data']).strftime('%d/%m/%Y')}**")
                        st.write(f"Aluno: {acao.get('nome_guerra', 'N/A')}")
                        st.write(f"Pelotão: {acao.get('pelotao', 'N/A')}")
                    with col2:
                        st.write(f"**{acao.get('nome', 'N/A')}**")
                        st.write(acao['descricao'])
                    with col3:
                        pontuacao = float(acao.get('pontuacao_efetiva', 0.0))
                        cor = "green" if pontuacao > 0 else "red" if pontuacao < 0 else "gray"
                        st.markdown(f"<h3 style='color:{cor};text-align:center'>{pontuacao:+.1f}</h3>", unsafe_allow_html=True)
                    st.divider()
        else:
            st.info("Tipos de Ação não carregados, não é possível exibir pontuação.")

# Esta função é mantida por compatibilidade, caso seja usada em outra parte do sistema.
def registrar_acao(aluno_id, nome_aluno):
    st.subheader(f"Registrar Ação para {nome_aluno}")
    supabase = init_supabase_client()
    tipos_acao_df = load_data("Tipos_Acao")
    acoes_df = load_data("Acoes")

    with st.form("registrar_acao_form"):
        if not tipos_acao_df.empty:
            tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao',0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação", list(tipos_opcoes.keys()))
        else:
            st.error("Nenhum tipo de ação cadastrado."); return

        data = st.date_input("Data", datetime.now())
        descricao = st.text_area("Descrição/Justificativa", height=100)
        
        if st.form_submit_button("Registrar"):
            if not descricao or not tipo_selecionado_str:
                st.error("Por favor, forneça uma descrição para a ação.")
            else:
                try:
                    tipo_info = tipos_opcoes[tipo_selecionado_str]
                    ids_numericos = pd.to_numeric(acoes_df['id'], errors='coerce').dropna()
                    novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1
                    nova_acao = {'id': str(novo_id),'aluno_id': str(aluno_id),'tipo_acao_id': str(tipo_info['id']),'tipo': tipo_info['nome'],'descricao': descricao,'data': data.strftime('%Y-%m-%d'),'usuario': st.session_state.username,'lancado_faia': False}
                    supabase.table("Acoes").insert(nova_acao).execute()
                    st.success(f"Ação registrada com sucesso!")
                    load_data.clear()
                    if 'registrar_acao' in st.session_state: st.session_state.registrar_acao = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar a ação: {e}")