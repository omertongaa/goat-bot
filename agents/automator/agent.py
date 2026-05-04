"""Automator — n8n workflow runner inside goat-bot.

Lists/installs/runs n8n JSON templates without needing n8n itself.
Backed by core/automations.py. Acts as a normal goat-bot agent so
runs become tickets, costs roll up, approval gates work the same.

Actions:
    list           — show available templates
    install        — clone a template to active company
    trigger        — fire a webhook-style payload at an installed automation
    delete         — remove an installed automation
"""

from agents.base import BaseAgent
from core import automations, store


class AutomatorAgent(BaseAgent):
    agent_id = "automator"
    name = "Automator"
    role = "n8n workflow JSON'larını goat-bot içinde kurar ve çalıştırır"
    category = "system"

    def run(self, action: str = "list", template_id: str = "", automation_id: str = "", payload: dict = None) -> dict:
        company_id = store.active_company_id()
        action = (action or "list").lower()

        if action == "list":
            tmpls = automations.list_templates()
            installed = automations.list_installed(company_id)
            return {
                "status": "ok",
                "summary": f"{len(tmpls)} şablon, {len(installed)} kurulu otomasyon",
                "metrics": {"templates": len(tmpls), "installed": len(installed)},
                "result": {"templates": tmpls, "installed": installed},
                "recommendations": [
                    "automator install template_id=02-hot-lead-slack-alert ile kur",
                    "Sonra trigger ile payload gönder",
                ],
            }

        if action == "install":
            if not template_id:
                return {"status": "error", "summary": "template_id gerekli", "metrics": {}, "recommendations": []}
            self.log(f"Şablon kuruluyor: {template_id}")
            rec = automations.install_template(company_id, template_id)
            if rec.get("error"):
                return {"status": "error", "summary": rec["error"], "metrics": {}, "recommendations": []}
            return {
                "status": "ok",
                "summary": f"{rec['name']} kuruldu (trigger={rec['trigger']})",
                "metrics": {"automation_id": rec["id"], "trigger": rec["trigger"]},
                "result": rec,
                "recommendations": [
                    f"Trigger için: automator trigger automation_id={rec['id']}",
                    "Webhook URL: /api/automations/{id}/trigger",
                ],
            }

        if action == "trigger":
            if not automation_id:
                return {"status": "error", "summary": "automation_id gerekli", "metrics": {}, "recommendations": []}
            self.log(f"Trigger: {automation_id}")
            res = automations.trigger(company_id, automation_id, payload=payload or {})
            return {
                "status": "ok" if res.get("ok") else "error",
                "summary": f"Otomasyon koştu: {len(res.get('log', []))} adım",
                "metrics": {"steps": len(res.get("log", [])), "ok": res.get("ok")},
                "result": res,
                "recommendations": [],
            }

        if action == "delete":
            if not automation_id:
                return {"status": "error", "summary": "automation_id gerekli", "metrics": {}, "recommendations": []}
            ok = automations.delete_installed(company_id, automation_id)
            return {
                "status": "ok" if ok else "warning",
                "summary": f"Silme: {ok}",
                "metrics": {"deleted": ok},
                "result": {"deleted": ok},
                "recommendations": [],
            }

        return {
            "status": "error",
            "summary": f"Bilinmeyen action: {action}",
            "metrics": {},
            "recommendations": ["action: list | install | trigger | delete"],
        }
