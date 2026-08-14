# 📊 Grafana & Loki Quickstart: Viewing & Filtering Logs

This guide explains how to quickly find and filter logs for Telegram Bots and core platform microservices in Grafana.

---

## 1. 🔑 Accessing Grafana

1. Open your browser and go to: **`http://localhost:3000`** (or your server's Grafana IP/URL).
2. **Default Login**: `admin` / `admin` (or the `GF_SECURITY_ADMIN_PASSWORD` configured in `.env`).

---

## 2. 🔍 Where to Click (Navigating to Logs)

1. **Open Explore View**: 
   - Click on the **Explore** icon (🧭 compass icon) in the left sidebar menu (or navigate directly to `http://localhost:3000/explore`).
2. **Select Data Source**:
   - In the top-left dropdown menu, choose **`Loki`**.

---

## 3. 🎯 How to Filter Logs (LogQL Basics)

Loki uses **LogQL** queries. Enter your query in the top search field and press `Shift + Enter` or click **Run query** (top right).

### A. Filter by Service or Container (`{label="value"}`)
- **By Service**:
  ```logql
  {service="webhook_server"}
  {service="ai_worker"}
  {service="admin_bot"}
  {service="image_bot_1"}
  ```
- **By Container Name**:
  ```logql
  {container_name="telegram_webhook_server"}
  ```

### B. Filter by Log Level
Promtail extracts log levels automatically from structured JSON logs:
```logql
{level="error"}
{service="ai_worker", level="error"}
{service="webhook_server", level="warning"}
```

### C. Filter by Bot ID
```logql
{bot_id="image_bot_1"}
{bot_id="admin_bot"}
```

### D. Search Text / Keywords (Line Filters)
- **Case-sensitive exact match**:
  ```logql
  {service="webhook_server"} |= "Exception"
  ```
- **Case-insensitive search**:
  ```logql
  {service="ai_worker"} |~ "(?i)failed"
  ```
- **Exclude noise / words**:
  ```logql
  {service="all_bots"} != "HTTP/1.1 200"
  ```

### E. Extract JSON Fields
Since all bots output structured JSON logs:
```logql
{service="webhook_server"} | json | level="error"
```

---

## 4. ⏱️ Useful Features & Tips

- **Time Range (Top Right)**: Select time windows like **`Last 15 minutes`**, **`Last 1 hour`**, or pick custom start/end times.
- **Live Stream**: Click the **Live** button in the top right to tail incoming logs in real time.
- **Expand Log Details**: Click on any log entry line to expand and inspect full structured JSON fields (`bot_id`, `timestamp`, `trace_id`, `error`, stack traces).
- **Pre-configured Dashboard**: Go to **Dashboards** (left menu) -> **Telegram Bots Overview** to view pre-built panels for bot throughput, queue latency, error rates, and live log tailing.

---

## 5. ❓ Why Don't I See Any Logs? (Common Fixes)

If your Explore screen is blank or showing "No data":

1. **Empty Query Input (`expr=""`)**:
   - Loki **requires** a selector query in the input line. If the search box is empty, no logs will load.
   - Enter `{service=~".+"}` (shows logs for all services) or `{job="docker"}` in the search box and click **Run query** (top right).
2. **Use the Label Browser**:
   - Click the **Label browser** button next to the query input line -> select `service` or `container_name` -> select a value -> click **Show logs**.
3. **Check the Time Range**:
   - If no logs occurred in the last hour, change the top-right time picker from **`Last 1 hour`** to **`Last 6 hours`**, **`Last 24 hours`**, or **`Last 7 days`**.
4. **Ensure Services are Running**:
   - Make sure Promtail and Loki containers are up and running on the host (`docker compose ps`).

