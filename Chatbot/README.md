# Link del video de presentación y demo

https://www.loom.com/share/046fe288d2804bc8996892d9972a107b?sid=030773b3-5761-4238-9514-2e564a4b404b

# Objetivo

Desarrollar un chatbot inteligente que:
- Mantenga un historial de conversación y un sistema de **memoria a largo plazo persistente**, permitiendo recordar interacciones pasadas incluso entre sesiones.
- Desarrolle una **personalidad consistente** a lo largo del tiempo, ofreciendo respuestas coherentes con su rol.
- Se **adapte al usuario**, ajustando su comportamiento con base en el contexto y las necesidades detectadas.
- Implemente manejo de **contexto conversacional**, asegurando fluidez y coherencia temática en las respuestas.
- Aplique herramientas como navegación web, ejecución de código, búsqueda y Wikipedia.
- Evalúe si ha cumplido correctamente con los **criterios de éxito** definidos para cada tarea.
- Solicite retroalimentación o más información cuando sea necesario, para mejorar sus respuestas.

Este proyecto combina agentes LLM con herramientas externas para lograr una interacción personalizada, contextual y útil.

---

# Cumplimiento de Objetivos

A continuación, se detalla cómo se cumple cada uno de los objetivos planteados:

- **Memoria a largo plazo persistente**  
  Se utiliza `AsyncSqliteSaver` (no `MemorySaver`) como backend de almacenamiento, mediante una base SQLite (`sidekick_memory.db`). Esto permite conservar el historial de conversación, retroalimentación y criterios incluso después de cerrar el programa, logrando una verdadera persistencia entre sesiones. La clave de la sesión (`thread_id`) es configurable y determina qué historial se conserva o reutiliza.

- **Personalidad consistente**  
  En cada paso del grafo se incluye un `SystemMessage` con instrucciones claras sobre el rol del asistente, su comportamiento esperado y su forma de comunicarse, asegurando una respuesta coherente a lo largo del tiempo.

- **Adaptación al usuario**  
  El agente evalúa sus respuestas con base en criterios de éxito proporcionados por el usuario y ajusta su comportamiento si recibe retroalimentación, usando el campo `feedback_on_work` para mejorar iterativamente.

- **Manejo de contexto conversacional**  
  El historial completo de la conversación (`messages`) se mantiene entre pasos, y es utilizado tanto por el asistente como por el evaluador LLM para comprender el contexto completo antes de generar nuevas respuestas.

- **Uso de herramientas externas**  
  Se integran múltiples herramientas mediante `ToolNode`, como `PythonREPLTool`, `PlayWrightBrowserToolkit`, `WikipediaQueryRun`, `GoogleSerperAPIWrapper`, `FileManagementToolkit`, y `Pushover`, habilitando capacidades extendidas como búsquedas, ejecución de código, navegación y envío de notificaciones.

- **Evaluación de criterios de éxito**  
  Un segundo agente (`evaluator_llm_with_output`) evalúa si la respuesta cumple con los criterios proporcionados por el usuario y devuelve retroalimentación estructurada mediante un modelo `pydantic`.

- **Solicitud de retroalimentación o aclaración**  
  Si la evaluación detecta que el criterio no se ha cumplido o se requiere más información, se indica al asistente que continúe con una nueva interacción, formulando una pregunta o corrigiendo su respuesta.

Este flujo iterativo, evaluado automáticamente y guiado por criterios explícitos, permite que el chatbot evolucione hacia respuestas útiles, relevantes y personalizadas.

---

# Arquitectura General

- **LLM principal (`worker`)**: Procesa las tareas del usuario y usa herramientas si es necesario.
- **Herramientas (`tools`)**: Navegador (Playwright), Wikipedia, Python REPL, búsqueda con Serper, sistema de notificaciones y manejo de archivos.
- **Evaluador (`evaluator`)**: Determina si la tarea fue completada exitosamente.
- **Grafo LangGraph**: Define el flujo condicional de nodos en función de la evaluación.
- **Memoria persistente (`SqliteSaver`)**: Guarda estados de conversación en una base SQLite para mantener el contexto entre sesiones.


## Documentación de la arquitectura de memoria (Entregable 2)
Se implementa una memoria a largo plazo con `AsyncSqliteSaver` de `langgraph.checkpoint.sqlite.aio`, conectando a una base de datos SQLite (`sidekick_memory.db`). Esta arquitectura permite:

