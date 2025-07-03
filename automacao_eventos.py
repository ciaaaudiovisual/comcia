import pandas as pd
from datetime import datetime
from database import init_supabase_client, load_data
import logging

# Configuração básica de logging para podermos ver o que o script está a fazer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def finalizar_eventos_automaticamente():
    """
    Verifica e finaliza eventos rotineiros que já passaram do seu horário.
    """
    logging.info("Iniciando verificação de eventos para finalização automática...")
    
    supabase = init_supabase_client()
    if not supabase:
        logging.error("Não foi possível conectar ao Supabase. Saindo.")
        return

    # Nomes dos eventos que devem ser finalizados automaticamente
    eventos_para_automatizar = [
        "Rancho Geral",
        "Ceia",
        "Verificação de presença",
        "Alojamento"
    ]

    try:
        # Carrega a programação completa
        programacao_df = load_data("Programacao")
        if programacao_df.empty:
            logging.info("Tabela de programação vazia. Nenhum evento para processar.")
            return

        # Filtra apenas os eventos que nos interessam e que ainda não foram concluídos
        eventos_filtrados = programacao_df[
            programacao_df['descricao'].isin(eventos_para_automatizar) &
            (programacao_df['status'] == 'A Realizar')
        ].copy()

        if eventos_filtrados.empty:
            logging.info("Nenhum evento automático pendente encontrado.")
            return

        # Combina data e horário para criar uma data/hora completa para cada evento
        eventos_filtrados['data_hora_evento'] = pd.to_datetime(
            eventos_filtrados['data'] + ' ' + eventos_filtrados['horario'],
            errors='coerce'
        )
        
        # Remove eventos que não puderam ter a data/hora convertida
        eventos_filtrados.dropna(subset=['data_hora_evento'], inplace=True)

        # Pega a hora atual
        agora = datetime.now()
        
        # Filtra os eventos cujo horário já passou
        eventos_a_finalizar = eventos_filtrados[eventos_filtrados['data_hora_evento'] <= agora]

        if eventos_a_finalizar.empty:
            logging.info("Nenhum evento atingiu o seu horário de finalização ainda.")
            return

        ids_para_finalizar = eventos_a_finalizar['id'].tolist()
        
        logging.info(f"Encontrados {len(ids_para_finalizar)} eventos para finalizar: {ids_para_finalizar}")

        # Prepara os dados para a atualização em massa
        update_data = {
            "status": "Concluído",
            "concluido_por": "Sistema (Automático)",
            "data_conclusao": agora.strftime('%d/%m/%Y %H:%M')
        }

        # Executa a atualização na base de dados
        supabase.table("Programacao").update(update_data).in_("id", ids_para_finalizar).execute()

        logging.info(f"Sucesso! {len(ids_para_finalizar)} eventos foram finalizados automaticamente.")

    except Exception as e:
        logging.error(f"Ocorreu um erro durante a execução da automação: {e}")

if __name__ == "__main__":
    finalizar_eventos_automaticamente()
