"""TaskPlanner Agent — Natural language to agent pipeline orchestrator (Manus-style)."""

import json
import re
from datetime import datetime

from agents.base import BaseAgent, DATA_DIR, OUTPUT_DIR


class TaskPlannerAgent(BaseAgent):
    agent_id = "taskplanner"
    name = "TaskPlanner"
    role = "Understands natural language requests and orchestrates multi-agent pipelines automatically"
    category = "master"

    # Agent capability map for intelligent routing
    AGENT_CAPABILITIES = {
        "scout": {
            "triggers": ["lead bul", "müşteri bul", "işletme ara", "google maps", "lead", "find leads", "prospect"],
            "description": "Lead bulma",
            "needs": [],
            "provides": ["leads"],
        },
        "filter": {
            "triggers": ["puanla", "filtrele", "skorla", "qualify", "score", "nitelikli"],
            "description": "Lead puanlama",
            "needs": ["leads"],
            "provides": ["qualified_leads"],
        },
        "auditor": {
            "triggers": ["audit", "seo", "analiz et", "website kontrol", "site analiz"],
            "description": "Website analizi",
            "needs": ["leads"],
            "provides": ["audit_reports"],
        },
        "pitch": {
            "triggers": ["teklif", "proposal", "pitch", "teklif hazırla"],
            "description": "Teklif oluşturma",
            "needs": ["qualified_leads"],
            "provides": ["proposals"],
        },
        "outreach": {
            "triggers": ["email", "outreach", "ulaş", "kampanya", "cold email"],
            "description": "Email kampanyası",
            "needs": ["qualified_leads"],
            "provides": ["campaigns"],
        },
        "designer": {
            "triggers": ["tasarım", "görsel", "banner", "logo", "design", "sosyal medya görseli", "creative"],
            "description": "Görsel tasarım",
            "needs": [],
            "provides": ["designs"],
        },
        "videomaker": {
            "triggers": ["video script", "video plan", "storyboard", "reels", "tiktok içerik"],
            "description": "Video içerik planı",
            "needs": [],
            "provides": ["video_scripts"],
        },
        "videoproducer": {
            "triggers": ["video üret", "video render", "remotion", "mp4", "video oluştur", "ai video"],
            "description": "AI video üretimi",
            "needs": [],
            "provides": ["rendered_video"],
        },
        "youtube": {
            "triggers": ["youtube", "yükle", "upload", "seo optimize", "thumbnail", "shorts"],
            "description": "YouTube yönetimi",
            "needs": [],
            "provides": ["youtube_metadata"],
        },
        "content": {
            "triggers": ["blog", "yazı", "içerik", "newsletter", "makale", "copy", "metin"],
            "description": "İçerik yazımı",
            "needs": [],
            "provides": ["content"],
        },
        "presenter": {
            "triggers": ["sunum", "presentation", "slayt", "pitch deck"],
            "description": "Sunum oluşturma",
            "needs": [],
            "provides": ["presentation"],
        },
        "brandkit": {
            "triggers": ["marka", "brand", "kimlik", "renk paleti", "font"],
            "description": "Marka kimliği",
            "needs": [],
            "provides": ["brand_kit"],
        },
        "admanager": {
            "triggers": ["reklam", "ads", "google ads", "meta ads", "kampanya planı", "reklam bütçe"],
            "description": "Reklam kampanyası",
            "needs": [],
            "provides": ["ad_campaigns"],
        },
        "social": {
            "triggers": ["sosyal medya", "instagram", "linkedin", "hashtag", "sosyal strateji"],
            "description": "Sosyal medya yönetimi",
            "needs": [],
            "provides": ["social_strategy"],
        },
        "analytics": {
            "triggers": ["analiz", "rakip", "pazar", "swot", "trend", "rapor", "performans"],
            "description": "İş analizi",
            "needs": [],
            "provides": ["analysis"],
        },
        "sitebuilder": {
            "triggers": ["site", "landing page", "website", "web sitesi"],
            "description": "Website oluşturma",
            "needs": [],
            "provides": ["website"],
        },
    }

    # Common pipeline templates
    PIPELINE_TEMPLATES = {
        "full_outreach": {
            "name": "Tam Müşteri Kazanım",
            "description": "Lead bul → puanla → audit → teklif → email",
            "agents": ["scout", "filter", "auditor", "pitch", "outreach"],
        },
        "content_campaign": {
            "name": "İçerik Kampanyası",
            "description": "Blog + sosyal medya + görsel + video",
            "agents": ["content", "social", "designer", "videomaker"],
        },
        "brand_launch": {
            "name": "Marka Lansmanı",
            "description": "Marka kimliği + website + sosyal medya + içerik",
            "agents": ["brandkit", "sitebuilder", "social", "content", "designer"],
        },
        "video_campaign": {
            "name": "Video Kampanyası",
            "description": "Script → üretim → YouTube optimize → sosyal paylaşım",
            "agents": ["videomaker", "videoproducer", "youtube", "social"],
        },
        "ad_campaign": {
            "name": "Reklam Kampanyası",
            "description": "Analiz → reklam planı → görsel → landing page",
            "agents": ["analytics", "admanager", "designer", "sitebuilder"],
        },
        "market_entry": {
            "name": "Pazara Giriş",
            "description": "Pazar araştırma → rakip analiz → marka → strateji",
            "agents": ["analytics", "brandkit", "social", "content", "sitebuilder"],
        },
    }

    def run(self, action: str = "plan", message: str = "", pipeline: str = "",
            auto_execute: bool = False) -> dict:
        self.log("TaskPlanner agent started")

        if action == "plan":
            return self._plan_from_message(message, auto_execute)
        elif action == "template":
            return self._use_template(pipeline, auto_execute)
        elif action == "templates":
            return self._list_templates()
        elif action == "execute":
            return self._execute_pipeline(message)
        else:
            return self._plan_from_message(message, auto_execute)

    def _plan_from_message(self, message, auto_execute):
        """Parse natural language and create an agent pipeline."""
        if not message:
            return {
                "status": "error",
                "summary": "Mesaj gerekli — ne yapmak istediğinizi yazın",
                "metrics": {},
                "recommendations": [
                    "Örnek: 'İstanbul restoranları için müşteri bul ve teklif hazırla'",
                    "Örnek: 'YouTube kanalım için 30 günlük içerik planı yap'",
                    "Örnek: 'Marka kimliği oluştur ve landing page yap'",
                ],
            }

        self.log(f"Planning from message: {message[:100]}")

        # Step 1: Try Claude for intelligent planning
        prompt = f"""Sen bir AI otomasyon orkestratörüsün. Kullanıcının isteğini analiz et ve hangi agentların hangi sırayla çalışması gerektiğini belirle.

Kullanıcı isteği: "{message}"

Mevcut agentlar:
{json.dumps({k: v['description'] for k, v in self.AGENT_CAPABILITIES.items()}, indent=2, ensure_ascii=False)}

Hazır pipeline şablonları:
{json.dumps({k: v['description'] for k, v in self.PIPELINE_TEMPLATES.items()}, indent=2, ensure_ascii=False)}

Aşağıdaki JSON formatında cevap ver:
```json
{{
  "understood_task": "Kullanıcının ne istediğinin kısa özeti",
  "pipeline": ["agent1", "agent2", "agent3"],
  "params": {{
    "agent1": {{"param": "value"}},
    "agent2": {{"param": "value"}}
  }},
  "explanation": "Neden bu sırayı seçtiğinin kısa açıklaması",
  "estimated_time": "Tahmini süre",
  "warnings": ["Varsa uyarılar"]
}}
```

Sadece JSON döndür."""

        plan = self.call_claude(prompt)
        parsed_plan = self._parse_plan(plan, message)

        # Step 2: If Claude failed, use keyword matching
        if not parsed_plan.get("pipeline"):
            parsed_plan = self._keyword_plan(message)

        # Step 3: Auto-execute if requested
        execution_results = None
        if auto_execute and parsed_plan.get("pipeline"):
            execution_results = self._run_pipeline(parsed_plan)

        # Save plan
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        plan_data = {
            "message": message,
            "plan": parsed_plan,
            "auto_executed": auto_execute,
            "execution_results": execution_results,
            "created_at": timestamp,
        }
        self.save_data(f"plans/{timestamp}_plan.json", plan_data)

        results = {
            "status": "ok",
            "summary": parsed_plan.get("understood_task", f"Pipeline: {' → '.join(parsed_plan.get('pipeline', []))}"),
            "metrics": {
                "agents_planned": len(parsed_plan.get("pipeline", [])),
                "auto_executed": auto_execute,
                "pipeline": parsed_plan.get("pipeline", []),
                "timestamp": datetime.now().isoformat(),
            },
            "plan": parsed_plan,
            "execution": execution_results,
            "recommendations": [
                f"Pipeline: {' → '.join(parsed_plan.get('pipeline', []))}",
                parsed_plan.get("explanation", ""),
                "auto_execute: true ile otomatik çalıştırabilirsiniz",
            ],
        }

        self.save_output("taskplanner_report.json", results)
        self.log(f"Plan created: {len(parsed_plan.get('pipeline', []))} agents")
        return results

    def _keyword_plan(self, message):
        """Fallback: match agents by keywords in the message."""
        msg_lower = message.lower()
        matched = []

        for agent_id, info in self.AGENT_CAPABILITIES.items():
            for trigger in info["triggers"]:
                if trigger in msg_lower:
                    if agent_id not in matched:
                        matched.append(agent_id)
                    break

        # If we matched some agents, sort by dependency
        if matched:
            matched = self._sort_by_dependency(matched)

        # Extract params from message
        params = self._extract_params(message)

        return {
            "understood_task": f"Tespit edilen görevler: {', '.join(self.AGENT_CAPABILITIES[a]['description'] for a in matched)}" if matched else "Görev anlaşılamadı",
            "pipeline": matched,
            "params": params,
            "explanation": "Anahtar kelime eşleştirmesi ile planlandı",
            "estimated_time": f"~{len(matched) * 2} dakika",
            "warnings": [] if matched else ["Görev anlaşılamadı — daha spesifik yazın"],
        }

    def _sort_by_dependency(self, agents):
        """Sort agents by their dependency order."""
        priority = {
            "scout": 1, "filter": 2, "auditor": 3,
            "analytics": 1, "brandkit": 2,
            "content": 3, "designer": 3, "videomaker": 3,
            "pitch": 4, "admanager": 4, "social": 4,
            "sitebuilder": 5, "videoproducer": 5,
            "outreach": 6, "youtube": 6,
            "presenter": 7,
        }
        return sorted(agents, key=lambda a: priority.get(a, 5))

    def _extract_params(self, message):
        """Extract common parameters from natural language."""
        params = {}
        msg_lower = message.lower()

        # Location extraction
        cities = ["istanbul", "ankara", "izmir", "antalya", "bursa", "adana", "konya"]
        for city in cities:
            if city in msg_lower:
                params["scout"] = params.get("scout", {})
                params["scout"]["location"] = city.title()

        # Industry/query extraction
        industries = ["restoran", "klinik", "otel", "kuaför", "spor", "emlak", "cafe", "avukat", "diş"]
        for ind in industries:
            if ind in msg_lower:
                params["scout"] = params.get("scout", {})
                params["scout"]["query"] = ind

        # Platform extraction
        platforms = ["instagram", "youtube", "tiktok", "linkedin", "facebook", "twitter"]
        for plat in platforms:
            if plat in msg_lower:
                params["social"] = params.get("social", {})
                params["social"]["platform"] = plat
                params["designer"] = params.get("designer", {})
                params["designer"]["platform"] = plat

        return params

    def _parse_plan(self, response, message):
        """Parse Claude's JSON response into a plan."""
        if not response:
            return {}
        try:
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                plan = json.loads(json_match.group())
                if isinstance(plan.get("pipeline"), list):
                    # Validate agent IDs
                    plan["pipeline"] = [a for a in plan["pipeline"] if a in self.AGENT_CAPABILITIES]
                    return plan
        except (json.JSONDecodeError, AttributeError):
            pass
        return {}

    def _run_pipeline(self, plan):
        """Execute the planned pipeline sequentially."""
        results = {}
        pipeline = plan.get("pipeline", [])
        params = plan.get("params", {})

        self.log(f"Executing pipeline: {' → '.join(pipeline)}")

        for agent_id in pipeline:
            try:
                from app import get_agent_instance
                agent = get_agent_instance(agent_id)
                agent_params = params.get(agent_id, {})

                self.log(f"Running {agent_id}...")
                result = agent.run(**agent_params) if agent_params else agent.run()
                results[agent_id] = {"status": result.get("status", "ok"), "summary": result.get("summary", "")}
                self.log(f"{agent_id}: {result.get('status', 'ok')}")

            except Exception as e:
                results[agent_id] = {"status": "error", "summary": str(e)[:200]}
                self.log(f"{agent_id} failed: {e}")

        return results

    def _use_template(self, pipeline_name, auto_execute):
        """Use a predefined pipeline template."""
        template = self.PIPELINE_TEMPLATES.get(pipeline_name)
        if not template:
            return {
                "status": "error",
                "summary": f"Template bulunamadı: {pipeline_name}",
                "metrics": {},
                "recommendations": [f"Mevcut: {', '.join(self.PIPELINE_TEMPLATES.keys())}"],
            }

        plan = {
            "understood_task": template["description"],
            "pipeline": template["agents"],
            "params": {},
            "explanation": f"Şablon: {template['name']}",
            "estimated_time": f"~{len(template['agents']) * 2} dakika",
            "warnings": [],
        }

        execution_results = None
        if auto_execute:
            execution_results = self._run_pipeline(plan)

        return {
            "status": "ok",
            "summary": f"{template['name']}: {' → '.join(template['agents'])}",
            "metrics": {"template": pipeline_name, "agents": len(template["agents"])},
            "plan": plan,
            "execution": execution_results,
            "recommendations": [],
        }

    def _list_templates(self):
        """List all available pipeline templates."""
        templates = []
        for tid, t in self.PIPELINE_TEMPLATES.items():
            templates.append({
                "id": tid,
                "name": t["name"],
                "description": t["description"],
                "agents": t["agents"],
                "agent_count": len(t["agents"]),
            })

        return {
            "status": "ok",
            "summary": f"{len(templates)} hazır pipeline şablonu",
            "metrics": {"templates": len(templates)},
            "templates": templates,
            "recommendations": ["template action ile şablon çalıştırabilirsiniz"],
        }
