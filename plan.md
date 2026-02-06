## 問題與方向
目標是設計一個互動式網頁，讓使用者以文字描述建築主體/外觀，先生成「渲染圖 + 工程圖」兩種建築圖片，再依運鏡提示詞生成影片。後端採用 Python/FastAPI，前端為輕量靜態頁面，模型以 Gemini API 呼叫：圖片使用 `gemini-3-pro-image-preview`（Nano Banana Pro）、影片使用 `veo-3.1-generate-preview`，REST Base URL 為 `https://generativelanguage.googleapis.com/v1beta`。

## 工作計畫
- [x] 確認模型資訊：Gemini API 模型為 `gemini-3-pro-image-preview`（image: `:generateContent`）、`veo-3.1-generate-preview`（video: `:predictLongRunning` + operation polling）。
- [ ] 設計提示詞結構（可直接實作的欄位與範例）：  
  - **輸入欄位（前端表單）**  
    - `building_type`：建築類型（住宅/商業/公共/工業/其他）  
    - `structure`：主體結構（鋼構/鋼筋混凝土/木構/混合）  
    - `floors`：樓層數（數字）  
    - `materials`：主要材料（混凝土/玻璃/金屬/木材/石材）  
    - `facade_style`：外觀設計（現代/新古典/極簡/工業/有機曲線/高科技）  
    - `roof`：屋頂形式（平屋頂/斜屋頂/曲面/綠屋頂）  
    - `windows`：窗體語彙（落地窗/水平帶狀窗/格柵/挑高中庭）  
    - `context`：場域（都市/海岸/山區/校園/園區）  
    - `lighting`：光線（晨光/黃昏/夜景/室內柔光）  
    - `camera`：鏡頭視角（低角度仰視/空拍俯視/等距/人眼視角）  
    - `style_refs`：參考風格（自由文字，可選）  
  - **渲染圖提示詞模板（Render）**  
    - `A photorealistic architectural render of a {facade_style} {building_type}, {floors} floors, {structure} structure, primary materials {materials}. {roof} roof, {windows} windows. Located in {context}. {lighting} with soft realistic shadows. {camera} view. High detail, PBR materials, clean composition, no people.`  
  - **工程圖提示詞模板（Engineering）**  
    - `An architectural technical drawing of the same building: orthographic elevation + floor plan, clean black linework on white background, labeled grid lines, minimal text, no shading, no people, CAD/blueprint style.`  
  - **運鏡提示詞清單（Video）**  
    - `Slow orbit around the building, 8 seconds, cinematic, stable.`  
    - `Dolly-in from wide shot to facade detail, 8 seconds.`  
    - `Crane down from aerial to ground level entrance, 8 seconds.`  
    - `Side tracking shot along facade, 8 seconds.`  
  - **合成規則**：render 使用完整材質與光線；engineering 固定為黑線白底；video 以 render 圖作為參考，拼接運鏡提示詞。
