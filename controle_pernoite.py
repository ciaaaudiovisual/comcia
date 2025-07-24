# controle_pernoite.py

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from io import BytesIO
from fpdf import FPDF

# --- FUNÇÃO PARA GERAR PDF (sem alterações) ---
def gerar_pdf_pernoite(cabecalho_texto, data_selecionada, lista_alunos):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    
    # Cabeçalho
    pdf.cell(0, 10, cabecalho_texto, 0, 1, 'C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Data: {data_selecionada.strftime('%d/%m/%Y')}", 0, 1, 'C')
    pdf.ln(10)
    
    # Corpo com a lista de alunos
    pdf.set_font("Arial", '', 12)
    for aluno in lista_alunos:
        pdf.cell(0, 8, f"- {aluno}", 0, 1)
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total de Militares em Pernoite: {len(lista_alunos)}", 0, 1)

    pdf_buffer = BytesIO()
    # FPDF precisa de um encoding para o output em Bytes
    return pdf.output(dest='S').encode('latin-1')


# --- PÁGINA PRINCIPAL DO MÓDULO (REFEITA) ---
def show_controle_pernoite():
    st.title("Controle de Pernoite (Base de Dados)")

    supabase = init_supabase_client()
    
    # Carregar dados
    alunos_df = load_data("Alunos")
    pernoite_df = load_data("pernoite")

    # --- Interface de Seleção ---
    st.subheader("1. Selecione a Data e o Pelotão")
    col1, col2 = st.columns(2)
    with col1:
        data_selecionada = st.date_input("Selecione a Data", datetime.now().date(), key="data_pernoite")
    with col2:
        pelotoes = ["Todos"] + sorted(alunos_df['pelotao'].dropna().unique().tolist())
        pelotao_selecionado = st.selectbox("Selecione o Pelotão", pelotoes, key="pelotao_pernoite")

    # Filtrar alunos com base na seleção
    alunos_filtrados_df = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao_selecionado]
    
    # Garante que os IDs dos alunos visíveis estão em formato de string
    alunos_visiveis_ids = [str(id) for id in alunos_filtrados_df['id'].tolist()]

    st.markdown("---")
    st.subheader("2. Marque os Alunos em Pernoite")

    # Obter o status de pernoite já salvo para a data selecionada
    if not pernoite_df.empty and data_selecionada:
        pernoite_df['data'] = pd.to_datetime(pernoite_df['data']).dt.date
        pernoite_hoje_df = pernoite_df[pernoite_df['data'] == data_selecionada]
        alunos_presentes_ids = [str(id) for id in pernoite_hoje_df[pernoite_hoje_df['presente'] == True]['aluno_id'].tolist()]
    else:
        alunos_presentes_ids = []
    
    # Inicializa o estado da sessão para os checkboxes, se ainda não existir
    if 'pernoite_status' not in st.session_state:
        st.session_state.pernoite_status = {}
    
    # Carrega o estado atual para os checkboxes visíveis
    for aluno_id in alunos_visiveis_ids:
        st.session_state.pernoite_status[aluno_id] = aluno_id in alunos_presentes_ids

    # --- NOVA FUNCIONALIDADE: Botões de Ação em Massa ---
    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    if col_b1.button("Marcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = True
    
    if col_b2.button("Desmarcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = False
    
    st.write("") # Espaçamento

    # Exibe a lista de alunos com checkboxes (sem o `on_change` para evitar recarregamento)
    for _, aluno in alunos_filtrados_df.sort_values('nome_guerra').iterrows():
        aluno_id_str = str(aluno['id'])
        st.checkbox(
            label=f"**{aluno['nome_guerra']}** ({aluno.get('numero_interno', 'S/N')})",
            key=f"check_{aluno_id_str}",
            value=st.session_state.pernoite_status.get(aluno_id_str, False),
            on_change=lambda status, aid=aluno_id_str: st.session_state.pernoite_status.update({aid: status}),
            args=(st.session_state.get(f"check_{aluno_id_str}", False),)
        )

    st.write("") # Espaçamento
    # --- NOVO BOTÃO DE SALVAR ---
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        with st.spinner("A gravar as alterações..."):
            registos_para_salvar = []
            for aluno_id, presente in st.session_state.pernoite_status.items():
                # Apenas salva os alunos que estão visíveis no filtro atual
                if aluno_id in alunos_visiveis_ids:
                    registos_para_salvar.append({
                        'aluno_id': aluno_id,
                        'data': data_selecionada.strftime('%Y-%m-%d'),
                        'presente': presente
                    })
            
            if registos_para_salvar:
                try:
                    # Usa upsert para inserir ou atualizar todos os registos de uma vez
                    supabase.table("pernoite").upsert(registos_para_salvar, on_conflict='aluno_id,data').execute()
                    st.success("Alterações salvas com sucesso!")
                    load_data.clear() # Limpa o cache para a próxima leitura ser fresca
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    
    st.markdown("---")
    st.subheader("3. Gerar Relatório em PDF")

    # Obter o cabeçalho salvo ou usar um padrão
    config_df = load_data("Config")
    cabecalho_salvo = config_df[config_df['chave'] == 'cabecalho_pernoite_pdf']['valor'].iloc[0] if 'cabecalho_pernoite_pdf' in config_df['chave'].values else "Relação de Militares em Pernoite"

    cabecalho_editado = st.text_area("Cabeçalho do PDF", value=cabecalho_salvo, key="cabecalho_pdf")
    
    if st.button("Salvar Cabeçalho Padrão"):
        supabase.table("Config").upsert({'chave': 'cabecalho_pernoite_pdf', 'valor': cabecalho_editado}).execute()
        st.success("Cabeçalho padrão salvo com sucesso!")
        load_data.clear()

    # Preparar dados para o PDF a partir dos dados JÁ SALVOS na base de dados
    # CORREÇÃO DO BUG: A lista para o PDF é gerada a partir dos IDs que foram confirmados como 'presente'
    alunos_para_pdf_df = alunos_df[alunos_df['id'].isin(alunos_presentes_ids)]
    lista_nomes_pdf = sorted(alunos_para_pdf_df['nome_guerra'].tolist())

    st.write(f"**Total de militares em pernoite (salvo no banco de dados):** {len(lista_nomes_pdf)}")

    # O botão de gerar PDF agora funciona com base nos dados salvos, resolvendo o bug.
    if st.button("Gerar PDF", type="secondary"):
        if not lista_nomes_pdf:
            st.warning("Nenhum aluno em pernoite salvo para esta data.")
        else:
            pdf_bytes = gerar_pdf_pernoite(cabecalho_editado, data_selecionada, lista_nomes_pdf)
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
