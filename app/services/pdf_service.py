from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML
import os

# Configuración de Jinja2 para buscar en la carpeta 'templates'
# Usamos os.path para evitar errores de rutas en diferentes sistemas operativos
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))

def generar_pdf_entrega(datos_entrega: dict) -> bytes:
    """
    Toma un diccionario de datos, llena la plantilla y devuelve los bytes del PDF.
    """
    # 1. Cargar el template
    template = env.get_template("formato_entrega.html")
    
    # 2. Renderizar el HTML con los datos
    html_content = template.render(datos_entrega)
    
    # 3. Generar PDF en memoria
    pdf_bytes = HTML(string=html_content).write_pdf()
    
    return pdf_bytes