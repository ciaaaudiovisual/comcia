import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import load_data, init_supabase_client
from PIL import Image
import numpy as np
from pyzbar.pyzbar import decode
import plotly.express as px
from acoes import calcular_pontuacao_efetiva
from ordens import display_task_notifications
from auth import check_permission

# --- FUNÇÃO PARA DECODIFICAR CÓDIGO DE BARRAS ---
def decodificar_codigo_de_barras(upload_de_imagem):
    """Lê um arquivo de imagem e retorna uma lista de NIPs encontrados."""
    try:
        imagem = Image.open(upload_de_imagem)
        imagem_cv = np.array(imagem)
        codigos_barras = decode(imagem_cv)
        
        nips_encontrados = []
        if not codigos_barras:
            return nips_encontrados, "Nenhum código de barras encontrado na imagem."

        for codigo in codigos_barras:
            nip = codigo.data.decode('utf-8')
            if len(nip) == 8 and nip.isdigit():
                nips_encontrados.append(nip)
        
        if not nips_encontrados:
            return [], "Código(s) de barras encontrado(s), mas nenhum é um NIP válido (8 dígitos)."
            
        return nips_encontrados, f"{len(nips_encontrados)} NIP(s) encontrado(s) com sucesso!"

    except Exception as e:
        return [], f"Erro ao processar a imagem: {e}"

