import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from acoes import calcular_pontuacao_efetiva
from io import BytesIO
import zipfile

# ==============================================================================
# FUNÇÕES DE CALLBACK (CORRIGIDAS)
# ==============================================================================

def on_faia_status_change(acao_id, supabase, key_name):
    """
    Atualiza o status 'lancado_faia' de uma ação.
    A chamada st.rerun() foi removida, pois o Streamlit recarrega o app
    automaticamente após a execução de um callback.
    """
    novo_status = st.session_state[key_name]
    try:
        supabase.table("Acoes").update({'lancado_faia': novo_status}).eq('id', acao_id).execute()
        st.toast("Status FAIA atualizado!")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao atualizar status: {e}")


def on_faia_delete_click(acao_id, supabase):
    """
    Exclui um lançamento da FAIA.
    Corrigido de 'experimental_rerun' e depois removido pela mesma razão acima.
    """
    try:
        supabase.table("Acoes").delete().eq('id', acao_id).execute()
        st.success("Lançamento excluído com sucesso.")
        load_data.clear()
    except Exception as e:
        st.error(f"Erro ao excluir lançamento: {e}")

# ==============================================================================
# FUNÇÕES DE APOIO (HELPERS)
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

def render_filters(alunos_df):
    """Renderiza os widgets de filtro e retorna as seleções."""
    st.subheader("Filtros")
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        opcoes_pelotao = ["Todos"] + sorted([p for p in alunos_df['pelotao'].unique() if pd.notna(p)])
        pelotao = st.selectbox("Filtrar por Pelotão:", opcoes_pelotao)
        
    with col2:
        # --- INÍCIO DA CORREÇÃO ---
        # 1. Pega os nomes de guerra únicos
        nomes_unicos = alunos_df['nome_guerra'].unique()
        
        # 2. Filtra a lista para remover valores nulos (NaN/None) e garante que tudo seja string
        nomes_validos = [str(nome) for nome in nomes_unicos if pd.notna(nome)]
        
        # 3. Cria a lista de opções final, agora com dados limpos e seguros para ordenar
        opcoes_alunos = ["Todos"] + sorted(nomes_validos)
        # --- FIM DA CORREÇÃO ---
        
        aluno = st.selectbox("Filtrar por Aluno:", opcoes_alunos)
        
    with col3:
        status = st.radio("Filtrar Status:", ["A Lançar", "Lançados", "Todos"], horizontal=True, index=0)
        
    return pelotao, aluno, status

def render_export_section(df_filtrado, alunos_df, pelotao_selecionado, aluno_selecionado):
    """Renderiza a seção de exportação de relatórios."""
    if not check_permission('pode_exportar_relatorio_faia'):
        return

    with st.container(border=True):
        st.subheader("📥 Exportar Relatórios")
        if aluno_selecionado != "Todos":
            aluno_info = alunos_df[alunos_df['nome_guerra'] == aluno_selecionado].iloc[0]
            acoes_do_aluno = df_filtrado[df_filtrado['aluno_id'] == aluno_info['id']]
            conteudo_txt = formatar_relatorio_individual_txt(aluno_info, acoes_do_aluno)
            nome_arquivo = f"{aluno_info.get('numero_interno','S-N')}_{aluno_info['nome_guerra']}.txt"
            st.download_button(label=f"Exportar relatório de {aluno_selecionado}", data=conteudo_txt.encode('utf-8'), file_name=nome_arquivo, mime="text/plain")
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
                    st.download_button("Clique para baixar o .ZIP", zip_buffer, f"relatorios_{pelotao_selecionado}.zip", "application/zip", use_container_width=True)
        else:
            st.warning("Selecione um pelotão ou um aluno específico para habilitar a exportação.")


