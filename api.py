#!/usr/bin/env python3
"""
FastAPI wrapper for the Civil Engineering Scope of Work agent.
Accepts project details via POST and returns the generated report.
"""

import logging
import os
import sys
import tempfile

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from civil_agent import agency
from utils.pdf import save_research_to_pdf

logger = logging.getLogger(__name__)

app = FastAPI(title="Scope of Work Agent API")

ALLOWED_ORIGINS = [
    "https://www.gursewak-singh.com",
    "https://gursewak-singh.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProjectInput(BaseModel):
    project_owner: str
    project_objective: str
    project_budget: str
    project_info: str
    technical_services: str
    completion_estimate: str


class PdfInput(BaseModel):
    report: str
    project_owner: str = "scope_of_work"


def build_prompt(inputs: ProjectInput) -> str:
    """Build the combined prompt from project inputs."""
    prompts = [
        ("Who is the project owner?", inputs.project_owner),
        ("What is the project objective?", inputs.project_objective),
        ("Estimated project budget?", inputs.project_budget),
        ("Project Information (e.g., Roadway Design & Culvert Construction):", inputs.project_info),
        ("What will be some technical services?", inputs.technical_services),
        ("Estimate project completion:", inputs.completion_estimate),
    ]

    combined_prompt_parts = [
        "Create a comprehensive Scope of Work document for Civil Engineering based on the following project details:\n\n",
    ]
    for question, answer in prompts:
        combined_prompt_parts.append(f"- **{question}**\n  {answer}\n\n")
    combined_prompt_parts.append(
        "\nProduce a detailed civil engineering report that synthesizes all of the above into a cohesive Scope of Work document. "
        "Format the entire response in well-structured markdown with ## section headings, bullet or numbered lists where appropriate, "
        "and blank lines between all sections. Do not wrap the response in a code block."
    )
    return "".join(combined_prompt_parts)


@app.post("/generate")
async def generate_scope_of_work(inputs: ProjectInput):
    """Generate a Scope of Work document from project details."""
    combined_prompt = build_prompt(inputs)
    try:
        response = await agency.get_response(combined_prompt)
    except Exception:
        # Let the error surface as a normal response so it keeps its CORS
        # headers; an unhandled exception returns a bare 500 that the browser
        # reports as a CORS failure instead.
        logger.exception("Scope of work generation failed")
        raise HTTPException(status_code=502, detail="Scope of work generation failed.")
    return {"report": response.final_output}


@app.post("/to-pdf")
async def convert_to_pdf(data: PdfInput):
    """Convert report text to a downloadable PDF."""
    from fastapi.responses import Response

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = save_research_to_pdf(
            research_content=data.report,
            query=data.project_owner,
            output_dir=tmp_dir,
        )
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=scope_of_work.pdf"},
    )
