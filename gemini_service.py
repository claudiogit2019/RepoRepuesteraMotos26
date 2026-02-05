import os
from groq import Groq
from dotenv import load_dotenv  

load_dotenv()  

api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=api_key)
def transcribir_audio_fluido(archivo_audio):
    try:
        with open(archivo_audio, "rb") as audio:
            return client.audio.transcriptions.create(
                file=(archivo_audio, audio.read()),
                model="whisper-large-v3",
                response_format="text",
                language="es"
            )
    except Exception as e: return f"Error: {str(e)}"

def procesar_pedido_con_ia(pedido, inventario_contexto):
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system", 
                    "content": f"""Eres el experto en repuestos de 'MotoRepuestos'. 
                    INVENTARIO DISPONIBLE: {inventario_contexto}.
                    TAREA: Responde ÚNICAMENTE con este formato por línea: PRODUCTO | CANTIDAD | SUBTOTAL_CALCULADO
                    Ejemplo: Piñón 14T | 1 | 15000"""
                },
                {"role": "user", "content": pedido}
            ],
            temperature=0.1
        )
        return completion.choices[0].message.content
    except Exception as e: return f"Error: {str(e)}"
