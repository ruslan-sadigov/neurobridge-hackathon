"""Minimal API contract (spec section 9). The analysis runs synchronously with a simple job status."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..adapters.embeddings import get_embedder
from ..adapters.llm import get_llm
from ..config import get_settings
from ..db import Analysis, Document, DocumentChunk, ModelRun, RequirementRow, RiskRow, ScoreRow, get_session
from ..enums import JobStatus
from ..services import parser
from ..services.pipeline import run_analysis

log = logging.getLogger(__name__)
router = APIRouter()


def _get(db, analysis_id: str) -> Analysis:
    a = db.get(Analysis, analysis_id)
    if not a:
        raise HTTPException(404, "analysis not found")
    return a


@router.post("/analyses")
def create_analysis() -> dict:
    with get_session() as db:
        a = Analysis()
        db.add(a)
        db.commit()
        return {"analysis_id": a.id, "status": a.status}


@router.delete("/analyses/{analysis_id}")  # NFR-005: delete path
def delete_analysis(analysis_id: str) -> dict:
    s = get_settings()
    with get_session() as db:
        db.delete(_get(db, analysis_id))
        db.commit()
    shutil.rmtree(Path(s.storage_dir) / analysis_id, ignore_errors=True)
    return {"deleted": analysis_id}


@router.post("/analyses/{analysis_id}/documents")
async def upload_documents(analysis_id: str, files: list[UploadFile] = File(...)) -> dict:
    s = get_settings()
    if not 1 <= len(files) <= s.max_files_per_analysis:
        raise HTTPException(400, f"upload 1-{s.max_files_per_analysis} PDF files")
    out = []
    with get_session() as db:
        _get(db, analysis_id)
        for f in files:
            data = await f.read()
            if len(data) > s.max_upload_mb * 1024 * 1024:
                raise HTTPException(413, f"{f.filename}: file too large")
            if not parser.is_pdf(data):
                raise HTTPException(415, f"{f.filename}: not a PDF")
            doc = Document(analysis_id=analysis_id, filename=parser.sanitize_filename(f.filename or "upload.pdf"),
                           size=len(data), checksum=parser.checksum(data), storage_path="")
            db.add(doc)
            db.flush()
            path = Path(s.storage_dir) / analysis_id / f"{doc.id}.pdf"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            doc.storage_path = str(path)
            for c in parser.parse_pdf(doc.id, data):
                db.add(DocumentChunk(document_id=doc.id, page_number=c.page_number, text=c.text,
                                     extraction_method=c.extraction_method))
            out.append({"document_id": doc.id, "filename": doc.filename, "size": doc.size, "checksum": doc.checksum})
        db.commit()
    return {"documents": out}


@router.post("/analyses/{analysis_id}/supplier")
def attach_supplier(analysis_id: str, profile: dict[str, Any]) -> dict:
    with get_session() as db:
        a = _get(db, analysis_id)
        a.supplier_profile = profile
        db.commit()
    return {"ok": True, "company_name": profile.get("company_name")}


def _execute(analysis_id: str) -> None:
    with get_session() as db:
        a = _get(db, analysis_id)
        a.status, a.error = JobStatus.RUNNING.value, None
        db.commit()
        try:
            chunks = [parser.PageChunk(c.document_id, c.page_number, c.text, c.extraction_method)
                      for d in a.documents for c in d.chunks]
            llm = get_llm()
            res = run_analysis(chunks, a.supplier_profile or {}, llm, get_embedder())

            for r in a.requirements:
                db.delete(r)
            for k in a.risks:
                db.delete(k)
            by_res = {c.requirement_id: c for c in res["results"]}
            for r in res["requirements"]:
                cands = [{"evidence": e.model_dump(), "score": sc} for e, sc in res["matches"][r.requirement_id]]
                db.add(RequirementRow(analysis_id=analysis_id, requirement_id=r.requirement_id,
                                      category=r.category.value, mandatory_level=r.mandatory_level.value,
                                      data=r.model_dump(mode="json"),
                                      result=by_res[r.requirement_id].model_dump(mode="json"),
                                      evidence_candidates=cands))
            for k in res["risks"]:
                db.add(RiskRow(analysis_id=analysis_id, data=k.model_dump(mode="json")))
            if a.score:
                db.delete(a.score)
            db.add(ScoreRow(analysis_id=analysis_id, data=res["score"].model_dump(mode="json")))
            if getattr(llm, "last_run", None):
                db.add(ModelRun(analysis_id=analysis_id, stage="last", data=llm.last_run))
            a.summary = {"warnings": res["warnings"], "timings": res["timings"],
                         "parsing_coverage": res["parsing_coverage"], "requirement_count": len(res["requirements"])}
            a.status = JobStatus.COMPLETE.value
        except Exception as e:  # failures must be visible, never a silent partial success (NFR-003)
            log.exception("analysis %s failed", analysis_id)
            db.rollback()
            a = _get(db, analysis_id)
            a.status, a.error = JobStatus.FAILED.value, str(e)
        db.commit()


@router.post("/analyses/{analysis_id}/run")
def run(analysis_id: str, bg: BackgroundTasks, sync: bool = False) -> dict:
    with get_session() as db:
        a = _get(db, analysis_id)
        if not a.documents:
            raise HTTPException(400, "upload tender documents first")
        if not a.supplier_profile:
            raise HTTPException(400, "attach a supplier profile first")
        a.status = JobStatus.PENDING.value
        db.commit()
    if sync:
        _execute(analysis_id)
    else:
        bg.add_task(_execute, analysis_id)
    return {"analysis_id": analysis_id, "status": JobStatus.PENDING.value}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str) -> dict:
    from collections import Counter

    with get_session() as db:
        a = _get(db, analysis_id)
        statuses = Counter(r.result["status"] for r in a.requirements)
        return {"analysis_id": a.id, "status": a.status, "error": a.error, "summary": a.summary,
                "documents": [{"document_id": d.id, "filename": d.filename, "pages": len(d.chunks)} for d in a.documents],
                "counts": {"total": len(a.requirements),
                           "mandatory": sum(r.mandatory_level == "MANDATORY" for r in a.requirements),
                           **{k: statuses.get(k, 0) for k in ("MET", "PARTIALLY_MET", "NOT_MET", "UNKNOWN")}},
                "recommendation": a.score.data["recommendation"] if a.score else None,
                "final_score": a.score.data["final_score"] if a.score else None}


@router.get("/analyses/{analysis_id}/requirements")
def get_requirements(analysis_id: str, status: str | None = None, category: str | None = None,
                     mandatory_level: str | None = None) -> list[dict]:
    with get_session() as db:
        rows = _get(db, analysis_id).requirements
        out = []
        for r in rows:
            if status and r.result["status"] != status:
                continue
            if category and r.category != category:
                continue
            if mandatory_level and r.mandatory_level != mandatory_level:
                continue
            out.append({**r.data, "result": r.result, "evidence_candidates": r.evidence_candidates})
        return out


@router.get("/analyses/{analysis_id}/risks")
def get_risks(analysis_id: str) -> list[dict]:
    with get_session() as db:
        return [k.data for k in _get(db, analysis_id).risks]


@router.get("/analyses/{analysis_id}/score")
def get_score(analysis_id: str) -> dict:
    with get_session() as db:
        a = _get(db, analysis_id)
        if not a.score:
            raise HTTPException(404, "score not computed yet")
        return a.score.data


@router.get("/documents/{document_id}/pages/{page}")
def get_page(document_id: str, page: int) -> dict:
    with get_session() as db:
        chunk = (db.query(DocumentChunk)
                 .filter_by(document_id=document_id, page_number=page).first())
        if not chunk:
            raise HTTPException(404, "page not found")
        return {"document_id": document_id, "page": page, "text": chunk.text,
                "extraction_method": chunk.extraction_method}


@router.get("/documents/{document_id}/file")
def get_file(document_id: str):
    with get_session() as db:
        doc = db.get(Document, document_id)
        if not doc:
            raise HTTPException(404, "document not found")
        return FileResponse(doc.storage_path, media_type="application/pdf", filename=doc.filename)