- Guardar cada estado de la conversación, incluyendo mensajes del usuario, del asistente y del evaluador.
- Recordar retroalimentación y criterios de éxito entre interacciones.
- Continuar conversaciones previas sin perder contexto ni consistencia.
- Garantizar persistencia del historial de interacción incluso si el sistema se reinicia.

Cada sesión se identifica mediante un `thread_id`, configurable desde la interfaz de usuario.

---

# `Sidekick` (Clase principal)

| Método                       | Descripción                                                                 |
|-----------------------------|-----------------------------------------------------------------------------|
| `setup()`                   | Inicializa herramientas, modelos y compila el grafo.                        |
| `worker()`                  | Ejecuta la tarea solicitada usando el modelo + herramientas.                |
| `worker_router()`           | Decide si continuar usando herramientas o ir al evaluador.                  |
| `evaluator()`               | Evalúa si el criterio de éxito ha sido cumplido.                            |
| `route_based_on_evaluation()` | Decide si se finaliza, repite o se pide entrada al usuario.                |
| `build_graph()`             | Define el flujo entre nodos usando LangGraph.                               |
| `run_superstep()`           | Ejecuta una interacción completa del grafo.                                 |
| `cleanup()`                 | Cierra instancias de navegador Playwright activas.                          |

---

# Herramientas Integradas

- `PythonREPLTool`: Ejecuta código Python.
- `PlayWrightBrowserToolkit`: Navegación web (headful mode).
- `FileManagementToolkit`: Operaciones seguras sobre archivos (lectura/escritura).
- `WikipediaQueryRun`: Consulta Wikipedia.
- `GoogleSerperAPIWrapper`: Realiza búsquedas web.
- `Pushover`: Envía notificaciones push.

---

# Flujo de Trabajo

1. El usuario inicia una conversación con un criterio de éxito.
2. El agente analiza el mensaje y responde.
3. Si usa herramientas, se ejecutan automáticamente.
4. Un evaluador LLM analiza si la respuesta cumple el criterio:
   - Si cumple: finaliza.
   - Si falla: el agente intenta corregirlo.
   - Si necesita ayuda: solicita más información al usuario.
5. Todo el estado se conserva en **memoria persistente** (`SQLite`) incluyendo conversación, feedback, criterios y decisiones.

---

# Consideraciones

- Asegúrate de correr `playwright install` si ves errores al lanzar el navegador.
- El sistema usa variables de entorno `.env` para servicios como Pushover.
- Si ejecutas múltiples agentes, recuerda cerrar el navegador con `cleanup()`.
- - El historial de interacción y evaluación se almacena en la base de datos `sidekick_memory.db` para continuidad entre sesiones.

---

# Requisitos

- Python 3.10+
- LangGraph
- LangChain + LangChain Community
- Playwright
- Pydantic
- OpenAI (ChatOpenAI)
- Pushover
- dotenv
- asyncio
- aiosqlite

---

# ¿Cómo ejecutar la aplicación?

## 1. Clona el repositorio y entra al proyecto

```bash
git clone git@github.com:OmarGarciaFlores/Chatbot-con-Memoria-y-Personalidad.git
cd tu_repo
```

## 2. Crea entorno virtual e instala dependencias

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

## 3. Instala navegadores de Playwright

```bash
playwright install
```

## 4. Crea archivo .env con tus claves 

```env
PUSHOVER_TOKEN=...
PUSHOVER_USER=...
OPENAI_API_KEY=...
```

## 5. Ejecuta la aplicación

```bash
uv run app.py
```


## Ejemplos de conversaciones extendidas (Entregable 3)

### Iteración con retroalimentación

**Introductoria:**
¿Qué es una red neuronal artificial?
¿Para qué sirve una red neuronal?

**Intermedia:**
- ¿Cómo aprende una red neuronal?
- ¿Qué es la backpropagation?

**Avanzada:**
- Dame el bloque de código para una red neuronal sencilla

---

##  Evaluación de consistencia (Entregable 4)

La consistencia del chatbot se asegura mediante:

- Instrucciones persistentes en `SystemMessage` que definen el comportamiento del asistente.
- Evaluación posterior a cada respuesta por un modelo independiente (`evaluator_llm_with_output`) que verifica:
  - Si la respuesta es coherente con el historial.
  - Si cumple con el criterio de éxito.
  - Si se requiere o no interacción adicional con el usuario.
- En caso de error o retroalimentación, el asistente ajusta su comportamiento, evitando repetir errores y manteniendo una línea narrativa uniforme.

**Resultado:** Respuestas consistentes, progresivamente mejoradas, y adaptadas a criterios dinámicos de éxito.
