# acoes.py
import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva # Mantido para compatibilidade, mas a função agora está em alunos.py
from aluno_selection_components import render_alunos_filter_and_selection # Importa o novo componente

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

    # --- FORMULÁRIO (MODIFICADO COM O COMPONENTE PADRONIZADO) ---
    st.subheader("Novo Lançamento")
    with st.form("novo_lancamento"):
        st.info("Utilize os campos abaixo para buscar e selecionar o aluno. Apenas um aluno pode ser selecionado para registro de ação individual.")
        
        # Chamada do componente padronizado com todos os campos de busca
        alunos_para_registro_df = render_alunos_filter_and_selection(
            key_suffix="lancamento_acao_individual",
            include_full_name_search=True # Ativa a busca por NIP e Nome Completo
        )

        if len(alunos_para_registro_df) == 1:
            aluno_encontrado = alunos_para_registro_df.iloc[0]
            st.success(f"Aluno selecionado: **{aluno_encontrado['nome_guerra']}**")
            
            st.divider()
            st.markdown("#### Detalhes da Ação")
            col_acao1, col_acao2 = st.columns(2)
            with col_acao1:
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
                aluno_id = aluno_encontrado['id']
                
                if not tipo_selecionado_str:
                    st.error("Por favor, selecione um tipo de ação.")
                else:
                    try:
                        tipo_info = tipos_opcoes[tipo_selecionado_str]
                        # IDs agora são gerenciados pelo Supabase automaticamente para novas inserções
                        # se a coluna 'id' for do tipo UUID ou SERIAL. Se for INT, precisa de lógica.
                        # Considerando que 'id' é gerado pelo BD, removemos a lógica de max()+1
                        nova_acao = {
                            'aluno_id': str(aluno_id), 'tipo_acao_id': str(tipo_info['id']),
                            'tipo': tipo_info['nome'], 'descricao': descricao, 'data': data.strftime('%Y-%m-%d'),
                            'usuario': st.session_state.username, 'lancado_faia': False
                        }
                        
                        supabase.table("Acoes").insert(nova_acao).execute()
                        st.success(f"Ação '{tipo_info['nome']}' registrada com sucesso para o aluno {aluno_encontrado['nome_guerra']}!")
                        load_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar a ação: {e}")

        elif len(alunos_para_registro_df) > 1:
            st.warning(f"Múltiplos alunos ({len(alunos_para_registro_df)}) encontrados. Por favor, refine a sua busca para identificar um único aluno.")
        else:
            st.info("Nenhum aluno selecionado. Use os filtros acima para encontrar um aluno.")


    # --- HISTÓRICO DE LANÇAMENTOS (SEM MUDANÇAS ESTRUTURAIS GRANDES AQUI) ---
    st.divider()
    col_header, col_filter = st.columns([3, 1])
    with col_header:
        st.subheader("Lançamentos Recentes")
    with col_filter:
        num_recentes = st.number_input("Mostrar últimos", min_value=5, max_value=50, value=10, step=5, label_visibility="collapsed")

    if acoes_df.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        acoes_df['tipo_acao_id'] = acoes_df['tipo_acao_id'].astype(str)
        tipos_acao_df['id'] = tipos_acao_df['id'].astype(str)

        acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
        
        if not acoes_com_pontos_df.empty:
            acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')
            acoes_recentes_df = acoes_com_pontos_df.sort_values('data', ascending=False).head(num_recentes)
            
            acoes_display = pd.merge(acoes_recentes_df, alunos_df[['id', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id', how='left')

            for _, acao in acoes_display.iterrows():
                with st.container(border=True):
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
    # Esta função provavelmente não será mais chamada diretamente,
    # pois o fluxo de registro de ação agora passa pelo show_lancamentos_page.
    # Mas a mantemos para evitar erros de importação se for usada em outro lugar.
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
                    # Assume que o ID é gerado pelo banco de dados para novas entradas
                    nova_acao = {'aluno_id': str(aluno_id),'tipo_acao_id': str(tipo_info['id']),'tipo': tipo_info['nome'],'descricao': descricao,'data': data.strftime('%Y-%m-%d'),'usuario': st.session_state.username,'lancado_faia': False}
                    supabase.table("Acoes").insert(nova_acao).execute()
                    st.success(f"Ação registrada com sucesso!")
                    load_data.clear()
                    if 'registrar_acao' in st.session_state: st.session_state.registrar_acao = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar a ação: {e}")
