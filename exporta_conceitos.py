import streamlit as st
import pandas as pd
from io import BytesIO
from database import load_data
from auth import check_permission
from alunos import calcular_pontuacao_efetiva, calcular_conceito_final

@st.cache_data(ttl=300)
def processar_dados_para_exportacao():
    """
    Processa todos os dados dos alunos, calcula pontuações e conceitos.
    Esta função é otimizada com cache para não reprocessar a cada interação.
    """
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if alunos_df.empty:
        return pd.DataFrame()

    # Remover alunos com pelotão 'BAIXA'
    alunos_df = alunos_df[alunos_df['pelotao'].str.strip().str.upper() != 'BAIXA'].copy()

    # Lógica de cálculo de pontos e conceitos (reutilizada de outros módulos)
    config_dict = pd.Series(config_df.valor.values, index=config_df.chave).to_dict() if not config_df.empty else {}
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    
    soma_pontos_por_aluno = acoes_com_pontos.groupby('aluno_id')['pontuacao_efetiva'].sum()
    
    alunos_df['id'] = alunos_df['id'].astype(str)
    soma_pontos_por_aluno.index = soma_pontos_por_aluno.index.astype(str)
    
    alunos_df['soma_pontos_acoes'] = alunos_df['id'].map(soma_pontos_por_aluno).fillna(0)
    
    alunos_df['conceito_final'] = alunos_df.apply(
        lambda row: calcular_conceito_final(
            row['soma_pontos_acoes'],
            float(row.get('media_academica', 0.0)),
            alunos_df, # Passa o DataFrame completo para o cálculo
            config_dict
        ),
        axis=1
    )
    
    alunos_df['media_academica_num'] = pd.to_numeric(alunos_df['media_academica'], errors='coerce').fillna(0.0)
    alunos_df['classificacao_final_prevista'] = ((alunos_df['media_academica_num'] * 3) + (alunos_df['conceito_final'] * 2)) / 5
    
    # Lógica de ordenação por número interno (corrigida)
    alunos_df['numero_interno_str'] = alunos_df['numero_interno'].astype(str)
    split_cols = alunos_df['numero_interno_str'].str.split('-', expand=True)
    alunos_df['sort_part_1'] = split_cols[0]
    if len(split_cols.columns) > 1:
        alunos_df['sort_part_2'] = pd.to_numeric(split_cols[1], errors='coerce').fillna(0)
    else:
        alunos_df['sort_part_2'] = 0
    if len(split_cols.columns) > 2:
        alunos_df['sort_part_3'] = pd.to_numeric(split_cols[2], errors='coerce').fillna(0)
    else:
        alunos_df['sort_part_3'] = 0

    alunos_df = alunos_df.sort_values(by=['sort_part_1', 'sort_part_2', 'sort_part_3'])

    return alunos_df

def to_excel(df: pd.DataFrame) -> bytes:
    """
    Converte um DataFrame para um arquivo Excel em memória.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Conceitos')
        # Auto-ajuste da largura das colunas
        for column in df:
            column_width = max(df[column].astype(str).map(len).max(), len(column))
            col_idx = df.columns.get_loc(column)
            writer.sheets['Conceitos'].set_column(col_idx, col_idx, column_width)
    processed_data = output.getvalue()
    return processed_data

def show_exporta_conceitos():
    st.title("Exportar Planilha de Conceitos")
    st.caption("Gere um arquivo Excel com os conceitos dos alunos, ordenado por número interno.")

    if not check_permission('acesso_pagina_relatorios'):
        st.error("Acesso negado.")
        return

    df_completo = processar_dados_para_exportacao()

    if df_completo.empty:
        st.warning("Não há dados de alunos para processar.")
        return

    # Filtro por Pelotão (Mike)
    pelotoes = ["Todos os Pelotões"] + sorted(df_completo['pelotao'].dropna().unique().tolist())
    pelotao_selecionado = st.selectbox(
        "Selecione a Mike (Pelotão) para exportar:",
        pelotoes
    )

    df_filtrado = df_completo.copy()
    if pelotao_selecionado != "Todos os Pelotões":
        df_filtrado = df_filtrado[df_filtrado['pelotao'] == pelotao_selecionado]

    # Selecionar e renomear colunas para o relatório final
    colunas_exportar = {
        'numero_interno': 'Nº Interno',
        'nome_guerra': 'Nome de Guerra',
        'pelotao': 'Pelotão',
        'soma_pontos_acoes': 'Saldo de Pontos',
        'media_academica_num': 'Média Acadêmica',
        'conceito_final': 'Conceito Final',
        'classificacao_final_prevista': 'Classificação Prevista'
    }
    
    df_export = df_filtrado[list(colunas_exportar.keys())].rename(columns=colunas_exportar)

    st.subheader("Pré-visualização dos Dados")
    st.dataframe(df_export, hide_index=True, use_container_width=True)

    st.divider()

    excel_bytes = to_excel(df_export)
    
    st.download_button(
        label="📥 Baixar Planilha (.xlsx)",
        data=excel_bytes,
        file_name=f"relatorio_conceitos_{pelotao_selecionado.replace(' ', '_')}_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )
