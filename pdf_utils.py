# Dentro de pdf_utils.py
from io import BytesIO
from pypdf import PdfReader, PdfWriter
import pandas as pd

def fill_pdf_auxilio(template_bytes, aluno_data, pdf_mapping):
    # ... (código completo da sua função aqui) ...
    # Exemplo simplificado:
    reader = PdfReader(BytesIO(template_bytes))
    writer = PdfWriter(clone_from=reader)
    # ... resto da sua lógica
    output_buffer = BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer

def merge_pdfs(pdf_buffers):
    # ... (código completo da sua função aqui) ...
    # Exemplo simplificado:
    merger = PdfWriter()
    for buffer in pdf_buffers:
        reader = PdfReader(buffer)
        for page in reader.pages:
            merger.add_page(page)
    merged_pdf_buffer = BytesIO()
    merger.write(merged_pdf_buffer)
    merged_pdf_buffer.seek(0)
    return merged_pdf_buffer
