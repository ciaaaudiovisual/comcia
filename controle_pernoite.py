# controle_pernoite.py (v2 - Layout do PDF Atualizado)

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from io import BytesIO
from fpdf import FPDF
import math

# --- FUNÇÃO PARA GERAR PDF (COM O NOVO LAYOUT) ---
def gerar_pdf_pernoite(
    cabecalho_principal,
    texto_esquerda,
    texto_direita,
    rodape_texto,
    data_selecionada,
    alunos_df_sorted
):
    """
    Gera o PDF do relatório de pernoite com o novo layout personalizado.
    """
    # --- Classe PDF personalizada para controlar cabeçalho e rodapé ---
    class PDF(FPDF):
        def __init__(self, cabecalho_txt, txt_esq, txt_dir, rodape_txt):
            super().__init__()
            # Armazena os textos personalizados
            self.cabecalho_texto = cabecalho_txt
            self.texto_esquerda = txt_esq
            self.texto_direita = txt_dir
            self.rodape_texto = rodape_txt

        def header(self):
            # 1. Cabeçalho principal com quebra de linha
            self.set_font("Arial", 'B', 12)
            # O multi_cell permite que o texto quebre a linha automaticamente
            self.multi_cell(0, 6, self.cabecalho_texto, 0, 'C')
            self.ln(2)

            # 2. Data da seleção
            self.set_font("Arial", '', 12)
            self.cell(0, 10, f"Data: {data_selecionada.strftime('%d/%m/%Y')}", 0, 1, 'C')
            self.ln(5)

            # 3. Campos de texto personalizados (esquerda e direita)
            y_antes = self.get_y()
            self.cell(self.w / 2, 8, self.texto_esquerda, 0, 0, 'L')
            self.set_y(y_antes) # Reposiciona o cursor para a mesma linha
            self.cell(0, 8, self.texto_direita, 0, 1, 'R')
            self.ln(5)

            # 4. Cabeçalho da tabela
            self.set_font("Arial", 'B', 12)
            self.cell(0, 10, "NÚMERO INTERNO DE ALUNOS", 1, 1, 'C')

        def footer(self):
            # Posiciona o cursor para o rodapé (2 cm do fundo)
            self.set_y(-20)
            self.set_font('Arial', 'I', 10)
            # Rodapé personalizado com quebra de linha
            self.multi_cell(0, 5, self.rodape_texto, 0, 'C')
            
            # Número da página
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    # --- Lógica de Geração do PDF ---
    pdf = PDF(cabecalho_principal, texto_esquerda, texto_direita, rodape_texto)
    pdf.add_page()
    pdf.set_font("Arial", '', 10) 

    lista_numeros_internos = alunos_df_sorted['numero_interno'].tolist()
    total_militares = len(lista_numeros_internos)

    # Definição do novo layout da tabela (4 pares de colunas por linha)
    num_pares_por_linha = 4
    largura_pagina = pdf.w - 2 * pdf.l_margin
    
    # Define a largura das colunas (20% para o N° de ordem, 80% para o N° Interno)
    largura_par = largura_pagina / num_pares_por_linha
    largura_col_ordem = largura_par * 0.20
    largura_col_valor = largura_par * 0.80
    altura_linha = 8

    for idx, numero_interno in enumerate(lista_numeros_internos):
        # Inicia uma nova linha quando necessário
        if idx % num_pares_por_linha == 0 and idx > 0:
            pdf.ln()

        # Adiciona a célula do número de ordem
        pdf.cell(largura_col_ordem, altura_linha, str(idx + 1), 1, 0, 'C')
        # Adiciona a célula do número interno do aluno
        pdf.cell(largura_col_valor, altura_linha, str(numero_interno), 1, 0, 'C')

    # Codifica a saída do PDF para download
    return pdf.output(dest='S').encode('latin-1')


