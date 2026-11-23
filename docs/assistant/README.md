# IARG Assistant — Documentation Index

Documentation for the Assistant tab (free in-product chatbot) added to the
IARG dashboard.

| Doc | What it covers |
|---|---|
| [`one-pager.md`](./one-pager.md) | TL;DR — problem, solution, success criteria, risks, status. |
| [`requirements.md`](./requirements.md) | User stories, functional and non-functional requirements, acceptance checks. |
| [`design.md`](./design.md) | Architecture, frontend design, backend design, upstream choice, future work. |
| [`wireframes.md`](./wireframes.md) | UI wireframes for empty, active, and error states, plus runtime architecture diagram. |

## Live surfaces

- UI: http://localhost:3000/chat
- API: `POST http://localhost:8003/api/guardian/chat`
  (body: `{"model": "mistral-nemo", "messages": [...]}`)

## Code pointers

- Frontend page: `app/dash/src/pages/Chat.tsx`
- Nav entry: `app/dash/src/components/Layout.tsx`
- Route: `app/dash/src/App.tsx`
- Backend endpoint: `app/guardian/src/api/routes.py` (section *Chat (free LLM proxy)*)
