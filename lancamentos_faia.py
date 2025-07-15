import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from acoes import calcular_pontuacao_efetiva
from io import BytesIO
import zipfile

# --- FUNÇÕES DE CALLBACK ---
def on_faia_status_change(acao_id, supabase, key_name):
    novo_status = st.session_state[key_name]
    try:
        supabase.table("Acoes").update({'lancado_faia': novo_status}).eq('id', acao_id).execute()
        st.toast("Status FAIA atualizado!")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")

def on_faia_delete_click(acao_id, supabase):
    try:
        supabase.table("Acoes").delete().eq('id', acao_id).execute()
        st.success("Lançamento excluído com sucesso.")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir lançamento: {e}")

# --- FUNÇÕES DE APOIO (HELPER) ---
def formatar_relatorio_individual_txt(aluno_info, acoes_aluno_df):
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

# --- FUNÇÃO DE FILTROS (CORRIGIDA: REMOVIDO BLOCO DUPLICADO) ---
def render_filters(alunos_df):
    """Renderiza os widgets de filtro com seletores dependentes e busca."""
    st.subheader("Filtros")
    col1, col2, col3 = st.columns([2, 2, 1])

    with col1:
        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
        pelotao = st.selectbox("1. Filtrar por Pelotão:", opcoes_pelotao)

    alunos_filtrados_df = alunos_df.copy() # Make a copy to avoid SettingWithCopyWarning
    if pelotao != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao]

    with col2:
        busca_nome = st.text_input("2. Buscar por Nome de Guerra", help="Pode ser usado em conjunto com o filtro de pelotão.")
        if busca_nome:
            alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['nome_guerra'].str.contains(busca_nome, case=False, na=False)]

        nomes_unicos = alunos_filtrados_df['nome_guerra'].unique()
        nomes_validos = [str(nome) for nome in nomes_unicos if pd.notna(nome)]
        
        opcoes_alunos = ["Todos"] + sorted(nomes_validos)
        aluno = st.selectbox("3. Filtrar por Aluno:", opcoes_alunos)

    with col3:
        status = st.radio("Filtrar Status:", ["A Lançar", "Lançados", "Todos"], horizontal=True, index=0)

    return pelotao, aluno, status, busca_nome

def render_export_section(df_filtrado, alunos_df, pelotao_selecionado, aluno_selecionado):
    """Renderiza a seção de exportação de relatórios."""
    if not check_permission('pode_exportar_relatorio_faia'):
        return

    with st.container(border=True):
        st.subheader("📥 Exportar Relatórios")
        # Check if a specific student is selected (not "Todos")
        if aluno_selecionado != "Todos":
            # Find the student information from the *original* alunos_df
            aluno_info_df = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado]
            if not aluno_info_df.empty:
                aluno_info = aluno_info_df.iloc[0]
                # Filter actions specifically for this selected student by their actual ID
                acoes_do_aluno = df_filtrado[df_filtrado['aluno_id'] == aluno_info['id']]
                conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
                nome_arquivo = f"{aluno_info.get('numero_interno','S-N')}_{aluno_info['nome_guerra']}.txt"
                st.download_button(label=f"Exportar relatório de {aluno_selecionado}", data=conteudo_txt.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")
            else:
                st.warning(f"Aluno '{aluno_selecionado}' não encontrado no banco de dados. Não é possível gerar o relatório.")
        elif pelotao_selecionado != "Todos":
            if st.button(f"Gerar e Baixar .ZIP para {pelotao_selecionado}"):
                with st.spinner("Gerando relatórios..."):
                    alunos_do_pelotao = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]
                    zip_buffer = BytesIO()
                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                        for _, aluno_info in alunos_do_pelotao.iterrows():
                            acoes_do_aluno = df_filtrado[df_filtrado['aluno_id'] == aluno_info['id']]
                            conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
                            nome_arquivo = f"{aluno_info.get('numero_interno','S-N')}_{aluno_info.get('nome_guerra','S-N')}.txt"
                            zip_file.writestr(nome_arquivo, conteudo_txt)
                    st.download_button("Clique para baixar o .ZIP", zip_buffer.getvalue(), f"relatorios_{pelotao_selecionado}.zip", "application/zip", use_container_width=True)
        else:
            st.warning("Selecione um pelotão ou um aluno específico para habilitar a exportação.")


