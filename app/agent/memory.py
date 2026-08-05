from collections import defaultdict


Message = dict[str, str]


class ConversationMemory:
    def __init__(self, max_messages: int = 20) -> None:
        self.max_messages = max_messages
        self._messages: dict[str, list[Message]] = defaultdict(list)

    def add_message(self, session_id: str, role: str, content: str) -> None:
        history = self._messages[session_id]
        history.append({"role": role, "content": content})
        if len(history) > self.max_messages:
            self._messages[session_id] = history[-self.max_messages :]

    def get_history(self, session_id: str) -> list[Message]:
        return list(self._messages.get(session_id, []))

    def clear(self) -> None:
        self._messages.clear()


conversation_memory = ConversationMemory()