- [ ] 後端 API 設計（FastAPI）：  
  - `POST /api/image`：接收文字描述，組合兩種提示詞，呼叫 `.../models/gemini-3-pro-image-preview:generateContent` 兩次，回傳 Base64 圖片（inline_data）。  
  - `POST /api/video`：接收指定圖片與運鏡提示詞，呼叫 `.../models/veo-3.1-generate-preview:predictLongRunning`，回傳 operation name 作為 jobId。  
  - `GET /api/video/{jobId}`：用 `GET {BASE_URL}/{operation_name}` 輪詢，完成後回傳下載 URI。  
  - 認證方式：Gemini API Key（`GEMINI_API_KEY`），不使用 Vertex AI OAuth。
  - **API JSON 範例**  
    - `/api/image` Request
      ```json
      {
        "building_type": "公共",
        "structure": "鋼構",
        "floors": 3,
        "materials": "玻璃, 金屬",
        "facade_style": "現代",
        "roof": "平屋頂",
        "windows": "落地窗",
        "context": "都市",
        "lighting": "黃昏",
        "camera": "低角度仰視",
        "style_refs": "高科技感、簡潔線條"
      }
      ```
    - `/api/image` Response
      ```json
      {
        "render": {
          "prompt": "A photorealistic architectural render ...",
          "image_base64": "<BASE64_PNG>"
        },
        "engineering": {
          "prompt": "An architectural technical drawing ...",
          "image_base64": "<BASE64_PNG>"
        }
      }
      ```
    - `/api/video` Request
      ```json
      {
        "render_image_base64": "<BASE64_PNG>",
        "camera_moves": [
          "Slow orbit around the building, 8 seconds, cinematic, stable."
        ],
        "extra_prompt": "ultra realistic, no people"
      }
      ```
    - `/api/video` Response
      ```json
      {
        "job_id": "operations/xyz123",
        "status": "pending"
      }
      ```
    - `/api/video/{jobId}` Response (pending)
      ```json
      {
        "job_id": "operations/xyz123",
        "status": "running"
      }
      ```
    - `/api/video/{jobId}` Response (done)
      ```json
      {
        "job_id": "operations/xyz123",
        "status": "done",
        "video_url": "https://generativelanguage.googleapis.com/v1beta/.../file.mp4"
      }
      ```
  - **Gemini API 直連 REST 範例**  
    - 產生圖片（Render/Engineering 都用此端點）
      ```bash
      curl -s -X POST \
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
          "contents": [{
            "parts": [
              {"text": "A photorealistic architectural render of a modern public building..."}
            ]
          }]
        }'
      ```
    - 產生影片（長任務）
      ```bash
      curl -s -X POST \
        "https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-generate-preview:predictLongRunning" \
        -H "x-goog-api-key: $GEMINI_API_KEY" \
        -H "Content-Type: application/json" \
        -d '{
          "instances": [{
            "prompt": "Slow orbit around the building, 8 seconds, cinematic."
          }]
        }'
      ```
    - 輪詢任務狀態
      ```bash
      curl -s -H "x-goog-api-key: $GEMINI_API_KEY" \
        "https://generativelanguage.googleapis.com/v1beta/operations/xyz123"
      ```
    - 下載影片（完成後的 `video.uri`）
      ```bash
      curl -L -H "x-goog-api-key: $GEMINI_API_KEY" \
        "https://generativelanguage.googleapis.com/v1beta/..."
      ```
  - **FastAPI 後端請求樣板（Python + httpx）**
      ```python
      import os
      import httpx

      BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
      API_KEY = os.getenv("GEMINI_API_KEY")

      async def generate_image_base64(prompt: str) -> str:
          url = f"{BASE_URL}/models/gemini-3-pro-image-preview:generateContent"
          payload = {
              "contents": [{
                  "parts": [{"text": prompt}]
              }]
          }
          headers = {
              "x-goog-api-key": API_KEY,
              "Content-Type": "application/json",
          }
          async with httpx.AsyncClient(timeout=60) as client:
              resp = await client.post(url, json=payload, headers=headers)
              resp.raise_for_status()
              parts = resp.json()["candidates"][0]["content"]["parts"]
              for part in parts:
                  inline = part.get("inlineData") or part.get("inline_data")
                  if inline and inline.get("data"):
                      return inline["data"]
          raise RuntimeError("No image data in response")

      async def start_video_job(prompt: str) -> str:
          url = f"{BASE_URL}/models/veo-3.1-generate-preview:predictLongRunning"
          payload = {"instances": [{"prompt": prompt}]}
          headers = {
              "x-goog-api-key": API_KEY,
              "Content-Type": "application/json",
          }
          async with httpx.AsyncClient(timeout=60) as client:
              resp = await client.post(url, json=payload, headers=headers)
              resp.raise_for_status()
              return resp.json()["name"]  # operation name

      async def get_video_uri(operation_name: str) -> str | None:
          url = f"{BASE_URL}/{operation_name}"
          headers = {"x-goog-api-key": API_KEY}
          async with httpx.AsyncClient(timeout=60) as client:
              resp = await client.get(url, headers=headers)
              resp.raise_for_status()
              data = resp.json()
              if not data.get("done"):
                  return None
              return data["response"]["generateVideoResponse"]["generatedSamples"][0]["video"]["uri"]
      ```
  - **FastAPI 路由樣板（含 Request/Response Schema）**
      ```python
      from typing import List, Optional
      from fastapi import FastAPI, HTTPException
      from pydantic import BaseModel

      app = FastAPI()

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

      @app.post("/api/image", response_model=ImageResponse)
      async def generate_images(payload: ImageRequest):
          # build prompts from payload
          render_prompt = "..."
          engineering_prompt = "..."
          try:
              render_b64 = await generate_image_base64(render_prompt)
              engineering_b64 = await generate_image_base64(engineering_prompt)
          except Exception as exc:
              raise HTTPException(status_code=502, detail=str(exc))
          return ImageResponse(
              render=ImageResult(prompt=render_prompt, image_base64=render_b64),
              engineering=ImageResult(prompt=engineering_prompt, image_base64=engineering_b64),
          )

      @app.post("/api/video", response_model=VideoResponse)
      async def generate_video(payload: VideoRequest):
          prompt = " ".join(payload.camera_moves)
          if payload.extra_prompt:
              prompt = f"{prompt} {payload.extra_prompt}"
          try:
              job_id = await start_video_job(prompt)
          except Exception as exc:
              raise HTTPException(status_code=502, detail=str(exc))
          return VideoResponse(job_id=job_id, status="pending")

      @app.get("/api/video/{job_id}", response_model=VideoStatusResponse)
      async def get_video(job_id: str):
          try:
              uri = await get_video_uri(job_id)
          except Exception as exc:
              raise HTTPException(status_code=502, detail=str(exc))
          if uri is None:
              return VideoStatusResponse(job_id=job_id, status="running")
          return VideoStatusResponse(job_id=job_id, status="done", video_url=uri)
      ```
  - **提示詞組合函式（前端表單 → Prompt）**
      ```python
      def build_render_prompt(p) -> str:
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

      def build_engineering_prompt(p) -> str:
          return (
              "An architectural technical drawing of the same building: "
              "orthographic elevation + floor plan, clean black linework on white "
              "background, labeled grid lines, minimal text, no shading, no people, "
              "CAD/blueprint style."
          )

      def build_video_prompt(camera_moves: list[str], extra: str | None) -> str:
          prompt = " ".join(camera_moves)
          if extra:
              prompt = f"{prompt} {extra}"
          return prompt
      ```
