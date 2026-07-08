"""CLI for the outreach agent.

  python -m outreach_agent.cli run    --input data/leads.csv --out output/outreach_campaign.xlsx
  python -m outreach_agent.cli run    --sheet-id <ID> --push-sheet          # Google Sheets in/out
  python -m outreach_agent.cli run    --use-claude                          # Claude-written copy
  python -m outreach_agent.cli report --input data/leads.csv --slack       # campaign report
"""
import argparse
import logging
import os
import sys

from . import messaging, reporting, scoring, sheets_io
from .models import ScoredLead

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("outreach_agent")


def _load_leads(args):
    if args.sheet_id:
        log.info("Reading leads from Google Sheet %s", args.sheet_id)
        return sheets_io.read_google_sheet(args.sheet_id, args.tab)
    log.info("Reading leads from %s", args.input)
    return sheets_io.read_csv(args.input)


def _score_and_generate(args) -> list[ScoredLead]:
    leads = [l for l in _load_leads(args) if l.full_name or l.email]
    log.info("Loaded %d leads", len(leads))

    claude_client = None
    if args.use_claude:
        import anthropic
        claude_client = anthropic.Anthropic()

    scored: list[ScoredLead] = []
    for lead in leads:
        breakdown = scoring.score_lead(lead)
        item = ScoredLead(lead=lead, score=breakdown)
        if breakdown.enters_sequence:
            if claude_client:
                try:
                    item.sequence = messaging.generate_with_claude(lead, breakdown, claude_client)
                except Exception as exc:  # fall back rather than lose the lead
                    log.warning("Claude generation failed for %s (%s); using template engine",
                                lead.full_name, exc)
                    item.sequence = messaging.generate_sequence(lead, breakdown)
            else:
                item.sequence = messaging.generate_sequence(lead, breakdown)
            item.status = "Draft"
        else:
            item.status = "Parked - Low Score"
        scored.append(item)

    eligible = sum(1 for s in scored if s.score.enters_sequence)
    log.info("Scored %d leads — %d sequence-eligible (score >= 55)", len(scored), eligible)
    return scored


def cmd_run(args):
    scored = _score_and_generate(args)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    from .excel_export import build_workbook
    build_workbook(scored, args.out)
    log.info("Workbook written: %s", args.out)

    csv_out = os.path.splitext(args.out)[0] + ".csv"
    sheets_io.write_csv(scored, csv_out)
    log.info("CSV mirror written: %s", csv_out)

    summary = reporting.summarize(scored)
    report_path = os.path.join(os.path.dirname(args.out) or ".", "campaign_report.md")
    with open(report_path, "w") as f:
        f.write(reporting.to_markdown(summary))
    log.info("Report written: %s", report_path)

    if args.push_sheet:
        if not args.sheet_id:
            log.error("--push-sheet requires --sheet-id")
            sys.exit(1)
        sheets_io.write_back_google_sheet(args.sheet_id, scored, args.tab)
        log.info("Score/message/status columns written back to Google Sheet")

    if args.slack and reporting.post_to_slack(summary):
        log.info("Report posted to Slack")


def cmd_report(args):
    scored = [ScoredLead(lead=l, score=scoring.score_lead(l)) for l in _load_leads(args)]
    summary = reporting.summarize(scored)
    print(reporting.to_markdown(summary))
    if args.slack and reporting.post_to_slack(summary):
        log.info("Report posted to Slack")


def main():
    parser = argparse.ArgumentParser(prog="outreach_agent", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--input", default="data/leads.csv", help="Lead CSV path")
        p.add_argument("--sheet-id", default=os.environ.get("GOOGLE_SHEET_ID", ""),
                       help="Read leads from this Google Sheet instead of CSV")
        p.add_argument("--tab", default=None, help="Sheet tab name (optional)")
        p.add_argument("--slack", action="store_true", help="Post report to Slack")

    run_p = sub.add_parser("run", help="Score leads, generate sequences, build workbook")
    common(run_p)
    run_p.add_argument("--out", default="output/outreach_campaign.xlsx")
    run_p.add_argument("--use-claude", action="store_true",
                       help="Generate copy with the Anthropic API (needs ANTHROPIC_API_KEY)")
    run_p.add_argument("--push-sheet", action="store_true",
                       help="Write score/message/status columns back to the Google Sheet")
    run_p.set_defaults(func=cmd_run)

    rep_p = sub.add_parser("report", help="Print/post the campaign report")
    common(rep_p)
    rep_p.set_defaults(func=cmd_report)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
