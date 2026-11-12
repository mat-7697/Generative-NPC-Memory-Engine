import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from app.auth.utils import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.database import get_db
from app.limiter import limiter
from app.models.auth import Token, UserLogin, UserRegister

router = APIRouter(tags=["Authentication"])
settings = get_settings()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Register a new player account and return a signed JWT access token."""
    # Check if username or email already exists
    existing = await conn.fetchrow(
        "SELECT player_id, username, email FROM players WHERE username = $1 OR email = $2",
        data.username,
        data.email,
    )
    if existing:
        if existing["username"].lower() == data.username.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A player with this username already exists",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="A player with this email address already exists",
            )

    hashed_pw = hash_password(data.password)

    try:
        row = await conn.fetchrow(
            """
            INSERT INTO players (username, email, password_hash, role, gold, level, xp)
            VALUES ($1, $2, $3, 'player', 100, 1, 0)
            RETURNING player_id, username, role
            """,
            data.username,
            data.email,
            hashed_pw,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create player account: {exc}",
        )

    access_token = create_access_token(
        data={"sub": row["username"], "player_id": row["player_id"], "role": row["role"]}
    )
    return Token(access_token=access_token, token_type="bearer")


@router.post("/login", response_model=Token)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    credentials: UserLogin,
    conn: asyncpg.Connection = Depends(get_db),
):
    """Authenticate player credentials and issue a signed JWT access token."""
    row = await conn.fetchrow(
        "SELECT player_id, username, password_hash, role FROM players WHERE username = $1",
        credentials.username,
    )
    if not row or not verify_password(credentials.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": row["username"], "player_id": row["player_id"], "role": row["role"]}
    )
    return Token(access_token=access_token, token_type="bearer")
