import streamlit as st
import pandas as pd
from datetime import datetime
from database import load_data, save_data

def show_lancamentos_page():
    st.title("Lançamento de Ações")
    
    # Carregar dados
    alunos_df = load_data("Sistema_Acoes_Militares", "Alunos")
    acoes_df = load_data("Sistema_Acoes_Militares", "Acoes")
    tipos_acao_df = load_data("Sistema_Acoes_Militares", "Tipos_Acao")
    
    if alunos_df.empty:
        st.warning("Não há alunos cadastrados. Por favor, cadastre alunos primeiro.")
        return
    
    # Formulário para novo lançamento
    st.subheader("Novo Lançamento")
    
    with st.form("novo_lancamento"):
        col1, col2 = st.columns(2)
        
        with col1:
            # Seleção do aluno
            alunos_opcoes = [f"{aluno['nome_guerra']} ({aluno['numero_interno']}) - {aluno['pelotao']}" 
                            for _, aluno in alunos_df.iterrows()]
            aluno_selecionado = st.selectbox("Selecione o Aluno", alunos_opcoes)
            
            # Obter ID do aluno selecionado
            aluno_index = alunos_opcoes.index(aluno_selecionado)
            aluno_id = alunos_df.iloc[aluno_index]['id']
            
            # Seleção do tipo de ação
            if not tipos_acao_df.empty:
                tipos_opcoes = [f"{tipo['nome']} ({tipo['pontuacao']} pts)" 
                               for _, tipo in tipos_acao_df.iterrows()]
                tipo_selecionado = st.selectbox("Tipo de Ação", tipos_opcoes)
                
                # Obter ID e pontuação do tipo selecionado
                tipo_index = tipos_opcoes.index(tipo_selecionado)
                tipo_id = tipos_acao_df.iloc[tipo_index]['id']
                pontuacao = float(tipos_acao_df.iloc[tipo_index]['pontuacao'])
            else:
                # Tipos padrão se não houver dados
                tipos_padrao = [
                    "Anotação Positiva (+1 pt)",
                    "Anotação Negativa (-1 pt)",
                    "Destaque em Instrução (+3 pts)",
                    "Falta em Formação (-2 pts)",
                    "Hospital (0 pt)"
                ]
                tipo_selecionado = st.selectbox("Tipo de Ação", tipos_padrao)
                
                # Extrair pontuação do texto
                import re
                pontuacao_match = re.search(r'([+-]?\d+)', tipo_selecionado)
                pontuacao = float(pontuacao_match.group(1)) if pontuacao_match else 0
                tipo_id = "1"  # ID padrão
        
        with col2:
            # Data e hora
            data = st.date_input("Data", datetime.now())
            
            # Verificar se está no período de adaptação
            config_df = load_data("Sistema_Acoes_Militares", "Config")
            
            periodo_adaptacao_inicio = None
            periodo_adaptacao_fim = None
            fator_adaptacao = 0.25  # Valor padrão
            
            if not config_df.empty:
                # Buscar configurações
                if 'periodo_adaptacao_inicio' in config_df['chave'].values:
                    inicio_row = config_df[config_df['chave'] == 'periodo_adaptacao_inicio']
                    periodo_adaptacao_inicio = pd.to_datetime(inicio_row['valor'].iloc[0])
                
                if 'periodo_adaptacao_fim' in config_df['chave'].values:
                    fim_row = config_df[config_df['chave'] == 'periodo_adaptacao_fim']
                    periodo_adaptacao_fim = pd.to_datetime(fim_row['valor'].iloc[0])
                
                if 'fator_adaptacao' in config_df['chave'].values:
                    fator_row = config_df[config_df['chave'] == 'fator_adaptacao']
                    fator_adaptacao = float(fator_row['valor'].iloc[0])
            
            # Verificar se a data está no período de adaptação
            data_lancamento = pd.to_datetime(data)
            em_adaptacao = False
            
            if periodo_adaptacao_inicio and periodo_adaptacao_fim:
                em_adaptacao = (data_lancamento >= periodo_adaptacao_inicio) and (data_lancamento <= periodo_adaptacao_fim)
            
            # Mostrar status de adaptação
            if em_adaptacao:
                st.info(f"📢 Período de Adaptação: pontuação será multiplicada por {fator_adaptacao}")
                pontuacao_efetiva = pontuacao * fator_adaptacao
            else:
                pontuacao_efetiva = pontuacao
            
            # Descrição
            descricao = st.text_area("Descrição/Justificativa", height=100)
        
        # Botão de submissão
        submitted = st.form_submit_button("Registrar Ação")
        
        if submitted:
            if not descricao:
                st.error("Por favor, forneça uma descrição para a ação.")
            else:
                # Criar novo ID
                novo_id = 1
                if not acoes_df.empty and 'id' in acoes_df.columns:
                    novo_id = int(acoes_df['id'].max()) + 1
                
                # Criar novo lançamento
                nova_acao = {
                    'id': novo_id,
                    'aluno_id': aluno_id,
                    'tipo_acao_id': tipo_id,
                    'tipo': tipo_selecionado.split(' (')[0],  # Extrair apenas o nome
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
                    st.success(f"Ação registrada com sucesso! Pontuação: {pontuacao_efetiva:+.2f}")
                    
                    # Atualizar pontuação do aluno
                    # (Na implementação completa, isso seria feito através de uma função separada)
                else:
                    st.error("Erro ao salvar a ação. Verifique a conexão com o Google Sheets.")
    
    # Histórico de lançamentos recentes
    st.subheader("Lançamentos Recentes")
    
    if acoes_df.empty:
        st.info("Nenhum lançamento registrado ainda.")
    else:
        # Ordenar por data (mais recentes primeiro)
        acoes_df['data'] = pd.to_datetime(acoes_df['data'])
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
        
        # Exibir lançamentos recentes
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

def registrar_acao(aluno_id, nome_aluno):
    st.subheader(f"Registrar Ação para {nome_aluno}")
    
    # Carregar tipos de ação
    tipos_acao_df = load_data("Sistema_Acoes_Militares", "Tipos_Acao")
    acoes_df = load_data("Sistema_Acoes_Militares", "Acoes")
    
    with st.form("registrar_acao_form"):
        # Seleção do tipo de ação
        if not tipos_acao_df.empty:
            tipos_opcoes = [f"{tipo['nome']} ({tipo['pontuacao']} pts)" 
                           for _, tipo in tipos_acao_df.iterrows()]
            tipo_selecionado = st.selectbox("Tipo de Ação", tipos_opcoes)
            
            # Obter ID e pontuação do tipo selecionado
            tipo_index = tipos_opcoes.index(tipo_selecionado)
            tipo_id = tipos_acao_df.iloc[tipo_index]['id']
            pontuacao = float(tipos_acao_df.iloc[tipo_index]['pontuacao'])
        else:
            # Tipos padrão se não houver dados
            tipos_padrao = [
                "Anotação Positiva (+1 pt)",
                "Anotação Negativa (-1 pt)",
                "Destaque em Instrução (+3 pts)",
                "Falta em Formação (-2 pts)",
                "Hospital (0 pt)"
            ]
            tipo_selecionado = st.selectbox("Tipo de Ação", tipos_padrao)
            
            # Extrair pontuação do texto
            import re
            pontuacao_match = re.search(r'([+-]?\d+)', tipo_selecionado)
            pontuacao = float(pontuacao_match.group(1)) if pontuacao_match else 0
            tipo_id = "1"  # ID padrão
        
        # Data e descrição
        data = st.date_input("Data", datetime.now())
        descricao = st.text_area("Descrição/Justificativa", height=100)
        
        # Botão de submissão
        submitted = st.form_submit_button("Registrar")
        
        if submitted:
            if not descricao:
                st.error("Por favor, forneça uma descrição para a ação.")
            else:
                # Criar novo ID
                novo_id = 1
                if not acoes_df.empty and 'id' in acoes_df.columns:
                    novo_id = int(acoes_df['id'].max()) + 1
                
                # Criar novo lançamento
                nova_acao = {
                    'id': novo_id,
                    'aluno_id': aluno_id,
                    'tipo_acao_id': tipo_id,
                    'tipo': tipo_selecionado.split(' (')[0],  # Extrair apenas o nome
                    'descricao': descricao,
                    'data': data.strftime('%Y-%m-%d'),
                    'usuario': st.session_state.username,
                    'pontuacao': pontuacao,
                    'pontuacao_efetiva': pontuacao  # Sem verificação de adaptação nesta versão simplificada
                }
                
                # Adicionar à DataFrame
                if acoes_df.empty:
                    acoes_df = pd.DataFrame([nova_acao])
                else:
                    acoes_df = pd.concat([acoes_df, pd.DataFrame([nova_acao])], ignore_index=True)
                
                # Salvar no Google Sheets
                if save_data("Sistema_Acoes_Militares", "Acoes", acoes_df):
                    st.success(f"Ação registrada com sucesso! Pontuação: {pontuacao:+.2f}")
                    st.session_state.registrar_acao = False
                    st.rerun()
                else:
                    st.error("Erro ao salvar a ação. Verifique a conexão com o Google Sheets.")
