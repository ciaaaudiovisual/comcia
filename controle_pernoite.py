# controle_pernoite.py

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from auth import check_permission
from io import BytesIO
from fpdf import FPDF # Usaremos FPDF para gerar um PDF simples

# --- Funções de Callback para o Toggle ---
def on_toggle_change(aluno_id, data_selecionada, supabase):
    """
    Esta função é chamada sempre que um toggle é alterado.
    Ela insere ou atualiza o status de pernoite na base de dados.
    """
    novo_status = st.session_state[f"toggle_{aluno_id}"]
    
    try:
        # Usa upsert: cria se não existir, atualiza se já existir
        supabase.table("pernoite").upsert({
            'aluno_id': str(aluno_id),
            'data': data_selecionada.strftime('%Y-%m-%d'),
            'presente': novo_status
        }, on_conflict='aluno_id,data').execute()
        
        # Opcional: Mostra uma mensagem de sucesso discreta
        # st.toast(f"Status de pernoite atualizado para o aluno.", icon="✅")
        load_data.clear() # Limpa o cache para futuras leituras
    except Exception as e:
        st.error(f"Erro ao salvar status: {e}")

# --- Função para Gerar PDF ---
def gerar_pdf_pernoite(cabecalho_texto, lista_alunos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Cabeçalho
    pdf.cell(0, 10, cabecalho_texto, 0, 1, 'C')
    pdf.ln(10) # Pula uma linha
    
    # Corpo com a lista de alunos
    pdf.set_font("Arial", '', 12)
    for aluno in lista_alunos:
        pdf.cell(0, 10, f"- {aluno}", 0, 1)
        
    # Salva o PDF em memória
    pdf_buffer = BytesIO()
    pdf.output(pdf_buffer)
    return pdf_buffer.getvalue()

# --- Página Principal do Módulo ---
def show_controle_pernoite():
    st.title("Controle de Pernoite (Base de Dados)")

    supabase = init_supabase_client()
    
    # Carregar dados
    alunos_df = load_data("Alunos")
    pernoite_df = load_data("pernoite") # Carrega a nova tabela

    # --- Interface de Seleção ---
    st.subheader("1. Selecione a Data e o Pelotão")
    col1, col2 = st.columns(2)
    with col1:
        data_selecionada = st.date_input("Selecione a Data", datetime.now().date())
    with col2:
        pelotoes = ["Todos"] + sorted(alunos_df['pelotao'].dropna().unique().tolist())
        pelotao_selecionado = st.selectbox("Selecione o Pelotão", pelotoes)

    # Filtrar alunos com base na seleção
    alunos_filtrados_df = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao_selecionado]

    st.markdown("---")
    st.subheader("2. Marque os Alunos em Pernoite")
    
    # Obter o status de pernoite para a data selecionada
    if not pernoite_df.empty and data_selecionada:
        pernoite_df['data'] = pd.to_datetime(pernoite_df['data']).dt.date
        pernoite_hoje = pernoite_df[pernoite_df['data'] == data_selecionada]
        alunos_presentes_ids = pernoite_hoje[pernoite_hoje['presente'] == True]['aluno_id'].tolist()
    else:
        alunos_presentes_ids = []

    # Exibir a lista de alunos com toggles
    for _, aluno in alunos_filtrados_df.sort_values('nome_guerra').iterrows():
        aluno_id = aluno['id']
        default_status = str(aluno_id) in alunos_presentes_ids
        
        st.toggle(
            label=f"**{aluno['nome_guerra']}** ({aluno.get('numero_interno', 'S/N')})",
            value=default_status,
            key=f"toggle_{aluno_id}",
            on_change=on_toggle_change,
            args=(aluno_id, data_selecionada, supabase)
        )
        
    st.markdown("---")
    st.subheader("3. Gerar Relatório em PDF")

    # Obter o cabeçalho salvo ou usar um padrão
    config_df = load_data("Config")
    cabecalho_salvo = config_df[config_df['chave'] == 'cabecalho_pernoite_pdf']['valor'].iloc[0] if 'cabecalho_pernoite_pdf' in config_df['chave'].values else "Relação de Militares em Pernoite"

    cabecalho_editado = st.text_area("Cabeçalho do PDF", value=cabecalho_salvo)
    
    if st.button("Salvar Cabeçalho Padrão"):
        supabase.table("Config").upsert({
            'chave': 'cabecalho_pernoite_pdf',
            'valor': cabecalho_editado
        }).execute()
        st.success("Cabeçalho padrão salvo com sucesso!")
        load_data.clear()

    # Preparar dados para o PDF
    alunos_para_pdf_df = alunos_df[alunos_df['id'].isin(map(str, alunos_presentes_ids))]
    lista_nomes_pdf = sorted(alunos_para_pdf_df['nome_guerra'].tolist())

    st.write(f"**Total de militares em pernoite:** {len(lista_nomes_pdf)}")
    
    if st.button("Gerar PDF", type="primary"):
        if not lista_nomes_pdf:
            st.warning("Nenhum aluno selecionado para pernoite.")
        else:
            pdf_bytes = gerar_pdf_pernoite(cabecalho_editado, lista_nomes_pdf)
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
