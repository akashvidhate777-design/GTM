#!/usr/bin/env python3
"""Generate a clean two-page PDF CV for Akassh Vidhatey."""

from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).with_name("Akassh_Vidhatey_AI_Automation_Specialist_CV.pdf")


FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


class CVPDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font("DejaVu", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"{self.page_no()}", align="C")


def section_title(pdf: CVPDF, title: str):
    pdf.ln(2)
    pdf.set_font("DejaVu", "B", 11)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 7, title.upper(), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(40, 40, 40)
    pdf.set_line_width(0.4)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(3)


def body(pdf: CVPDF, text: str, size: float = 9.5):
    pdf.set_font("DejaVu", "", size)
    pdf.set_text_color(35, 35, 35)
    pdf.multi_cell(0, 4.4, text)
    pdf.ln(1)


def bullet(pdf: CVPDF, text: str):
    pdf.set_font("DejaVu", "", 9.5)
    pdf.set_text_color(35, 35, 35)
    x = pdf.l_margin
    pdf.set_x(x)
    pdf.cell(4, 4.4, "•")
    pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 4, 4.4, text)
    pdf.ln(0.6)


def job_header(pdf: CVPDF, title: str, dates: str):
    pdf.set_font("DejaVu", "B", 10)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "I", 9)
    pdf.set_text_color(70, 70, 70)
    pdf.cell(0, 4.5, dates, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(0.5)


def main():
    pdf = CVPDF(format="A4")
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_font("DejaVu", "I", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(14, 12, 14)
    pdf.add_page()

    # Header
    pdf.set_font("DejaVu", "B", 18)
    pdf.set_text_color(15, 15, 15)
    pdf.cell(0, 8, "AKASSH VIDHATEY", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "B", 10.5)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(
        0,
        5.5,
        "AI & Automation Specialist | CRM Systems, Workflows & Client Implementation",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_font("DejaVu", "", 8.5)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(
        0,
        4,
        "Pune, India (Remote — overlaps US/EU hours)  •  +91 96230 11124  •  "
        "akashvidhate777@gmail.com  •  linkedin.com/in/akasshvidhatey",
    )
    pdf.ln(1)

    section_title(pdf, "Summary")
    body(
        pdf,
        "AI & automation specialist with 7.5+ years designing, building, and scaling "
        "intelligent systems that power internal operations and client success. I architect "
        "multi-step automation workflows, integrate CRMs with email, enrichment, calendars, "
        "and collaboration tools via APIs and webhooks, and translate complex systems into "
        "clear SOPs and stakeholder-ready explanations. Recent work: an n8n + Apollo + Zoho "
        "CRM enrichment pipeline that cut hygiene effort 80%+, a 12-agent outbound suite that "
        "reduced content production effort 70%, and an AI growth stack that delivered 3× team "
        "productivity with ~30% lower operating cost. High-ownership operator comfortable in "
        "fast-moving environments — n8n, Make, Zapier, Zoho CRM, HubSpot, Apollo, Google Sheets, "
        "and LLM orchestration.",
    )

    section_title(pdf, "Selected AI & Automation Systems (Built & Shipped)")
    systems = [
        "CRM Enrichment & Hygiene Pipeline — n8n + Apollo + Zoho CRM automation via APIs/webhooks; eliminated manual data entry and reduced CRM hygiene effort 80%+.",
        "Multi-Step Lead Gen & Nurture Workflows — end-to-end sequences connecting enrichment, CRM stages, email outreach, and sales handoff; 40% faster discovery-call bookings and 30% lift in MQL→SQL conversion.",
        "12-Vertical Outbound Agent Suite — custom AI agents mapped to ICPs, verticals, and regions for personalized multi-channel outreach at scale; 70% reduction in content production effort.",
        "Account Research Automation — Gemini + NotebookLM workflow automating enterprise account profiling; 600× faster than manual research (20 hrs → <2 min).",
        "Competitive Intelligence Bot — real-time market-tracking automation feeding battle cards and talk tracks to reps; 80% cut in deal-prep time.",
        "GTM AI Operations Stack — AI-first automation across campaigns, email, lead gen, ads, and collateral; 3× productivity uplift, ~30% lower operating cost.",
    ]
    for s in systems:
        bullet(pdf, s)

    section_title(pdf, "Experience")
    job_header(
        pdf,
        "Lead — Growth Marketing & AI Strategy, Groupsoft US Inc / Compliance Cart",
        "May 2025 – Present  |  Remote  |  SAP consulting & proprietary AI product firm",
    )
    body(
        pdf,
        "Owned org-wide AI and automation systems across marketing, presales, and sales operations.",
        size=9,
    )
    for b in [
        "Designed and deployed scalable automation workflows (n8n, Zapier, Apollo, Zoho CRM, Slack, Google AI Studio) integrating CRM, enrichment, messaging, and outreach — ~30% lower operational cost.",
        "Built multi-step lead generation, nurturing, and sales-process workflows that drove 30% pipeline growth and 3× team productivity.",
        "Architected CRM pipelines and micro-automations for account research, enrichment, and handoff — improved data reliability and reduced manual ops.",
        "Translated complex AI/automation systems into SOPs, enablement kits, and plain-language guidance for founders, sales, and non-technical stakeholders.",
        "Partnered with leadership to audit and improve existing GTM systems for scalability, reliability, and maintainability.",
        "Led PLG practice using usage data and customer feedback to iterate product, pricing, and packaging.",
    ]:
        bullet(pdf, b)

    pdf.ln(1.5)
    job_header(
        pdf,
        "Product Marketing & Presales | Segment Owner — OTT, Magnaquest Technologies",
        "May 2022 – Apr 2025  |  Enterprise OTT/broadcast SaaS — India, Middle East, Africa, APAC, Europe",
    )
    for b in [
        "Owned enterprise client solutions across 5 regions — 50% customer-base growth and expansion into 4 new markets.",
        "Built ICP, pipeline, and multi-step ABM workflows targeting C-suite buyers — 30% SQL pipeline growth; managed a $4.5M global pipeline with the VP of Sales.",
        "Connected CRM, events, partner, and outbound channels into a single operating system — 200+ MQLs at 30% MQL→SQL conversion while leading a team of 5.",
        "Delivered technical discovery workshops, demos, PoCs, and RFP/RFI responses; translated product systems into clear next steps for clients and partners.",
        "Produced technical and sales documentation that accelerated enterprise deal cycles with system integrators and CMS partners.",
    ]:
        bullet(pdf, b)

    pdf.ln(1.5)
    job_header(
        pdf,
        "Business Consultant — B2B Presales & GTM",
        "Dec 2017 – Oct 2021  |  Elsner Technologies · Prosols Technology · Solace Infotech (agency/consulting)",
    )
    for b in [
        "Drove ₹2 Cr (~$250K) in revenue via customer-development engagements across custom software, mobile, and web for enterprise B2B clients.",
        "Scoped MVPs with delivery leads; produced GTM plans, product marketing collateral, and launch documentation for each engagement.",
        "Integrated ZoomInfo and Lusha enrichment with CRM ecosystems; built automated lifecycle-nurture frameworks across Delivery, CS, and Marketing.",
        "Worked directly with clients and stakeholders to design practical automation and process solutions under ambiguous, fast-moving timelines.",
    ]:
        bullet(pdf, b)

    section_title(pdf, "Skills & Stack")
    skills = [
        "Automation Platforms: n8n, Make.com, Zapier — multi-step workflows, webhooks, error handling, and ops reliability",
        "CRM & Revenue Systems: Zoho CRM, HubSpot — pipelines, lifecycle stages, enrichment, lead routing, and sales handoff",
        "Integration & Data: APIs, webhooks, systems integration; Google Sheets / spreadsheet ops; Apollo.io, Clay, ZoomInfo, Lusha",
        "AI Workflows in Business Processes: LLM orchestration, RAG, prompt engineering, multi-agent systems — Claude, Gemini, OpenAI, Google AI Studio, NotebookLM, GCP Vertex AI",
        "Documentation & Client Communication: SOPs, user guides, technical specs, enablement kits, stakeholder-ready explanations",
        "Collaboration & Delivery: Slack, Jira, Power BI, Advanced Excel; agency/consulting delivery experience",
    ]
    for s in skills:
        bullet(pdf, s)

    section_title(pdf, "Education & Certifications")
    body(
        pdf,
        "B.E., MGM's College of Engineering & Technology, Mumbai University (2016)\n"
        "AI for Business Specialization — Wharton / Coursera (2026)  •  "
        "PG Certification, Product Management & Marketing — SP Jain (2025)  •  "
        "Growth Hacking — GrowthSchool (2024)",
    )

    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
