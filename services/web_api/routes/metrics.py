from fastapi import APIRouter, Request

router = APIRouter()

@router.get("/metrics")
def metrics(request: Request):
    m = getattr(request.app.state, "metrics", {"runs": 0, "updates": 0, "errors": 0})
    return m
