# relatorio_geral.py

import streamlit as st
import pandas as pd
from database import load_data
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final
from aluno_selection_components import render_alunos_filter_and_selection

def processar_dados_alunos_selecionados(alunos_selecionados_df, acoes_df, tipos_acao_df, config_df, todos_alunos_df):
    """
    Calcula as métricas e coleta as anotações para os alunos selecionados.
    Retorna um DataFrame pronto para exibição.
    """
    if alunos_selecionados_df.empty or acoes_df.empty or tipos_acao_df.empty:
        return pd.DataFrame()

    # Calcula a pontuação para TODAS as ações de uma vez para otimização
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)

    # Dicionário de configuração para o cálculo do conceito
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}

    # Lista para armazenar os dados processados de cada aluno
    dados_processados = []

    for _, aluno in alunos_selecionados_df.iterrows():
        aluno_id_str = str(aluno['id'])
        
        # Filtra as ações para o aluno atual
        acoes_do_aluno = acoes_com_pontos[acoes_com_pontos['aluno_id'] == aluno_id_str]
        
        soma_pontos = acoes_do_aluno['pontuacao_efetiva'].sum()
        
        media_academica = float(aluno.get('media_academica', 0.0))
        
        conceito_final = calcular_conceito_final(
            soma_pontos,
            media_academica,
            todos_alunos_df, # Passa o DataFrame completo para o cálculo
            config_dict
        )
        
        # Separa as anotações em positivas e negativas
        anotacoes_positivas = acoes_do_aluno[acoes_do_aluno['pontuacao_efetiva'] > 0]
        anotacoes_negativas = acoes_do_aluno[acoes_do_aluno['pontuacao_efetiva'] < 0]

        dados_processados.append({
            'id': aluno_id_str,
            'nome_guerra': aluno.get('nome_guerra', 'N/A'),
            'numero_interno': aluno.get('numero_interno', 'S/N'),
            'pelotao': aluno.get('pelotao', 'N/A'),
            'soma_pontos_acoes': soma_pontos,
            'conceito_final': conceito_final,
            'anotacoes_positivas': anotacoes_positivas,
            'anotacoes_negativas': anotacoes_negativas
        })
        
    return pd.DataFrame(dados_processados)


def show_relatorio_geral():
    """
    Renderiza a página do Relatório Geral Compacto.
    """
    st.title("Relatório Geral de Alunos")
    st.caption("Uma visão planilhada e compacta do desempenho e anotações dos alunos.")

    if not check_permission('acesso_pagina_relatorios'):
        st.error("Acesso negado. Você não tem permissão para visualizar esta página.")
        return

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df.empty:
        st.warning("Nenhum aluno cadastrado no sistema.")
        return

    # Seção de Filtros e Seleção
    st.subheader("1. Selecione os Alunos ou Pelotões")
    alunos_selecionados_df = render_alunos_filter_and_selection(
        key_suffix="relatorio_geral",
        include_full_name_search=True
    )

    st.divider()

    # Seção de Exibição dos Relatórios
    st.subheader("2. Relatório de Desempenho")
    if alunos_selecionados_df.empty:
        st.info("Utilize os filtros acima para selecionar os alunos que deseja analisar.")
    else:
        with st.spinner("Processando dados dos alunos selecionados..."):
            df_relatorio = processar_dados_alunos_selecionados(
                alunos_selecionados_df, acoes_df, tipos_acao_df, config_df, alunos_df
            )

        st.info(f"Exibindo relatório para **{len(df_relatorio)}** aluno(s) selecionado(s).")
        st.write("")

        # Ordenação
        df_relatorio = df_relatorio.sort_values(by='conceito_final', ascending=False)

        for _, aluno_data in df_relatorio.iterrows():
            with st.container(border=True):
                col_info, col_metricas, col_pos, col_neg = st.columns([1.5, 1, 2, 2])

                with col_info:
                    st.markdown(f"**{aluno_data['nome_guerra']}**")
                    st.caption(f"Nº {aluno_data['numero_interno']} | Pel: {aluno_data['pelotao']}")
                
                with col_metricas:
                    st.metric("Conceito Final", f"{aluno_data['conceito_final']:.3f}")
                    st.metric("Saldo de Pontos", f"{aluno_data['soma_pontos_acoes']:.2f}", delta_color="off")

                with col_pos:
                    st.markdown("✅ **Positivas**")
                    anotacoes = aluno_data['anotacoes_positivas']
                    if anotacoes.empty:
                        st.caption("Nenhuma anotação.")
                    else:
                        for _, an in anotacoes.iterrows():
                            st.caption(f"- {an['nome']} ({an['pontuacao_efetiva']:+.1f})")

                with col_neg:
                    st.markdown("⚠️ **Negativas**")
                    anotacoes = aluno_data['anotacoes_negativas']
                    if anotacoes.empty:
                        st.caption("Nenhuma anotação.")
                    else:
                        for _, an in anotacoes.iterrows():
                            st.caption(f"- {an['nome']} ({an['pontuacao_efetiva']:+.1f})")
