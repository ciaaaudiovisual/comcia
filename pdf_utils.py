from io import BytesIO
from pdfrw import PdfReader, PdfWriter, IndirectPdfDict
from PyPDF2 import PdfMerger

def fill_pdf_auxilio(template_bytes, data, mapping):
    """
    Preenche um formulário PDF com base nos dados fornecidos.
    - template_bytes: O conteúdo do modelo PDF em bytes.
    - data: Uma linha (Pandas Series) com os dados do aluno.
    - mapping: Um dicionário que mapeia nomes de campos do PDF para nomes de colunas nos dados.
    """
    # Cria um fluxo de bytes em memória para o pdfrw ler
    template_stream = BytesIO(template_bytes)
    template = PdfReader(template_stream)
    
    # Dicionário para armazenar os dados a serem preenchidos
    data_to_fill = {}
    for pdf_field, data_col in mapping.items():
        if data_col != '-- Não Mapear --' and data_col in data:
            data_to_fill[f'({pdf_field})'] = data[data_col]

    if template.Root.AcroForm and template.Root.AcroForm.Fields:
        for page in template.pages:
            annotations = page.get('/Annots')
            if annotations:
                for annotation in annotations:
                    field_key = annotation.get('/T')
                    if field_key in data_to_fill:
                        # Preenche o valor e define o campo como somente leitura
                        annotation.update(
                            PdfWriter.PdfDict(V=str(data_to_fill[field_key]), Ff=1)
                        )

    # Salva o PDF preenchido num buffer de memória
    output_buffer = BytesIO()
    PdfWriter().write(output_buffer, template)
    output_buffer.seek(0)
    
    return output_buffer


def merge_pdfs(pdf_list):
    """
    Junta vários PDFs (em buffers de memória) num único ficheiro.
    - pdf_list: Uma lista de buffers BytesIO, cada um contendo um PDF.
    """
    merger = PdfMerger()
    
    for pdf_buffer in pdf_list:
        pdf_buffer.seek(0)
        merger.append(pdf_buffer)
        
    output_buffer = BytesIO()
    merger.write(output_buffer)
    merger.close()
    
    output_buffer.seek(0)
    return output_buffer
