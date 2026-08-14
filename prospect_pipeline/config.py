from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE lines, '#' comments, no shell expansion."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_app_password: str
    sender_name: str
    sender_company: str
    sender_postal_address: str
    max_per_run: int
    per_state_cap: int
    cooldown_days: int
    send_delay_seconds: float
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_from: str
    leads_csv: Path
    template_path: Path
    whatsapp_template_path: Path
    state_dir: Path
    outbox_dir: Path
    reports_dir: Path
    auto_send: bool

    @classmethod
    def from_env(cls, root: Path = ROOT) -> "Settings":
        load_dotenv(root / ".env")
        env = os.environ
        auto_send_raw = env.get("AUTO_SEND", "false").strip().lower()
        return cls(
            smtp_host=env.get("SMTP_HOST", "smtp.gmail.com"),
            smtp_port=int(env.get("SMTP_PORT", "587")),
            smtp_user=env.get("SMTP_USER", ""),
            smtp_app_password=env.get("SMTP_APP_PASSWORD", ""),
            sender_name=env.get("SENDER_NAME", ""),
            sender_company=env.get("SENDER_COMPANY", ""),
            sender_postal_address=env.get("SENDER_POSTAL_ADDRESS", ""),
            max_per_run=int(env.get("MAX_PER_RUN", "50")),
            per_state_cap=int(env.get("PER_STATE_CAP", "5")),
            cooldown_days=int(env.get("COOLDOWN_DAYS", "30")),
            send_delay_seconds=float(env.get("SEND_DELAY_SECONDS", "3")),
            twilio_account_sid=env.get("TWILIO_ACCOUNT_SID", ""),
            twilio_auth_token=env.get("TWILIO_AUTH_TOKEN", ""),
            twilio_whatsapp_from=env.get("TWILIO_WHATSAPP_FROM", ""),
            leads_csv=root / env.get("LEADS_CSV", "data/leads.csv"),
            template_path=root / "prospect_pipeline" / "templates" / "outreach_email.txt",
            whatsapp_template_path=root / "prospect_pipeline" / "templates" / "outreach_whatsapp.txt",
            state_dir=root / "state",
            outbox_dir=root / "outbox",
            reports_dir=root / "reports",
            auto_send=auto_send_raw in {"1", "true", "yes", "on"},
        )

    def missing_for_send(self) -> list[str]:
        missing = []
        if not self.smtp_user:
            missing.append("SMTP_USER (Gmail address used to send)")
        if not self.smtp_app_password:
            missing.append("SMTP_APP_PASSWORD (Gmail app password, not the login password)")
        if not self.sender_name:
            missing.append("SENDER_NAME")
        if not self.sender_postal_address:
            missing.append("SENDER_POSTAL_ADDRESS (CAN-SPAM requires a real postal address in every email)")
        return missing

    def missing_for_whatsapp(self) -> list[str]:
        missing = []
        if not self.sender_name:
            missing.append("SENDER_NAME")
        if not self.twilio_account_sid:
            missing.append("TWILIO_ACCOUNT_SID")
        if not self.twilio_auth_token:
            missing.append("TWILIO_AUTH_TOKEN")
        if not self.twilio_whatsapp_from:
            missing.append("TWILIO_WHATSAPP_FROM (your Twilio WhatsApp-enabled number, E.164)")
        return missing

    @property
    def whatsapp_sent_log_path(self) -> Path:
        return self.state_dir / "whatsapp_sent_log.csv"

    @property
    def sent_log_path(self) -> Path:
        return self.state_dir / "sent_log.csv"

    @property
    def suppression_path(self) -> Path:
        return self.state_dir / "suppression_list.txt"
