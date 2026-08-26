"""Günlük rapor: istatistikleri topla ve admin'e Resend ile gönder."""
import logging
import os
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def build_daily_report() -> dict:
    """Bugünkü tüm aktiviteleri Supabase'den topla."""
    from .db import sb_select

    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    since = today_start.isoformat()

    # ── Email queue (bugün) ──
    try:
        queue_today = sb_select("email_queue", {
            "created_at": f"gte.{since}",
            "select":     "status",
        })
    except Exception:
        queue_today = []

    q = {}
    for item in queue_today:
        s = item.get("status", "unknown")
        q[s] = q.get(s, 0) + 1

    sent_today    = q.get("sent", 0)
    pending_today = q.get("pending", 0) + q.get("sending", 0)
    failed_today  = q.get("failed", 0)

    # ── Email events (bugün) ──
    try:
        events_today = sb_select("email_events", {
            "occurred_at": f"gte.{since}",
            "select":      "event_type",
        })
    except Exception:
        events_today = []

    ev = {}
    for e in events_today:
        t = e.get("event_type", "")
        ev[t] = ev.get(t, 0) + 1

    delivered = ev.get("email.delivered", 0)
    opened    = ev.get("email.opened", 0)
    clicked   = ev.get("email.clicked", 0)
    bounced   = ev.get("email.bounced", 0)
    complained = ev.get("email.complained", 0)

    open_rate  = round(opened  / sent_today * 100, 1) if sent_today > 0 else 0
    click_rate = round(clicked / sent_today * 100, 1) if sent_today > 0 else 0

    # ── Kampanyalar ──
    try:
        campaigns_today = sb_select("campaigns", {
            "created_at": f"gte.{since}",
            "select":     "id,name,type,status",
        })
    except Exception:
        campaigns_today = []

    try:
        active_campaigns = sb_select("campaigns", {
            "status": "eq.running",
            "select": "id,name,type,trigger_type",
        })
    except Exception:
        active_campaigns = []

    auto_campaigns = [c for c in active_campaigns if c.get("trigger_type") == "lead_created"]

    # ── Yeni enrollment (bugün) ──
    try:
        enrollments_today = sb_select("campaign_enrollments", {
            "enrolled_at": f"gte.{since}",
            "select":      "id",
        })
    except Exception:
        enrollments_today = []

    # ── Suppression ──
    try:
        suppressions_today = sb_select("email_suppressions", {
            "created_at": f"gte.{since}",
            "select":     "email,reason",
        })
        total_suppressions = sb_select("email_suppressions", {"select": "email"})
    except Exception:
        suppressions_today = []
        total_suppressions = []

    return {
        "date":              today_start.strftime("%d %B %Y"),
        "day_of_week":       today_start.strftime("%A"),
        # mail
        "sent_today":        sent_today,
        "pending_today":     pending_today,
        "failed_today":      failed_today,
        "delivered":         delivered,
        "opened":            opened,
        "clicked":           clicked,
        "bounced":           bounced,
        "complained":        complained,
        "open_rate":         open_rate,
        "click_rate":        click_rate,
        # kampanyalar
        "campaigns_created": len(campaigns_today),
        "campaigns_new":     campaigns_today,
        "active_campaigns":  len(active_campaigns),
        "auto_campaigns":    len(auto_campaigns),
        # enrollment
        "enrollments_today": len(enrollments_today),
        # suppression
        "unsub_today":       len(suppressions_today),
        "total_suppressed":  len(total_suppressions),
    }


