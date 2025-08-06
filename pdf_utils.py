from io import BytesIO
import pdfrw
from PyPDF2 import PdfMerger

def fill_pdf_auxilio(template_bytes, data, mapping):
    """
    Preenche um formulário PDF com base nos dados fornecidos.
    - template_bytes: O conteúdo do modelo PDF em bytes.
    - data: Uma linha (Pandas Series) com os dados do aluno.
    - mapping: Um dicionário que mapeia nomes de campos do PDF para nomes de colunas nos dados.
    """
    template_stream = BytesIO(template_bytes)
    template = pdfrw.PdfReader(template_stream)
    
    data_to_fill = {}
    for pdf_field, data_col in mapping.items():
        if data_col != '-- Não Mapear --' and data_col in data:
            # O nome do campo no PDF é envolvido por parênteses
            data_to_fill[f'({pdf_field})'] = data[data_col]

    if template.Root.AcroForm and template.Root.AcroForm.Fields:
        for page in template.pages:
            annotations = page.get('/Annots')
            if annotations:
                for annotation in annotations:
                    # --- INÍCIO DA CORREÇÃO ---
                    # Pega o objeto de nome de campo do PDF
                    field_object = annotation.get('/T')
                    
                    # Verifica se o campo tem um nome
                    if field_object:
                        # Converte o nome do campo para um texto normal (str) antes de usar
                        field_key = str(field_object)
                        
                        if field_key in data_to_fill:
                            # Preenche o valor e define o campo como somente leitura
                            annotation.update(
                                pdfrw.PdfDict(V=str(data_to_fill[field_key]), Ff=1)
                            )
                    # --- FIM DA CORREÇÃO ---

    output_buffer = BytesIO()
    pdfrw.PdfWriter().write(output_buffer, template)
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
