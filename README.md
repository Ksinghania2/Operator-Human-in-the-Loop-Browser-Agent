# Operator: the "do it for me" browser agent

Type (or speak) an instruction. A [browser-use](https://github.com/browser-use/browser-use) agent opens a **real browser window**,
reads the page visually with a vision-language model, and clicks, types and navigates for you while a live mirror and action log
stream into the dashboard.

## Features
- Real, visible Chromium window; the same window and profile persist between tasks, so carts and logins survive.
- Live screenshot mirror, step-by-step action log (click any step to revisit its screenshot).
- **Pause / Resume / Stop** at any time.
- **Human in the loop**: the agent has an `ask_human` tool. It must ask before logging in, sending, deleting or booking, and when it hits a CAPTCHA or 2FA. You approve, deny, or reply.
- **Safety rail**: the system prompt forbids placing orders or entering payment details; it stops at checkout and the window stays open for you.
- Voice input (browser speech recognition), GPT / Gemini / Claude backends.

## Run it (VS Code)
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium                            # or: uvx browser-use install
cp .env.example .env                                   # add one API key
uvicorn app.main:app --reload
```
Open http://localhost:8000 and keep the dashboard and the browser window side by side.

## Push to GitHub from VS Code
Source Control → **Initialize Repository** → commit → **Publish Branch**. `.env` and the browser profile (`data/`) are git-ignored,
so your keys and logins stay local. Add a screen recording of a run as `demo.gif` to make the repo stand out.

## Notes
- Runs on your own machine because it needs a display. Do not expose the server publicly: it controls a browser that may be logged in as you.
- Sites such as Amazon may show CAPTCHAs or block automation; the agent will ask you to solve them.
- Only automate sites whose terms allow it.
