from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
IMAGE_MODEL = "gemini-3-pro-image-preview"
VIDEO_MODEL = "veo-3.1-generate-preview"
STATIC_DIR = Path("static")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/outputs"))

# ensure writable dir (Vercel requires /tmp)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")


class ImageRequest(BaseModel):
    building_type: str
    structure: str
    floors: int
    materials: str
    facade_style: str
    roof: str
    windows: str
    context: str
    lighting: str
    camera: str
    style_refs: Optional[str] = None


class ImageResult(BaseModel):
    prompt: str
    image_base64: str


class ImageResponse(BaseModel):
    render: ImageResult
    engineering: ImageResult


class VideoRequest(BaseModel):
    render_image_base64: str
    camera_moves: List[str]
    extra_prompt: Optional[str] = None


class VideoResponse(BaseModel):
    job_id: str
    status: str


class VideoStatusResponse(BaseModel):
    job_id: str
    status: str
    video_url: Optional[str] = None


def get_api_key() -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY is not set")
    return api_key


def strip_data_uri(value: str) -> str:
    value = value.strip()
    if value.startswith("data:") and "," in value:
        return value.split(",", 1)[1]
    return value


def build_render_prompt(p: ImageRequest) -> str:
    base = (
        f"A photorealistic architectural render of a {p.facade_style} "
        f"{p.building_type}, {p.floors} floors, {p.structure} structure, "
        f"primary materials {p.materials}. {p.roof} roof, {p.windows} windows. "
        f"Located in {p.context}. {p.lighting} with soft realistic shadows. "
        f"{p.camera} view. High detail, PBR materials, clean composition, no people."
    )
    if p.style_refs:
        base = f"{base} Style references: {p.style_refs}."
    return base


def build_engineering_prompt(_: ImageRequest) -> str:
    return (
        "An architectural technical drawing of the same building: "
        "orthographic elevation + floor plan, clean black linework on white "
        "background, labeled grid lines, minimal text, no shading, no people, "
        "CAD/blueprint style."
    )


def build_video_prompt(camera_moves: List[str], extra_prompt: Optional[str]) -> str:
    prompt = " ".join(camera_moves)
    if extra_prompt:
        prompt = f"{prompt} {extra_prompt}"
    return prompt


async def generate_image_base64(prompt: str) -> str:
    url = f"{BASE_URL}/models/{IMAGE_MODEL}:generateContent"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    headers = {
        "x-goog-api-key": get_api_key(),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
    parts = data["candidates"][0]["content"]["parts"]
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return inline["data"].replace("\n", "")
    raise HTTPException(status_code=502, detail="No image data in response")


async def start_video_job(prompt: str, image_base64: str) -> str:
    """
    Use predictLongRunning with the image placed inside each instance as inlineData.
    Returns operation name.
    """
    url = f"{BASE_URL}/models/{VIDEO_MODEL}:predictLongRunning"

    # Build one instance with prompt; attach image to instance if provided
    instance = {"prompt": prompt}
    if image_base64:
        instance["image"] = {
            "inlineData": {
                "mimeType": "image/png",
                "data": strip_data_uri(image_base64),
            }
        }

    payload = {"instances": [instance]}

    # Debug log (truncated)
    try:
        print("VIDEO REQUEST PAYLOAD:", json.dumps(payload)[:2000])
    except Exception:
        pass

    headers = {
        "x-goog-api-key": get_api_key(),
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, json=payload, headers=headers)

        # log response for debugging
        status = resp.status_code
        try:
            body_text = await resp.text()
        except Exception:
            body_text = str(resp.content)
        print("VIDEO API STATUS:", status)
        print("VIDEO API RESPONSE BODY:", (body_text or "")[:4000])

        if status >= 400:
            # return detailed error to caller for easier debugging
            raise HTTPException(status_code=502, detail=f"Video API error {status}: {body_text}")

        data = resp.json()
        # predictLongRunning should return an operation name in 'name'
        return data.get("name") or data.get("operation") or ""


async def get_video_uri(operation_name: str) -> Optional[str]:
    url = f"{BASE_URL}/{operation_name}"
    headers = {"x-goog-api-key": get_api_key()}
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    # Operation formats may vary; check common locations for generated video URI
    if not data.get("done"):
        return None

    # 1) older predictLongRunning response shape
    try:
        return data["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
    except Exception:
        pass

    # 2) newer generateVideos response shape
    try:
        return data["response"]["generatedVideos"][0]["video"]["uri"]
    except Exception:
        pass

    # 3) fallback: search tree for any 'uri' field
    def find_uri(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "uri" and isinstance(v, str):
                    return v
                res = find_uri(v)
                if res:
                    return res
        if isinstance(obj, list):
            for item in obj:
                res = find_uri(item)
                if res:
                    return res
        return None

    return find_uri(data)


async def download_video(uri: str, target_path: Path) -> None:
    headers = {"x-goog-api-key": get_api_key()}
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        resp = await client.get(uri, headers=headers)
        resp.raise_for_status()
        target_path.write_bytes(resp.content)


def video_filename(job_id: str) -> str:
    digest = hashlib.sha256(job_id.encode("utf-8")).hexdigest()[:16]
    return f"video_{digest}.mp4"


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/image", response_model=ImageResponse)
async def create_images(payload: ImageRequest) -> ImageResponse:
    render_prompt = build_render_prompt(payload)
    engineering_prompt = build_engineering_prompt(payload)
    render_b64 = await generate_image_base64(render_prompt)
    engineering_b64 = await generate_image_base64(engineering_prompt)
    return ImageResponse(
        render=ImageResult(prompt=render_prompt, image_base64=render_b64),
        engineering=ImageResult(prompt=engineering_prompt, image_base64=engineering_b64),
    )


@app.post("/api/video", response_model=VideoResponse)
async def create_video(payload: VideoRequest) -> VideoResponse:
    prompt = build_video_prompt(payload.camera_moves, payload.extra_prompt)
    job_id = await start_video_job(prompt, payload.render_image_base64)
    return VideoResponse(job_id=job_id, status="pending")


@app.get("/api/video/{job_id}", response_model=VideoStatusResponse)
async def get_video(job_id: str) -> VideoStatusResponse:
    uri = await get_video_uri(job_id)
    if uri is None:
        return VideoStatusResponse(job_id=job_id, status="running")
    filename = video_filename(job_id)
    target_path = OUTPUT_DIR / filename
    if not target_path.exists():
        await download_video(uri, target_path)
    return VideoStatusResponse(job_id=job_id, status="done", video_url=f"/outputs/{filename}")