# --- PÁGINA PRINCIPAL DO MÓDULO (COM NOVOS CAMPOS) ---
def show_controle_pernoite():
    st.title("Controle de Pernoite")
    st.caption("Marque os alunos e, ao final, clique em 'Salvar Alterações' para gravar os dados.")

    supabase = init_supabase_client()
    
    alunos_df = load_data("Alunos")
    pernoite_df = load_data("pernoite")

    st.subheader("1. Selecione a Data e o Pelotão")
    col1, col2 = st.columns(2)
    with col1:
        if 'data_selecionada_pernoite' not in st.session_state:
            st.session_state.data_selecionada_pernoite = datetime.now().date()
        data_selecionada = st.date_input(
            "Selecione a Data", 
            key="data_selecionada_pernoite",
            on_change=lambda: st.session_state.pop('pernoite_status_carregado', None)
        )
    with col2:
        pelotoes = ["Todos"] + sorted(alunos_df['pelotao'].dropna().unique().tolist())
        pelotao_selecionado = st.selectbox(
            "Selecione o Pelotão", 
            pelotoes, 
            key="pelotao_pernoite",
            on_change=lambda: st.session_state.pop('pernoite_status_carregado', None)
        )

    alunos_filtrados_df = alunos_df.copy()
    if pelotao_selecionado != "Todos":
        alunos_filtrados_df = alunos_filtrados_df[alunos_filtrados_df['pelotao'] == pelotao_selecionado]
    
    alunos_visiveis_ids = [str(id) for id in alunos_filtrados_df['id'].tolist()]

    st.markdown("---")
    st.subheader("2. Marque os Alunos em Pernoite")

    if 'pernoite_status' not in st.session_state:
        st.session_state.pernoite_status = {}
    
    if not st.session_state.get('pernoite_status_carregado'):
        if not pernoite_df.empty and data_selecionada:
            pernoite_df['data'] = pd.to_datetime(pernoite_df['data']).dt.date
            pernoite_hoje_df = pernoite_df[pernoite_df['data'] == data_selecionada]
            alunos_presentes_ids = [str(id) for id in pernoite_hoje_df[pernoite_hoje_df['presente'] == True]['aluno_id'].tolist()]
        else:
            alunos_presentes_ids = []
        
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = aluno_id in alunos_presentes_ids
        st.session_state.pernoite_status_carregado = True

    col_b1, col_b2, col_b3 = st.columns([1, 1, 2])
    if col_b1.button("Marcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = True
        st.rerun()
    
    if col_b2.button("Desmarcar Todos Visíveis"):
        for aluno_id in alunos_visiveis_ids:
            st.session_state.pernoite_status[aluno_id] = False
        st.rerun()
    
    st.write("") 

    for _, aluno in alunos_filtrados_df.sort_values('nome_guerra').iterrows():
        aluno_id_str = str(aluno['id'])
        st.session_state.pernoite_status[aluno_id_str] = st.checkbox(
            label=f"**{aluno['nome_guerra']}** ({aluno.get('numero_interno', 'S/N')})",
            value=st.session_state.pernoite_status.get(aluno_id_str, False),
            key=f"check_{aluno_id_str}"
        )

    st.write("") 
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        with st.spinner("A gravar as alterações..."):
            registos_para_salvar = []
            for aluno_id in alunos_visiveis_ids:
                registos_para_salvar.append({
                    'aluno_id': int(aluno_id),
                    'data': data_selecionada.strftime('%Y-%m-%d'),
                    'presente': st.session_state.pernoite_status.get(aluno_id, False)
                })
            
            if registos_para_salvar:
                try:
                    supabase.table("pernoite").upsert(registos_para_salvar, on_conflict='aluno_id,data').execute()
                    st.success("Alterações salvas com sucesso!")
                    load_data.clear()
                    st.session_state.pop('pernoite_status_carregado', None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
    
    st.markdown("---")
    st.subheader("3. Gerar Relatório em PDF")

    # --- NOVOS CAMPOS DE TEXTO PARA O PDF ---
    config_df = load_data("Config")
    
    def get_config_value(key, default):
        return config_df[config_df['chave'] == key]['valor'].iloc[0] if key in config_df['chave'].values else default

    cabecalho_salvo = get_config_value('cabecalho_pernoite_pdf', "Relação de Militares em Pernoite")
    texto_esq_salvo = get_config_value('texto_sup_esq_pdf', "Apresentação:")
    texto_dir_salvo = get_config_value('texto_sup_dir_pdf', "Assinatura do Of de Dia:")
    rodape_salvo = get_config_value('rodape_pernoite_pdf', "Texto do rodapé padrão.")

    st.info("Personalize os textos que aparecerão no relatório em PDF.")
    cabecalho_editado = st.text_area("Texto do Cabeçalho Principal", value=cabecalho_salvo, help="Use quebras de linha (Enter) para múltiplas linhas.")
    
    col_txt1, col_txt2 = st.columns(2)
    with col_txt1:
        texto_esq_editado = st.text_input("Texto Superior Esquerdo", value=texto_esq_salvo)
    with col_txt2:
        texto_dir_editado = st.text_input("Texto Superior Direito", value=texto_dir_salvo)
    
    rodape_editado = st.text_area("Texto do Rodapé", value=rodape_salvo)

    if st.button("Salvar Textos Padrão do Relatório"):
        configs_para_salvar = [
            {'chave': 'cabecalho_pernoite_pdf', 'valor': cabecalho_editado},
            {'chave': 'texto_sup_esq_pdf', 'valor': texto_esq_editado},
            {'chave': 'texto_sup_dir_pdf', 'valor': texto_dir_editado},
            {'chave': 'rodape_pernoite_pdf', 'valor': rodape_editado}
        ]
        supabase.table("Config").upsert(configs_para_salvar).execute()
        st.success("Textos padrão salvos com sucesso!"); load_data.clear()

    # Filtra os alunos marcados para incluir no PDF
    ids_selecionados_na_tela = [
        aluno_id for aluno_id, marcado in st.session_state.pernoite_status.items() 
        if marcado and aluno_id in alunos_visiveis_ids
    ]
    
    alunos_para_pdf_df = alunos_filtrados_df[alunos_filtrados_df['id'].astype(str).isin(ids_selecionados_na_tela)]
    alunos_para_pdf_df_sorted = alunos_para_pdf_df.sort_values('numero_interno')

    st.write(f"**Total de militares marcados para pernoite (nesta tela):** {len(alunos_para_pdf_df_sorted)}")

    if st.button("Gerar PDF", type="secondary"):
        if alunos_para_pdf_df_sorted.empty:
            st.warning("Nenhum aluno está marcado como 'pernoite' na tela.")
        else:
            # Passa todos os textos personalizados para a função de geração de PDF
            pdf_bytes = gerar_pdf_pernoite(
                cabecalho_principal=cabecalho_editado,
                texto_esquerda=texto_esq_editado,
                texto_direita=texto_dir_editado,
                rodape_texto=rodape_editado,
                data_selecionada=data_selecionada,
                alunos_df_sorted=alunos_para_pdf_df_sorted
            )
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
