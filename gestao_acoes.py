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
    """Exibe um popup de sucesso que o utilizador precisa de fechar manually."""
    st.success(message)
    if st.button("OK"):
        st.rerun()

@st.dialog("Pré-visualização da FAIA")
def preview_faia_dialog(aluno_info, acoes_aluno_df):
    """Exibe o conteúdo da FAIA e o botão para exportar."""
    st.header(f"FAIA de: {aluno_info.get('nome_guerra', 'N/A')}")
    texto_relatorio = formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df)
    st.text_area("Conteúdo do Relatório:", value=texto_relatorio, height=300)
    nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','N/A')}.txt"
    st.download_button(label="✅ Baixar Relatório .TXT", data=texto_relatorio.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")

# ==============================================================================
# FUNÇÕES DE APOIO E EXPORTAÇÃO
# ==============================================================================
def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
    """Formata os dados de um único aluno para uma string de texto."""
    texto = [
        "============================================================",
        f"FICHA DE ACOMPANHAMENTO INDIVIDUAL DO ALUNO (FAIA)\n",
        f"Pelotão: {aluno_info.get('pelotao', 'N/A')}",
        f"Aluno: {aluno_info.get('nome_completo', 'N/A')}",
        f"Nome de Guerra: {aluno_info.get('nome_guerra', 'N/A')}",
        f"Numero Interno: {aluno_info.get('numero_interno', 'N/A')}",
        "\n------------------------------------------------------------",
        "LANÇAMENTOS (STATUS 'LANÇADO') EM ORDEM CRONOLÓGICA:",
        "------------------------------------------------------------\n"
    ]
    acoes_lancadas = acoes_aluno_df[acoes_aluno_df['status'] == 'Lançado']

    if acoes_lancadas.empty:
        texto.append("Nenhum lançamento com status 'Lançado' encontrado para este aluno.")
    else:
        for _, acao in acoes_lancadas.sort_values(by='data').iterrows():
            texto.extend([
                f"Data: {pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')}",
                f"Tipo: {acao.get('nome', 'Tipo Desconhecido')}",
                f"Pontos: {acao.get('pontuacao_efetiva', 0.0):+.1f}",
                f"Descrição: {acao.get('descricao', '')}",
                f"Registrado por: {acao.get('usuario', 'N/A')}",
                "\n-----------------------------------\n"
            ])
    texto.extend([
        "\n============================================================",
        f"Fim do Relatório - Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "============================================================"
    ])
    return "\n".join(texto)

def render_export_section(df_acoes_geral, alunos_df, pelotao_selecionado, aluno_selecionado):
    """Renderiza a seção de exportação com opções individual e por pelotão."""
    # Verificação de Permissão: Se o usuário não tiver, a função para aqui.
    if not check_permission('pode_exportar_relatorio_faia'):
        return

    with st.container(border=True):
        st.subheader("📥 Exportar Relatórios FAIA")
        
        # LÓGICA PARA EXPORTAÇÃO INDIVIDUAL
        if aluno_selecionado != "Nenhum":
            st.info(f"Pré-visualize e exporte o relatório individual para {aluno_selecionado}. Serão incluídas apenas as ações com status 'Lançado'.")
            aluno_info = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado].iloc[0]
            acoes_do_aluno = df_acoes_geral[df_acoes_geral['aluno_id'] == aluno_info['id']]
            if st.button(f"👁️ Pré-visualizar e Exportar FAIA de {aluno_selecionado}"):
                preview_faia_dialog(aluno_info, acoes_do_aluno)

        # LÓGICA PARA EXPORTAÇÃO POR PELOTÃO
        elif pelotao_selecionado != "Todos":
            st.info(f"A exportação gerará um arquivo .ZIP com os relatórios de todos os alunos do pelotão '{pelotao_selecionado}'. Serão incluídas apenas as ações com status 'Lançado'.")
            
            alunos_do_pelotao = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]
            with st.expander(f"Ver os {len(alunos_do_pelotao)} alunos que serão incluídos no .ZIP"):
                for _, aluno_info in alunos_do_pelotao.iterrows():
                    st.write(f"- {aluno_info.get('numero_interno', 'SN')} - {aluno_info.get('nome_guerra', 'N/A')}")

            if st.button(f"Gerar e Baixar .ZIP para {pelotao_selecionado}"):
                with st.spinner("Gerando relatórios..."):
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for _, aluno_info in alunos_do_pelotao.iterrows():
                            acoes_do_aluno = df_acoes_geral[df_acoes_geral['aluno_id'] == aluno_info['id']]
                            conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
                            nome_arquivo = f"FAIA_{aluno_info.get('numero_interno','SN')}_{aluno_info.get('nome_guerra','S-N')}.txt"
                            zip_file.writestr(nome_arquivo, conteudo_txt)
                    
                    st.download_button(
                        label="Clique para baixar o .ZIP", 
                        data=zip_buffer.getvalue(), 
                        file_name=f"relatorios_FAIA_{pelotao_selecionado}.zip", 
                        mime="application/zip", 
                        use_container_width=True
                    )
        else:
            st.warning("Selecione um pelotão ou um aluno específico nos filtros para habilitar a exportação.")

