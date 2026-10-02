import os
import json
import csv
import io
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, PlainTextResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field

from backend.scraper import scraper_instance, normalize_channel_input

app = FastAPI(title="YouTube Top Shorts & Videos Scraper API", version="1.1.0")


class NoCacheFrontendMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith(("/css/", "/js/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        return response


app.add_middleware(NoCacheFrontendMiddleware)

# CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ScrapeRequest(BaseModel):
    channels: List[str] = Field(..., description="List of channel handles, URLs, or usernames")
    content_type: str = Field("shorts", description="Content type: 'shorts' (default) or 'videos'")
    top_percentage: float = Field(10.0, ge=0.1, le=100.0, description="Percentage of top videos to extract (e.g. 10 for 10%)")
    metric: str = Field("views", description="Metric to rank by: 'views', 'comments', or 'combined'")
    max_videos_per_channel: Optional[int] = Field(None, description="Optional cap on items to inspect per channel")
    min_views: int = Field(0, ge=0, description="Only include items with at least this many views")
    fetch_comments: bool = Field(False, description="Whether to deep fetch comment counts if not available in flat metadata")

# Global cache for the last scrape result for quick export
LATEST_SCRAPE_RESULT = {}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "YouTube Shorts Scraper API"}

@app.post("/api/scrape")
async def run_scrape(req: ScrapeRequest):
    """Run scrape synchronously and return full JSON results."""
    global LATEST_SCRAPE_RESULT
    if not req.channels:
        raise HTTPException(status_code=400, detail="Please provide at least one channel username or URL.")
    
    clean_channels = [c.strip() for c in req.channels if c.strip()]
    if not clean_channels:
        raise HTTPException(status_code=400, detail="Channels list cannot be empty.")

    try:
        result = await scraper_instance.scrape_multiple_channels_async(
            channels=clean_channels,
            content_type=req.content_type,
            top_percentage=req.top_percentage,
            metric=req.metric,
            max_videos_per_channel=req.max_videos_per_channel,
            min_views=req.min_views,
            fetch_comments=req.fetch_comments
        )
        LATEST_SCRAPE_RESULT = result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/scrape/stream")
async def stream_scrape(
    channels: str,
    content_type: str = "shorts",
    top_percentage: float = 10.0,
    metric: str = "views",
    max_videos_per_channel: Optional[int] = None,
    min_views: int = 0,
    fetch_comments: bool = False
):
    """Server-Sent Events (SSE) endpoint to stream live scraping progress and final results."""
    global LATEST_SCRAPE_RESULT
    channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    if not channel_list:
        raise HTTPException(status_code=400, detail="No channels provided.")

    async def event_generator():
        queue = asyncio.Queue()

        async def status_cb(data: dict):
            await queue.put(data)

        async def worker():
            try:
                result = await scraper_instance.scrape_multiple_channels_async(
                    channels=channel_list,
                    content_type=content_type,
                    top_percentage=top_percentage,
                    metric=metric,
                    max_videos_per_channel=max_videos_per_channel,
                    min_views=min_views,
                    fetch_comments=fetch_comments,
                    status_callback=status_cb
                )
                global LATEST_SCRAPE_RESULT
                LATEST_SCRAPE_RESULT = result
                await queue.put({'type': 'complete', 'data': result})
            except Exception as ex:
                await queue.put({'type': 'fatal_error', 'message': str(ex)})
            finally:
                await queue.put(None)

        task = asyncio.create_task(worker())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.get("/api/export/txt")
async def export_txt(mode: str = "plain"):
    """
    Download a .txt file containing top Shorts / video URLs.
    mode = 'plain' -> Just URLs (one per line)
    mode = 'detailed' -> Formatted with channel name, title, view count, comments, and URL
    """
    global LATEST_SCRAPE_RESULT
    if not LATEST_SCRAPE_RESULT or not LATEST_SCRAPE_RESULT.get('all_top_videos'):
        raise HTTPException(status_code=404, detail="No scrape results available to download. Please perform a scrape first.")

    videos = LATEST_SCRAPE_RESULT.get('all_top_videos', [])
    pct = LATEST_SCRAPE_RESULT.get('percentage', 10)
    metric = LATEST_SCRAPE_RESULT.get('metric', 'views')
    ctype = LATEST_SCRAPE_RESULT.get('content_type', 'shorts')

    lines = []
    if mode == "detailed":
        lines.append(f"# YouTube Top {pct}% {ctype.upper()} Export (Ranked by {metric.upper()})")
        lines.append(f"# Total {ctype.capitalize()}: {len(videos)}")
        lines.append(f"# Channels Processed: {LATEST_SCRAPE_RESULT.get('channels_processed', 0)}")
        lines.append("# " + "=" * 60 + "\n")
        
        current_chan = None
        for v in videos:
            if v.get('channel') != current_chan:
                current_chan = v.get('channel')
                lines.append(f"\n## Channel: {current_chan}")
            
            views_str = f"{v.get('view_count', 0):,}"
            comments_str = f"{v.get('comment_count', 0):,}"
            lines.append(f"- [{v.get('rank', 0)}] {v.get('title')}")
            lines.append(f"  Views: {views_str} | Comments: {comments_str} | Top {v.get('percentile_pct', 0)}%")
            lines.append(f"  {v.get('url')}\n")
    else:
        for v in videos:
            lines.append(v['url'])

    content = "\n".join(lines)
    filename = f"youtube_top_{int(pct)}pct_{ctype}_{metric}_urls.txt"

    return PlainTextResponse(
        content=content,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

@app.get("/api/export/csv")
async def export_csv():
    """Download CSV file of all top videos/shorts with full metadata."""
    global LATEST_SCRAPE_RESULT
    if not LATEST_SCRAPE_RESULT or not LATEST_SCRAPE_RESULT.get('all_top_videos'):
        raise HTTPException(status_code=404, detail="No scrape results available.")

    videos = LATEST_SCRAPE_RESULT.get('all_top_videos', [])
    pct = LATEST_SCRAPE_RESULT.get('percentage', 10)
    ctype = LATEST_SCRAPE_RESULT.get('content_type', 'shorts')

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Channel", "Title", "URL", "Views", "Comments", "Top Percentile (%)", "Content Type", "Video ID"])

    for v in videos:
        writer.writerow([
            v.get('rank', ''),
            v.get('channel', ''),
            v.get('title', ''),
            v.get('url', ''),
            v.get('view_count', 0),
            v.get('comment_count', 0),
            v.get('percentile_pct', ''),
            "Short" if v.get('is_short') else "Video",
            v.get('id', '')
        ])

    filename = f"youtube_top_{int(pct)}pct_{ctype}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )

# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
