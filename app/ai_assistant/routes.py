import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import current_app, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.ai_assistant import bp
from app.models import Appointment, ChatbotMessage, DoctorReferral, MedicalFile, User
from app.utils.gemini_client import GeminiClient
from app.utils.helpers import create_notification

SESSION_MEMORY: Dict[str, List[Dict[str, Any]]] = {}
RATE_LIMIT: Dict[str, float] = {}
MEMORY_LIMIT = 5

TOOL_REGISTRY: Dict[str, Dict[str, Any]] = {
    "book_appointment": {
        "name": "book_appointment",
        "description": "Book a new appointment between a patient and doctor. Requires confirm flag for scheduling.",
        "schema": {
            "type": "object",
            "properties": {
                "doctor_id": {"type": "integer", "description": "Doctor user id"},
                "patient_id": {"type": "integer", "description": "Patient user id (defaults to current user)"},
                "appointment_date": {"type": "string", "description": "Date in YYYY-MM-DD"},
                "appointment_time": {"type": "string", "description": "Time in HH:MM (24h)"},
                "appointment_type": {"type": "string", "description": "consultation, follow-up, teleconsultation, etc"},
                "notes": {"type": "string"},
                "reason": {"type": "string"},
                "confirm": {"type": "boolean", "description": "Must be true to place booking"}
            },
            "required": ["doctor_id", "appointment_date", "appointment_time", "appointment_type", "confirm"]
        }
    },
    "reschedule_appointment": {
        "name": "reschedule_appointment",
        "description": "Move an existing appointment to a new date/time.",
        "schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer"},
                "appointment_date": {"type": "string", "description": "New date YYYY-MM-DD"},
                "appointment_time": {"type": "string", "description": "New time HH:MM (24h)"},
                "notes": {"type": "string"},
                "confirm": {"type": "boolean", "description": "Optional confirmation flag"}
            },
            "required": ["appointment_id", "appointment_date", "appointment_time"]
        }
    },
    "cancel_appointment": {
        "name": "cancel_appointment",
        "description": "Cancel an appointment. Requires confirm flag.",
        "schema": {
            "type": "object",
            "properties": {
                "appointment_id": {"type": "integer"},
                "reason": {"type": "string"},
                "confirm": {"type": "boolean", "description": "Must be true to cancel"}
            },
            "required": ["appointment_id", "confirm"]
        }
    },
    "send_notification": {
        "name": "send_notification",
        "description": "Send an in-app notification or reminder. Announcements require confirm flag.",
        "schema": {
            "type": "object",
            "properties": {
                "target_user_id": {"type": "integer"},
                "title": {"type": "string"},
                "message": {"type": "string"},
                "notification_type": {"type": "string", "description": "notification, reminder, announcement"},
                "link": {"type": "string"},
                "confirm": {"type": "boolean", "description": "Required when notification_type is announcement"}
            },
            "required": ["target_user_id", "title", "message", "notification_type"]
        }
    },
    "create_referral": {
        "name": "create_referral",
        "description": "Create a doctor-to-doctor referral for a patient.",
        "schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer"},
                "to_doctor_id": {"type": "integer"},
                "reason": {"type": "string"},
                "notes": {"type": "string"},
                "confirm": {"type": "boolean", "description": "Optional confirmation"}
            },
            "required": ["patient_id", "to_doctor_id", "reason"]
        }
    },
    "upload_report": {
        "name": "upload_report",
        "description": "Upload a report on behalf of a patient. Only metadata is accepted via assistant.",
        "schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer"},
                "report_type": {"type": "string"},
                "description": {"type": "string"},
                "file_name": {"type": "string", "description": "Reference name or link"},
                "confirm": {"type": "boolean", "description": "Must be true to record metadata"}
            },
            "required": ["patient_id", "report_type", "file_name", "confirm"]
        }
    },
    "list_reports": {
        "name": "list_reports",
        "description": "List recent reports for a patient.",
        "schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer"},
                "limit": {"type": "integer", "description": "Number of reports to fetch"}
            },
            "required": []
        }
    },
    "download_report": {
        "name": "download_report",
        "description": "Get a download link for a report.",
        "schema": {
            "type": "object",
            "properties": {
                "report_id": {"type": "integer"}
            },
            "required": ["report_id"]
        }
    },
    "fetch_patient_profile": {
        "name": "fetch_patient_profile",
        "description": "Fetch a concise patient profile.",
        "schema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer"}
            },
            "required": []
        }
    },
    "run_admin_report": {
        "name": "run_admin_report",
        "description": "Run an admin analytics snippet (admin only).",
        "schema": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "description": "appointments, payments, usage"},
                "confirm": {"type": "boolean", "description": "Set true to execute"}
            },
            "required": ["report_type", "confirm"]
        }
    }
}


