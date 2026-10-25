"""Operator: a plain-English instruction -> a real, visible browser that does it for you."""
import asyncio, inspect, os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from browser_use import ActionResult, Agent, Browser

try:
    from browser_use import Tools
except ImportError:  # older browser-use releases
    from browser_use import Controller as Tools

load_dotenv()
ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Operator")

RULES = """You operate a real browser for a human who is watching live.
1. Work step by step using the visible UI and keep going until the task is done.
2. NEVER complete a purchase, enter payment details, or submit a final order. Stop on the checkout page and report.
3. Before any irreversible or account-affecting action (logging in, sending, posting, deleting, booking), call ask_human and wait for the answer.
4. If you hit a CAPTCHA or 2FA, call ask_human so the human can solve it in the browser window.
5. Finish with a short summary: what you did, what you chose and why, with prices and links."""


def make_llm():
    p, model = os.getenv("LLM_PROVIDER", "openai").lower(), os.getenv("MODEL") or None
    if p == "gemini":
        from browser_use import ChatGoogle
        return ChatGoogle(model=model or "gemini-2.5-flash")
    if p == "anthropic":
        from browser_use import ChatAnthropic
        return ChatAnthropic(model=model or "claude-sonnet-4-5")
    from browser_use import ChatOpenAI
    return ChatOpenAI(model=model or "gpt-4.1")


_browser = None
def get_browser():
    """One persistent window: carts and logins survive between tasks, and it stays open at the end."""
    global _browser
    if _browser is None:
        try:
            _browser = Browser(headless=False, keep_alive=True, user_data_dir=str(ROOT / "data" / "profile"))
        except TypeError:
            _browser = Browser(headless=False)
    return _browser


class Session:
    def __init__(self, ws: WebSocket):
        self.ws, self.agent, self.job, self.answer = ws, None, None, None

    async def send(self, kind, **data):
        try:
            await self.ws.send_json({"type": kind, **data})
        except Exception:
            pass

    async def start(self, task, max_steps):
        if self.job and not self.job.done():
            return
        tools = Tools()

        @tools.action("Ask the human to approve an irreversible step, solve a CAPTCHA, or provide missing info. Waits for the reply.")
        async def ask_human(question: str):
            self.answer = asyncio.get_running_loop().create_future()
            await self.send("ask", question=question)
            reply = await self.answer
            await self.send("status", state="running")
            return ActionResult(extracted_content=f"Human replied: {reply}", include_in_memory=True)

        key = "tools" if "tools" in inspect.signature(Agent.__init__).parameters else "controller"
        self.agent = Agent(task=task, llm=make_llm(), browser=get_browser(), extend_system_message=RULES, **{key: tools})
        self.job = asyncio.create_task(self.run(max_steps))

    async def run(self, max_steps):
        async def on_step(agent):
            try:
                h = agent.history
                shots = [s for s in h.screenshots() if s]
                th, acts = h.model_thoughts(), h.model_actions()
                action = next((k for k in acts[-1] if k != "interacted_element"), "") if acts else ""
                await self.send("step", n=len(h.history), url=(h.urls() or [""])[-1], action=action,
                                goal=getattr(th[-1], "next_goal", "") if th else "", shot=shots[-1] if shots else None)
            except Exception:
                pass

        await self.send("status", state="running")
        try:
            h = await self.agent.run(max_steps=max_steps, on_step_end=on_step)
            await self.send("done", result=h.final_result() or "Stopped before finishing.", steps=len(h.history))
        except Exception as e:
            await self.send("error", msg=str(e))

    def control(self, kind, text=""):
        if kind == "reply" and self.answer and not self.answer.done():
            self.answer.set_result(text)
        elif self.agent and kind == "pause":
            self.agent.pause()
        elif self.agent and kind == "resume":
            self.agent.resume()
        elif self.agent and kind == "stop":
            self.agent.stop()
            if self.answer and not self.answer.done():
                self.answer.set_result("DENIED: the human stopped the task.")


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    s = Session(ws)
    try:
        while True:
            m = await ws.receive_json()
            if m["type"] == "start":
                await s.start(m["task"], int(m.get("max_steps", 25)))
            else:
                s.control(m["type"], m.get("text", ""))
                if m["type"] in ("pause", "resume"):
                    await s.send("status", state="paused" if m["type"] == "pause" else "running")
    except WebSocketDisconnect:
        s.control("stop")


@app.get("/")
def index():
    # Serve the dashboard. Prefer the packaged copy under static/, fall back to
    # the project-root copy so the app runs in either layout.
    for candidate in (ROOT / "static" / "index.html", ROOT / "index.html"):
        if candidate.exists():
            return FileResponse(candidate)
    return FileResponse(ROOT / "index.html")
