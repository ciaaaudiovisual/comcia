# Conteúdo para o ficheiro: pdf_utils.py

import pandas as pd
from io import BytesIO
from pypdf import PdfReader, PdfWriter

def fill_pdf_auxilio(template_bytes, aluno_data, pdf_mapping):
    """
    Preenche um único formulário PDF com os dados de um aluno.
    """
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter(clone_from=reader)
    
    fill_data = {}
    for pdf_field, df_column in pdf_mapping.items():
        if not df_column or df_column == "-- Não Mapear Este Campo --":
            continue

        valor = aluno_data.get(df_column)
        if pd.isna(valor):
            valor = ''
        
        campos_moeda = ['despesa_diaria', 'despesa_mensal_total', 'parcela_descontada_6_porcento', 'auxilio_transporte_pago', 'soldo']
        if df_column in campos_moeda or 'tarifa' in df_column:
            try:
                valor_numerico = float(valor)
                valor_formatado = f"R$ {valor_numerico:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                fill_data[pdf_field] = valor_formatado
            except (ValueError, TypeError):
                fill_data[pdf_field] = "R$ 0,00"
        else:
            fill_data[pdf_field] = str(valor)

    if writer.get_form_text_fields():
        for page in writer.pages:
            writer.update_page_form_field_values(page, fill_data)
            
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer

def merge_pdfs(pdf_buffers):
    """Junta vários PDFs (em memória) num único ficheiro."""
    merger = PdfWriter()
    for buffer in pdf_buffers:
        reader = PdfReader(buffer)
        for page in reader.pages:
            merger.add_page(page)
            
    merged_pdf_buffer = BytesIO()
    merger.write(merged_pdf_buffer)
    merged_pdf_buffer.seek(0)
    return merged_pdf_buffer
