from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from dotenv import load_dotenv
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
#from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from typing import List, Any, Optional, Dict
from pydantic import BaseModel, Field
from sidekick_tools import playwright_tools, other_tools
import uuid
import asyncio
from datetime import datetime
import sqlite3
import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver

# Cargar variables de entorno
load_dotenv(override=True)

# Definición del estado del grafo
class State(TypedDict):
    messages: Annotated[List[Any], add_messages]   # Lista de mensajes que se va actualizando
    success_criteria: str                          # Criterio de éxito
    feedback_on_work: Optional[str]                # Feedback sobre el trabajo anterior
    success_criteria_met: bool                     # Indica si el criterio de éxito se ha cumplido
    user_input_needed: bool                        # Indica si se necesita más input del usuario

# Clase para salida estructurada del evaluador
class EvaluatorOutput(BaseModel):
    feedback: str = Field(description="Feedback on the assistant's response")
    success_criteria_met: bool = Field(description="Whether the success criteria have been met")
    user_input_needed: bool = Field(description="True if more input is needed from the user, or clarifications, or the assistant is stuck")

# Clase principal del asistente inteligente
class Sidekick:
    def __init__(self, thread_id: str = "default"):
        self.worker_llm_with_tools = None
        self.evaluator_llm_with_output = None
        self.tools = None
        self.llm_with_tools = None
        self.graph = None
        #self.sidekick_id = str(uuid.uuid4())
        self.sidekick_id = thread_id  # se controla desde app.py
        #self.memory = MemorySaver()
        self.memory = None

        self.browser = None
        self.playwright = None


    async def setup(self):
        # Inicializar herramientas y navegador
        self.tools, self.browser, self.playwright = await playwright_tools()
        self.tools += await other_tools()
        
        # Configurar LLM para el worker
        worker_llm = ChatOpenAI(model="gpt-4o-mini")
        self.worker_llm_with_tools = worker_llm.bind_tools(self.tools)
        
        # Configurar LLM para el evaluador
        evaluator_llm = ChatOpenAI(model="gpt-4o-mini")
        self.evaluator_llm_with_output = evaluator_llm.with_structured_output(EvaluatorOutput)
        
        # Inicializar memoria persistente
        db_path = "sidekick_memory.db"
        conn = await aiosqlite.connect(db_path)
        self.memory = AsyncSqliteSaver(conn)

        # Construir el grafo
        await self.build_graph()

    # Worker: Realiza tareas y usa herramientas
    def worker(self, state: State) -> Dict[str, Any]:
        # Define comportamiento del asistente con herramientas
        system_message = f"""You are a helpful assistant that can use tools to complete tasks.
    You keep working on a task until either you have a question or clarification for the user, or the success criteria is met.
    You have many tools to help you, including tools to browse the internet, navigating and retrieving web pages.
    You have a tool to run python code, but note that you would need to include a print() statement if you wanted to receive output.
    The current date and time is {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    This is the success criteria:
    {state['success_criteria']}
    You should reply either with a question for the user about this assignment, or with your final response.
    If you have a question for the user, you need to reply by clearly stating your question. An example might be:

    Question: please clarify whether you want a summary or a detailed answer

    If you've finished, reply with the final answer, and don't ask a question; simply reply with the answer.
    """
        
        # Si hay feedback sobre el trabajo anterior, añadirlo al sistema
        if state.get("feedback_on_work"):
            system_message += f"""
    Previously you thought you completed the assignment, but your reply was rejected because the success criteria was not met.
    Here is the feedback on why this was rejected:
    {state['feedback_on_work']}
    With this feedback, please continue the assignment, ensuring that you meet the success criteria or have a question for the user."""
        
        # Añadir en el mensaje de sistema
        found_system_message = False
        messages = state["messages"]
        for message in messages:
            if isinstance(message, SystemMessage):
                message.content = system_message
                found_system_message = True
        
        # Si no se encontró un mensaje de sistema, añadir uno nuevo
        if not found_system_message:
            messages = [SystemMessage(content=system_message)] + messages
        
        # Invocar el LLM con herramientas
        response = self.worker_llm_with_tools.invoke(messages)
        
        # Devolver el estado actualizado
        return {
            "messages": [response],
        }


    def worker_router(self, state: State) -> str:
        last_message = state["messages"][-1]
        
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"
        else:
            return "evaluator"
        
    # Formato de la conversación
    def format_conversation(self, messages: List[Any]) -> str:
        conversation = "Conversation history:\n\n"
        for message in messages:
            if isinstance(message, HumanMessage):
                conversation += f"User: {message.content}\n"
            elif isinstance(message, AIMessage):
                text = message.content or "[Tools use]"
                conversation += f"Assistant: {text}\n"
        return conversation
        
    # Evaluador: Determina si el trabajo se ha completado correctamente
    def evaluator(self, state: State) -> State:
        last_response = state["messages"][-1].content

        # Mensaje de sistema para el evaluador
        system_message = f"""You are an evaluator that determines if a task has been completed successfully by an Assistant.
    Assess the Assistant's last response based on the given criteria. Respond with your feedback, and with your decision on whether the success criteria has been met,
    and whether more input is needed from the user."""
        
        # Mensaje de usuario para el evaluador
        user_message = f"""You are evaluating a conversation between the User and Assistant. You decide what action to take based on the last response from the Assistant.

    The entire conversation with the assistant, with the user's original request and all replies, is:
    {self.format_conversation(state['messages'])}

    The success criteria for this assignment is:
    {state['success_criteria']}

    And the final response from the Assistant that you are evaluating is:
    {last_response}

    Respond with your feedback, and decide if the success criteria is met by this response.
    Also, decide if more user input is required, either because the assistant has a question, needs clarification, or seems to be stuck and unable to answer without help.

    The Assistant has access to a tool to write files. If the Assistant says they have written a file, then you can assume they have done so.
    Overall you should give the Assistant the benefit of the doubt if they say they've done something. But you should reject if you feel that more work should go into this.

    """
        
        # Si hay feedback sobre el trabajo anterior, añadirlo al mensaje de usuario
        if state["feedback_on_work"]:
            user_message += f"Also, note that in a prior attempt from the Assistant, you provided this feedback: {state['feedback_on_work']}\n"
            user_message += "If you're seeing the Assistant repeating the same mistakes, then consider responding that user input is required."
        
        # Crear lista de mensajes para el evaluador
        evaluator_messages = [SystemMessage(content=system_message), HumanMessage(content=user_message)]

        # Invocar el evaluador con el mensaje de usuario
        eval_result = self.evaluator_llm_with_output.invoke(evaluator_messages)
        
        # Actualizar el estado con el resultado del evaluador
        new_state = {
            "messages": [{"role": "assistant", "content": f"Evaluator Feedback on this answer: {eval_result.feedback}"}],
            "feedback_on_work": eval_result.feedback,
            "success_criteria_met": eval_result.success_criteria_met,
            "user_input_needed": eval_result.user_input_needed
        }
        return new_state

    # Ruta basada en la evaluación
    def route_based_on_evaluation(self, state: State) -> str:
        if state["success_criteria_met"] or state["user_input_needed"]:
            return "END"
        else:
            return "worker"

    # Construir el grafo
    async def build_graph(self):
        # Configurar el constructor de gráficos con el estado
        graph_builder = StateGraph(State)

        # Añadir nodos
        graph_builder.add_node("worker", self.worker)
        graph_builder.add_node("tools", ToolNode(tools=self.tools))
        graph_builder.add_node("evaluator", self.evaluator)

        # Añadir aristas
        graph_builder.add_conditional_edges("worker", self.worker_router, {"tools": "tools", "evaluator": "evaluator"})
        graph_builder.add_edge("tools", "worker")
        graph_builder.add_conditional_edges("evaluator", self.route_based_on_evaluation, {"worker": "worker", "END": END})
        graph_builder.add_edge(START, "worker")

        # Compilar el grafo
        self.graph = graph_builder.compile(checkpointer=self.memory)

    # Ejecutar superstep
    async def run_superstep(self, message, success_criteria, history):
        config = {"configurable": {"thread_id": self.sidekick_id}}

        state = {
            "messages": message,
            "success_criteria": success_criteria or "The answer should be clear and accurate",
            "feedback_on_work": None,
            "success_criteria_met": False,
            "user_input_needed": False
        }
        result = await self.graph.ainvoke(state, config=config)
        user = {"role": "user", "content": message}
        reply = {"role": "assistant", "content": result["messages"][-2].content}
        feedback = {"role": "assistant", "content": result["messages"][-1].content}
        return history + [user, reply, feedback]
    
    # Limpiar recursos
    def cleanup(self):
        if self.browser:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.browser.close())
                if self.playwright:
                    loop.create_task(self.playwright.stop())
            except RuntimeError:
                # If no loop is running, do a direct run
                asyncio.run(self.browser.close())
                if self.playwright:
                    asyncio.run(self.playwright.stop())
