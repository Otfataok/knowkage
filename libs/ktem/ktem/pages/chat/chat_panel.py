import gradio as gr
from ktem.app import BasePage
from theflow.settings import settings as flowsettings

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)

if not KH_DEMO_MODE:
    PLACEHOLDER_TEXT = (
        "Это начало нового диалога.\n"
        "Загрузите файл или веб-ссылку. "
        "Вкладка Файлы — для дополнительных опций (например: GraphRAG)."
    )
else:
    PLACEHOLDER_TEXT = (
        "Добро пожаловать в демо Kotaemon. "
        "Начните с просмотра загруженных диалогов.\n"
        "Раздел Подсказки — для дополнительных советов."
    )


class ChatPanel(BasePage):
    def __init__(self, app):
        self._app = app
        self.on_building_ui()

    def on_building_ui(self):
        self.chatbot = gr.Chatbot(
            label=self._app.app_name,
            placeholder=PLACEHOLDER_TEXT,
            show_label=False,
            elem_id="main-chat-bot",
            show_copy_button=True,
            likeable=True,
            bubble_full_width=False,
        )
        with gr.Row():
            self.text_input = gr.MultimodalTextbox(
                interactive=True,
                scale=20,
                file_count="multiple",
                placeholder=(
                    "Введите сообщение, поиск @web или укажите файл @filename"
                ),
                container=False,
                show_label=False,
                elem_id="chat-input",
            )

    def submit_msg(self, chat_input, chat_history):
        """Submit a message to the chatbot"""
        return "", chat_history + [(chat_input, None)]
