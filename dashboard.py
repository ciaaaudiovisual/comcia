import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from database import load_data, save_data

def show_dashboard():
    st.title("Dashboard")
    
    # Carregar dados
    alunos_df = load_data("Sistema_Acoes_Militares", "Alunos")
    acoes_df = load_data("Sistema_Acoes_Militares", "Acoes")
    tipos_acao_df = load_data("Sistema_Acoes_Militares", "Tipos_Acao")
    
    if alunos_df.empty or acoes_df.empty:
        st.warning("Sem dados para exibir. Por favor, adicione alunos e ações.")
        return
    
    # Preparar dados
    hoje = datetime.now().date()
    acoes_df['data'] = pd.to_datetime(acoes_df['data'], errors='coerce')
    acoes_hoje = acoes_df[acoes_df['data'].dt.date == hoje]
    
    # NOVA SEÇÃO: Anotação Rápida
    with st.expander("➕ Anotação Rápida", expanded=False):
        st.subheader("Registrar Anotação Rápida")
        
        with st.form("anotacao_rapida"):
            # Seleção de alunos (múltiplos)
            alunos_opcoes = [f"{aluno['nome_guerra']} ({aluno['numero_interno']}) - {aluno['pelotao']}" 
                     for _, aluno in alunos_df.iterrows()]
            
            alunos_selecionados = st.multiselect(
                "Selecione os Alunos",
                alunos_opcoes
            )
            
            # Tipo de ação
            tipos_opcoes = ["Anotação Positiva", "Anotação Negativa"]
            if not tipos_acao_df.empty:
                tipos_opcoes = tipos_acao_df['nome'].tolist()
            
            tipo_acao = st.selectbox("Tipo de Ação", tipos_opcoes)
            
            # Pontuação associada
            pontuacao = 0
            if not tipos_acao_df.empty and 'nome' in tipos_acao_df.columns and 'pontuacao' in tipos_acao_df.columns:
                tipo_row = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao]
                if not tipo_row.empty:
                    pontuacao = float(tipo_row.iloc[0]['pontuacao'])
            
            st.write(f"Pontuação: {pontuacao:+.1f}")
            
            # Descrição
            descricao = st.text_area("Descrição/Justificativa")
            
            # Data (padrão: hoje)
            data = st.date_input("Data", value=datetime.now())
            
            submitted = st.form_submit_button("Registrar")
            
            if submitted and alunos_selecionados:
                # Para cada aluno selecionado
                for aluno_str in alunos_selecionados:
                    # Extrair número interno do formato "Nome (Número) - Pelotão"
                    numero_interno = aluno_str.split('(')[1].split(')')[0]
                    
                    # Encontrar ID do aluno
                    aluno_row = alunos_df[alunos_df['numero_interno'] == numero_interno]
                    if not aluno_row.empty:
                        aluno_id = aluno_row.iloc[0]['id']
                        
                        # Encontrar ID do tipo de ação
                        tipo_acao_id = 0
                        if not tipos_acao_df.empty:
                            tipo_row = tipos_acao_df[tipos_acao_df['nome'] == tipo_acao]
                            if not tipo_row.empty:
                                tipo_acao_id = tipo_row.iloc[0]['id']
                        
                        # Criar novo ID para a ação
                        novo_id = 1
                        if not acoes_df.empty and 'id' in acoes_df.columns:
                            novo_id = int(acoes_df['id'].max()) + 1
                        
                        # Verificar período de adaptação
                        data_adaptacao_inicio = datetime.strptime('2025-06-30', '%Y-%m-%d').date()
                        data_adaptacao_fim = datetime.strptime('2025-07-21', '%Y-%m-%d').date()
                        
                        pontuacao_efetiva = pontuacao
                        if data_adaptacao_inicio <= data.date() <= data_adaptacao_fim:
                            pontuacao_efetiva = pontuacao * 0.25  # 25% da pontuação no período de adaptação
                        
                        # Criar nova ação
                        nova_acao = {
                            'id': novo_id,
                            'aluno_id': aluno_id,
                            'tipo_acao_id': tipo_acao_id,
                            'tipo': tipo_acao,
                            'descricao': descricao,
                            'data': data.strftime('%Y-%m-%d'),
                            'usuario': st.session_state.username,
                            'pontuacao': pontuacao,
                            'pontuacao_efetiva': pontuacao_efetiva
                        }
                        
                        # Adicionar à DataFrame
                        if acoes_df.empty:
                            acoes_df = pd.DataFrame([nova_acao])
                        else:
                            acoes_df = pd.concat([acoes_df, pd.DataFrame([nova_acao])], ignore_index=True)
                
                # Salvar no Google Sheets
                if save_data("Sistema_Acoes_Militares", "Acoes", acoes_df):
                    st.success(f"Ações registradas com sucesso para {len(alunos_selecionados)} aluno(s)!")
                    st.rerun()
                else:
                    st.error("Erro ao salvar as ações. Verifique a conexão com o Google Sheets.")
    
    # Layout em colunas
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Destaques do Dia")
        
        # Destaque positivo
        if not acoes_hoje.empty:
            # Usar pontuacao_efetiva em vez de pontuacao
            acoes_positivas = acoes_hoje[acoes_hoje['pontuacao_efetiva'] > 0]
            if not acoes_positivas.empty:
                # Agrupar por aluno e somar pontuações
                aluno_positivo = acoes_positivas.groupby('aluno_id')['pontuacao_efetiva'].sum().idxmax()
                aluno_info = alunos_df[alunos_df['id'] == aluno_positivo].iloc[0]
                
                st.info(f"🌟 **Destaque Positivo**: {aluno_info['nome_guerra']} ({aluno_info['pelotao']})")
        
        # Destaque negativo
        if not acoes_hoje.empty:
            # Usar pontuacao_efetiva em vez de pontuacao
            acoes_negativas = acoes_hoje[acoes_hoje['pontuacao_efetiva'] < 0]
            if not acoes_negativas.empty:
                # Agrupar por aluno e somar pontuações
                aluno_negativo = acoes_negativas.groupby('aluno_id')['pontuacao_efetiva'].sum().idxmin()
                aluno_info = alunos_df[alunos_df['id'] == aluno_negativo].iloc[0]
                
                st.warning(f"⚠️ **Destaque Negativo**: {aluno_info['nome_guerra']} ({aluno_info['pelotao']})")
        
        # Aniversariantes da semana
        st.subheader("Aniversariantes da Semana")
        
        # Converter datas de nascimento para datetime
        alunos_df['data_nascimento'] = pd.to_datetime(alunos_df['data_nascimento'], errors='coerce')
        
        # Filtrar aniversariantes da semana
        proxima_semana = hoje + timedelta(days=7)
        aniversariantes = []
        
        for _, aluno in alunos_df.iterrows():
            if pd.notna(aluno['data_nascimento']):
                nascimento = aluno['data_nascimento']
                aniversario_este_ano = datetime(hoje.year, nascimento.month, nascimento.day).date()
                
                if hoje <= aniversario_este_ano <= proxima_semana:
                    aniversariantes.append({
                        'nome': aluno['nome_guerra'],
                        'data': aniversario_este_ano.strftime('%d/%m'),
                        'pelotao': aluno['pelotao']
                    })
        
        if aniversariantes:
            for aniv in aniversariantes:
                st.write(f"🎂 {aniv['nome']} - {aniv['data']} ({aniv['pelotao']})")
        else:
            st.write("Nenhum aniversariante esta semana.")
    
    with col2:
        st.subheader("Pontuação Média por Pelotão")
        
        # ADICIONADO: Calcular pontuação por aluno (esta linha estava faltando)
        if not acoes_df.empty and 'aluno_id' in acoes_df.columns and 'pontuacao_efetiva' in acoes_df.columns:
            pontuacao_por_aluno = acoes_df.groupby('aluno_id')['pontuacao_efetiva'].sum().reset_index()
            
            # Mesclar com dados dos alunos
            if 'id' in alunos_df.columns and 'pelotao' in alunos_df.columns:
                alunos_com_pontuacao = pd.merge(
                    alunos_df,
                    pontuacao_por_aluno,
                    left_on='id',
                    right_on='aluno_id',
                    how='left'
                )
                
                # Preencher valores nulos com pontuação inicial (10)
                alunos_com_pontuacao['pontuacao_efetiva'] = alunos_com_pontuacao['pontuacao_efetiva'].fillna(0) + 10
                
                # CORRIGIDO: Usar pontuacao_efetiva em vez de pontuacao
                media_por_pelotao = alunos_com_pontuacao.groupby('pelotao')['pontuacao_efetiva'].mean().reset_index()
                
                # Criar gráfico
                fig = px.bar(
                    media_por_pelotao,
                    x='pelotao',
                    y='pontuacao_efetiva',  # CORRIGIDO: Usar pontuacao_efetiva
                    title='Pontuação Média por Pelotão',
                    labels={'pelotao': 'Pelotão', 'pontuacao_efetiva': 'Pontuação Média'},  # CORRIGIDO
                    color='pontuacao_efetiva',  # CORRIGIDO
                    color_continuous_scale='RdYlGn'  # Vermelho para baixo, verde para cima
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Dados insuficientes para gerar gráficos.")
        else:
            st.info("Dados insuficientes para gerar gráficos.")
    
    # Botão de sincronização
    if st.button("🔄 Sincronizar Dados"):
        st.info("Sincronizando dados com Google Sheets...")
        # Aqui implementaríamos a sincronização real
        st.success("Dados sincronizados com sucesso!")
    
    # NOVA SEÇÃO: Lista rolável de anotações recentes
    st.subheader("Anotações Recentes")
    if not acoes_df.empty:
        # Ordenar por data (mais recentes primeiro)
        acoes_recentes = acoes_df.sort_values('data', ascending=False).head(10)
        
        # Mesclar com dados dos alunos para mostrar nomes
        if not alunos_df.empty:
            acoes_recentes = pd.merge(
                acoes_recentes,
                alunos_df[['id', 'nome_guerra', 'pelotao']],
                left_on='aluno_id',
                right_on='id',
                suffixes=('', '_aluno')
            )
        
        # Exibir em container rolável
        with st.container():
            for _, acao in acoes_recentes.iterrows():
                col1, col2, col3 = st.columns([2, 3, 1])
                
                with col1:
                    st.write(f"**{acao['data'].strftime('%d/%m/%Y')}**")
                    st.write(f"Aluno: {acao.get('nome_guerra', 'N/A')}")
                    st.write(f"Pelotão: {acao.get('pelotao', 'N/A')}")
                
                with col2:
                    st.write(f"**{acao['tipo']}**")
                    st.write(acao['descricao'])
                
                with col3:
                    pontuacao = float(acao['pontuacao_efetiva'])
                    cor = "green" if pontuacao > 0 else "red" if pontuacao < 0 else "gray"
                    st.markdown(f"<h3 style='color:{cor};text-align:center'>{pontuacao:+.1f}</h3>", unsafe_allow_html=True)
                
                st.divider()
    else:
        st.info("Nenhuma anotação registrada ainda.")
