import gradio as gr
from sidekick import Sidekick
import uuid


# Setup thread_id dinámico
async def setup(thread_id):
    sidekick = Sidekick(thread_id=thread_id)
    await sidekick.setup()
    return sidekick

# Procesamiento del mensaje
async def process_message(sidekick, message, success_criteria, history):
    results = await sidekick.run_superstep(message, success_criteria, history)
    return results, sidekick
    
# Reset reinicia manteniendo thread_id
async def reset(thread_id):
    new_sidekick = Sidekick(thread_id=thread_id)
    await new_sidekick.setup()
    return "", "", None, new_sidekick

# Limpieza de recursos
def free_resources(sidekick):
    print("Cleaning up")
    try:
        if sidekick:
            sidekick.free_resources()
    except Exception as e:
        print(f"Exception during cleanup: {e}")


# Generar un ID único para la sesión
session_id = str(uuid.uuid4())

# Interfaz gráfica con Gradio
with gr.Blocks(title="Sidekick", theme=gr.themes.Default(primary_hue="emerald")) as ui:
    gr.Markdown("## Sidekick Personal Co-Worker")
    sidekick = gr.State(delete_callback=free_resources)

    with gr.Row():
        thread_id_input = gr.Textbox(
            label="Nombre de sesión", 
            placeholder="Por ejemplo: omar-session", 
            value="session_id")

    with gr.Row():
        chatbot = gr.Chatbot(label="Sidekick", height=300, type="messages")

    with gr.Group():
        with gr.Row():
            message = gr.Textbox(show_label=False, placeholder="Your request to the Sidekick")
        with gr.Row():
            success_criteria = gr.Textbox(show_label=False, placeholder="What are your success critiera?")

    with gr.Row():
        reset_button = gr.Button("Reset", variant="stop")
        go_button = gr.Button("Go!", variant="primary")
        
    # Se pasa thread_id a setup y reset
    ui.load(setup, [thread_id_input], [sidekick])
    message.submit(process_message, [sidekick, message, success_criteria, chatbot], [chatbot, sidekick])
    success_criteria.submit(process_message, [sidekick, message, success_criteria, chatbot], [chatbot, sidekick])
    go_button.click(process_message, [sidekick, message, success_criteria, chatbot], [chatbot, sidekick])
    reset_button.click(reset, [thread_id_input], [message, success_criteria, chatbot, sidekick])

    
ui.launch(inbrowser=True)