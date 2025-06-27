import streamlit as st
import pandas as pd
from database import load_data, save_data
import logging
from datetime import datetime
import os

# Configuração do logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Nome do ficheiro Google Sheets
SHEET_NAME = "Sistema_Acoes_Militares"

def show_alunos():
    """Função principal para exibir e gerir a página de Alunos."""
    st.title("Gestão de Alunos")

    try:
        alunos_df = load_data(SHEET_NAME, "Alunos")
        acoes_df = load_data(SHEET_NAME, "Acoes")
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # Demais lógicas de adicionar e editar aluno (mantidas)
    # ...

    # Exibição da lista de alunos
    search = st.text_input("🔍 Buscar aluno (nome, número, pelotão...)")
    if not alunos_df.empty and search:
        search_lower = search.lower()
        mask = (alunos_df['nome_guerra'].astype(str).str.lower().str.contains(search_lower, na=False) |
                alunos_df['nome_completo'].astype(str).str.lower().str.contains(search_lower, na=False) |
                alunos_df['numero_interno'].astype(str).str.contains(search_lower, na=False) |
                alunos_df['pelotao'].astype(str).str.lower().str.contains(search_lower, na=False))
        filtered_df = alunos_df[mask]
    else:
        filtered_df = alunos_df

    if not filtered_df.empty:
        st.subheader(f"Alunos ({len(filtered_df)} encontrados)")
        
        # --- CORREÇÃO APLICADA AQUI ---
        # Converte a coluna de pontuação para numérica UMA VEZ antes do loop
        if not acoes_df.empty and 'pontuacao_efetiva' in acoes_df.columns:
            acoes_df['pontuacao_efetiva'] = pd.to_numeric(acoes_df['pontuacao_efetiva'], errors='coerce').fillna(0)
        # --- FIM DA CORREÇÃO ---

        for i, (_, aluno) in enumerate(filtered_df.iterrows()):
            with st.container(border=True):
                st.markdown(f"**{aluno.get('nome_guerra', 'N/A')}**")
                st.write(f"Nº: {aluno.get('numero_interno', 'N/A')}")

                pontuacao = 10.0 # Pontuação inicial
                if not acoes_df.empty and 'aluno_id' in acoes_df.columns:
                    # Garante que a comparação de ID seja consistente (str vs str)
                    acoes_aluno = acoes_df[acoes_df['aluno_id'] == str(aluno.get('id'))]
                    if not acoes_aluno.empty:
                        # Agora a soma funcionará corretamente pois a coluna é numérica
                        pontuacao += acoes_aluno['pontuacao_efetiva'].sum()

                cor = "green" if pontuacao >= 10 else "red"
                st.markdown(f"<h4 style='color:{cor}'>{pontuacao:.1f} pts</h4>", unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("👁️ Ver", key=f"ver_{aluno['id']}"):
                        st.session_state.aluno_selecionado_para_detalhes = aluno['id']
                        st.rerun()
                with c2:
                    if st.button("✏️ Editar", key=f"editar_{aluno['id']}"):
                        st.warning("Funcionalidade de edição a ser implementada.")
                with c3:
                    if st.button("➕ Ação", key=f"acao_{aluno['id']}"):
                        st.session_state.aluno_selecionado_para_acao = aluno['id']
                        st.info(f"Vá para a página 'Lançamento de Ações' para registrar uma ação para {aluno['nome_guerra']}.")
                        st.rerun()

    if 'aluno_selecionado' in st.session_state:
        show_detalhes_aluno(st.session_state.aluno_selecionado, alunos_df, acoes_df)
    
    if st.session_state.get('registrar_acao', False):
        aluno_id = st.session_state.aluno_acao
        aluno = alunos_df[alunos_df['id'] == aluno_id].iloc[0]
        registrar_acao(aluno_id, aluno['nome_guerra'])

def show_detalhes_aluno(aluno_id, alunos_df, acoes_df):
    aluno = alunos_df[alunos_df['id'] == aluno_id].iloc[0]
    acoes_aluno = pd.DataFrame()
    if not acoes_df.empty and 'aluno_id' in acoes_df.columns:
        acoes_aluno = acoes_df[acoes_df['aluno_id'] == aluno_id].sort_values('data', ascending=False)
    
    pontuacao_atual = 10
    if not acoes_aluno.empty and 'pontuacao_efetiva' in acoes_aluno.columns:
        pontuacao_atual += acoes_aluno['pontuacao_efetiva'].sum()
    
    st.subheader(f"Detalhes do Aluno: {aluno['nome_guerra']}")
    col1, col2 = st.columns([1, 2])
    with col1:
        CLOUD_NAME = st.secrets.gcp_service_account.get("cloudinary_cloud_name")
        FOLDER = st.secrets.gcp_service_account.get("cloudinary_folder")
        numero_interno = aluno.get('numero_interno')
        if numero_interno and CLOUD_NAME and FOLDER:
            photo_url = f"https://res.cloudinary.com/{CLOUD_NAME}/image/upload/{FOLDER}/{numero_interno}.jpg"
            st.image(photo_url, width=150)
        else:
            st.image("https://via.placeholder.com/150?text=Sem+Foto", width=150 )
            
        st.markdown(f"""
        ### {aluno['nome_guerra']}
        **Nome Completo:** {aluno['nome_completo']}  
        **Número Interno:** {aluno['numero_interno']}  
        **Pelotão:** {aluno['pelotao']}  
        **Especialidade:** {aluno['especialidade']}  
        **Pontuação Atual:** {pontuacao_atual:.1f}
        """)
        
        if st.button("Voltar para Lista"):
            del st.session_state.aluno_selecionado
            st.rerun()
    
    with col2:
        st.subheader("Histórico de Ações")
        if acoes_aluno.empty:
            st.info("Nenhuma ação registrada para este aluno.")
        else:
            for _, acao in acoes_aluno.iterrows():
                pontuacao = acao.get('pontuacao_efetiva', 0)
                cor = "green" if pontuacao > 0 else "red" if pontuacao < 0 else "gray"
                st.markdown(f"""
                <div style="border-left: 3px solid {cor}; padding-left: 10px; margin-bottom: 10px">
                    <p><strong>{acao.get('tipo', 'Ação')}</strong> ({pontuacao:+.1f} pontos) - {acao.get('data', 'N/A')}</p>
                    <p>{acao.get('descricao', '')}</p>
                    <p><small>Registrado por: {acao.get('usuario', 'Sistema')}</small></p>
                </div>
                """, unsafe_allow_html=True)

pass