def display_launch_list(df_filtrado, alunos_df, supabase):
    """Exibe a lista de lançamentos filtrados."""
    st.header(f"Exibindo {len(df_filtrado)} Lançamentos")
    st.info("Marque a caixa de seleção para confirmar que o lançamento foi realizado na FAIA do aluno.")

    if df_filtrado.empty:
        st.info("Nenhum lançamento encontrado para os filtros selecionados.")
        return

    # Certifica que as colunas de ID são do mesmo tipo para o merge
    df_filtrado['aluno_id'] = df_filtrado['aluno_id'].astype(str)
    alunos_df['id'] = alunos_df['id'].astype(str)

    df_display = pd.merge(df_filtrado, alunos_df[['id','nome_guerra','pelotao']], left_on='aluno_id', right_on='id', how='inner')
    for idx, acao in df_display.sort_values(by='data', ascending=False).iterrows():
        key_checkbox = f"check_{acao['id_x']}_{idx}"
        key_delete = f"delete_{acao['id_x']}_{idx}"

        with st.container(border=True):
            cols = st.columns([1, 10, 1] if check_permission('pode_excluir_lancamento_faia') else [1, 10])
            
            cols[0].checkbox("Lançado?", value=bool(acao['lancado_faia']), key=key_checkbox, on_change=on_faia_status_change, args=(acao['id_x'], supabase, key_checkbox), label_visibility="collapsed")
            
            cor_fundo = "rgba(128, 128, 128, 0.1)" # Gray for neutral/archived or no effective points
            if pd.notna(acao['pontuacao_efetiva']): # Only apply color if pontuacao_efetiva is not NaN
                if acao['pontuacao_efetiva'] > 0: cor_fundo = "rgba(0, 255, 0, 0.1)" # Green for positive points
                elif acao['pontuacao_efetiva'] < 0: cor_fundo = "rgba(255, 0, 0, 0.1)" # Red for negative points

            # Ensure 'data' is datetime before formatting
            data_formatada = pd.to_datetime(acao['data']).strftime('%d/%m/%Y') if pd.notna(acao['data']) else "N/A"

            cols[1].markdown(f"""
            <div style="background-color: {cor_fundo}; padding: 10px; border-radius: 5px; {'opacity: 0.6;' if acao['lancado_faia'] else ''}">
                <b>{data_formatada} - {acao.get('nome_guerra','N/A')} ({acao.get('pelotao','N/A')})</b>
                <br><b>{acao.get('nome','Tipo Desconhecido')}</b>
                <br><small><i>Registrado por: {acao.get('usuario','N/A')}</i></small>
                <br><small>{acao.get('descricao','') if pd.notna(acao.get('descricao')) else 'Sem descrição.'}</small>
            </div>
            """, unsafe_allow_html=True)

            if check_permission('pode_excluir_lancamento_faia'):
                cols[2].button("🗑️", key=key_delete, help="Excluir este lançamento", on_click=on_faia_delete_click, args=(acao['id_x'], supabase))

# --- FUNÇÃO PRINCIPAL ---
def show_lancamentos_faia():
    """Função principal que renderiza a página de gestão de lançamentos da FAIA."""
    st.title("Gestão de Lançamentos (FAIA)")
    st.caption("Controle das anotações a serem lançadas na Ficha de Acompanhamento Individual do Aluno.")
    
    supabase = init_supabase_client()
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if 'lancado_faia' not in acoes_df.columns:
        acoes_df['lancado_faia'] = False
    else:
        # Ensure 'lancado_faia' is boolean for proper filtering
        acoes_df['lancado_faia'] = acoes_df['lancado_faia'].apply(lambda x: str(x).lower() in ['true', '1', 't', 'y', 'yes', 'sim'])
    
    acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)

    # Renderiza os filtros e obtém os valores selecionados
    pelotao_selecionado, aluno_selecionado, status_selecionado, busca_nome = render_filters(alunos_df)

    # Aplica os filtros
    df_filtrado_para_display = acoes_com_pontos_df.copy()

    # Filter by Pelotão
    if pelotao_selecionado != "Todos":
        alunos_ids_no_pelotao = alunos_df[alunos_df['pelotao'] == pelotao_selecionado]['id'].tolist()
        df_filtrado_para_display = df_filtrado_para_display[df_filtrado_para_display['aluno_id'].isin(alunos_ids_no_pelotao)]
    
    # Filter by Search Name
    if busca_nome:
        alunos_ids_por_busca = alunos_df[alunos_df['nome_guerra'].str.contains(busca_nome, case=False, na=False)]['id'].tolist()
        df_filtrado_para_display = df_filtrado_para_display[df_filtrado_para_display['aluno_id'].isin(alunos_ids_por_busca)]

    # Filter by Specific Student (if selected)
    if aluno_selecionado != "Todos":
        # Find the ID of the selected student by name
        aluno_id_obj = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado]['id']
        if not aluno_id_obj.empty:
            aluno_id_especifico = str(aluno_id_obj.iloc[0])
            df_filtrado_para_display = df_filtrado_para_display[df_filtrado_para_display['aluno_id'] == aluno_id_especifico]
        else:
            st.warning(f"Aluno '{aluno_selecionado}' não encontrado para aplicar o filtro.")
            df_filtrado_para_display = pd.DataFrame() # Clear dataframe if student not found

    # Filter by FAIA Status
    if status_selecionado == "A Lançar":
        df_filtrado_para_display = df_filtrado_para_display[df_filtrado_para_display['lancado_faia'] == False]
    elif status_selecionado == "Lançados":
        df_filtrado_para_display = df_filtrado_para_display[df_filtrado_para_display['lancado_faia'] == True]

    st.divider()
    render_export_section(df_filtrado_para_display, alunos_df, pelotao_selecionado, aluno_selecionado)
    st.divider()
    display_launch_list(df_filtrado_para_display, alunos_df, supabase)
