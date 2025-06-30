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

    # --- FORMULÁRIO (MODIFICADO COM CAMPOS DE BUSCA SEPARADOS) ---
    st.subheader("Novo Lançamento")
    with st.form("novo_lancamento"):
        st.info("Preencha um ou mais campos abaixo para buscar o aluno e, em seguida, preencha os detalhes da ação.")
        
        # Novos campos de busca para o aluno
        col_busca1, col_busca2, col_busca3 = st.columns(3)
        with col_busca1:
            busca_num_interno = st.text_input("Buscar por Número Interno")
        with col_busca2:
            busca_nome_guerra = st.text_input("Buscar por Nome de Guerra")
        with col_busca3:
            busca_nip = st.text_input("Buscar por NIP")

        st.divider()

        # Campos para os detalhes da ação
        col_acao1, col_acao2 = st.columns(2)
        with col_acao1:
            # Lógica para ordenar tipos de ação por frequência de uso
            if not acoes_df.empty:
                contagem_acoes = acoes_df['tipo_acao_id'].value_counts().to_dict()
                tipos_acao_df['contagem'] = tipos_acao_df['id'].astype(str).map(contagem_acoes).fillna(0)
                tipos_acao_df = tipos_acao_df.sort_values('contagem', ascending=False)
            
            tipos_opcoes = {f"{tipo['nome']} ({float(tipo.get('pontuacao', 0)):.1f} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação (mais usados primeiro)", tipos_opcoes.keys())

        with col_acao2:
            data = st.date_input("Data", datetime.now())
            descricao = st.text_area("Descrição/Justificativa (Opcional)", height=100)

        if st.form_submit_button("Registrar Ação"):
            # Lógica de busca do aluno ao submeter o formulário
            df_busca = alunos_df.copy()
            if busca_num_interno:
                df_busca = df_busca[df_busca['numero_interno'].astype(str) == str(busca_num_interno)]
            if busca_nome_guerra:
                df_busca = df_busca[df_busca['nome_guerra'].str.contains(busca_nome_guerra, case=False, na=False)]
            if busca_nip:
                # Garante que a coluna NIP exista e faz a busca
                if 'nip' in df_busca.columns:
                    df_busca = df_busca[df_busca['nip'].astype(str) == str(busca_nip)]
                else:
                    st.error("A coluna 'NIP' não foi encontrada na base de dados de alunos.")
                    st.stop()
            
            # Validação do resultado da busca
            if len(df_busca) == 1:
                aluno_encontrado = df_busca.iloc[0]
                aluno_id = aluno_encontrado['id']
                
                # Validação dos campos da ação
                if not tipo_selecionado_str:
                    st.error("Por favor, selecione um tipo de ação.")
                else:
                    try:
                        tipo_info = tipos_opcoes[tipo_selecionado_str]
                        ids_numericos = pd.to_numeric(acoes_df['id'], errors='coerce').dropna()
                        novo_id = int(ids_numericos.max()) + 1 if not ids_numericos.empty else 1

                        nova_acao = {
                            'id': str(novo_id), 'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_info['id']),
                            'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.strftime('%Y-%m-%d'),
                            'usuario': st.session_state.username, 'lancado_faia': False
                        }
                        
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.success(f"Ação '{tipo_info['nome']}' registrada com sucesso para o aluno {aluno_encontrado['nome_guerra']}!")
                        load_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar a ação: {e}")

            elif len(df_busca) > 1:
                st.warning(f"Múltiplos alunos ({len(df_busca)}) encontrados. Por favor, refine a sua busca para identificar um único aluno.")
            else:
                st.error("Nenhum aluno encontrado com os critérios de busca fornecidos.")


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
