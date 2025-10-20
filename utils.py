# utils.py
import streamlit as st

def get_student_photo_url(numero_interno: str) -> str:
    """
    Constrói a URL pública para a foto de um aluno no Supabase Storage.
    Assume que as imagens são .png e estão em um bucket público 'fotos-alunos'.
    """
    if not numero_interno or not isinstance(numero_interno, str):
        return "https://via.placeholder.com/100?text=S/Foto"

    try:
        project_id = st.secrets["supabase"]["project_id"]
        # IMPORTANTE: Garanta que todas as suas imagens no bucket terminem com .png
        # Você pode alterar para .jpg se preferir, mas padronize.
        file_name = f"{numero_interno.strip()}.png"
        
        # Monta a URL pública padrão do Supabase Storage
        url = f"https://{project_id}.supabase.co/storage/v1/object/public/fotos-alunos/{file_name}"
        return url
        
    except (KeyError, TypeError):
        # Retorna uma imagem padrão se a configuração nos segredos não for encontrada
        return "https://via.placeholder.com/100?text=Erro+Conf"
