from playwright.async_api import async_playwright                          # Importa la API asíncrona de Playwright para automatizar navegadores
from langchain_community.agent_toolkits import PlayWrightBrowserToolkit    # Toolkit de LangChain para integrar Playwright como herramienta del agente
from dotenv import load_dotenv                                             # Para cargar variables de entorno desde un archivo .env
import os                                                                  # Módulo estándar de Python para acceder a variables del sistema
import requests                                                            # Librería para hacer peticiones HTTP, usada aquí para enviar notificaciones
from langchain.agents import Tool                                          # Clase base de herramientas en LangChain (para registrar herramientas personalizadas)
from langchain_community.agent_toolkits import FileManagementToolkit       # Toolkit de LangChain para manejo de archivos en el sistema de archivos
from langchain_community.tools.wikipedia.tool import WikipediaQueryRun     # Herramienta de consulta de Wikipedia integrada en LangChain
from langchain_experimental.tools import PythonREPLTool                    # Herramienta que permite ejecutar código Python directamente en tiempo de ejecución
from langchain_community.utilities import GoogleSerperAPIWrapper           # Wrapper que permite hacer búsquedas usando la API de Serper (Google Search)
from langchain_community.utilities.wikipedia import WikipediaAPIWrapper    # API Wrapper de Wikipedia usado internamente por WikipediaQueryRun


# Cargo las variables del archivo .env, sobrescribiendo si ya existían
load_dotenv(override=True)

# Obtengo credenciales para Pushover desde variables de entorno
pushover_token = os.getenv("PUSHOVER_TOKEN")
pushover_user = os.getenv("PUSHOVER_USER")
pushover_url = "https://api.pushover.net/1/messages.json"

# Inicializo el wrapper de Google Serper para búsquedas web
serper = GoogleSerperAPIWrapper()

# Defino la función asíncrona para obtener herramientas de Playwright
async def playwright_tools():
    # Inicio el navegador de Playwright
    playwright = await async_playwright().start()

    # Lanzo una instancia de Chromium (modo visible: headless=False)
    browser = await playwright.chromium.launch(headless=False)

    # Creo un toolkit de Playwright para usar en el agente
    toolkit = PlayWrightBrowserToolkit.from_browser(async_browser=browser)

    # Devuelvo las herramientas, el navegador y la instancia de Playwright
    return toolkit.get_tools(), browser, playwright


# Función que envía una notificación push al usuario usando la API de Pushover
def push(text: str):
    """Send a push notification to the user"""
    requests.post(pushover_url, data = {"token": pushover_token, "user": pushover_user, "message": text})
    return "success"

# Inicializa herramientas de manejo de archivos dentro de la carpeta "sandbox"
def get_file_tools():
    toolkit = FileManagementToolkit(root_dir="sandbox")
    return toolkit.get_tools()

# Define otras herramientas personalizadas para ser utilizadas por el agente
async def other_tools():
    # Herramienta para enviar notificaciones push
    push_tool = Tool(name="send_push_notification", func=push, description="Use this tool when you want to send a push notification")

    # Herramientas de manejo de archivos
    file_tools = get_file_tools()

    # Herramienta para hacer búsquedas web
    tool_search =Tool(
        name="search",
        func=serper.run,
        description="Use this tool when you want to get the results of an online web search"
    )

    # Inicializo wrapper de Wikipedia y crea la herramienta de consulta
    wikipedia = WikipediaAPIWrapper()
    wiki_tool = WikipediaQueryRun(api_wrapper=wikipedia)

    # Herramienta para ejecutar código Python dinámicamente
    python_repl = PythonREPLTool()
    
    # Devuelvo una lista con todas las herramientas disponibles
    return file_tools + [push_tool, tool_search, python_repl,  wiki_tool]

