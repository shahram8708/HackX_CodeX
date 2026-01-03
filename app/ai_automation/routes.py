import json
import time
from typing import Any, Dict, List

from flask import jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.ai_automation import bp
from app.models import AutomationMessage
from app.utils.gemini_client import GeminiClient
from app.ai_assistant.routes import _tool_schemas, _dispatch_tool, _extract_tool_calls

SESSION_MEMORY: Dict[str, List[Dict[str, Any]]] = {}
RATE_LIMIT: Dict[str, float] = {}
MEMORY_LIMIT = 5


def _system_prompt() -> str:
    return (
        "You are HealneX Automation Copilot. You run structured actions and give very concise summaries (<80 words). "
        "Prefer tool calls when possible. Do not include extra chatter."
    )


def _shorten(text: str, limit: int = 500) -> str:
    if not text:
        return ""
    return text if len(text) <= limit else text[:limit] + "... (truncated)"


def _is_rate_limited(session_id: str, window_seconds: int = 3) -> bool:
    now = time.time()
    last = RATE_LIMIT.get(session_id)
    if last and now - last < window_seconds:
        return True
    RATE_LIMIT[session_id] = now
    return False


def _persist_message(session_id: str, content: str, role: str) -> None:
    entry = AutomationMessage(user_id=current_user.id, session_id=session_id, role=role, content=content)
    db.session.add(entry)
    db.session.commit()


def _recent_messages(session_id: str, limit: int = 30) -> List[AutomationMessage]:
    return (
        AutomationMessage.query.filter_by(user_id=current_user.id, session_id=session_id)
        .order_by(AutomationMessage.created_at.desc())
        .limit(limit)
        .all()
    )


def _to_chronological(messages: List[AutomationMessage]) -> List[AutomationMessage]:
    return list(reversed(messages))


@bp.route('/assistant', methods=['GET', 'POST'])
@login_required
def assistant():
    if request.method == 'GET':
        return render_template('ai_automation/assistant.html')

    data = request.get_json() or {}
    incoming_messages: List[Dict[str, Any]] = data.get('messages') or []
    session_id = (data.get('session_id') or f"auto-session-{current_user.id}")[:64]

    last_user_msg = next((m for m in reversed(incoming_messages) if (m.get('role') or '').lower() == 'user'), None)
    user_text = (last_user_msg or {}).get('content', '').strip()

    if not user_text:
        return jsonify({'error': 'Message is required'}), 400

    if _is_rate_limited(session_id):
        return jsonify({'error': 'Too many requests, please slow down.'}), 429

    memory = SESSION_MEMORY.get(session_id, [])
    conversation = (memory + incoming_messages)[-MEMORY_LIMIT:]

    try:
        client = GeminiClient()
    except RuntimeError as exc:
        return jsonify({'error': str(exc)}), 500

    # Keep prompt lean: translate if needed but avoid large preambles.
    translation = client.detect_and_translate(user_text, target_language='en')
    english_user_text = translation.get('translation') or user_text
    detected_language = translation.get('language') or 'en'

    gemini_messages: List[Dict[str, Any]] = []
    for msg in conversation:
        role = (msg.get('role') or 'user').lower()
        content = msg.get('content') or ''
        if role == 'user' and msg is last_user_msg:
            content = english_user_text
        content = _shorten(content, 500)
        gemini_messages.append({
            'role': 'user' if role == 'user' else 'model',
            'parts': [content]
        })

    tools = _tool_schemas()
    system_prompt = _system_prompt()

    first = client.generate(
        gemini_messages,
        tools=tools,
        system_instruction=system_prompt,
        generation_config={'temperature': 0.2, 'max_output_tokens': 256}
    )

    tool_calls = _extract_tool_calls(first)
    tool_results: List[Dict[str, Any]] = []
    final_text = first.text or 'I could not complete that request.'

    if tool_calls:
        for call in tool_calls:
            result = _dispatch_tool(call['name'], call.get('args') or {})
            tool_results.append({'name': call['name'], 'result': result})
        gemini_messages.append({'role': 'model', 'parts': [json.dumps({'tool_results': tool_results})]})
        follow_up = client.generate(
            gemini_messages,
            tools=tools,
            system_instruction=system_prompt,
            generation_config={'temperature': 0.18, 'max_output_tokens': 256}
        )
        final_text = follow_up.text or final_text

    reply = final_text
    if detected_language.lower() != 'en':
        try:
            reply = client.translate_text(final_text, target_language=detected_language)
        except Exception:
            reply = final_text

    SESSION_MEMORY[session_id] = (conversation + [
        {'role': 'user', 'content': user_text},
        {'role': 'assistant', 'content': reply}
    ])[-MEMORY_LIMIT:]

    _persist_message(session_id, user_text, 'user')
    _persist_message(session_id, reply, 'assistant')

    ordered = _to_chronological(_recent_messages(session_id, limit=30))

    return jsonify({
        'reply': reply,
        'language': detected_language,
        'tool_calls': tool_calls,
        'tool_results': tool_results,
        'messages': [m.to_dict() for m in ordered]
    })


@bp.route('/history', methods=['GET', 'DELETE'])
@login_required
def history():
    session_id = (request.args.get('session_id') or f"auto-session-{current_user.id}")[:64]
    if request.method == 'DELETE':
        AutomationMessage.query.filter_by(user_id=current_user.id, session_id=session_id).delete()
        db.session.commit()
        SESSION_MEMORY.pop(session_id, None)
        return jsonify({'ok': True, 'deleted': True})

    limit_arg = request.args.get('limit', default=30, type=int)
    limit = max(1, min(limit_arg, 100))
    messages = (
        AutomationMessage.query.filter_by(user_id=current_user.id, session_id=session_id)
        .order_by(AutomationMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return jsonify([m.to_dict() for m in _to_chronological(messages)])
