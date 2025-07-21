import os
import asyncpg
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import APIKeyHeader

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/app")

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(title="MCP Management API")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Validate API key against the database."""
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="API key required")
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        row = await conn.fetchrow(
            "SELECT key FROM api_keys WHERE key = $1 AND active = TRUE",
            api_key,
        )
        if row is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid API key")
    finally:
        await conn.close()
    return api_key

@app.get("/health")
async def health_check():
    """Basic health check."""
    return {"status": "ok"}

@app.get("/protected", dependencies=[Depends(verify_api_key)])
async def protected_endpoint():
    """Example protected endpoint."""
    return {"message": "authenticated"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