def _render_report_html(data: dict) -> str:
    d = data
    date_str = d["date"]

    def stat_row(label, value, color="#1e293b"):
        return f"""
        <tr>
          <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;color:#64748b;font-size:14px;">{label}</td>
          <td style="padding:10px 0;border-bottom:1px solid #f1f5f9;text-align:right;font-size:16px;font-weight:700;color:{color};">{value}</td>
        </tr>"""

    def section(title, rows_html, icon_path=""):
        return f"""
        <tr><td style="padding:28px 40px 0;">
          <p style="margin:0 0 14px;color:#1e293b;font-size:16px;font-weight:700;border-bottom:2px solid #f1f5f9;padding-bottom:8px;">{title}</p>
          <table width="100%" cellpadding="0" cellspacing="0">{rows_html}</table>
        </td></tr>"""

    # Email stats section
    email_rows = (
        stat_row("Gönderilen",  d["sent_today"],   "#2563eb") +
        stat_row("Teslim",      d["delivered"],    "#16a34a") +
        stat_row("Açılan",      f"{d['opened']} ({d['open_rate']}%)",  "#0891b2") +
        stat_row("Tıklanan",    f"{d['clicked']} ({d['click_rate']}%)", "#7c3aed") +
        stat_row("Bekleyen",    d["pending_today"], "#64748b") +
        stat_row("Başarısız",   d["failed_today"],  "#dc2626" if d["failed_today"] > 0 else "#64748b") +
        stat_row("Bounce",      d["bounced"],       "#dc2626" if d["bounced"] > 0 else "#64748b") +
        stat_row("Şikayet",     d["complained"],    "#dc2626" if d["complained"] > 0 else "#64748b")
    )

    # Campaign section
    new_cmp_html = ""
    for c in d["campaigns_new"]:
        badge_color = "#7c3aed" if c.get("type") == "sequence" else "#2563eb"
        new_cmp_html += f'<li style="margin-bottom:4px;font-size:13px;color:#334155;"><span style="background:{badge_color}1a;color:{badge_color};padding:1px 7px;border-radius:10px;font-size:11px;font-weight:600;">{c.get("type","").capitalize()}</span> {c.get("name","")}</li>'

    new_cmp_section = f'<ul style="margin:10px 0 0;padding-left:16px;">{new_cmp_html}</ul>' if new_cmp_html else '<p style="font-size:13px;color:#94a3b8;margin:8px 0 0;">Bugün yeni kampanya oluşturulmadı.</p>'

    campaign_rows = (
        stat_row("Aktif Kampanya",   d["active_campaigns"], "#2563eb") +
        stat_row("Otomasyon Aktif",  d["auto_campaigns"],   "#f59e0b" if d["auto_campaigns"] > 0 else "#64748b") +
        stat_row("Yeni Enrollment",  d["enrollments_today"],"#16a34a")
    )

    # Suppression section
    supp_rows = (
        stat_row("Bugün Abonelik İptal", d["unsub_today"],      "#dc2626" if d["unsub_today"] > 0 else "#64748b") +
        stat_row("Toplam Suppression",   d["total_suppressed"], "#64748b")
    )

    status_color = "#16a34a" if d["sent_today"] > 0 else "#64748b"
    status_text  = "Aktif Gün" if d["sent_today"] > 0 else "Sakin Gün"

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:'Helvetica Neue',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:32px 16px;">
<tr><td align="center">
<table width="580" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:14px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.1);">

  <!-- Header -->
  <tr><td style="background:linear-gradient(135deg,#1e293b,#0f172a);padding:32px 40px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <p style="margin:0;color:#94a3b8;font-size:12px;text-transform:uppercase;letter-spacing:1px;">Günlük Rapor</p>
          <h1 style="margin:6px 0 0;color:#ffffff;font-size:22px;font-weight:800;">{date_str}</h1>
        </td>
        <td align="right">
          <span style="background:rgba(255,255,255,0.08);color:{status_color};border:1px solid {status_color}40;padding:6px 14px;border-radius:20px;font-size:12px;font-weight:700;">{status_text}</span>
        </td>
      </tr>
    </table>
  </td></tr>

  <!-- KPI bar -->
  <tr><td style="background:#f8fafc;padding:20px 40px;border-bottom:1px solid #e2e8f0;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="text-align:center;padding:0 8px;border-right:1px solid #e2e8f0;">
          <div style="font-size:28px;font-weight:800;color:#2563eb;">{d["sent_today"]}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">Gönderildi</div>
        </td>
        <td style="text-align:center;padding:0 8px;border-right:1px solid #e2e8f0;">
          <div style="font-size:28px;font-weight:800;color:#0891b2;">{d["open_rate"]}%</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">Açılma</div>
        </td>
        <td style="text-align:center;padding:0 8px;border-right:1px solid #e2e8f0;">
          <div style="font-size:28px;font-weight:800;color:#7c3aed;">{d["click_rate"]}%</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">Tıklanma</div>
        </td>
        <td style="text-align:center;padding:0 8px;">
          <div style="font-size:28px;font-weight:800;color:#f59e0b;">{d["active_campaigns"]}</div>
          <div style="font-size:11px;color:#64748b;margin-top:2px;">Aktif Kamp.</div>
        </td>
      </tr>
    </table>
  </td></tr>

  {section("📧 E-posta İstatistikleri", email_rows)}
  {section("🎯 Kampanyalar", campaign_rows)}

  <!-- New campaigns list -->
  <tr><td style="padding:0 40px;">
    <p style="margin:16px 0 4px;font-size:13px;color:#64748b;font-weight:600;">Bugün Oluşturulan Kampanyalar</p>
    {new_cmp_section}
  </td></tr>

  {section("🚫 Suppression", supp_rows)}

  <!-- Footer -->
  <tr><td style="background:#f8fafc;padding:24px 40px;border-top:1px solid #e2e8f0;margin-top:28px;">
    <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <strong style="color:#1e293b;font-size:14px;">DijiMagic — DijiScraper</strong><br>
          <span style="color:#94a3b8;font-size:12px;">Bu rapor her gün saat 20:00'da otomatik gönderilir.</span>
        </td>
        <td align="right">
          <a href="https://scanner.onursuay.com/marketing" style="color:#2563eb;text-decoration:none;font-size:13px;font-weight:600;">Panele Git →</a>
        </td>
      </tr>
    </table>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""


def send_daily_report():
    """Günlük raporu admin'e gönder."""
    import resend

    admin_email = os.getenv("ADMIN_EMAIL", "").strip()
    if not admin_email:
        logger.warning("send_daily_report: ADMIN_EMAIL env değişkeni tanımlı değil, rapor atlandı")
        return

    resend.api_key = os.getenv("RESEND_API_KEY", "")
    if not resend.api_key:
        logger.warning("send_daily_report: RESEND_API_KEY eksik")
        return

    try:
        data = build_daily_report()
        html = _render_report_html(data)
        from_name  = os.getenv("FROM_NAME", "DijiMagic")
        from_email = os.getenv("FROM_EMAIL", "info@dijimagic.com")

        resend.Emails.send({
            "from":    f"{from_name} <{from_email}>",
            "to":      [admin_email],
            "subject": f"📊 Günlük Rapor — {data['date']}",
            "html":    html,
        })
        logger.info(f"Günlük rapor gönderildi → {admin_email}")
    except Exception as e:
        logger.error(f"send_daily_report error: {e}")
