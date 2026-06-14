"""Generate PDF listing all 82 RAG source repositories."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

DARK = HexColor('#0f172a')
ACCENT = HexColor('#7c3aed')
BLUE = HexColor('#3b82f6')
GRAY = HexColor('#64748b')
GRAY_LIGHT = HexColor('#f1f5f9')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(BASE_DIR, "knowledge", "RAG_Source_Repos.pdf")

categories = {
    "Training Plans & Coaching Logic (19)": [
        ("sbailliez/training-plan", "FIRST method (5K-marathon) plan templates"),
        ("jandroav/vtrain", "Jack Daniels VDOT-based auto-generated plans"),
        ("PatrickWiloak/proper-distance-running-training-guidance", "Scientific training guide (content-rich)"),
        ("ColinEberhardt/claude-running-coach", "AI coach skill, evidence-based"),
        ("jnkue/open-trainaa", "Endurance AI coach (FastAPI + Supabase)"),
        ("Raistlfiren/garmin-csv-plan", "Garmin CSV plan importer"),
        ("eddmann/intervals-icu-mcp", "MCP server for training data"),
        ("hhopke/intervals-icu-mcp", "MCP for intervals.icu"),
        ("hoovercj/time-to-run", "Running schedule generator"),
        ("apsureda/garmin-planner", "Garmin training planner"),
        ("supermitch/runblueprint.com", "Run blueprint web app"),
        ("trifectalabs/trifecta", "Training platform"),
        ("benranderson/training-plan", "Training plan generator"),
        ("furgerf/TrainingPlanner", "Training planner app"),
        ("SKOHscripts/workout-planner", "Workout planner"),
        ("danielcoats/training-planner", "Training planner"),
        ("matthewbeckler/training_plan_to_ics", "Plan to calendar export"),
        ("selesse/marathon-trainer", "Marathon training app"),
        ("iROCKBUNNY/Marathon", "Marathon training reference"),
    ],
    "Running Coach Apps - AI/ML (11)": [
        ("EmmanuelDav/Smart-Run", "AI coaching, overexertion-aware"),
        ("v-pramod/RunningCoach", "Strava clone + AI coach"),
        ("GermanAlonzo/RunningCoachingApp", "Running coaching app"),
        ("raptors2019-ai/running-coach", "AI running coach"),
        ("latinovation/running-coach-app", "Running coach app"),
        ("RonRan123/running-app", "Running app with features"),
        ("EmmanuelDiaz95/trail-running-coach", "Trail running coach (411KB architecture docs)"),
        ("naamkeng/RunningCoachApp", "Running coach app"),
        ("Maksat/RunningCoach", "Running coach"),
        ("Joeglasses95/Running-Coach", "Running coach"),
        ("mdmedley/cadence-coach", "Cadence coaching"),
    ],
    "Pace / VDOT / VO2max Calculators (10)": [
        ("ronek22/runningCalculator", "Jack Daniels VDOT implementation"),
        ("hivrich/vdot-calculator", "VDOT + race predictions"),
        ("ZacBlanco/vdot", "Clean VDOT implementation"),
        ("tlgs/vdot", "VDOT calculator"),
        ("oliverbeal/Running-Calculator", "Running calculator"),
        ("xuthus/DistanceCalculator", "Distance calculator"),
        ("chaserycse/VdotCalculator", "VDOT calculator"),
        ("jonathanlofgren/running", "Pace calculator"),
        ("johnjdavisiv/gap-app", "Grade-adjusted pace algorithm"),
        ("thehivemakes/hive-run-calc", "Pace + VO2max + HR zones combined"),
    ],
    "Strava / Garmin / Data Analysis (20)": [
        ("ropensci/Athlytics", "ACWR, TRIMP, EWMA training load calculations"),
        ("aaron-schroeder/heartandsole", "Running data analysis library"),
        ("markwk/qs_ledger", "Quantified-self data aggregator"),
        ("danielgtr/running_analysis", "FIT file parsing + HR zones + form metrics"),
        ("mattambrogi/strava-data-analysis", "Strava data analysis"),
        ("mandieq/strava_related", "Strava analysis tools"),
        ("MathBunny/strava-wind-analysis", "Wind impact on running analysis"),
        ("c-wilkinson/StravaDataAnalysis", "Strava data analysis"),
        ("ikivanc/Data-Driven-Cycling-and-Workout-Prediction", "Workout prediction ML"),
        ("lucasjellema/data-analytics-strava-tour-de-france", "Tour de France analytics"),
        ("Lucs1590/strava-analysis", "Strava analysis"),
        ("kylethmas/stravaDataAnalysis", "Strava data analysis"),
        ("newns92/MarathonTrainingAnalysis", "Marathon training analysis"),
        ("AhmedJouda2000/Marathon-App", "Marathon app"),
        ("Ahmosys/garmin-metrics-api", "Garmin metrics API wrapper"),
        ("alexanderakbik/GarminExport", "Garmin data export"),
        ("tehj4ckass/garmin-connector", "Garmin connector"),
        ("COLINZH26/garmin-ai-skill", "Garmin + AI coaching skill"),
        ("MrPabloUK/Garmin-Connect-Export", "Garmin Connect export"),
        ("ubershmekel/cardiorounds", "HR zones / interval analysis"),
    ],
    "Exercise Physiology & Sports Science (13)": [
        ("dpfens/PyExPhys", "Exercise physiology equations (Python)"),
        ("dpfens/FitnessJS", "Exercise physiology equations (TypeScript)"),
        ("physusp/physusp", "Physiology simulation"),
        ("aaronzpearson/PhysAndSportSciData", "Sports science ML datasets"),
        ("villekuosmanen/physiology-sim", "Physiology simulator"),
        ("MoTrPAC/MotrpacRatTrainingPhysiologyData", "Training physiology data"),
        ("mtpa/sads", "Sports analytics and data science"),
        ("tuangauss/DataScienceProjects", "Data science sports projects"),
        ("skoval/UseRSportTutorial", "Sports analytics R tutorial"),
        ("bruinsportsanalytics/Resource-Folder", "Sports analytics resources"),
        ("akirademoss/SportsScienceAnalytics", "Sports science analytics"),
        ("JD-008/Edge-AI-Gait-Classification", "Gait/biomechanics AI classification"),
        ("jeff3388/awesome-injury-prevention-science", "Curated peer-reviewed injury evidence"),
    ],
    "Agentic RAG / LLM Fitness Coach Architecture (14)": [
        ("Mohamed-Elguindy/Fitness-App", "Agentic RAG router, LlamaIndex, Groq"),
        ("Hayfa78/fitness-nutrition-agent", "Hybrid RAG, FAISS, LangGraph"),
        ("Mohamedreda333-crypto/FitAI-Pro-Multi-Agent-AI-Fitness-Coaching-Platform", "RAG + Groq multi-agent platform"),
        ("kenhuangus/fitness-multi-agent-plan", "LangGraph + memory + injury avoidance"),
        ("CHANDRA294/multi-agent-gym-buddy", "RAG + vector DB fitness"),
        ("saisrujanseelam/AI-multi-agentic-consensus-fitness-trainer-", "Multi-LLM consensus coaching"),
        ("vimalkumarasamy/agent-balboa", "Strava + coach + LLM tools"),
        ("Coding-Phantom/FitnessForge", "Fitness forge agent"),
        ("LI-explorer/LLM-Fitness-Coach", "LLM fitness coach"),
        ("blandevv/home-fitness-agent", "Home fitness agent"),
        ("MachaaX/FitAgent", "Fitness agent"),
        ("oscartiz/hermes-agent", "Tool-calling agent loop pattern"),
        ("ipranaysatija/Nutrition-Energy-Exercise-Agent-NEXA-", "Nutrition + exercise agent"),
        ("JorgeRan/NeuroFit", "Neural fitness agent"),
    ],
}


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=15*mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle('TitleW', fontName='Helvetica-Bold', fontSize=20,
                              textColor=white, alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle('SubW', fontName='Helvetica', fontSize=10,
                              textColor=HexColor('#a5b4fc'), alignment=TA_CENTER))
    styles.add(ParagraphStyle('H2', fontName='Helvetica-Bold', fontSize=11,
                              textColor=ACCENT, spaceBefore=12, spaceAfter=5))
    styles.add(ParagraphStyle('RepoName', fontName='Helvetica-Bold', fontSize=9,
                              textColor=HexColor('#1e293b'), leading=11, spaceAfter=1))
    styles.add(ParagraphStyle('RepoDesc', fontName='Helvetica', fontSize=8,
                              textColor=HexColor('#475569'), leading=10, leftIndent=8, spaceAfter=1))
    styles.add(ParagraphStyle('RepoURL', fontName='Courier', fontSize=7,
                              textColor=BLUE, leading=9, leftIndent=8, spaceAfter=4))
    styles.add(ParagraphStyle('Foot', fontName='Helvetica', fontSize=7,
                              textColor=GRAY, alignment=TA_CENTER))

    story = []

    # Header
    hdr_data = [
        [Paragraph("Sprint Society AI Coach", styles['TitleW'])],
        [Paragraph("RAG Knowledge Source Repositories", styles['SubW'])],
        [Paragraph("82 repos cloned, extracted, and indexed into the coaching knowledge base", styles['SubW'])],
    ]
    hdr = Table(hdr_data, colWidths=[180*mm])
    hdr.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), DARK),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (0, 0), 18),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 14),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 8*mm))

    total_repos = 0
    for cat_name, repos in categories.items():
        story.append(Paragraph(cat_name, styles['H2']))
        story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY_LIGHT))
        story.append(Spacer(1, 2*mm))

        for repo, desc in repos:
            url = f"https://github.com/{repo}"
            story.append(Paragraph(repo, styles['RepoName']))
            story.append(Paragraph(desc, styles['RepoDesc']))
            story.append(Paragraph(url, styles['RepoURL']))
            total_repos += 1

        story.append(Spacer(1, 3*mm))

    # Footer
    story.append(Spacer(1, 6*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        f"Total: {total_repos} repositories | Sprint Society | Kendu Entertainment | June 2026",
        styles['Foot']
    ))

    doc.build(story)
    print(f"PDF generated: {OUTPUT}")
    print(f"Total repos: {total_repos}")


if __name__ == "__main__":
    build_pdf()
