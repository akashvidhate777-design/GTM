FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY outreach_agent/ outreach_agent/
COPY gtm_agent.py .
CMD ["python", "-m", "outreach_agent.cli", "run", "--input", "data/leads.csv", "--out", "output/outreach_campaign.xlsx"]
