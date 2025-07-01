import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from alunos import calcular_pontuacao_efetiva
from io import BytesIO
import zipfile

# ==============================================================================
# DIÁLOGOS E POPUPS
# ==============================================================================

@st.dialog("Sucesso!")
def show_success_dialog(message):
    """Exibe um popup de sucesso que o utilizador precisa de fechar manualmente."""
    st.success(message)
    if st.button("OK"):
        st.rerun()

@st.dialog("Pré-visualização da FAIA")
def preview_faia_dialog(aluno_info, acoes_aluno_df):
    """Exibe o conteúdo da FAIA e o botão para exportar."""
    st.header(f"FAIA de: {aluno_info['nome_guerra']}")

    # Gera o conteúdo de texto do relatório
    texto_relatorio = formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df)

    # Exibe o conteúdo numa caixa de texto
    st.text_area("Conteúdo do Relatório:", value=texto_relatorio, height=300)

    # Botão para download dentro do popup
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info['nome_guerra']}.txt"
    st.download_button(
        label="✅ Exportar Relatório",
        data=texto_relatorio.encode('utf-8'),
        file_name=nome_arquivo,
        mime="text/plain"
    )

# ==============================================================================
# FUNÇÕES DE CALLBACK
# ==============================================================================

def on_launch_click(acao, supabase):
    """
    Função chamada ao clicar em 'Lançar na FAIA'.
    Atualiza o DB e depois chama o popup de sucesso.
    """
    try:
        supabase.table("Acoes").update({'lancado_faia': True}).eq('id', acao['id']).execute()
        load_data.clear()  # Limpa o cache para garantir que a lista seja atualizada

        # Carrega os dados dos alunos para encontrar o nome para a mensagem de sucesso
        alunos_df = load_data("Alunos")
        aluno_info_query = alunos_df[alunos_df['id'] == str(acao['aluno_id'])]

        if not aluno_info_query.empty:
            aluno_info = aluno_info_query.iloc[0]
            msg = f"A ação '{acao['nome']}' para o aluno {aluno_info['nome_guerra']} foi lançada na FAIA com sucesso!"
            show_success_dialog(msg)
        else:
            # Fallback caso o aluno não seja encontrado
            show_success_dialog("Ação lançada na FAIA com sucesso!")

    except Exception as e:
        st.error(f"Ocorreu um erro ao lançar a ação: {e}")

# ==============================================================================
# FUNÇÕES DE APOIO
# ==============================================================================
def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
    """Formata os dados de um único aluno para uma string de texto."""
    texto = [
        "============================================================",
        "      FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)",
        "============================================================",
        f"\nPelotão: {aluno_info.get('pelotao', 'N/A')}",
        f"Aluno: {aluno_info.get('nome_completo', 'N/A')}",
        f"Nome de Guerra: {aluno_info.get('nome_guerra', 'N/A')}",
        f"Numero Interno: {aluno_info.get('numero_interno', 'N/A')}",
        "\n------------------------------------------------------------",
        "LANÇAMENTOS EM ORDEM CRONOLÓGICA:",
        "------------------------------------------------------------\n"
    ]
    if acoes_aluno_df.empty:
        texto.append("Nenhum lançamento encontrado para este aluno no período filtrado.")
    else:
        for _, acao in acoes_aluno_df.sort_values(by='data').iterrows():
            texto.extend([
                f"Data: {pd.to_datetime(acao['data']).strftime('%Y-%m-%d')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
                f"Descrição: {acao.get('descricao', '')}",
                f"Registrado por: {acao.get('usuario', 'N/A')}",
                f"Lançado na FAIA: {'Sim' if acao.get('lancado_faia') else 'Não'}",
                "\n-----------------------------------\n"
            ])
    texto.extend([
        "\n============================================================",
        f"Fim do Relatório - Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "============================================================"
    ])
    return "\n".join(texto)

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_gestao_acoes():
    st.title("Gestão de Ações dos Alunos")
    supabase = init_supabase_client()

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    # --- FORMULÁRIO DE CRIAÇÃO ---
    with st.expander("➕ Registrar Nova Ação"):
        with st.form("novo_lancamento_unificado", clear_on_submit=True):
            st.info("Preencha os campos de busca para encontrar o aluno e depois os detalhes da ação.")

            # Busca de aluno
            c1, c2, c3 = st.columns(3)
            busca_num_interno = c1.text_input("Buscar por Nº Interno")
            busca_nome_guerra = c2.text_input("Buscar por Nome de Guerra")
            busca_nip = c3.text_input("Buscar por NIP")

            st.divider()

            # Detalhes da Ação
            c4, c5 = st.columns(2)
            if not acoes_df.empty and 'tipo_acao_id' in acoes_df.columns:
                contagem = acoes_df['tipo_acao_id'].value_counts().to_dict()
                tipos_acao_df['contagem'] = tipos_acao_df['id'].astype(str).map(contagem).fillna(0)
                tipos_acao_df = tipos_acao_df.sort_values('contagem', ascending=False)

            tipos_opcoes = {f"{t['nome']} ({float(t.get('pontuacao', 0)):.1f} pts)": t for _, t in tipos_acao_df.iterrows()}
            tipo_selecionado_str = c4.selectbox("Tipo de Ação (mais usados primeiro)", tipos_opcoes.keys())
            data = c5.date_input("Data", datetime.now())
            descricao = st.text_area("Descrição/Justificativa (Opcional)")

            lancar_direto = False
            if check_permission('acesso_pagina_lancamentos_faia'):
                lancar_direto = st.checkbox("🚀 Lançar diretamente na FAIA (ignorar revisão)")

            if st.form_submit_button("Registrar Ação"):
                df_busca = alunos_df.copy()
                if busca_num_interno: df_busca = df_busca[df_busca['numero_interno'] == busca_num_interno]
                if busca_nome_guerra: df_busca = df_busca
