# 建築影像生成器（Image Veo）

以文字描述建築外觀，生成「渲染圖 + 工程圖」，再透過運鏡提示詞生成影片。  
後端採 FastAPI，前端為靜態表單頁，並以 Gemini API / Veo 模型產出結果。

---

## 功能簡介
- 建築渲染圖生成（Render）
- ��築工程圖生成（Engineering）
- 影片生成（Video + 運鏡提示詞）
- 即時提示詞預覽

---

## 專案結構
```
.
├── app.py              # FastAPI 後端
├── static/
│   └── index.html      # 前端表單頁
├── outputs/            # 影片輸出（執行時產生）
├── plan.md             # 規劃文件
```

---

## 環境需求
- Python 3.10+
- Gemini API Key

---

## 環境變數
請設定：

```
GEMINI_API_KEY=你的 Gemini API Key
```

---

## 本地啟動

```bash
pip install -r requirements.txt
uvicorn app:app --reload
```

開啟瀏覽器：
```
http://localhost:8000
```

---

## API 使用方式

### 產生圖片
`POST /api/image`

範例：
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

### 產生影片
`POST /api/video`

```json
{
  "render_image_base64": "<BASE64_PNG>",
  "camera_moves": [
    "Slow orbit around the building, 8 seconds, cinematic, stable."
  ],
  "extra_prompt": "ultra realistic, no people"
}
```

### 取得影片狀態
`GET /api/video/{job_id}`

---

## Vercel 部署

新增 `vercel.json` 與 `requirements.txt` 後，推送到 GitHub，
即可在 Vercel 直接 Import 專案。

環境變數需設定：
```
GEMINI_API_KEY=你的 Gemini API Key
```

---

## 資安建議（重要）
- 建議加入 API 驗證（Token / API Key）
- 建議實作速率限制避免濫用
- 限制 prompt 長度與請求大小
- 影片輸出需有清理策略（避免磁碟膨脹）

---

## 授權
尚未指定授權，可依需求補上。