# ==============================================================================
# PÁGINA PRINCIPAL
# ==============================================================================
def show_gestao_acoes():
    st.title("Lançamentos de Ações dos Alunos")
    supabase = init_supabase_client()

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")
    
    with st.expander("➕ Registrar Nova Ação", expanded=False):
        # A lógica para registrar nova ação permanece a mesma
        pass
    
    st.divider()
    
    st.subheader("Filtros e Exportação")
    
    # FILTROS PRINCIPAIS COM FILTRO DE ALUNO
    col_filtros1, col_filtros2 = st.columns(2)
    with col_filtros1:
        filtro_pelotao = st.selectbox("1. Filtrar Pelotão", ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)]))
        alunos_filtrados_pelotao = alunos_df[alunos_df['pelotao'] == filtro_pelotao] if filtro_pelotao != "Todos" else alunos_df
        # Pega os nomes de guerra únicos
        nomes_unicos = alunos_filtrados_pelotao['nome_guerra'].unique()
        # Remove valores nulos (None/NaN) e garante que tudo seja string antes de ordenar
        nomes_validos = [str(nome) for nome in nomes_unicos if pd.notna(nome)]
        
        # Cria a lista de opções final com os dados limpos e ordenados
        opcoes_alunos = ["Nenhum"] + sorted(nomes_validos)

filtro_aluno = st.selectbox("2. Filtrar Aluno (Opcional)", opcoes_alunos)
    with col_filtros2:
        filtro_status = st.selectbox("Filtrar Status", ["Pendente", "Lançado", "Arquivado", "Todos"], index=0)
        opcoes_tipo_acao = ["Todos"] + sorted(tipos_acao_df['nome'].unique().tolist())
        filtro_tipo_acao = st.selectbox("Filtrar por Tipo de Ação", opcoes_tipo_acao)

    ordenar_por = st.selectbox("Ordenar por", ["Mais Recentes", "Mais Antigos", "Aluno (A-Z)"])

    # LÓGICA DE FILTRAGEM
    acoes_com_pontos = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    df_display = pd.DataFrame()
    if not acoes_com_pontos.empty:
        df_display = pd.merge(acoes_com_pontos, alunos_df[['id', 'numero_interno', 'nome_guerra', 'pelotao', 'nome_completo']], left_on='aluno_id', right_on='id', how='inner')
    
    df_filtrado_final = df_display.copy()
    if not df_filtrado_final.empty:
        if filtro_pelotao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['pelotao'] == filtro_pelotao]
        if filtro_aluno != "Nenhum":
             aluno_id_filtrado = alunos_df[alunos_df['nome_guerra'] == filtro_aluno].iloc[0]['id']
             df_filtrado_final = df_filtrado_final[df_filtrado_final['aluno_id'] == aluno_id_filtrado]
        if filtro_status != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['status'] == filtro_status]
        if filtro_tipo_acao != "Todos": df_filtrado_final = df_filtrado_final[df_filtrado_final['nome'] == filtro_tipo_acao]
        
        if ordenar_por == "Mais Antigos": df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=True)
        elif ordenar_por == "Aluno (A-Z)": df_filtrado_final = df_filtrado_final.sort_values(by="nome_guerra", ascending=True)
        else: df_filtrado_final = df_filtrado_final.sort_values(by="data", ascending=False) 

    st.divider()
    # CHAMADA DA SEÇÃO DE EXPORTAÇÃO
    render_export_section(acoes_com_pontos, alunos_df, filtro_pelotao, filtro_aluno)
    st.divider()

    st.subheader("Fila de Revisão e Ações")
    # A LÓGICA DE EXIBIÇÃO DA FILA permanece a mesma...
    if df_filtrado_final.empty:
        st.info("Nenhuma ação encontrada para os filtros selecionados.")
    else:
        df_filtrado_final.drop_duplicates(subset=['id_x'], keep='first', inplace=True)
        for _, acao in df_filtrado_final.iterrows():
            with st.container(border=True):
                info_col, actions_col = st.columns([7, 3])
                with info_col:
                    cor = "green" if acao['pontuacao_efetiva'] > 0 else "red" if acao['pontuacao_efetiva'] < 0 else "gray"
                    data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y %H:%M')
                    st.markdown(f"**{acao.get('numero_interno', 'S/N')} - {acao.get('nome_guerra', 'N/A')}** em {data_formatada}")
                    st.markdown(f"**Ação:** {acao['nome']} <span style='color:{cor}; font-weight:bold;'>({acao['pontuacao_efetiva']:+.1f} pts)</span>", unsafe_allow_html=True)
                    st.caption(f"Descrição: {acao['descricao']}" if aco['descricao'] else "Sem descrição.")
                
                with actions_col:
                    status_atual = acao.get('status', 'Pendente')
                    can_launch = check_permission('acesso_pagina_lancamentos_faia')
                    can_delete = check_permission('pode_excluir_lancamento_faia')

                    if status_atual == 'Lançado':
                        st.success("✅ Lançado")
                    elif status_atual == 'Arquivado':
                        st.warning("🗄️ Arquivado")
                    elif status_atual == 'Pendente' and can_launch:
                        with st.form(f"launch_form_{acao['id_x']}"):
                            if st.form_submit_button("🚀 Lançar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Lançado'}).eq('id', acao['id_x']).execute()
                                load_data.clear(); st.rerun()
                    
                    if status_atual != 'Arquivado' and can_delete:
                        with st.form(f"archive_form_{acao['id_x']}"):
                            if st.form_submit_button("🗑️ Arquivar", use_container_width=True):
                                supabase.table("Acoes").update({'status': 'Arquivado'}).eq('id', acao['id_x']).execute()
                                load_data.clear(); st.rerun()
