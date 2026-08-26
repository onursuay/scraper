"""Email Marketing — Flask Blueprint (sayfa + API route'ları)."""
from flask import Blueprint, render_template, request, jsonify
from .campaigns import (
    list_campaigns, get_campaign, create_campaign, update_campaign,
    launch_campaign, cancel_campaign,
    get_campaign_stats, get_recent_events, get_enrollments,
    get_overview_stats, get_steps, save_steps, enroll_lead,
)
from .segments import load_leads, count_source

marketing_bp = Blueprint("marketing", __name__)

# ─── SAYFA ROUTE'LARI ────────────────────────────────────────────────────────

@marketing_bp.route("/marketing")
@marketing_bp.route("/pazarlama")
def marketing_index():
    return render_template("marketing_index.html")


@marketing_bp.route("/marketing/campaigns/new")
@marketing_bp.route("/pazarlama/kampanyalar/yeni")
def marketing_campaign_new():
    from dashboard import SECTORS  # kampanya wizard sektör listesi için
    sectors = list(SECTORS.keys())
    return render_template("marketing_campaign_new.html", sectors=sectors)


@marketing_bp.route("/marketing/campaigns/<cid>")
@marketing_bp.route("/pazarlama/kampanyalar/<cid>")
def marketing_campaign_detail(cid):
    return render_template("marketing_campaign_detail.html", campaign_id=cid)


# ─── API: GENEL ──────────────────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/stats")
def api_marketing_stats():
    return jsonify(get_overview_stats())


@marketing_bp.route("/api/marketing/segment/preview")
def api_segment_preview():
    """Filtre parametrelerine göre kaç lead eşleştiğini döndür."""
    source = request.args.get("source", "scanner")
    f = {
        "source":    source,
        "sector":    request.args.get("sector", ""),
        "city":      request.args.get("city", ""),
        "date_from": request.args.get("date_from", ""),
        "date_to":   request.args.get("date_to", ""),
    }
    try:
        leads = load_leads(f)
        return jsonify({"count": len(leads)})
    except Exception as e:
        return jsonify({"count": 0, "error": str(e)})


@marketing_bp.route("/api/marketing/segment/counts")
def api_segment_counts():
    """Her kaynak için toplam e-postalı lead sayısını döndür."""
    try:
        return jsonify({
            "scanner": count_source("scanner"),
            "import":  count_source("import"),
        })
    except Exception as e:
        return jsonify({"scanner": 0, "import": 0, "error": str(e)})


# ─── API: KAMPANYALAR ────────────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/campaigns", methods=["GET"])
def api_campaigns_list():
    return jsonify(list_campaigns())


@marketing_bp.route("/api/marketing/campaigns", methods=["POST"])
def api_campaigns_create():
    data = request.json or {}
    if not data.get("name"):
        return jsonify({"error": "Kampanya adı zorunlu"}), 400
    if data.get("type") not in ("broadcast", "sequence"):
        return jsonify({"error": "Tür broadcast veya sequence olmalı"}), 400
    campaign = create_campaign(data)
    return jsonify(campaign), 201


@marketing_bp.route("/api/marketing/campaigns/<cid>", methods=["GET"])
def api_campaign_get(cid):
    campaign = get_campaign(cid)
    if not campaign:
        return jsonify({"error": "Bulunamadı"}), 404
    campaign["steps"] = get_steps(cid)
    return jsonify(campaign)


@marketing_bp.route("/api/marketing/campaigns/<cid>", methods=["PATCH"])
def api_campaign_update(cid):
    data = request.json or {}
    updated = update_campaign(cid, data)
    if data.get("steps") is not None:
        save_steps(cid, data["steps"])
    return jsonify(updated)


@marketing_bp.route("/api/marketing/campaigns/<cid>/launch", methods=["POST"])
def api_campaign_launch(cid):
    result = launch_campaign(cid)
    if result.get("error"):
        return jsonify(result), 400
    return jsonify(result)


@marketing_bp.route("/api/marketing/campaigns/<cid>/cancel", methods=["POST"])
def api_campaign_cancel(cid):
    return jsonify(cancel_campaign(cid))


# ─── API: İSTATİSTİK & EVENTS ────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/campaigns/<cid>/stats")
def api_campaign_stats(cid):
    return jsonify(get_campaign_stats(cid))


@marketing_bp.route("/api/marketing/campaigns/<cid>/events")
def api_campaign_events(cid):
    limit = min(int(request.args.get("limit", 50)), 200)
    return jsonify(get_recent_events(cid, limit))


# ─── API: ENROLLMENTS (Faz 3) ────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/campaigns/<cid>/enrollments")
def api_campaign_enrollments(cid):
    return jsonify(get_enrollments(cid))


@marketing_bp.route("/api/marketing/campaigns/<cid>/enroll", methods=["POST"])
def api_campaign_enroll(cid):
    data = request.json or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "E-posta zorunlu"}), 400
    ok = enroll_lead(cid, email, data.get("name", ""), data.get("lead_data"))
    return jsonify({"ok": ok})


# ─── TEST MAİL GÖNDERİMİ ─────────────────────────────────────────────────────

@marketing_bp.route("/api/marketing/test-send", methods=["POST"])
def api_test_send():
    """Wizard'dan kullanıcının kendisine örnek değerlerle test maili gönderir."""
    import os
    import requests as _req
    from .campaigns import _render
    from .queue import _email_footer
    from .unsub import generate_token

    data = request.json or {}
    to_email   = (data.get("to_email") or "").strip()
    subject    = data.get("subject") or ""
    body_html  = data.get("body_html") or ""
    source     = data.get("source") or "scanner"

    if not to_email or "@" not in to_email:
        return jsonify({"error": "Geçerli bir e-posta giriniz."}), 400
    if not subject.strip() or not body_html.strip():
        return jsonify({"error": "Konu ve içerik boş olamaz."}), 400

    # Örnek lead — gerçek kampanya değişkenleriyle aynı isimler
    if source == "scanner":
        sample_lead = {
            "name":   "Örnek Teknoloji A.Ş.",
            "email":  to_email,
            "sector": "Teknoloji",
            "city":   "İstanbul",
            "domain": "ornek.com",
        }
    else:
        sample_lead = {
            "name":       "Ahmet Yılmaz",
            "first_name": "Ahmet",
            "last_name":  "Yılmaz",
            "email":      to_email,
            "city":       "İstanbul",
        }

    rendered_subject = "[TEST] " + _render(subject, sample_lead)
    rendered_body    = _render(body_html, sample_lead)

    api_key    = os.getenv("RESEND_API_KEY", "")
    from_name  = os.getenv("FROM_NAME", "DijiMagic")
    from_email = os.getenv("FROM_EMAIL", "info@dijimagic.com")
    base_url   = os.getenv("APP_BASE_URL", "https://scanner.onursuay.com")

    if not api_key:
        return jsonify({"error": "RESEND_API_KEY tanımlı değil — test gönderilemez."}), 500

    unsub_url = f"{base_url}/unsubscribe?token={generate_token(to_email)}"
    final_html = rendered_body + _email_footer(unsub_url)

    try:
        resp = _req.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{from_name} <{from_email}>",
                "to": [to_email],
                "subject": rendered_subject,
                "html": final_html,
            },
            timeout=15,
        )
        if resp.status_code == 200:
            return jsonify({"ok": True, "message_id": resp.json().get("id", "")})
        return jsonify({"error": resp.json().get("message", resp.text)[:300]}), 502
    except Exception as e:
        return jsonify({"error": str(e)[:300]}), 500
