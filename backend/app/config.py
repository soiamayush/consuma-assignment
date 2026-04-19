from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Backend package root (directory that contains `app/` and `data/`).
_BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # Always load `.env` from the backend folder, even if uvicorn is started
    # from another working directory.
    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./data/watch.db"
    use_fixtures: bool = False
    # When false: after live sources, ingest committed JSON for peers that still
    # have zero products (Mamaearth / MyGlamm when APIs are blocked).
    hybrid_fixture_fallback: bool = True
    scrape_timeout: int = 20
    scrape_user_agent: str = "CompetitorWatchBot/0.1 (+https://example.com/bot)"
    scrape_max_pages: int = 5
    frontend_origin: str = "http://localhost:5173"

    # Provider-backed scraping (set in backend/.env)
    scraperapi_key: str | None = None
    scraper_proxy_url: str | None = None
    scraper_render_js: bool = False
    # ScraperAPI flags for protected sites (costs more credits).
    scraperapi_premium: bool = False
    scraperapi_ultra_premium: bool = False

    # Social / buzz scrapers
    youtube_api_key: str | None = None  # Google Cloud > YouTube Data API v3
    # Instagram Graph API (hashtag top/recent media) — optional; see instagram_graph_hashtag.py
    instagram_access_token: str | None = None
    instagram_graph_user_id: str | None = None  # Instagram Business/Creator user id (numeric)

    # Chat assistant (Gemini). Free tier works; default model picked for low latency.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    # Max tokens per model reply. 1200 truncates long answers; 8k is safe for Flash.
    gemini_max_output_tokens: int = 8192
    # Cap how many recent turns we send back to Gemini per request (keeps prompt small).
    chat_history_window: int = 8

    @property
    def resolved_database_url(self) -> str:
        """Turn relative sqlite URLs into an absolute file path under `_BACKEND_ROOT`.

        Otherwise `sqlite:///./data/watch.db` depends on the process cwd and you can
        accidentally read an empty DB or miss the file bootstrap wrote.
        """
        url = self.database_url.strip()
        if not url.startswith("sqlite:///"):
            return url
        path_part = url[len("sqlite:///") :]
        if path_part.startswith("./"):
            p = (_BACKEND_ROOT / path_part[2:]).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{p.as_posix()}"
        return url

    @property
    def data_dir(self) -> Path:
        d = _BACKEND_ROOT / "data"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def fixtures_dir(self) -> Path:
        return self.data_dir / "fixtures"


@lru_cache
def get_settings() -> Settings:
    return Settings()