def _tool_schemas() -> List[Dict[str, Any]]:
    return [{
        "function_declarations": [
            {
                "name": spec["name"],
                "description": spec.get("description", ""),
                "parameters": spec.get("schema", {})
            }
            for spec in TOOL_REGISTRY.values()
        ]
    }]


def _system_prompt() -> str:
    return (
        "You are HealneX Copilot, a concise multilingual healthcare assistant. "
        "Use the provided tools for appointments, notifications, referrals, and reports. "
        "Never fabricate confirmations—require a confirm flag for booking, cancelling, or announcements. "
        "Respect consent and privacy; refuse to share PII or medical advice beyond summarization. "
        "If data is missing, ask for it. Keep answers short (under 80 words) and actionable."
    )


def _recent_messages(user_id: int, limit: int = 30) -> List[ChatbotMessage]:
    return ChatbotMessage.query.filter_by(user_id=user_id).order_by(ChatbotMessage.created_at.desc()).limit(limit).all()


def _to_chronological(messages: List[ChatbotMessage]) -> List[ChatbotMessage]:
    return list(reversed(messages))


def _is_blocked(text: str) -> bool:
    blocked_terms = ["kill", "bomb", "terror"]
    lowered = text.lower()
    return any(term in lowered for term in blocked_terms)


def _is_rate_limited(session_id: str, window_seconds: int = 3) -> bool:
    now = time.time()
    last = RATE_LIMIT.get(session_id)
    if last and now - last < window_seconds:
        return True
    RATE_LIMIT[session_id] = now
    return False


def _shorten(text: str, limit: int = 600) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "... (truncated)"


def _persist_message(content: str, role: str) -> None:
    entry = ChatbotMessage(user_id=current_user.id, role=role, content=content)
    db.session.add(entry)
    db.session.commit()


