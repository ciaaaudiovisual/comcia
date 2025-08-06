from io import BytesIO
import pdfrw
from PyPDF2 import PdfMerger

def fill_pdf_auxilio(template_bytes, data, mapping):
    """
    Preenche um formulário PDF com base nos dados fornecidos.
    """
    print("\n--- DEBUG: INICIANDO PREENCHIMENTO DE UM PDF ---") # DEBUG
    
    template_stream = BytesIO(template_bytes)
    template = pdfrw.PdfReader(template_stream)
    
    data_to_fill = {}
    for pdf_field, data_col in mapping.items():
        if data_col != '-- Não Mapear --' and data_col in data:
            data_to_fill[f'({pdf_field})'] = data[data_col]

    print(f"DEBUG: Dicionário de dados criado. Chaves: {list(data_to_fill.keys())}") # DEBUG

    match_found = False
    if template.Root.AcroForm and template.Root.AcroForm.Fields:
        for page in template.pages:
            annotations = page.get('/Annots')
            if annotations:
                for annotation in annotations:
                    field_object = annotation.get('/T')
                    
                    if field_object:
                        field_key = str(field_object)
                        # Imprime o campo encontrado no PDF para vermos o seu formato exato
                        print(f"DEBUG: Campo encontrado no PDF -> '{field_key}'") # DEBUG
                        
                        if field_key in data_to_fill:
                            match_found = True
                            print(f"    ==> MATCH ENCONTRADO! Preenchendo '{field_key}' com o valor '{data_to_fill[field_key]}'") # DEBUG
                            annotation.update(
                                pdfrw.PdfDict(V=str(data_to_fill[field_key]), Ff=1)
                            )

    if not match_found:
        print("DEBUG: AVISO! Nenhum campo do PDF correspondeu às chaves dos dados a preencher.") # DEBUG
    
    print("--- DEBUG: FIM DO PREENCHIMENTO ---\n") # DEBUG

    output_buffer = BytesIO()
    pdfrw.PdfWriter().write(output_buffer, template)
    output_buffer.seek(0)
    
    return output_buffer

def merge_pdfs(pdf_list):
    """
    Junta vários PDFs.
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
