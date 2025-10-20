# utils.py
import streamlit as st

def get_student_photo_url(numero_interno: str) -> str:
    if not numero_interno or not isinstance(numero_interno, str):
        return "https://via.placeholder.com/100?text=S/Foto"

    try:
        project_id = st.secrets["supabase"]["project_id"]
        # Garanta que a extensão (.png ou .jpg) corresponde aos seus arquivos no bucket
        file_name = f"{numero_interno.strip()}.png"
        
        url = f"https://{project_id}.supabase.co/storage/v1/object/public/fotos-alunos/{file_name}"
        return url
        
    except (KeyError, TypeError):
        return "https://via.placeholder.com/100?text=Erro+Conf"
