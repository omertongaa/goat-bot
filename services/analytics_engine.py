"""Analytics engine service — business metrics, competitor data, market insights."""

import json
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"


def gather_pipeline_metrics(log=None):
    """Gather all internal pipeline metrics from reports and data files."""
    metrics = {
        "leads": {"total": 0, "qualified": 0, "hot": 0, "warm": 0, "cold": 0, "with_email": 0, "with_website": 0},
        "deals": {"total": 0, "won": 0, "lost": 0, "open": 0, "won_value": 0, "pipeline_value": 0, "win_rate": 0},
        "campaigns": {"total": 0},
        "proposals": {"total": 0},
        "audits": {"total": 0, "avg_score": 0},
    }

    # Lead metrics
    reports_dir = OUTPUT_DIR / "reports"
    scout_report = reports_dir / "scout_leads_report.json"
    if scout_report.exists():
        with open(scout_report) as f:
            data = json.load(f)
            m = data.get("metrics", {})
            metrics["leads"]["total"] = m.get("total_found", 0)
            metrics["leads"]["with_email"] = m.get("with_email", 0)
            metrics["leads"]["with_website"] = m.get("with_website", 0)

    filter_report = reports_dir / "filter_qualified_report.json"
    if filter_report.exists():
        with open(filter_report) as f:
            data = json.load(f)
            m = data.get("metrics", {})
            metrics["leads"]["qualified"] = m.get("total_scored", 0)
            metrics["leads"]["hot"] = m.get("hot", 0)
            metrics["leads"]["warm"] = m.get("warm", 0)
            metrics["leads"]["cold"] = m.get("cold", 0)

    # Deal metrics
    deals_path = DATA_DIR / "pipeline" / "deals.json"
    if deals_path.exists():
        with open(deals_path) as f:
            deals = json.load(f)
            metrics["deals"]["total"] = len(deals)
            metrics["deals"]["won"] = sum(1 for d in deals if d.get("status") == "won")
            metrics["deals"]["lost"] = sum(1 for d in deals if d.get("status") == "lost")
            metrics["deals"]["open"] = sum(1 for d in deals if d.get("status") in ("proposal", "negotiation"))
            metrics["deals"]["won_value"] = sum(d.get("value", 0) for d in deals if d.get("status") == "won")
            metrics["deals"]["pipeline_value"] = sum(d.get("value", 0) for d in deals if d.get("status") in ("proposal", "negotiation"))
            closed = metrics["deals"]["won"] + metrics["deals"]["lost"]
            if closed > 0:
                metrics["deals"]["win_rate"] = round(metrics["deals"]["won"] / closed * 100)

    # Campaign count
    campaigns_dir = DATA_DIR / "campaigns"
    if campaigns_dir.exists():
        metrics["campaigns"]["total"] = len(list(campaigns_dir.glob("*.json")))

    # Proposal count
    proposals_dir = DATA_DIR / "proposals"
    if proposals_dir.exists():
        metrics["proposals"]["total"] = len(list(proposals_dir.glob("*.md")))

    # Audit metrics
    audits_dir = DATA_DIR / "audits"
    if audits_dir.exists():
        audit_files = list(audits_dir.glob("*.json"))
        metrics["audits"]["total"] = len(audit_files)
        scores = []
        for af in audit_files[:10]:
            try:
                with open(af) as f:
                    ad = json.load(f)
                    if "overall_score" in ad:
                        scores.append(ad["overall_score"])
                    elif "results" in ad:
                        for r in ad["results"]:
                            if "overall_score" in r:
                                scores.append(r["overall_score"])
            except Exception:
                pass
        if scores:
            metrics["audits"]["avg_score"] = round(sum(scores) / len(scores), 1)

    if log:
        log(f"Gathered metrics: {metrics['leads']['total']} leads, {metrics['deals']['total']} deals")

    return metrics


def calculate_conversion_funnel(log=None):
    """Calculate conversion rates across the pipeline."""
    metrics = gather_pipeline_metrics()

    total_leads = metrics["leads"]["total"]
    qualified = metrics["leads"]["qualified"]
    hot = metrics["leads"]["hot"]
    deals_total = metrics["deals"]["total"]
    deals_won = metrics["deals"]["won"]

    funnel = {
        "stages": [
            {"name": "Leads Found", "count": total_leads, "rate": 100},
            {"name": "Qualified", "count": qualified, "rate": round(qualified / total_leads * 100) if total_leads > 0 else 0},
            {"name": "Hot Leads", "count": hot, "rate": round(hot / total_leads * 100) if total_leads > 0 else 0},
            {"name": "Deals Created", "count": deals_total, "rate": round(deals_total / hot * 100) if hot > 0 else 0},
            {"name": "Deals Won", "count": deals_won, "rate": round(deals_won / deals_total * 100) if deals_total > 0 else 0},
        ],
        "overall_conversion": round(deals_won / total_leads * 100, 2) if total_leads > 0 else 0,
    }

    if log:
        log(f"Funnel: {total_leads} → {qualified} → {hot} → {deals_total} → {deals_won}")

    return funnel


def generate_weekly_summary(log=None):
    """Generate a weekly performance summary."""
    metrics = gather_pipeline_metrics()
    funnel = calculate_conversion_funnel()

    summary = {
        "period": "Son 7 gün",
        "generated_at": datetime.now().isoformat(),
        "highlights": [],
        "metrics": metrics,
        "funnel": funnel,
    }

    # Generate highlights
    if metrics["leads"]["total"] > 0:
        summary["highlights"].append(f"{metrics['leads']['total']} lead bulundu")
    if metrics["leads"]["hot"] > 0:
        summary["highlights"].append(f"{metrics['leads']['hot']} hot lead — hemen ulaşın")
    if metrics["deals"]["won_value"] > 0:
        summary["highlights"].append(f"${metrics['deals']['won_value']} kazanıldı")
    if metrics["deals"]["pipeline_value"] > 0:
        summary["highlights"].append(f"${metrics['deals']['pipeline_value']} pipeline'da")

    if not summary["highlights"]:
        summary["highlights"].append("Henüz veri yok — Scout agent ile başlayın")

    if log:
        log(f"Weekly summary generated: {len(summary['highlights'])} highlights")

    return summary
