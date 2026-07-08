"""Data models for the outreach pipeline."""
from dataclasses import dataclass, field
import re


@dataclass
class Lead:
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    company: str = ""
    email: str = ""
    employees: int | None = None
    industry: str = ""
    person_linkedin: str = ""
    website: str = ""
    company_linkedin: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    annual_revenue: float | None = None
    row_index: int = 0  # 1-based sheet row (header = 1)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def has_valid_email(self) -> bool:
        return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", self.email))

    @staticmethod
    def _to_int(value: str) -> int | None:
        cleaned = re.sub(r"[^\d]", "", value or "")
        return int(cleaned) if cleaned else None

    @staticmethod
    def _to_float(value: str) -> float | None:
        cleaned = re.sub(r"[^\d.]", "", value or "")
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None

    @classmethod
    def from_row(cls, row: dict, row_index: int = 0) -> "Lead":
        get = lambda key: (row.get(key) or "").strip()
        industry = get("Industry").lower()
        # Guard against shifted rows: an industry cell holding a number or an
        # email address means the source row was misaligned.
        if re.fullmatch(r"[\d,]+", industry) or "@" in industry:
            industry = ""
        return cls(
            first_name=get("First Name"),
            last_name=get("Last Name"),
            title=get("Title"),
            company=get("Company"),
            email=get("Email"),
            employees=cls._to_int(get("# Employees")),
            industry=industry,
            person_linkedin=get("Person Linkedin Url"),
            website=get("Website"),
            company_linkedin=get("Company Linkedin Url"),
            city=get("City"),
            state=get("State"),
            country=get("Country"),
            annual_revenue=cls._to_float(get("Annual Revenue")),
            row_index=row_index,
        )


@dataclass
class ScoreBreakdown:
    icp_title: int = 0
    function: int = 0
    industry: int = 0
    scale: int = 0
    revenue: int = 0
    completeness: int = 0
    news_bonus: int = 0
    icp_tier: str = ""
    persona: str = ""
    news_signal: str = ""

    @property
    def total(self) -> int:
        return min(
            100,
            self.icp_title + self.function + self.industry + self.scale
            + self.revenue + self.completeness + self.news_bonus,
        )

    @property
    def grade(self) -> str:
        t = self.total
        if t >= 90:
            return "A - Hot"
        if t >= 75:
            return "B - Warm"
        if t >= 55:
            return "C - Nurture"
        return "D - Low"

    @property
    def enters_sequence(self) -> bool:
        return self.total >= 55


@dataclass
class Sequence:
    linkedin_connection: str = ""
    linkedin_followup_1: str = ""
    linkedin_followup_2: str = ""
    email_1_subject: str = ""
    email_1_body: str = ""
    email_2_subject: str = ""
    email_2_body: str = ""
    email_3_subject: str = ""
    email_3_body: str = ""


@dataclass
class ScoredLead:
    lead: Lead
    score: ScoreBreakdown
    sequence: Sequence = field(default_factory=Sequence)
    status: str = "Draft"  # Draft | Approved | Sent - Step 1/2/3 | Replied | Bounced | Do Not Contact
