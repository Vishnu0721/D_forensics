"""Plain-language helpers for incidents and suspicious findings."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import re

IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def severity_label(score: float) -> str:
    if score >= 0.8:
        return "High"
    if score >= 0.5:
        return "Medium"
    return "Low"


def severity_color(score: float) -> str:
    if score >= 0.8:
        return "#c62828"
    if score >= 0.5:
        return "#e67e22"
    return "#757575"


def _friendly_node(node_id: str, node_data: Optional[dict] = None) -> str:
    node_data = node_data or {}
    if node_data.get("label"):
        return str(node_data["label"])
    if node_data.get("process"):
        return str(node_data["process"])
    text = str(node_id)
    if IP_RE.match(text):
        return text
    if text.startswith("proc:"):
        return text[5:]
    if "_" in text:
        return text.rsplit("_", 1)[-1]
    return text[:48]


def format_suspicious_item(act: Dict[str, Any]) -> str:
    score = act.get("score", 0)
    sev = severity_label(score)
    rule = act.get("rule_name", "Unusual activity")
    reason = act.get("reason", "Pattern matched by detection rules.")
    return (
        f"[{sev} priority] {rule}\n"
        f"{reason}\n"
        f"Click for details · open Evidence Graph to see linked programs and services."
    )


def format_suspicious_detail_html(act: Dict[str, Any]) -> str:
    score = act.get("score", 0)
    sev = severity_label(score)
    color = severity_color(score)
    rule = act.get("rule_name", "Unusual activity")
    reason = act.get("reason", "")

    html = f"<h3 style='color:{color};'>Needs attention — {sev} priority</h3>"
    html += f"<p style='font-size:15px; font-weight:bold;'>{rule}</p>"
    html += f"<p>{reason}</p>"
    html += (
        "<p style='color:#666;'>This is a rule-based hint, not a final verdict. "
        "Review the linked programs and files in the Evidence Graph.</p>"
    )

    nodes = act.get("nodes", [])
    if nodes:
        html += "<p><b>Involved:</b> "
        html += ", ".join(_friendly_node(str(n)) for n in nodes[:6])
        if len(nodes) > 6:
            html += f" (+{len(nodes) - 6} more)"
        html += "</p>"

    html += "<details><summary><b>Technical details</b></summary>"
    html += f"<p>Score: {score:.2f}<br/>Activity ID: {act.get('activity_id', 'N/A')}</p>"
    ev_ids = act.get("evidence_ids", [])
    if ev_ids:
        html += "<ul>"
        for eid in ev_ids[:8]:
            html += f"<li>{eid}</li>"
        html += "</ul>"
    html += "</details>"
    return html


def _story_from_timeline(timeline: str) -> str:
    if not timeline:
        return "Related activity was linked together by time and matching details."
    lines = [ln.strip() for ln in timeline.split("\n") if ln.strip() and not ln.strip().startswith("->")]
    if not lines:
        return "Related activity was linked together."
    # Take first 3 entity steps
    steps = []
    for ln in lines[:4]:
        if ln.lower().startswith("step"):
            steps.append(ln.split(":", 1)[-1].strip())
    if steps:
        return " → ".join(steps)
    return lines[0][:200]


def format_incident_card_html(inc: Dict[str, Any]) -> str:
    status = inc.get("status", "Normal")
    status_color = "#c62828" if status == "Requires Investigation" else "#2e7d32"
    status_plain = "Review recommended" if status == "Requires Investigation" else "Informational"

    story = _story_from_timeline(inc.get("timeline", ""))
    n_nodes = len(inc.get("nodes", []))
    n_links = len(inc.get("relationships", []))

    html = f"<div style='border:1px solid #ccc; border-radius:4px; padding:10px; margin-bottom:12px;'>"
    html += f"<h4 style='margin:0 0 6px 0;'>{inc.get('incident_id', 'Story')}</h4>"
    html += f"<p style='margin:0 0 8px 0;'><b>Status:</b> <span style='color:{status_color};'>{status_plain}</span>"
    html += f" · {n_nodes} items · {n_links} links</p>"
    html += f"<p style='font-size:14px;'><b>What happened:</b> {story}</p>"

    suspicious = inc.get("suspicious_activities", [])
    if suspicious:
        html += "<p><b>Why it stands out:</b></p><ul>"
        for act in suspicious:
            html += f"<li>{act.get('rule_name', 'Finding')}: {act.get('reason', '')}</li>"
        html += "</ul>"
    else:
        html += "<p style='color:#666;'>No high-priority flags — this is a normal linked activity chain "
        html += "(for example a browser contacting a website).</p>"

    if inc.get("timeline"):
        html += "<details><summary><b>Step-by-step timeline</b></summary>"
        html += "<pre style='background:#1e1e1e; color:#d4d4d4; padding:8px; white-space:pre-wrap;'>"
        html += inc["timeline"]
        html += "</pre></details>"

    html += "</div>"
    return html


def format_incidents_page_html(incidents: List[Dict[str, Any]]) -> str:
    if not incidents:
        return (
            "<p style='color: gray;'>No linked stories yet.</p>"
            "<p>When the app connects related events — for example "
            "<b>a program → an internet service</b> — a short story appears here.</p>"
            "<p style='color:#666;'>Normal Chrome, Cursor, or GitHub traffic often creates "
            "informational stories with status “Informational”, not “Review recommended”.</p>"
        )
    html = "<h3>Activity stories</h3>"
    html += "<p style='color:#666;'>Each card is a chain of related events on this PC.</p>"
    for inc in incidents:
        html += format_incident_card_html(inc)
    return html