# --- PÁGINA PRINCIPAL DO DASHBOARD ---
def show_dashboard():
    # --- CORREÇÃO APLICADA AQUI ---
    # Acesso seguro ao nome do usuário para o título
    user_display_name = st.session_state.get('full_name', st.session_state.get('username', ''))
    st.title(f"Dashboard - Bem-vindo(a), {user_display_name}!")
    
    supabase = init_supabase_client()
    display_task_notifications()
    
    # Inicializa os estados da sessão para o scanner
    if 'scanner_ativo' not in st.session_state:
        st.session_state.scanner_ativo = False
    if 'alunos_escaneados_nomes' not in st.session_state:
        st.session_state.alunos_escaneados_nomes = []

    # Carregamento de dados
    alunos_df = load_data("Alunos")
    acoes_df = load_data("Acoes")
    tipos_acao_df = load_data("Tipos_Acao")
    config_df = load_data("Config")

    if not acoes_df.empty and not tipos_acao_df.empty:
        acoes_com_pontos_df = calcular_pontuacao_efetiva(acoes_df, tipos_acao_df, config_df)
    else:
        acoes_com_pontos_df = pd.DataFrame()

    # --- SEÇÃO DE ANOTAÇÃO RÁPIDA COM CONTROLE DE PERMISSÃO ---
    if check_permission('pode_escanear_cracha'):
        with st.expander("⚡ Anotação Rápida em Massa", expanded=True):
            if st.button("📸 Iniciar/Parar Leitor de Crachás", type="primary"):
                st.session_state.scanner_ativo = not st.session_state.scanner_ativo
                if not st.session_state.scanner_ativo:
                    st.session_state.alunos_escaneados_nomes = []

            if st.session_state.scanner_ativo:
                with st.container(border=True):
                    st.info("O modo scanner está ativo. Aponte a câmera para um ou mais crachás e tire a foto.")
                    imagem_cracha = st.camera_input("Escanear Crachá(s)", label_visibility="collapsed")

                    if imagem_cracha is not None:
                        nips, msg = decodificar_codigo_de_barras(imagem_cracha)
                        if nips:
                            if 'nip' in alunos_df.columns:
                                alunos_encontrados_df = alunos_df[alunos_df['nip'].isin(nips)]
                                if not alunos_encontrados_df.empty:
                                    nomes_encontrados = alunos_encontrados_df['nome_guerra'].tolist()
                                    novos_nomes = [nome for nome in nomes_encontrados if nome not in st.session_state.alunos_escaneados_nomes]
                                    st.session_state.alunos_escaneados_nomes.extend(novos_nomes)
                                    if novos_nomes: st.toast(f"Alunos adicionados: {', '.join(novos_nomes)}", icon="✅")
                                    else: st.toast("Todos os alunos escaneados já estavam na lista.", icon="ℹ️")
                                else:
                                    st.warning("Nenhum aluno encontrado no banco de dados com o(s) NIP(s) lido(s).")
                            else:
                                st.error("A coluna 'nip' não existe na tabela de Alunos para realizar a busca.")
                        else:
                            st.error(msg)
            
            with st.form("anotacao_rapida_form"):
                
                # --- CORREÇÃO APLICADA AQUI: Busca Aprimorada ---
                # Criamos um dicionário que mapeia a string de exibição completa para o NOME DE GUERRA do aluno
                if not alunos_df.empty:
                    alunos_opcoes_dict = {
                        f"{aluno['nome_guerra']} (Nº: {aluno.get('numero_interno', 'S/N')}, NIP: {aluno.get('nip', 'S/N')})": aluno['nome_guerra']
                        for _, aluno in alunos_df.sort_values('nome_guerra').iterrows()
                    }
                    alunos_opcoes_labels = list(alunos_opcoes_dict.keys())
                else:
                    alunos_opcoes_dict = {}
                    alunos_opcoes_labels = []

                # A seleção do scanner agora trabalha com as novas labels completas
                alunos_selecionados_labels = st.multiselect(
                    "Selecione os Alunos (busque por nome, número ou NIP)", 
                    options=alunos_opcoes_labels,
                    default=[label for label, nome in alunos_opcoes_dict.items() if nome in st.session_state.get('alunos_escaneados_nomes', [])]
                )
                
                # Convertemos as labels selecionadas de volta para apenas os nomes de guerra para o processamento
                alunos_selecionados = [alunos_opcoes_dict[label] for label in alunos_selecionados_labels]
                
                # (O restante do formulário permanece o mesmo)
                tipos_opcoes = {f"{row['nome']} ({float(row.get('pontuacao',0)):.1f})": row['id'] for _, row in tipos_acao_df.iterrows()} if not tipos_acao_df.empty else {}
                tipo_selecionado_label = st.selectbox("Tipo de Ação", options=tipos_opcoes.keys())
                descricao = st.text_area("Descrição da Ação")
                
                if st.form_submit_button("Registrar Ação"):
                    if not all([alunos_selecionados, tipo_selecionado_label, descricao]):
                        st.warning("Selecione ao menos um aluno, um tipo de ação e preencha a descrição.")
                    else:
                        try:
                            ids_alunos_selecionados = alunos_df[alunos_df['nome_guerra'].isin(alunos_selecionados)]['id'].tolist()
                            tipo_acao_id = tipos_opcoes[tipo_selecionado_label]
                            tipo_acao_info = tipos_acao_df[tipos_acao_df['id'] == tipo_acao_id].iloc[0]

                            id_atual = int(pd.to_numeric(acoes_df['id']).max()) if not acoes_df.empty and 'id' in acoes_df.columns and not pd.to_numeric(acoes_df['id'], errors='coerce').isna().all() else 0
                            
                            novas_acoes = []
                            for aluno_id in ids_alunos_selecionados:
                                id_atual += 1
                                nova_acao = {
                                    'id': str(id_atual),
                                    'aluno_id': str(aluno_id),
                                    'tipo_acao_id': str(tipo_acao_id),
                                    'tipo': tipo_acao_info['nome'],
                                    'descricao': descricao,
                                    'data': datetime.now().strftime('%Y-%m-%d'),
                                    'usuario': st.session_state.username,
                                    'lancado_faia': False
                                }
                                novas_acoes.append(nova_acao)
                            
                            if novas_acoes:
                                supabase.table("Acoes").insert(novas_acoes).execute()
                                st.success(f"Ação registrada com sucesso para {len(novas_acoes)} aluno(s)!")
                                st.session_state.alunos_escaneados_nomes = []
                                load_data.clear()
                                st.rerun()

                        except Exception as e:
                            st.error(f"Falha ao salvar a(s) ação(ões): {e}")

    st.divider()

    # --- VISUALIZAÇÕES DO DASHBOARD ---
    if alunos_df.empty or acoes_com_pontos_df.empty:
        st.info("Registre alunos e ações para visualizar os painéis de dados.")
    else:
        acoes_com_pontos_df['data'] = pd.to_datetime(acoes_com_pontos_df['data'], errors='coerce')
        hoje = datetime.now().date()
        acoes_hoje = acoes_com_pontos_df.dropna(subset=['data'])[acoes_com_pontos_df['data'].dt.date == hoje]

        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Destaques do Dia")
            if not acoes_hoje.empty:
                soma_pontos_hoje = acoes_hoje.groupby('aluno_id')['pontuacao_efetiva'].sum()
                
                if not soma_pontos_hoje[soma_pontos_hoje > 0].empty:
                    aluno_positivo_id = str(soma_pontos_hoje.idxmax())
                    aluno_info = alunos_df[alunos_df['id'] == aluno_positivo_id]
                    if not aluno_info.empty: st.success(f"🌟 **Positivo**: {aluno_info.iloc[0]['nome_guerra']}")

                if not soma_pontos_hoje[soma_pontos_hoje < 0].empty:
                    aluno_negativo_id = str(soma_pontos_hoje.idxmin())
                    aluno_info = alunos_df[alunos_df['id'] == aluno_negativo_id]
                    if not aluno_info.empty: st.warning(f"⚠️ **Negativo**: {aluno_info.iloc[0]['nome_guerra']}")
            else:
                st.info("Nenhuma ação registrada hoje.")

        with col2:
            st.subheader("Pontuação Média por Pelotão")
            pontuacao_inicial = 10.0
            if not config_df.empty:
                 try: pontuacao_inicial = float(config_df[config_df['chave'] == 'pontuacao_inicial']['valor'].iloc[0])
                 except (IndexError, ValueError): pass
            
            soma_pontos_por_aluno = acoes_com_pontos_df.groupby('aluno_id')['pontuacao_efetiva'].sum()
            alunos_com_pontuacao = pd.merge(alunos_df, soma_pontos_por_aluno.rename('soma_pontos'), left_on='id', right_on='aluno_id', how='left')
            alunos_com_pontuacao['soma_pontos'] = alunos_com_pontuacao['soma_pontos'].fillna(0)
            alunos_com_pontuacao['pontuacao_final'] = alunos_com_pontuacao['soma_pontos'] + pontuacao_inicial
            media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_final'].mean().reset_index()
            
            fig = px.bar(media_por_pelotao, x='pelotao', y='pontuacao_final', title='Pontuação Média Atual', labels={'pelotao': 'Pelotão', 'pontuacao_final': 'Pontuação Média'}, color='pontuacao_final', color_continuous_scale='RdYlGn', text_auto='.2f')
            st.plotly_chart(fig, use_container_width=True)

        st.divider()

        st.subheader("🎂 Aniversariantes (Última e Atual Semana)")
        if not alunos_df.empty and 'data_nascimento' in alunos_df.columns:
            alunos_df['data_nascimento'] = pd.to_datetime(alunos_df['data_nascimento'], errors='coerce')
            alunos_nasc_validos = alunos_df.dropna(subset=['data_nascimento'])
            hoje = datetime.now().date()
            inicio_periodo = hoje - timedelta(days=hoje.weekday() + 7)
            periodo_de_dias = [inicio_periodo + timedelta(days=i) for i in range(14)]
            aniversarios_no_periodo = [d.strftime('%m-%d') for d in periodo_de_dias]
            aniversariantes_df = alunos_nasc_validos[alunos_nasc_validos['data_nascimento'].dt.strftime('%m-%d').isin(aniversarios_no_periodo)].copy()
            
            if not aniversariantes_df.empty:
                aniversariantes_df['dia_mes'] = aniversariantes_df['data_nascimento'].dt.strftime('%m-%d')
                aniversariantes_df = aniversariantes_df.sort_values(by='dia_mes')
                for _, aluno in aniversariantes_df.iterrows():
                    st.success(f"**{aluno['nome_guerra']}** - {aluno['data_nascimento'].strftime('%d/%m')}")
            else:
                st.info("Nenhum aniversariante no período.")