- [ ] 前端互動設計（可直接實作的欄位與範例）：  
  - **表單區**  
    - 下拉選單：`building_type`, `structure`, `materials`, `facade_style`, `roof`, `windows`, `context`, `lighting`, `camera`  
    - 數字輸入：`floors`  
    - 文字輸入：`style_refs`（自由描述）  
    - 運鏡選單（多選）：`camera_moves`（上方清單）  
  - **提示詞預覽**：即時顯示 Render/Engineering/Video 三段最終提示詞（可複製）。  
  - **生成流程**  
    - 按鈕：`生成圖片` → 呼叫 `/api/image`  
    - 圖片完成後顯示兩張圖（Render/Engineering）  
    - 按鈕：`生成影片` → 呼叫 `/api/video` → 輪詢 `/api/video/{jobId}`  
  - **預設值範例**  
    - building_type=公共、structure=鋼構、floors=3、materials=玻璃+金屬、facade_style=現代、roof=平屋頂、windows=落地窗、context=都市、lighting=黃昏、camera=低角度仰視
- [ ] 展示與部署方案：  
  - Vercel：用 Serverless Functions 代理 FastAPI（或改為輕量 API 路由），注意影片生成時間與輪詢。  
  - Colab：啟動 FastAPI + ngrok/Cloudflared 供展示；素材暫存於本機。

## 注意事項 / 假設
- 模型資訊已改以 Gemini API 官方文件為準（ai.google.dev）。
- 若影片生成為長工序，需採非同步 job + 輪詢或 webhook。
- 圖片/影片素材若需持久化，建議使用 GCS 儲存並回傳簽名 URL。
