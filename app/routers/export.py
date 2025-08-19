# app/routers/export.py
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app import models
import json, csv, io

router = APIRouter(prefix="/export", tags=["export"])

def queries_to_rows(queries):
    """Flatten queries to rows for CSV (one row per saved query)."""
    rows = []
    for q in queries:
        try:
            parsed = json.loads(q.result) if q.result else {}
        except Exception:
            parsed = {}
        rows.append({
            "id": q.id,
            "location": q.location or "",
            "date_range": q.date_range or "",
            "created_at": q.created_at.isoformat(),
            "lat": parsed.get("lat", ""),
            "lon": parsed.get("lon", ""),
            # Compact, readable JSON of the payload for spreadsheets
            "payload": json.dumps(parsed.get("data", {}), ensure_ascii=False)
        })
    return rows

@router.get("/queries")
def export_all_csv(
    delim: str = Query(",", description="Delimiter to use. Use 'tab' for tab. Default=','"),
    db: Session = Depends(get_db)
):
    """
    Download all saved queries as a CSV.
    Query param `delim` controls the delimiter (',' default, ';', or 'tab').
    Example: /export/queries?delim=;  or  /export/queries?delim=tab
    """
    # choose delimiter
    if delim == "tab":
        delimiter = "\t"
    elif len(delim) == 1:
        delimiter = delim
    else:
        raise HTTPException(status_code=400, detail="delim must be a single character or 'tab'")

    queries = db.query(models.WeatherQuery).order_by(models.WeatherQuery.created_at.desc()).all()
    rows = queries_to_rows(queries)

    buffer = io.StringIO()
    fieldnames = ["id", "location", "date_range", "created_at", "lat", "lon", "payload"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for r in rows:
        # ensure strings (csv writer expects str)
        safe_row = {k: (v if isinstance(v, str) else str(v)) for k, v in r.items()}
        writer.writerow(safe_row)

    csv_bytes = buffer.getvalue().encode("utf-8")
    buffer.close()

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=weather_queries.csv"}
    )

@router.get("/query/{query_id}")
def export_single_csv(
    query_id: int,
    delim: str = Query(",", description="Delimiter to use. Use 'tab' for tab. Default=','"),
    db: Session = Depends(get_db)
):
    if delim == "tab":
        delimiter = "\t"
    elif len(delim) == 1:
        delimiter = delim
    else:
        raise HTTPException(status_code=400, detail="delim must be a single character or 'tab'")

    q = db.query(models.WeatherQuery).filter(models.WeatherQuery.id == query_id).first()
    if not q:
        raise HTTPException(status_code=404, detail="Query not found")

    try:
        parsed = json.loads(q.result) if q.result else {}
    except Exception:
        parsed = {}

    buffer = io.StringIO()
    fieldnames = ["id", "location", "date_range", "created_at", "lat", "lon", "payload"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=delimiter, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    writer.writerow({
        "id": q.id,
        "location": q.location or "",
        "date_range": q.date_range or "",
        "created_at": q.created_at.isoformat(),
        "lat": parsed.get("lat", ""),
        "lon": parsed.get("lon", ""),
        "payload": json.dumps(parsed.get("data", {}), ensure_ascii=False)
    })
    csv_bytes = buffer.getvalue().encode("utf-8")
    buffer.close()

    return StreamingResponse(
        iter([csv_bytes]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=query_{q.id}.csv"}
    )
