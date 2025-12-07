import logging
import os
from copy import deepcopy

import gradio as gr
from ktem.app import BasePage
from ktem.db.models import Conversation, User, engine
from sqlmodel import Session, or_, select

import flowsettings

from ...utils.conversation import sync_retrieval_n_message
from .chat_suggestion import ChatSuggestion
from .common import STATE

logger = logging.getLogger(__name__)

KH_DEMO_MODE = getattr(flowsettings, "KH_DEMO_MODE", False)
KH_SSO_ENABLED = getattr(flowsettings, "KH_SSO_ENABLED", False)


logout_js = """
function () {
    removeFromStorage('google_api_key');
    window.location.href = "/logout";
}
"""


def is_conv_name_valid(name):
    """Check if the conversation name is valid"""
    errors = []
    if len(name) == 0:
        errors.append("Название не может быть пустым")
    elif len(name) > 40:
        errors.append("Название не может быть длиннее 40 символов")

    return "; ".join(errors)


class ConversationControl(BasePage):
    """Manage conversation"""

    def __init__(self, app):
        self._app = app
        self.logout_js = logout_js
        self.on_building_ui()

    def on_building_ui(self):
        with gr.Row():
            title_text = "Диалоги" if not KH_DEMO_MODE else "Kotaemon Papers"
            gr.Markdown("## {}".format(title_text))
            self.btn_toggle_dark_mode = gr.Button(
                value="🌙",
                scale=1,
                size="sm",
                elem_classes=["no-background", "body-text-color"],
                elem_id="toggle-dark-button",
            )
            self.btn_chat_expand = gr.Button(
                value="⛶",
                scale=1,
                size="sm",
                elem_classes=["no-background", "body-text-color"],
                elem_id="chat-expand-button",
            )
            self.btn_info_expand = gr.Button(
                value="⛶",
                min_width=2,
                scale=1,
                size="sm",
                elem_classes=["no-background", "body-text-color"],
                elem_id="info-expand-button",
            )

            self.btn_toggle_dark_mode.click(
                None,
                js="""
                () => {
                    document.body.classList.toggle('dark');
                }
                """,
            )

        self.conversation_id = gr.State(value="")
        self.conversation = gr.Dropdown(
            label="Выберите диалог",
            choices=[],
            container=False,
            filterable=True,
            interactive=True,
            elem_classes=["unset-overflow"],
            elem_id="conversation-dropdown",
        )

        with gr.Row() as self._new_delete:
            self.cb_suggest_chat = gr.Checkbox(
                value=False,
                label="Предложить вопросы",
                min_width=10,
                scale=6,
                elem_id="suggest-chat-checkbox",
                container=False,
                visible=not KH_DEMO_MODE,
            )
            self.cb_is_public = gr.Checkbox(
                value=False,
                label="Поделиться диалогом",
                elem_id="is-public-checkbox",
                container=False,
                visible=not KH_DEMO_MODE and not KH_SSO_ENABLED,
            )

            if not KH_DEMO_MODE:
                self.btn_conversation_rn = gr.Button(
                    value="✏️",
                    min_width=2,
                    scale=1,
                    size="sm",
                    elem_classes=["no-background", "body-text-color"],
                )
                self.btn_del = gr.Button(
                    value="🗑️",
                    min_width=2,
                    scale=1,
                    size="sm",
                    elem_classes=["no-background", "body-text-color"],
                )
                self.btn_new = gr.Button(
                    value="➕",
                    min_width=2,
                    scale=1,
                    size="sm",
                    elem_classes=["no-background", "body-text-color"],
                    elem_id="new-conv-button",
                )
            else:
                self.btn_new = gr.Button(
                    value="Новый чат",
                    min_width=120,
                    size="sm",
                    scale=1,
                    variant="primary",
                    elem_id="new-conv-button",
                    visible=False,
                )

        if KH_DEMO_MODE:
            with gr.Row():
                self.btn_demo_login = gr.Button(
                    "Войдите для нового чата",
                    min_width=120,
                    size="sm",
                    scale=1,
                    variant="primary",
                )
                _js_redirect = """
                () => {
                    url = '/login' + window.location.search;
                    window.open(url, '_blank');
                }
                """
                self.btn_demo_login.click(None, js=_js_redirect)

                self.btn_demo_logout = gr.Button(
                    "Выйти",
                    min_width=120,
                    size="sm",
                    scale=1,
                    visible=False,
                )

        with gr.Row(visible=False) as self._delete_confirm:
            self.btn_del_conf = gr.Button(
                value="Удалить",
                variant="stop",
                min_width=10,
            )
            self.btn_del_cnl = gr.Button(value="Отмена", min_width=10)

        with gr.Row():
            self.conversation_rn = gr.Text(
                label="(Enter) сохранить",
                placeholder="Название диалога",
                container=True,
                scale=5,
                min_width=10,
                interactive=True,
                visible=False,
            )

    def load_chat_history(self, user_id):
        """Reload chat history"""

        can_see_public: bool = False
        with Session(engine) as session:
            statement = select(User).where(User.id == user_id)
            result = session.exec(statement).one_or_none()

            if result is not None:
                if flowsettings.KH_USER_CAN_SEE_PUBLIC:
                    can_see_public = (
                        result.username == flowsettings.KH_USER_CAN_SEE_PUBLIC
                    )
                else:
                    can_see_public = True

        print(f"User-id: {user_id}, can see public conversations: {can_see_public}")

        options = []
        with Session(engine) as session:
            if can_see_public:
                statement = (
                    select(Conversation)
                    .where(
                        or_(
                            Conversation.user == user_id,
                            Conversation.is_public,
                        )
                    )
                    .order_by(
                        Conversation.is_public.desc(), Conversation.date_created.desc()
                    )
                )
            else:
                statement = (
                    select(Conversation)
                    .where(Conversation.user == user_id)
                    .order_by(Conversation.date_created.desc())
                )

            results = session.exec(statement).all()
            for result in results:
                options.append((result.name, result.id))

        return options

    def reload_conv(self, user_id):
        conv_list = self.load_chat_history(user_id)
        if conv_list:
            return gr.update(value=None, choices=conv_list)
        else:
            return gr.update(value=None, choices=[])

    def new_conv(self, user_id):
        """Create new chat"""
        if user_id is None:
            gr.Warning("Сначала войдите (Настройки → Пользователь)")
            return None, gr.update()
        with Session(engine) as session:
            new_conv = Conversation(user=user_id)
            session.add(new_conv)
            session.commit()

            id_ = new_conv.id

        history = self.load_chat_history(user_id)

        return id_, gr.update(value=id_, choices=history)

    def delete_conv(self, conversation_id, user_id):
        """Delete the selected conversation"""
        if not conversation_id:
            gr.Warning("Диалог не выбран")
            return None, gr.update()

        if user_id is None:
            gr.Warning("Сначала войдите (Настройки → Пользователь)")
            return None, gr.update()

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            result = session.exec(statement).one()

            session.delete(result)
            session.commit()

        history = self.load_chat_history(user_id)
        if history:
            id_ = history[0][1]
            return id_, gr.update(value=id_, choices=history)
        else:
            return None, gr.update(value=None, choices=[])

    def select_conv(self, conversation_id, user_id):
        """Select the conversation"""
        default_chat_suggestions = [[each] for each in ChatSuggestion.CHAT_SAMPLES]

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            try:
                result = session.exec(statement).one()
                id_ = result.id
                name = result.name
                is_conv_public = result.is_public

                if user_id == result.user:
                    selected = result.data_source.get("selected", {})
                else:
                    selected = {}

                chats = result.data_source.get("messages", [])
                chat_suggestions = result.data_source.get(
                    "chat_suggestions", default_chat_suggestions
                )

                retrieval_history: list[str] = result.data_source.get(
                    "retrieval_messages", []
                )
                plot_history: list[dict] = result.data_source.get("plot_history", [])

                retrieval_history = sync_retrieval_n_message(chats, retrieval_history)

                info_panel = (
                    retrieval_history[-1]
                    if retrieval_history
                    else "<h5><b>Информация не найдена</b></h5>"
                )
                plot_data = plot_history[-1] if plot_history else None
                state = result.data_source.get("state", STATE)

            except Exception as e:
                logger.warning(e)
                id_ = ""
                name = ""
                selected = {}
                chats = []
                chat_suggestions = default_chat_suggestions
                retrieval_history = []
                plot_history = []
                info_panel = ""
                plot_data = None
                state = STATE
                is_conv_public = False

        indices = []
        for index in self._app.index_manager.indices:
            if index.selector is None:
                continue
            if isinstance(index.selector, int):
                indices.append(selected.get(str(index.id), index.default_selector))
            if isinstance(index.selector, tuple):
                indices.extend(selected.get(str(index.id), index.default_selector))

        return (
            id_,
            id_,
            name,
            chats,
            chat_suggestions,
            info_panel,
            plot_data,
            retrieval_history,
            plot_history,
            is_conv_public,
            state,
            *indices,
        )

    def rename_conv(self, conversation_id, new_name, is_renamed, user_id):
        """Rename the conversation"""
        if not is_renamed or KH_DEMO_MODE or user_id is None or not conversation_id:
            return (
                gr.update(),
                conversation_id,
                gr.update(visible=False),
            )

        errors = is_conv_name_valid(new_name)
        if errors:
            gr.Warning(errors)
            return (
                gr.update(),
                conversation_id,
                gr.update(visible=False),
            )

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            result = session.exec(statement).one()
            result.name = new_name
            session.add(result)
            session.commit()

        history = self.load_chat_history(user_id)
        gr.Info("Диалог переименован")
        return (
            gr.update(choices=history),
            conversation_id,
            gr.update(visible=False),
        )

    def persist_chat_suggestions(
        self, conversation_id, new_suggestions, is_updated, user_id
    ):
        """Update the conversation's chat suggestions"""
        if not is_updated:
            return

        if user_id is None:
            gr.Warning("Сначала войдите (Настройки → Пользователь)")
            return gr.update(), ""

        if not conversation_id:
            gr.Warning("Диалог не выбран")
            return gr.update(), ""

        with Session(engine) as session:
            statement = select(Conversation).where(Conversation.id == conversation_id)
            result = session.exec(statement).one()

            data_source = deepcopy(result.data_source)
            data_source["chat_suggestions"] = [
                [x] for x in new_suggestions.iloc[:, 0].tolist()
            ]

            result.data_source = data_source
            session.add(result)
            session.commit()

        gr.Info("Подсказки обновлены")

    def toggle_demo_login_visibility(self, user_api_key, request: gr.Request):
        try:
            import gradiologin as grlogin

            user = grlogin.get_user(request)
        except (ImportError, AssertionError):
            user = None

        if user:
            return [
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=False),
            ]
        else:
            return [
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=True),
            ]

    def _on_app_created(self):
        """Reload the conversation once the app is created"""
        self._app.app.load(
            self.reload_conv,
            inputs=[self._app.user_id],
            outputs=[self.conversation],
        )