def display_launch_list(df_filtrado, alunos_df, supabase):
    """Exibe a lista de lançamentos filtrados."""
    st.header(f"Exibindo {len(df_filtrado)} Lançamentos")
    st.info("Marque a caixa de seleção para confirmar que o lançamento foi realizado na FAIA do aluno.")

    if df_filtrado.empty:
        st.info("Nenhum lançamento encontrado para os filtros selecionados.")
        return

    df_display = pd.merge(df_filtrado, alunos_df[['id','nome_guerra','pelotao']], left_on='aluno_id', right_on='id')
    for idx, acao in df_display.sort_values(by='data', ascending=False).iterrows():
        key_checkbox = f"check_{acao['id_x']}_{idx}"
        key_delete = f"delete_{acao['id_x']}_{idx}"

        with st.container(border=True):
            cols = st.columns([1, 10, 1] if check_permission('pode_excluir_lancamento_faia') else [1, 10])
            
            cols[0].checkbox("Lançado?", value=bool(acao['lancado_faia']), key=key_checkbox, on_change=on_faia_status_change, args=(acao['id_x'], supabase, key_checkbox), label_visibility="collapsed")
            
            cor_fundo = "rgba(128, 128, 128, 0.1)"
            if acao['pontuacao_efetiva'] > 0: cor_fundo = "rgba(0, 255, 0, 0.1)"
            elif acao['pontuacao_efetiva'] < 0: cor_fundo = "rgba(255, 0, 0, 0.1)"
            
            cols[1].markdown(f"""
            <div style="background-color: {cor_fundo}; padding: 10px; border-radius: 5px; {'opacity: 0.6;' if acao['lancado_faia'] else ''}">
                <b>{pd.to_datetime(acao['data']).strftime('%d/%m/%Y')} - {acao.get('nome_guerra','N/A')} ({acao.get('pelotao','N/A')})</b>
                <br><b>{acao.get('nome','Tipo Desconhecido')}</b>
                <br><small><i>Registrado por: {acao.get('usuario','N/A')}</i></small>
                <br><small>{acao.get('descricao','')}</small>
            </div>
            """, unsafe_allow_html=True)

            if check_permission('pode_excluir_lancamento_faia'):
                cols[2].button("🗑️", key=key_delete, help="Excluir este lançamento", on_click=on_faia_delete_click, args=(acao['id_x'], supabase))

# ==============================================================================
# FUNÇÃO PRINCIPAL DA PÁGINA
# ==============================================================================

def show_lancamentos_faia():
    """Função principal que renderiza a página de gestão de lançamentos da FAIA."""
    st.title("Gestão de Lançamentos (FAIA)")
    st.caption("Controle das anotações a serem lançadas na Ficha de Acompanhamento Individual do Aluno.")
    
    # Inicialização e carregamento de dados
    supabase = init_supabase_client()
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if 'lancado_faia' not in acoes_df.columns:
        acoes_df['lancado_faia'] = False
    else:
        # Garante que a coluna seja booleana
        acoes_df['lancado_faia'] = acoes_df['lancado_faia'].apply(lambda x: str(x).lower() in ['true', '1', 't', 'y', 'yes', 'sim'])
    
    acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)

    # Renderiza os filtros e obtém os valores selecionados
    pelotao, aluno, status = render_filters(alunos_df)

    # Aplica os filtros
    df_filtrado = acoes_com_pontos_df.copy()
    if pelotao != "Todos":
        alunos_ids = alunos_df[alunos_df['pelotao'] == pelotao]['id'].tolist()
        df_filtrado = df_filtrado[df_filtrado['aluno_id'].isin(alunos_ids)]
    if aluno != "Todos":
        aluno_id = alunos_df[alunos_df['nome_guerra'] == aluno]['id'].iloc[0]
        df_filtrado = df_filtrado[df_filtrado['aluno_id'] == aluno_id]
    if status == "A Lançar":
        df_filtrado = df_filtrado[~df_filtrado['lancado_faia']]
    elif status == "Lançados":
        df_filtrado = df_filtrado[df_filtrado['lancado_faia']]

    # Renderiza as outras seções da página
    st.divider()
    render_export_section(df_filtrado, alunos_df, pelotao, aluno)
    st.divider()
    display_launch_list(df_filtrado, alunos_df, supabase)
