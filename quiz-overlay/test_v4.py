from __future__ import annotations

import json
import time
from datetime import datetime, timezone

from common import Question
from quiz_engine_v4 import QuizEngineV4
from soop_client_v4 import SoopChatClientV4


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, text: str) -> None:
        self.sent.append(json.loads(text))

    def close(self) -> None:
        pass


def event(seq: int, uid: str, nickname: str, message: str) -> str:
    return json.dumps({
        "type": "event",
        "seq": seq,
        "currentSeq": seq,
        "event": {
            "type": "CHAT_MESSAGE",
            "user": {"id": uid, "nickname": nickname},
            "message": message,
            "receivedAt": datetime.now(timezone.utc).isoformat(),
        },
    }, ensure_ascii=False)


def main() -> None:
    engine = QuizEngineV4()
    engine.set_questions([
        Question(
            kind="multiple",
            prompt="정답은 2번",
            choices=["1", "2", "3", "4"],
            answer="2",
            duration_sec=30,
            auto_close_time=False,
        )
    ])
    client = SoopChatClientV4(engine)
    fake = FakeWebSocket()
    client._generation = 1
    client.streamer_id = "test_streamer"
    client.ws = fake

    client._on_message(1, fake, json.dumps({"type": "hello", "protocol": 4, "currentSeq": 100}))
    assert fake.sent, "hello must cause subscribe"
    subscribe = fake.sent[-1]
    assert subscribe["action"] == "subscribe"
    assert subscribe["streamers"] == ["test_streamer"]
    assert subscribe["events"] == ["CHAT_MESSAGE"]

    client._on_message(1, fake, json.dumps({"type": "subscribed", "currentSeq": 100}))
    assert client.subscribed and engine.connected
    assert engine.start_recruitment()

    client._on_message(1, fake, event(101, "user1", "고래팬", "!참여"))
    assert "user1" in engine.participants

    client._on_message(1, fake, event(102, "user1", "고래팬", "안녕하세요"))
    feed = engine.participant_chat_feed(20)
    assert any(x["message"] == "안녕하세요" for x in feed), "joined participant normal chat must be tracked"

    client._on_message(1, fake, event(103, "outsider", "비참가", "저도 보여요?"))
    feed = engine.participant_chat_feed(20)
    assert not any(x["userId"] == "outsider" for x in feed), "non-participant chat must never be retained"

    assert engine.close_recruitment()
    assert engine.show_question()
    client._on_message(1, fake, event(104, "user1", "고래팬", "!2"))
    assert not engine.answers, "answer before START must not be accepted"
    assert any(x["seq"] == 104 and x["message"] == "!2" for x in engine.participant_chat_feed(20)), "pre-START participant chat must still be tracked"

    assert engine.open_answers(client.current_seq)
    time.sleep(0.01)
    client._on_message(1, fake, event(105, "user1", "고래팬", "!2"))
    assert engine.answers["user1"].correct
    accepted = [x for x in engine.participant_chat_feed(20) if x["seq"] == 105]
    assert accepted and accepted[0]["isAnswer"] and accepted[0]["accepted"]

    # Duplicate replay must not duplicate either answers or participant chat.
    before = engine.participant_chat_total
    client._on_message(1, fake, event(105, "user1", "고래팬", "!2"))
    assert engine.participant_chat_total == before

    # A gap during answering must close the round for fairness and be visible in diagnostics.
    client._on_message(1, fake, json.dumps({"type": "gap", "fromSeq": 106, "toSeq": 108, "currentSeq": 108}))
    assert engine.state == "QUESTION_CLOSED"
    d = client.diagnostics()
    assert d["protocol"] == 4
    assert d["subscribed"] is True
    assert d["eventCount"] == 6
    assert d["gapCount"] == 1
    assert d["lastEventSeq"] == 105

    # Chat feed is bounded and clearable without touching participant registration.
    engine.clear_participant_chat()
    assert engine.participant_chat_feed(10) == []
    assert "user1" in engine.participants

    print("v0.4 websocket + participant chat tracking tests passed")


if __name__ == "__main__":
    main()
