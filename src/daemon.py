from __future__ import annotations

import json
import random
import time
from datetime import datetime, timezone

from .config import DAEMON_LOG_PATH, SYNC_INTERVAL_SECONDS, ensure_directories
from .executor import Executor
from .listener import EventListener
from .planner import Planner
from .reporter import Reporter


def write_log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    with DAEMON_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


class MockWhatsAppInterface:
    def __init__(self, listener: EventListener):
        self.listener = listener

    def simulate_user_question(self, question: str):
        event = {
            "type": "whatsapp.message.received",
            "payload": {
                "sender": "+905000000000",
                "text": question,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        }
        self.listener.emit("whatsapp.message.received", event)


def run_learning_triggers(executor: Executor, reporter: Reporter, listener: EventListener):
    # Proactive learning check (Apprentice Persona)
    if random.random() < 0.05: # 5% chance per loop for demo/proactive learning
        write_log("learning:trigger:proactive_question")
        # Generate a question based on a random target/category for demonstration
        context = {
            "target": random.choice(["CNC", "Enjeksiyon Kalıbı", "Sac Metal", "Kaynak"]),
            "last_action": "idle_thought",
            "material": random.choice(["Alüminyum", "Çelik", "Plastik"])
        }
        result = executor.execute({
            "action": "generate_learning_question",
            "payload": context
        })
        
        # Report the question as an AI action
        reporter.write("ai.learning.question_generated", result)
        listener.emit("ai.learning.question_generated", result)
        write_log(f"learning:question:{result.get('question')}")

        # Sync to LIVE-CONTEXT for mobile visibility
        executor.execute({
            "action": "sync_context",
            "payload": {
                "key": "last_learning_question",
                "value": result.get("question")
            }
        })


def run_forever() -> None:
    ensure_directories()
    listener = EventListener()
    planner = Planner()
    executor = Executor()
    reporter = Reporter()
    whatsapp = MockWhatsAppInterface(listener)

    last_sync = 0.0
    write_log("daemon:start")

    while True:
        now = time.time()
        
        # Proactive Learning & WhatsApp Simulation (Optional/Demo)
        run_learning_triggers(executor, reporter, listener)

        if now - last_sync >= SYNC_INTERVAL_SECONDS:
            result = executor.execute({"action": "periodic_sync", "reason": "timer"})
            reporter.write("ai.memory.synced", result)
            listener.emit("ai.memory.synced", result)
            write_log(f"periodic_sync:{json.dumps(result, ensure_ascii=True)}")
            last_sync = now

        for message_id, fields in listener.poll():
            actions = planner.plan(fields)
            if not actions:
                # Handle WhatsApp specifically if planner doesn't catch it yet
                try:
                    envelope = json.loads(fields.get("payload", "{}"))
                    if envelope.get("type") == "whatsapp.message.received":
                        text = envelope["payload"]["text"]
                        write_log(f"whatsapp:received:{text}")
                        
                        # 1. Sync WhatsApp message to context
                        executor.execute({
                            "action": "sync_context",
                            "payload": {
                                "key": "last_whatsapp_msg",
                                "value": text
                            }
                        })
                        
                        # 2. Intelligent Response (Apprentice/Learning)
                        # Query memory for any relevant context
                        query_result = executor.execute({
                            "action": "query_memory",
                            "payload": {"query": text, "top_k": 2}
                        })
                        
                        # 3. Proactive Learning Question based on input
                        learn_context = {
                            "target": text[:15], # Use start of message as potential target
                            "last_action": "whatsapp_interaction"
                        }
                        question_result = executor.execute({
                            "action": "generate_learning_question",
                            "payload": learn_context
                        })
                        
                        # 4. Report and Emit Response
                        response_payload = {
                            "analysis": query_result.get("results"),
                            "question": question_result.get("question"),
                            "status": "processed_by_apprentice"
                        }
                        reporter.write("whatsapp.ai.response", response_payload)
                        listener.emit("whatsapp.ai.response", response_payload)
                        write_log(f"whatsapp:ai_response_generated:{question_result.get('question')}")
                except Exception:
                    pass
                listener.ack(message_id)
                continue
            for action in actions:
                result = executor.execute(action)
                event_type = "ai.memory.query.completed" if action["action"] == "query_memory" else "ai.memory.synced"
                reporter.write(event_type, result)
                listener.emit(event_type, result)
                write_log(f"event:{message_id}:{json.dumps(result, ensure_ascii=True)}")
            listener.ack(message_id)


if __name__ == "__main__":
    run_forever()
