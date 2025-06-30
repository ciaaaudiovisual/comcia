import streamlit as st
import pandas as pd
from database import load_data, init_supabase_client
from auth import check_permission

def show_admin_panel():
    st.title("Painel de Gestão do Administrador")
    supabase = init_supabase_client()

    if not check_permission('acesso_pagina_painel_admin'):
        st.error("Acesso negado. Você não tem permissão para visualizar esta página.")
        st.stop()

    st.warning("⚠️ Atenção: As alterações feitas aqui modificam diretamente a base de dados.")
    
    tabelas = ["Alunos", "Acoes", "Tipos_Acao", "Config", "Programacao", "Ordens_Diarias", "Tarefas", "Users", "Permissions"]
    tabela_selecionada = st.selectbox("Selecione uma tabela para visualizar/editar:", tabelas)

    if tabela_selecionada:
        df_original = load_data(tabela_selecionada)
        
        if not df_original.empty:
            st.info(f"Editando a tabela: {tabela_selecionada}. Cuidado ao modificar IDs e chaves.")
            df_editado = st.data_editor(df_original, num_rows="dynamic", key=f"editor_{tabela_selecionada}")
            
            if st.button(f"Salvar Alterações em {tabela_selecionada}"):
                if df_original.equals(df_editado):
                    st.info("Nenhuma alteração detectada para salvar.")
                    return

                try:
                    with st.spinner("Processando e salvando alterações..."):
                        # Define a chave primária de cada tabela
                        pk_map = {
                            "Config": "chave",
                            "Permissions": "feature_key"
                        }
                        primary_key = pk_map.get(tabela_selecionada, "id")

                        # Converte a chave primária para string para comparação segura
                        df_original[primary_key] = df_original[primary_key].astype(str)
                        df_editado[primary_key] = df_editado[primary_key].astype(str)

                        # 1. Encontrar e processar exclusões
                        ids_originais = set(df_original[primary_key])
                        ids_editados = set(df_editado[primary_key])
                        ids_excluidos = list(ids_originais - ids_editados)
                        
                        if ids_excluidos:
                            st.write(f"Excluindo {len(ids_excluidos)} linha(s)...")
                            supabase.table(tabela_selecionada).delete().in_(primary_key, ids_excluidos).execute()

                        # 2. Encontrar e processar adições e atualizações com 'upsert'
                        # Upsert: insere se a linha é nova, atualiza se a chave primária já existe.
                        registros_para_upsert = df_editado.to_dict(orient='records')
                        
                        # Garante que novas linhas adicionadas pelo editor tenham um ID
                        if primary_key == 'id':
                            ids_numericos = pd.to_numeric(df_original['id'], errors='coerce').dropna()
                            id_atual = int(ids_numericos.max()) if not ids_numericos.empty else 0
                            for registro in registros_para_upsert:
                                if pd.isna(registro.get('id')) or str(registro.get('id')) == 'nan':
                                    id_atual += 1
                                    registro['id'] = str(id_atual)

                        if registros_para_upsert:
                            st.write("Adicionando/Atualizando linha(s)...")
                            supabase.table(tabela_selecionada).upsert(registros_para_upsert).execute()

                    st.success(f"Tabela '{tabela_selecionada}' atualizada com sucesso no Supabase!")
                    load_data.clear() # Limpa o cache para recarregar tudo
                    st.rerun()

                except Exception as e:
                    st.error(f"Ocorreu um erro ao salvar: {e}")
        else:
            st.warning(f"A tabela '{tabela_selecionada}' está vazia ou não pôde ser carregada.")