import pandas as pd

# --- CONFIGURAÇÕES ---
# Nome do seu arquivo CSV
NOME_ARQUIVO_CSV = 'ANIVERSARIO ID E DATA.csv'
# Delimitador usado no seu CSV
DELIMITADOR_CSV = ';'

# Nome da sua tabela NO BANCO DE DADOS
NOME_TABELA_SQL = "Alunos" # Confirmado: Sua tabela é 'Alunos'

# Mapeamento das colunas: CSV para SQL
# A chave é o nome da coluna no seu CSV
# O valor é o nome da coluna CORRESPONDENTE na sua tabela SQL
MAPA_COLUNAS_ATUALIZAR = {
    'ID': 'id', # Coluna no CSV 'ID' (do seu ANIVERSARIO ID E DATA.csv) corresponde a 'id' na sua tabela Alunos
    'DATA_NASCIMENTO': 'data_nascimento' # Coluna no CSV 'DATA_NASCIMENTO' corresponde a 'data_nascimento' na sua tabela Alunos
}

# Nome do arquivo de saída SQL que será gerado
NOME_ARQUIVO_SQL_SAIDA = "atualizar_alunos_nascimento.sql"

# --- CÓDIGO ---
try:
    # 1. Carregar o arquivo CSV
    df = pd.read_csv(NOME_ARQUIVO_CSV, delimiter=DELIMITADOR_CSV)
    print(f"Arquivo '{NOME_ARQUIVO_CSV}' carregado com sucesso. Total de {len(df)} registros para processar.")

    # Abrir o arquivo de saída SQL para escrita
    with open(NOME_ARQUIVO_SQL_SAIDA, 'w') as f_sql:
        print(f"Gerando script SQL de UPDATE em '{NOME_ARQUIVO_SQL_SAIDA}'...")

        # Adicionar um cabeçalho informativo ao script SQL
        f_sql.write(f"-- Script gerado automaticamente para ATUALIZAR dados na tabela {NOME_TABELA_SQL}\n")
        f_sql.write("-- Este script atualiza a coluna 'data_nascimento' usando 'id' como referência.\n")
        f_sql.write("-- A coluna 'data_nascimento' é do tipo TEXT, portanto, as datas são formatadas como 'YYYY-MM-DD'.\n")
        f_sql.write("-- RECOMENDAÇÃO: Faça um backup da sua tabela antes de executar este script.\n")
        f_sql.write("-- -----------------------------------------------------------------------------------\n\n")

        # 2. Iterar sobre cada linha do DataFrame e gerar a instrução UPDATE
        for index, row in df.iterrows():
            # Extrair valores do CSV
            # Certifique-se de que a coluna 'ID' e 'DATA_NASCIMENTO' realmente existem no seu CSV
            militar_id_csv = row['ID']
            data_nascimento_str_csv = str(row['DATA_NASCIMENTO']).strip() # Pega como string e remove espaços

            # 3. Formatar os valores para SQL
            # Para 'id' (int8/BIGINT), o Python int já é adequado.
            # Para 'data_nascimento' (text), vamos formatar para 'YYYY-MM-DD' e envolver com aspas simples.

            data_formatada_sql = "NULL" # Valor padrão para caso de erro na data
            try:
                # Tenta inferir o formato da data do CSV.
                # Se seu CSV tiver um formato de data consistente (ex: 'DD/MM/AAAA'),
                # é mais seguro especificar o formato:
                # data_obj = pd.to_datetime(data_nascimento_str_csv, format='%d/%m/%Y', errors='coerce')
                # Ou para 'DD-MM-AAAA':
                # data_obj = pd.to_datetime(data_nascimento_str_csv, format='%d-%m-%Y', errors='coerce')

                data_obj = pd.to_datetime(data_nascimento_str_csv, infer_datetime_format=True, errors='coerce')
                
                if pd.isna(data_obj):
                    print(f"AVISO: Data inválida detectada para ID '{militar_id_csv}': '{data_nascimento_str_csv}'. Será definido como NULL.")
                else:
                    data_formatada_sql = f"'{data_obj.strftime('%Y-%m-%d')}'" # Formata para 'YYYY-MM-DD'
            except Exception as e:
                print(f"ERRO DE FORMATAÇÃO DE DATA para ID '{militar_id_csv}' e data '{data_nascimento_str_csv}': {e}. Será definido como NULL.")

            # 4. Construir a instrução UPDATE
            # Nomes das colunas SQL a serem usadas
            coluna_id_sql = MAPA_COLUNAS_ATUALIZAR['ID']
            coluna_data_nascimento_sql = MAPA_COLUNAS_ATUALIZAR['DATA_NASCIMENTO']

            update_statement = (
                f"UPDATE {NOME_TABELA_SQL} "
                f"SET {coluna_data_nascimento_sql} = {data_formatada_sql} "
                f"WHERE {coluna_id_sql} = {militar_id_csv};\n"
            )
            
            f_sql.write(update_statement)

    print(f"\nScript SQL '{NOME_ARQUIVO_SQL_SAIDA}' gerado com sucesso!")
    print(f"Contém {len(df)} instruções UPDATE. Agora você pode executá-lo no seu banco de dados.")
    print("LEMBRE-SE: Faça um backup da sua tabela 'Alunos' antes de executar o script de UPDATE.")

except FileNotFoundError:
    print(f"ERRO: O arquivo CSV '{NOME_ARQUIVO_CSV}' não foi encontrado. Certifique-se de que ele está na mesma pasta que o script Python.")
except KeyError as e:
    print(f"ERRO: Coluna esperada pelo script não encontrada no CSV: '{e}'. Verifique se 'ID' e 'DATA_NASCIMENTO' estão no seu CSV.")
except Exception as e:
    print(f"Ocorreu um erro inesperado: {e}")
