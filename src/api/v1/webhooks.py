"""
Webhook endpoints for Turkish Business Integration Platform
"""

from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
async def webhook_status():
    """Get webhook service status"""
    return {"status": "Webhook service ready"}