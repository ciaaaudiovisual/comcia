import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from database import load_data, save_data

def show_dashboard():
    st.title("Dashboard")

    # Carregar todos os dados necessários no início
    alunos_df = load_data("Sistema_Acoes_Militares", "Alunos")
    acoes_df = load_data("Sistema_Acoes_Militares", "Acoes")
    tipos_acao_df = load_data("Sistema_Acoes_Militares", "Tipos_Acao")
    config_df = load_data("Sistema_Acoes_Militares", "Config")

    # Garante que a coluna de pontuação seja numérica para evitar erros de cálculo
    if not acoes_df.empty and 'pontuacao_efetiva' in acoes_df.columns:
        acoes_df['pontuacao_efetiva'] = pd.to_numeric(acoes_df['pontuacao_efetiva'], errors='coerce').fillna(0)

    # --- SUGESTÃO APLICADA: "Anotação Rápida" visível por padrão ---
    # O parâmetro 'expanded' foi alterado para True.
    with st.expander("⚡ Anotação Rápida", expanded=True):
        # O bloco de formulário começa aqui
        with st.form("anotacao_rapida_form"):
            alunos_opcoes = {f"{aluno['nome_guerra']} ({aluno['numero_interno']})": aluno['id'] for _, aluno in alunos_df.iterrows()}
            alunos_selecionados_nomes = st.multiselect("Selecione os Alunos", options=list(alunos_opcoes.keys()))

            tipos_opcoes = {f"{tipo['nome']} ({tipo['pontuacao']} pts)": tipo for _, tipo in tipos_acao_df.iterrows()}
            tipo_selecionado_str = st.selectbox("Tipo de Ação", options=list(tipos_opcoes.keys()))
            
            descricao = st.text_area("Descrição/Justificativa")
            data = st.date_input("Data da Anotação", value=datetime.now())
            
            # O botão de submissão DEVE estar dentro do 'with st.form(...)'
            submitted = st.form_submit_button("Registrar Anotação Rápida")
            
            if submitted:
                if not alunos_selecionados_nomes or not descricao or not tipo_selecionado_str:
                    st.warning("Por favor, selecione pelo menos um aluno, um tipo de ação e preencha a descrição.")
                else:
                    # Lógica de salvamento completa
                    tipo_selecionado_info = tipos_opcoes[tipo_selecionado_str]
                    tipo_id = tipo_selecionado_info['id']
                    pontuacao_base = pd.to_numeric(tipo_selecionado_info['pontuacao'], errors='coerce')
                    if pd.isna(pontuacao_base): pontuacao_base = 0.0

                    fator_adaptacao = 0.25
                    em_adaptacao = False
                    if not config_df.empty:
                        try:
                            inicio_str = config_df.loc[config_df['chave'] == 'periodo_adaptacao_inicio', 'valor'].iloc[0]
                            fim_str = config_df.loc[config_df['chave'] == 'periodo_adaptacao_fim', 'valor'].iloc[0]
                            fator_str = config_df.loc[config_df['chave'] == 'fator_adaptacao', 'valor'].iloc[0]
                            
                            inicio_adaptacao = pd.to_datetime(inicio_str).date()
                            fim_adaptacao = pd.to_datetime(fim_str).date()
                            fator_adaptacao = float(fator_str)

                            if inicio_adaptacao <= data <= fim_adaptacao:
                                em_adaptacao = True
                        except (IndexError, ValueError):
                             pass 
                    
                    pontuacao_efetiva = pontuacao_base * fator_adaptacao if em_adaptacao else pontuacao_base

                    novas_acoes = []
                    id_atual = int(acoes_df['id'].max()) if not acoes_df.empty else 0

                    for nome_aluno in alunos_selecionados_nomes:
                        id_atual += 1
                        aluno_id = alunos_opcoes[nome_aluno]
                        nova_acao = {
                            'id': id_atual,
                            'aluno_id': aluno_id,
                            'tipo_acao_id': tipo_id,
                            'tipo': tipo_selecionado_str.split(' (')[0],
                            'descricao': descricao,
                            'data': data.strftime('%Y-%m-%d'),
                            'usuario': st.session_state.username,
                            'pontuacao': pontuacao_base,
                            'pontuacao_efetiva': pontuacao_efetiva
                        }
                        novas_acoes.append(nova_acao)
                    
                    if novas_acoes:
                        novas_acoes_df = pd.DataFrame(novas_acoes)
                        acoes_df_atualizado = pd.concat([acoes_df, novas_acoes_df], ignore_index=True)
                        if save_data("Sistema_Acoes_Militares", "Acoes", acoes_df_atualizado):
                            st.success(f"{len(novas_acoes)} anotação(ões) registrada(s) com sucesso!")
                            st.rerun()
                        else:
                            st.error("Falha ao salvar as anotações.")
        # Fim do bloco de formulário

    st.divider()

    # O restante do dashboard permanece aqui
    if alunos_df.empty:
        st.warning("Não há alunos cadastrados. Adicione alunos para visualizar o restante do dashboard.")
        return
    
    hoje = datetime.now().date()
    if not acoes_df.empty and 'data' in acoes_df.columns:
        acoes_df['data'] = pd.to_datetime(acoes_df['data'], errors='coerce')
        acoes_hoje = acoes_df.dropna(subset=['data'])[acoes_df['data'].dt.date == hoje]
    else:
        acoes_hoje = pd.DataFrame()

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Destaques do Dia")
        if not acoes_hoje.empty:
            acoes_positivas = acoes_hoje[acoes_hoje['pontuacao_efetiva'] > 0]
            if not acoes_positivas.empty:
                aluno_positivo_id = str(acoes_positivas.groupby('aluno_id')['pontuacao_efetiva'].sum().idxmax())
                aluno_info = alunos_df[alunos_df['id'] == aluno_positivo_id]
                if not aluno_info.empty:
                    st.success(f"🌟 **Destaque Positivo**: {aluno_info.iloc[0]['nome_guerra']} ({aluno_info.iloc[0]['pelotao']})")

            acoes_negativas = acoes_hoje[acoes_hoje['pontuacao_efetiva'] < 0]
            if not acoes_negativas.empty:
                aluno_negativo_id = str(acoes_negativas.groupby('aluno_id')['pontuacao_efetiva'].sum().idxmin())
                aluno_info = alunos_df[alunos_df['id'] == aluno_negativo_id]
                if not aluno_info.empty:
                    st.warning(f"⚠️ **Destaque Negativo**: {aluno_info.iloc[0]['nome_guerra']} ({aluno_info.iloc[0]['pelotao']})")
        else:
            st.info("Nenhuma ação registada hoje para exibir destaques.")
        
        st.subheader("Aniversariantes da Semana")
        if not alunos_df.empty and 'data_nascimento' in alunos_df.columns:
            alunos_df['data_nascimento'] = pd.to_datetime(alunos_df['data_nascimento'], errors='coerce')
            proxima_semana = hoje + timedelta(days=7)
            aniversariantes = []
            
            for _, aluno in alunos_df.iterrows():
                if pd.notna(aluno['data_nascimento']):
                    nascimento = aluno['data_nascimento']
                    aniversario_este_ano = datetime(hoje.year, nascimento.month, nascimento.day).date()
                    if hoje <= aniversario_este_ano <= proxima_semana:
                        aniversariantes.append(aluno)
            
            if aniversariantes:
                for aniv in aniversariantes:
                    st.write(f"🎂 {aniv['nome_guerra']} - {aniv['data_nascimento'].strftime('%d/%m')} ({aniv['pelotao']})")
            else:
                st.write("Nenhum aniversariante esta semana.")

    with col2:
        st.subheader("Pontuação Média por Pelotão")
        if not acoes_df.empty:
            pontuacao_por_aluno = acoes_df.groupby('aluno_id')['pontuacao_efetiva'].sum().reset_index()
            alunos_com_pontuacao = pd.merge(alunos_df, pontuacao_por_aluno, left_on='id', right_on='aluno_id', how='left')
            alunos_com_pontuacao['pontuacao_efetiva'] = alunos_com_pontuacao['pontuacao_efetiva'].fillna(0) + 10
            media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_efetiva'].mean().reset_index()
            
            fig = px.bar(
                media_por_pelotao, x='pelotao', y='pontuacao_efetiva',
                title='Pontuação Média por Pelotão',
                labels={'pelotao': 'Pelotão', 'pontuacao_efetiva': 'Pontuação Média'},
                color='pontuacao_efetiva', color_continuous_scale='RdYlGn'
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Sem dados de ações para gerar o gráfico de pelotões.")
    
    st.divider()

    st.subheader("Anotações Recentes")
    if not acoes_df.empty:
        acoes_df['aluno_id'] = acoes_df['aluno_id'].astype(str)
        alunos_df['id'] = alunos_df['id'].astype(str)
        
        acoes_recentes = acoes_df.sort_values('data', ascending=False).head(10)
        acoes_recentes = pd.merge(acoes_recentes, alunos_df[['id', 'nome_guerra', 'pelotao']], left_on='aluno_id', right_on='id', how='left')
        
        for _, acao in acoes_recentes.iterrows():
            col1, col2, col3 = st.columns([2, 4, 1])
            with col1:
                st.write(f"**{acao['data'].strftime('%d/%m/%Y')}**")
                st.write(f"{acao.get('nome_guerra', 'N/A')} ({acao.get('pelotao', 'N/A')})")
            with col2:
                st.write(f"**{acao['tipo']}**")
                st.caption(acao['descricao'])
            with col3:
                pont = float(acao['pontuacao_efetiva'])
                cor = "green" if pont > 0 else "red" if pont < 0 else "gray"
                st.markdown(f"<h3 style='color:{cor}; text-align:right;'>{pont:+.1f}</h3>", unsafe_allow_html=True)
            st.divider()
    else:
        st.info("Nenhuma anotação registrada ainda.")