# controle_pernoite.py (v4 - Separação de Alunos M e Q)

import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, init_supabase_client
from io import BytesIO
from fpdf import FPDF
import math

# --- FUNÇÃO PARA GERAR PDF (COM O LAYOUT FINAL E SEPARAÇÃO) ---
def gerar_pdf_pernoite(
    cabecalho_principal,
    rodape_texto,
    alunos_m_df,
    alunos_q_df,
    textos_m,
    textos_q
):
    """
    Gera o PDF do relatório de pernoite com seções separadas para alunos M e Q.
    """
    # --- Classe PDF personalizada para controlar cabeçalho e rodapé ---
    class PDF(FPDF):
        def __init__(self, cabecalho_txt, rodape_txt):
            super().__init__()
            self.cabecalho_texto = cabecalho_txt
            self.rodape_texto = rodape_txt

        def header(self):
            # O cabeçalho principal é único e será desenhado apenas uma vez no início.
            # Esta função será deixada em branco para evitar repetição em novas páginas.
            pass

        def footer(self):
            # Rodapé personalizado
            self.set_y(-25)
            self.set_font('Arial', 'I', 10)
            self.multi_cell(0, 5, self.rodape_texto, 0, 'C')
            
            # Número da página
            self.set_y(-15)
            self.set_font('Arial', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

        def desenhar_corpo_tabela(self, titulo_secao, texto_esq, texto_dir, alunos_df):
            """
            Função auxiliar para desenhar uma seção completa da tabela (cabeçalho da seção + corpo).
            """
            self.set_font("Arial", '', 12)
            y_antes = self.get_y()
            self.cell(self.w / 2, 8, texto_esq, 0, 0, 'L')
            self.set_y(y_antes)
            self.cell(0, 8, texto_dir, 0, 1, 'R')
            self.ln(5)

            self.set_font("Arial", 'B', 12)
            self.cell(0, 10, titulo_secao, 1, 1, 'C')

            # Corpo da tabela
            self.set_font("Arial", '', 10)
            lista_numeros_internos = alunos_df['numero_interno'].tolist()
            total_militares = len(lista_numeros_internos)

            if total_militares == 0:
                self.cell(0, 10, "Nenhum aluno selecionado para esta categoria.", 1, 1, 'C')
                self.ln(10)
                return

            num_pares_por_linha = 4
            largura_pagina = self.w - 2 * self.l_margin
            largura_par = largura_pagina / num_pares_por_linha
            largura_col_ordem = largura_par * 0.20
            largura_col_valor = largura_par * 0.80
            altura_linha = 8

            num_linhas_dados = math.ceil(total_militares / num_pares_por_linha)
            num_linhas_total = num_linhas_dados + 3
            total_celulas_grid = num_linhas_total * num_pares_por_linha

            for idx in range(total_celulas_grid):
                if idx % num_pares_por_linha == 0 and idx > 0:
                    self.ln()

                if idx < total_militares:
                    ordem = str(idx + 1)
                    numero_interno = str(lista_numeros_internos[idx])
                else:
                    ordem = ""
                    numero_interno = ""

                self.cell(largura_col_ordem, altura_linha, ordem, 1, 0, 'C')
                self.cell(largura_col_valor, altura_linha, numero_interno, 1, 0, 'C')
            
            self.ln(15) # Espaço extra após cada tabela

    # --- Lógica de Geração do PDF ---
    pdf = PDF(cabecalho_principal, rodape_texto)
    pdf.add_page()

    # Desenha o cabeçalho principal uma única vez
    pdf.set_font("Arial", 'B', 12)
    pdf.multi_cell(0, 6, pdf.cabecalho_texto, 0, 'C')
    pdf.ln(10)

    # Desenha a seção para Alunos M
    pdf.desenhar_corpo_tabela(
        "NÚMERO INTERNO DE ALUNOS (M)",
        textos_m['esquerda'],
        textos_m['direita'],
        alunos_m_df
    )

    # Desenha a seção para Alunos Q
    pdf.desenhar_corpo_tabela(
        "NÚMERO INTERNO DE ALUNOS (Q)",
        textos_q['esquerda'],
        textos_q['direita'],
        alunos_q_df
    )

    return pdf.output(dest='S').encode('latin-1')


# --- PÁGINA PRINCIPAL DO MÓDULO (INTERFACE DO STREAMLIT) ---
def show_controle_pernoite():
    st.title("Controle de Pernoite")
    st.caption("Marque os alunos e, ao final, clique em 'Salvar Alterações' para gravar os dados.")

    supabase = init_supabase_client()
    
    alunos_df = load_data("Alunos")
    pernoite_df = load_data("pernoite")

    # AJUSTE IMPORTANTE: Verifique se a coluna 'tipo_aluno' existe.
    # Se o nome da sua coluna for diferente, altere "tipo_aluno" aqui.
    COLUNA_TIPO_ALUNO = "tipo_aluno"
    if COLUNA_TIPO_ALUNO not in alunos_df.columns:
        st.error(f"Erro Crítico: A coluna '{COLUNA_TIPO_ALUNO}' não foi encontrada na tabela 'Alunos'. A separação M/Q não pode ser feita.")
        return

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
        tipo_str = f" ({aluno.get(COLUNA_TIPO_ALUNO, 'N/A')})"
        st.session_state.pernoite_status[aluno_id_str] = st.checkbox(
            label=f"**{aluno['nome_guerra']}** ({aluno.get('numero_interno', 'S/N')}){tipo_str}",
            value=st.session_state.pernoite_status.get(aluno_id_str, False),
            key=f"check_{aluno_id_str}"
        )

    st.write("") 
    if st.button("Salvar Alterações", type="primary", use_container_width=True):
        # ... (código de salvar permanece o mesmo)
        pass
    
    st.markdown("---")
    st.subheader("3. Gerar Relatório em PDF")

    config_df = load_data("Config")
    
    def get_config_value(key, default):
        return config_df[config_df['chave'] == key]['valor'].iloc[0] if key in config_df['chave'].values else default

    # Carrega todos os textos personalizáveis
    cabecalho_salvo = get_config_value('cabecalho_pernoite_pdf', "Relação de Militares em Pernoite")
    rodape_salvo = get_config_value('rodape_pernoite_pdf', "Texto do rodapé padrão.")
    
    texto_esq_m_salvo = get_config_value('texto_sup_esq_m_pdf', "Apresentação (Alunos M):")
    texto_dir_m_salvo = get_config_value('texto_sup_dir_m_pdf', "Assinatura (Alunos M):")
    texto_esq_q_salvo = get_config_value('texto_sup_esq_q_pdf', "Apresentação (Alunos Q):")
    texto_dir_q_salvo = get_config_value('texto_sup_dir_q_pdf', "Assinatura (Alunos Q):")

    st.info("Personalize os textos que aparecerão no relatório em PDF.")
    cabecalho_editado = st.text_area("Texto do Cabeçalho Principal (Comum)", value=cabecalho_salvo, help="Use quebras de linha (Enter) para múltiplas linhas.")
    
    st.markdown("##### Textos para Alunos M")
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        texto_esq_m_editado = st.text_input("Texto Superior Esquerdo (M)", value=texto_esq_m_salvo)
    with col_m2:
        texto_dir_m_editado = st.text_input("Texto Superior Direito (M)", value=texto_dir_m_salvo)

    st.markdown("##### Textos para Alunos Q")
    col_q1, col_q2 = st.columns(2)
    with col_q1:
        texto_esq_q_editado = st.text_input("Texto Superior Esquerdo (Q)", value=texto_esq_q_salvo)
    with col_q2:
        texto_dir_q_editado = st.text_input("Texto Superior Direito (Q)", value=texto_dir_q_salvo)

    rodape_editado = st.text_area("Texto do Rodapé (Comum)", value=rodape_salvo)

    if st.button("Salvar Textos Padrão do Relatório"):
        configs_para_salvar = [
            {'chave': 'cabecalho_pernoite_pdf', 'valor': cabecalho_editado},
            {'chave': 'rodape_pernoite_pdf', 'valor': rodape_editado},
            {'chave': 'texto_sup_esq_m_pdf', 'valor': texto_esq_m_editado},
            {'chave': 'texto_sup_dir_m_pdf', 'valor': texto_dir_m_editado},
            {'chave': 'texto_sup_esq_q_pdf', 'valor': texto_esq_q_editado},
            {'chave': 'texto_sup_dir_q_pdf', 'valor': texto_dir_q_editado},
        ]
        supabase.table("Config").upsert(configs_para_salvar).execute()
        st.success("Textos padrão salvos com sucesso!"); load_data.clear()

    # Filtra e separa os alunos por tipo
    ids_selecionados_na_tela = [
        aluno_id for aluno_id, marcado in st.session_state.pernoite_status.items() 
        if marcado and aluno_id in alunos_visiveis_ids
    ]
    
    alunos_para_pdf_df = alunos_filtrados_df[alunos_filtrados_df['id'].astype(str).isin(ids_selecionados_na_tela)]
    
    alunos_m_df = alunos_para_pdf_df[alunos_para_pdf_df[COLUNA_TIPO_ALUNO] == 'M'].sort_values('numero_interno')
    alunos_q_df = alunos_para_pdf_df[alunos_para_pdf_df[COLUNA_TIPO_ALUNO] == 'Q'].sort_values('numero_interno')

    st.write(f"**Total de militares marcados (M):** {len(alunos_m_df)} | **Total de militares marcados (Q):** {len(alunos_q_df)}")

    if st.button("Gerar PDF", type="secondary"):
        if alunos_para_pdf_df.empty:
            st.warning("Nenhum aluno está marcado como 'pernoite' na tela.")
        else:
            pdf_bytes = gerar_pdf_pernoite(
                cabecalho_principal=cabecalho_editado,
                rodape_texto=rodape_editado,
                alunos_m_df=alunos_m_df,
                alunos_q_df=alunos_q_df,
                textos_m={'esquerda': texto_esq_m_editado, 'direita': texto_dir_m_editado},
                textos_q={'esquerda': texto_esq_q_editado, 'direita': texto_dir_q_editado}
            )
            st.download_button(
                label="✅ Baixar Relatório de Pernoite",
                data=pdf_bytes,
                file_name=f"pernoite_{data_selecionada.strftime('%Y-%m-%d')}.pdf",
                mime="application/pdf"
            )