def _parse_date(date_str: str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def _parse_time(time_str: str):
    return datetime.strptime(time_str, "%H:%M").time()


def _ensure_patient_access(patient_id: int) -> Optional[str]:
    if patient_id == current_user.id:
        return None
    if current_user.role in ["doctor", "admin"]:
        return None
    return "Not authorized for that patient."


def _dispatch_tool(name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    handlers = {
        "book_appointment": _handle_book_appointment,
        "reschedule_appointment": _handle_reschedule_appointment,
        "cancel_appointment": _handle_cancel_appointment,
        "send_notification": _handle_send_notification,
        "create_referral": _handle_create_referral,
        "upload_report": _handle_upload_report,
        "list_reports": _handle_list_reports,
        "download_report": _handle_download_report,
        "fetch_patient_profile": _handle_fetch_patient_profile,
        "run_admin_report": _handle_run_admin_report
    }
    handler = handlers.get(name)
    if not handler:
        return {"ok": False, "message": f"Tool {name} not available"}
    try:
        return handler(args)
    except Exception as exc:
        current_app.logger.error(f"Tool {name} failed: {exc}")
        return {"ok": False, "message": "Tool execution failed"}


def _handle_book_appointment(args: Dict[str, Any]) -> Dict[str, Any]:
    if not args.get("confirm"):
        return {"ok": False, "message": "Confirmation required to book."}
    doctor = User.query.filter_by(id=args.get("doctor_id"), role="doctor").first()
    if not doctor:
        return {"ok": False, "message": "Doctor not found."}
    patient_id = args.get("patient_id") or current_user.id
    auth_error = _ensure_patient_access(patient_id)
    if auth_error:
        return {"ok": False, "message": auth_error}
    try:
        appointment_date = _parse_date(args["appointment_date"])
        appointment_time = _parse_time(args["appointment_time"])
    except Exception:
        return {"ok": False, "message": "Invalid date or time format."}

    appointment = Appointment(
        patient_id=patient_id,
        doctor_id=doctor.id,
        appointment_type=args.get("appointment_type", "consultation"),
        appointment_date=appointment_date,
        appointment_time=appointment_time,
        notes=args.get("notes"),
        reason=args.get("reason"),
        status="pending"
    )
    db.session.add(appointment)
    db.session.commit()

    create_notification(patient_id, "Appointment Created", f"Your appointment request with Dr. {doctor.name} is pending.", "appointment")
    create_notification(doctor.id, "New Appointment", f"New appointment request from user {patient_id}.", "appointment")

    return {"ok": True, "appointment": appointment.to_dict()}


def _handle_reschedule_appointment(args: Dict[str, Any]) -> Dict[str, Any]:
    appointment = Appointment.query.get(args.get("appointment_id"))
    if not appointment:
        return {"ok": False, "message": "Appointment not found."}
    if current_user.role == "patient" and appointment.patient_id != current_user.id:
        return {"ok": False, "message": "Not authorized to reschedule."}
    if current_user.role == "doctor" and appointment.doctor_id != current_user.id:
        return {"ok": False, "message": "Not authorized to reschedule."}
    try:
        appointment.appointment_date = _parse_date(args["appointment_date"])
        appointment.appointment_time = _parse_time(args["appointment_time"])
    except Exception:
        return {"ok": False, "message": "Invalid date or time."}
    if args.get("notes"):
        appointment.notes = (appointment.notes or "") + f"\nReschedule note: {args['notes']}"
    appointment.status = "pending"
    db.session.commit()
    create_notification(appointment.patient_id, "Appointment Rescheduled", "We updated your appointment timing.", "appointment")
    create_notification(appointment.doctor_id, "Appointment Rescheduled", "Patient updated appointment timing.", "appointment")
    return {"ok": True, "appointment": appointment.to_dict()}


def _handle_cancel_appointment(args: Dict[str, Any]) -> Dict[str, Any]:
    if not args.get("confirm"):
        return {"ok": False, "message": "Confirmation required to cancel."}
    appointment = Appointment.query.get(args.get("appointment_id"))
    if not appointment:
        return {"ok": False, "message": "Appointment not found."}
    if current_user.role == "patient" and appointment.patient_id != current_user.id:
        return {"ok": False, "message": "Not authorized to cancel."}
    if current_user.role == "doctor" and appointment.doctor_id != current_user.id:
        return {"ok": False, "message": "Not authorized to cancel."}
    appointment.status = "cancelled"
    appointment.reason = args.get("reason") or appointment.reason
    db.session.commit()
    create_notification(appointment.patient_id, "Appointment Cancelled", "Your appointment was cancelled.", "appointment")
    create_notification(appointment.doctor_id, "Appointment Cancelled", "An appointment was cancelled.", "appointment")
    return {"ok": True, "appointment": appointment.to_dict()}


def _handle_send_notification(args: Dict[str, Any]) -> Dict[str, Any]:
    if args.get("notification_type") == "announcement" and not args.get("confirm"):
        return {"ok": False, "message": "Confirmation required for announcements."}
    target = User.query.get(args.get("target_user_id"))
    if not target:
        return {"ok": False, "message": "Target user not found."}
    notification = create_notification(
        target.id,
        args.get("title", ""),
        args.get("message", ""),
        args.get("notification_type", "notification"),
        args.get("link")
    )
    return {"ok": True, "notification": notification.to_dict()}


def _handle_create_referral(args: Dict[str, Any]) -> Dict[str, Any]:
    if current_user.role not in ["doctor", "admin"]:
        return {"ok": False, "message": "Only doctors or admins can create referrals."}
    patient = User.query.filter_by(id=args.get("patient_id"), role="patient").first()
    to_doctor = User.query.filter_by(id=args.get("to_doctor_id"), role="doctor").first()
    if not patient or not to_doctor:
        return {"ok": False, "message": "Patient or doctor not found."}
    referral = DoctorReferral(
        from_doctor_id=current_user.id,
        to_doctor_id=to_doctor.id,
        patient_id=patient.id,
        reason=args.get("reason"),
        notes=args.get("notes"),
        status="pending"
    )
    db.session.add(referral)
    db.session.commit()
    create_notification(to_doctor.id, "New Referral", f"Referral for patient {patient.name}", "referral")
    return {"ok": True, "referral": referral.to_dict()}


def _handle_upload_report(args: Dict[str, Any]) -> Dict[str, Any]:
    if not args.get("confirm"):
        return {"ok": False, "message": "Confirmation required to record a report."}
    patient_id = args.get("patient_id") or current_user.id
    auth_error = _ensure_patient_access(patient_id)
    if auth_error:
        return {"ok": False, "message": auth_error}
    placeholder = MedicalFile(
        filename=args.get("file_name", "assistant-note"),
        original_filename=args.get("file_name", "assistant-note"),
        filepath=args.get("file_name", "assistant-note"),
        file_type="text/plain",
        file_size=0,
        report_type=args.get("report_type", "note"),
        description=args.get("description", "Assistant logged report metadata"),
        patient_id=patient_id,
        doctor_id=current_user.id
    )
    db.session.add(placeholder)
    db.session.commit()
    create_notification(patient_id, "Report Logged", "A report entry was added. Upload file via reports page if needed.", "upload")
    return {"ok": True, "report": placeholder.to_dict()}


def _handle_list_reports(args: Dict[str, Any]) -> Dict[str, Any]:
    patient_id = args.get("patient_id") or current_user.id
    auth_error = _ensure_patient_access(patient_id)
    if auth_error:
        return {"ok": False, "message": auth_error}
    limit = min(max(int(args.get("limit", 5)), 1), 20)
    reports = MedicalFile.query.filter_by(patient_id=patient_id).order_by(MedicalFile.upload_date.desc()).limit(limit).all()
    return {
        "ok": True,
        "reports": [
            {
                "id": r.id,
                "filename": r.original_filename,
                "report_type": r.report_type,
                "description": r.description,
                "uploaded_at": r.upload_date.isoformat()
            }
            for r in reports
        ]
    }


def _handle_download_report(args: Dict[str, Any]) -> Dict[str, Any]:
    report = MedicalFile.query.get(args.get("report_id"))
    if not report:
        return {"ok": False, "message": "Report not found."}
    auth_error = _ensure_patient_access(report.patient_id)
    if auth_error and not (current_user.role == "doctor" and report.doctor_id == current_user.id):
        return {"ok": False, "message": auth_error}
    link = None
    try:
        from flask import url_for

        link = url_for("uploads.download_file", file_id=report.id, _external=True)
    except Exception:
        link = None
    return {
        "ok": True,
        "report": {
            "id": report.id,
            "filename": report.original_filename,
            "download_url": link
        }
    }


def _handle_fetch_patient_profile(args: Dict[str, Any]) -> Dict[str, Any]:
    patient_id = args.get("patient_id") or current_user.id
    auth_error = _ensure_patient_access(patient_id)
    if auth_error:
        return {"ok": False, "message": auth_error}
    patient = User.query.filter_by(id=patient_id, role="patient").first()
    if not patient:
        return {"ok": False, "message": "Patient not found."}
    profile = patient.to_dict()
    profile.update({
        "age": patient.age,
        "gender": patient.gender,
        "conditions": patient.conditions,
        "allergies": patient.allergies
    })
    return {"ok": True, "patient": profile}


def _handle_run_admin_report(args: Dict[str, Any]) -> Dict[str, Any]:
    if current_user.role != "admin":
        return {"ok": False, "message": "Admin only."}
    if not args.get("confirm"):
        return {"ok": False, "message": "Confirmation required for admin reports."}
    report_type = (args.get("report_type") or "appointments").lower()
    summary: Dict[str, Any] = {"report_type": report_type}
    if report_type == "appointments":
        summary["count"] = Appointment.query.count()
    elif report_type == "users":
        summary["count"] = User.query.count()
    else:
        summary["message"] = "Report type not recognized; returning basic stats."
        summary["users"] = User.query.count()
        summary["appointments"] = Appointment.query.count()
    return {"ok": True, "summary": summary}


def _extract_tool_calls(response) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    try:
        for candidate in getattr(response, "candidates", []):
            content = getattr(candidate, "content", None)
            if not content:
                continue
            for part in getattr(content, "parts", []):
                fc = getattr(part, "function_call", None)
                if fc:
                    calls.append({"name": fc.name, "args": dict(fc.args or {})})
    except Exception as exc:
        current_app.logger.error(f"Failed to parse tool calls: {exc}")
    return calls


@bp.route('/history', methods=['GET', 'DELETE'])
@login_required
def history():
    if request.method == 'DELETE':
        ChatbotMessage.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        SESSION_MEMORY.pop(f"session-{current_user.id}", None)
        return jsonify({'ok': True, 'deleted': True})

    limit_arg = request.args.get('limit', default=30, type=int)
    limit = max(1, min(limit_arg, 100))
    messages = ChatbotMessage.query.filter_by(user_id=current_user.id).order_by(ChatbotMessage.created_at.desc()).limit(limit).all()
    ordered = _to_chronological(messages)
    return jsonify([m.to_dict() for m in ordered])


@bp.route('/assistant', methods=['GET', 'POST'])
@login_required
def assistant():
    if request.method == 'GET':
        return render_template('chat/assistant.html')

    data = request.get_json() or {}
    incoming_messages: List[Dict[str, Any]] = data.get('messages') or []
    session_id = (data.get('session_id') or f"session-{current_user.id}")[:64]
    preferred_language = data.get('language') or 'auto'

    user_message = next((m for m in reversed(incoming_messages) if (m.get('role') or '').lower() == 'user'), None)
    user_text = (user_message or {}).get('content', '').strip()

    if not user_text:
        return jsonify({'error': 'Message is required'}), 400

    if _is_blocked(user_text):
        return jsonify({'error': 'Message blocked by safety filters'}), 403

    if _is_rate_limited(session_id):
        return jsonify({'error': 'Too many requests, please slow down.'}), 429

    memory = SESSION_MEMORY.get(session_id, [])
    conversation = (memory + incoming_messages)[-MEMORY_LIMIT:]

    try:
        client = GeminiClient()
    except RuntimeError as exc:
        current_app.logger.error(exc)
        return jsonify({'error': 'GEMINI_API_KEY is missing. Set it in the environment.'}), 500

    translation = client.detect_and_translate(user_text, target_language='en')
    detected_language = translation.get('language') or 'en'
    english_user_text = translation.get('translation') or user_text

    system_prompt = _system_prompt()

    gemini_messages: List[Dict[str, Any]] = []
    for msg in conversation:
        role = (msg.get('role') or 'user').lower()
        content = msg.get('content') or ''
        if role == 'user' and msg is user_message:
            content = english_user_text
        content = _shorten(content, 600)
        gemini_messages.append({
            'role': 'user' if role == 'user' else 'model',
            'parts': [content]
        })

    tools = _tool_schemas()
    first_response = client.generate(
        gemini_messages,
        tools=tools,
        system_instruction=system_prompt,
        generation_config={'temperature': 0.25, 'max_output_tokens': 256}
    )

    tool_calls = _extract_tool_calls(first_response)
    tool_results: List[Dict[str, Any]] = []

    if tool_calls:
        for call in tool_calls:
            tool_result = _dispatch_tool(call['name'], call.get('args') or {})
            tool_results.append({'name': call['name'], 'result': tool_result})
        gemini_messages.append({'role': 'model', 'parts': [json.dumps({'tool_results': tool_results})]})
        follow_up = client.generate(
            gemini_messages,
            tools=tools,
            system_instruction=system_prompt,
            generation_config={'temperature': 0.2, 'max_output_tokens': 256}
        )
        final_text = follow_up.text or 'I could not complete that request.'
    else:
        final_text = first_response.text or 'I could not complete that request.'

    reply = final_text
    if detected_language.lower() != 'en' and preferred_language != 'en':
        try:
            reply = client.translate_text(final_text, target_language=detected_language)
        except Exception:
            reply = final_text

    SESSION_MEMORY[session_id] = (conversation + [
        {'role': 'user', 'content': user_text},
        {'role': 'assistant', 'content': reply}
    ])[-MEMORY_LIMIT:]

    _persist_message(user_text, 'user')
    _persist_message(reply, 'assistant')

    ordered_messages = _to_chronological(_recent_messages(current_user.id, limit=30))

    return jsonify({
        'reply': reply,
        'language': detected_language,
        'tool_calls': tool_calls,
        'tool_results': tool_results,
        'messages': [m.to_dict() for m in ordered_messages]
    })
