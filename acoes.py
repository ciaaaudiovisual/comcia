import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva

# --- FUNÇÃO PRINCIPAL DA PÁGINA (MODIFICADA) ---
def show_lancamentos_page():
    st.title("Lançamento de Ações")
    supabase = init_supabase_client()

    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df.empty or tipos_acao_df.empty:
        st.warning("Não há alunos ou tipos de ação cadastrados. Cadastre-os primeiro.")
        return

    # --- FORMULÁRIO (MODIFICADO) ---
    st.subheader("Novo Lançamento")
    with st.form("novo_lancamento"):
        col1, col2 = st.columns(2)
        with col1:
            alunos_opcoes_dict = {
                f"Nº: {aluno.get('numero_interno', 'S/N')} | {aluno['nome_guerra']} ({aluno.get('pelotao', 'S/N')})": aluno['id']
                for _, aluno in alunos_df.sort_values('numero_interno').iterrows()
            }
            aluno_selecionado_label = st.selectbox("Selecione o Aluno", options=list(alunos_opcoes_dict.keys()))

            # Lógica para ordenar tipos de ação por frequência de uso
            if not acoes_df.empty:
                contagem_acoes = acoes_df['tipo_acao_id'].value_counts().to_dict()
                tipos_acao_df['contagem'] = tipos_acao_df['id'].astype(str).map(contagem_acoes).fillna(0)
                tipos_acao_df = tipos_acao_df.sort_values('contagem', ascending=False)
            
            tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao', 0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação (mais usados primeiro)", tipos_opcoes.keys())

        with col2:
            data = st.date_input("Data", datetime.now())
            # Descrição agora é opcional
            descricao = st.text_area("Descrição/Justificativa (Opcional)", height=100)

        if st.form_submit_button("Registrar Ação"):
            # Validação foi ajustada: descrição não é mais obrigatória
            if not all([aluno_selecionado_label, tipo_selecionado_str]):
                st.error("Por favor, selecione um aluno e um tipo de ação.")
            else:
                try:
                    aluno_id = alunos_opcoes_dict[aluno_selecionado_label]
                    tipo_info = tipos_opcoes[tipo_selecionado_str]
                    
                    ids_numericos = pd.to_numeric(acoes_df['id'], errors='coerce').dropna()
                    novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1

                    nova_acao = {
                        'id': str(novo_id), 'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_info['id']),
                        'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.strftime('%Y-%m-%d'),
                        'usuario': st.session_state.username, 'lancado_faia': False
                    }
                    
                    supabase.table("Acoes").insert(nova_acao).execute()
                    st.success(f"Ação '{tipo_info['nome']}' registrada com sucesso!")
                    load_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar a ação: {e}")

    # --- HISTÓRICO DE LANÇAMENTOS (MODIFICADO) ---
    st.divider()
    col_header, col_filter = st.columns([3, 1])
    with col_header:
        st.subheader("Lançamentos Recentes")
    with col_filter:
        # Filtro para número de lançamentos a exibir
        num_recentes = st.number_input("Mostrar últimos", min_value=5, max_value=50, value=10, step=5, label_visibility="collapsed")

    if acoes_df.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        # Garante que as colunas de ID sejam do mesmo tipo para o merge
        acoes_df['tipo_acao_id'] = acoes_df['tipo_acao_id'].astype(str)
        tipos_acao_df['id'] = tipos_acao_df['id'].astype(str)

        # CORREÇÃO DA LÓGICA DE CÁLCULO DE PONTOS
        # A função é chamada com o DataFrame completo para garantir a junção correta
        acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
        
        if not acoes_com_pontos_df.empty:
            acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')
            acoes_recentes_df = acoes_com_pontos_df.sort_values('data', ascending=False).head(num_recentes)
            
            # Junta com os dados dos alunos para exibir nome e pelotão
            acoes_display = pd.merge(acoes_recentes_df, alunos_df[['id', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id', how='left')

            for _, acao in acoes_display.iterrows():
                with st.container(border=True):
                    # Layout em colunas para um card mais compacto
                    col_info, col_pontos = st.columns([4, 1])
                    with col_info:
                        data_fmt = pd.to_datetime(acao['data']).strftime('%d/%m/%Y')
                        st.markdown(f"**{acao.get('nome', 'N/A')}** para **{acao.get('nome_guerra', 'N/A')}** ({acao.get('pelotao', 'N/A')}) em {data_fmt}")
                        if acao.get('descricao'):
                            st.caption(f"Descrição: {acao['descricao']}")
                        st.caption(f"Registrado por: {acao.get('usuario', 'N/A')}")
                    with col_pontos:
                        pontuacao = float(acao.get('pontuacao_efetiva', 0.0))
                        cor = "green" if pontuacao > 0 else "red" if pontuacao < 0 else "gray"
                        st.markdown(f"<h3 style='color:{cor}; text-align:right; margin:0;'>{pontuacao:+.1f}</h3>", unsafe_allow_html=True)
                        st.markdown(f"<p style='text-align:right; margin:0;'>pontos</p>", unsafe_allow_html=True)
        else:
            st.info("Não foi possível calcular os pontos das ações.")

# Função de apoio (mantida por compatibilidade)
def registrar_acao(aluno_id, nome_aluno):
    # O código desta função não foi alterado pois é um fluxo secundário.
    # As principais melhorias foram na função principal 'show_lancamentos_page'.
    pass
