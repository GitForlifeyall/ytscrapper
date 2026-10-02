# 🎬 YouTube Top X% Video Scraper & URL Extractor

A web application powered by **`yt-dlp`**, **FastAPI**, and modern frontend to scrape multiple YouTube channels, calculate the **top X%** most viewed or commented videos, and export the resulting URLs to a `.txt` file or CSV.

---

## ✨ Key Features

- 🎯 **Multi-Channel Batch Scraping**: Enter handles (`@mkbhd`), channel URLs (`https://youtube.com/@veritasium`), or IDs.
- 📊 **Adjustable Top X% Filtering**: Customize the extraction percentage ($1\%$ to $100\%$) based on total channel video counts.
- ⚡ **Flexible Ranking Metrics**:
  - **Most Views**: Top videos by raw view count.
  - **Most Comments**: Top videos by audience discussion & comments.
  - **Combined Score**: Weighted engagement metric (views + comments).
- 💾 **One-Click Exports**:
  - **TXT (Plain URLs)**: Clean list of URLs (one per line) ready for batch downloaders / archiving.
  - **Detailed TXT**: Includes title, view counts, comment counts, and rank.
  - **CSV**: Full spreadsheet export.
  - **Copy All to Clipboard**: Fast copy with one click.
- 📡 **Real-Time Live Progress**: Server-Sent Events (SSE) stream extraction logs, video counters, and channel status in real time.
- 🎨 **Modern Dark Glassmorphism UI**: Responsive, sleek design with interactive video cards, search filter, and table view.

---

## 🚀 Quick Start

### 1. Requirements
- Python 3.9+
- `yt-dlp` & `fastapi` (already configured in requirements)

### 2. Run the Application

```bash
python run.py
```
Or with uvicorn directly:
```bash
python -m uvicorn backend.app:app --reload --port 8000
```

Open your browser and navigate to:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## 🛠️ Project Structure

```
ytscrapper/
├── backend/
│   ├── scraper.py         # yt-dlp core extractor & ranking algorithm
│   └── app.py             # FastAPI backend with SSE streaming and export endpoints
├── frontend/
│   ├── index.html         # Web application UI
│   ├── css/
│   │   └── style.css      # Glassmorphism dark mode stylesheet
│   └── js/
│       └── app.js         # Frontend controller, live updates & export logic
├── requirements.txt       # Dependencies
├── run.py                 # Startup script
└── README.md              # Documentation
```
