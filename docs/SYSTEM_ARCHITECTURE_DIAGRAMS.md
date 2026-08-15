# 📐 System Architecture & Sub-Architectures

This document provides visual diagrams and detailed explanations of the **Telegram AI Bot Platform** high-level architecture, module composition, execution flows, monetization, observability, and deployment topologies.

---

## 📑 Table of Contents

1. [High-Level System Architecture](#1-high-level-system-architecture)
2. [Bot Modular Architecture & Class Composition](#2-bot-modular-architecture--class-composition)
3. [Request & AI Generation Lifecycle](#3-request--ai-generation-lifecycle)
4. [Telegram Stars (XTR) Monetization & Credit Engine](#4-telegram-stars-xtr-monetization--credit-engine)
5. [Observability & Telemetry Pipeline](#5-observability--telemetry-pipeline)
6. [Deployment & Multi-Stack Infrastructure Topology](#6-deployment--multi-stack-infrastructure-topology)

---

## 1. High-Level System Architecture

The platform is designed as a decoupled, microservice-based architecture running across containerized stacks on a shared bridge network (`telegram_net`).

```mermaid
flowchart TB
    subgraph TelegramCloud["☁️ Telegram Cloud"]
        TGU[User / Client]
        TGA[Admin]
        TGAPI[Telegram Bot API & Webhooks]
        TGU <--> TGAPI
        TGA <--> TGAPI
    end

    subgraph IngressLayer["🌐 Gateway & Ingress Layer"]
        WHS["Webhook Server / Gateway<br/>(aiohttp / aiogram 3.x)<br/>:8000"]
        TGAPI -->|HTTPS POST| WHS
    end

    subgraph BotInstances["🤖 Bot Services / Micro-Instances"]
        IB1["Image Bot 1<br/>(aiogram Router)"]
        ADM["Admin Bot<br/>(aiogram Router)"]
        WHS -.->|Dispatch| IB1
        WHS -.->|Dispatch| ADM
        TGAPI <-->|Long Polling Mode| IB1
        TGAPI <-->|Long Polling Mode| ADM
    end

    subgraph CoreAsync["⚡ Asynchronous Task & State Layer"]
        RDS[("Redis 7.0<br/>:6379<br/>• FSM State<br/>• Redis Streams & Consumer Groups<br/>• Rate Limits")]
        IB1 <-->|FSM State & XADD Stream Jobs| RDS
        ADM <-->|FSM State| RDS
    end

    subgraph WorkerPool["⚙️ Generation & Execution Pool"]
        WRK["AI Worker Service<br/>(platform_core.queue.worker)<br/>• BotPool Session Reuse<br/>• XREADGROUP & XACK"]
        RDS -->|XREADGROUP / AutoClaim| WRK
    end

    subgraph ExternalAI["🧠 AI Model Providers (OpenRouter / LiteLLM)"]
        OR["OpenRouter Gateway"]
        FLUX["FLUX.1 / Recraft / Imagen"]
        GEMINI["Gemini 2.5/3.1 Flash (Vision / Gen)"]
        WRK -->|Unified Generator| OR
        OR --> FLUX
        OR --> GEMINI
    end

    subgraph Persistence["💾 Persistence Layer (Supabase / Postgres)"]
        DB[("PostgreSQL / Supabase<br/>:5432 / :8001<br/>• Users & Balances<br/>• Presets & Styles<br/>• Transaction History")]
        IB1 <--> DB
        ADM <--> DB
        WRK <--> DB
    end

    subgraph Observability["📊 Telemetry & Observability Stack"]
        PROM["Prometheus (:9090)<br/>Scrapes :8000/metrics"]
        PROMTAIL["Promtail Agent<br/>Collects JSON Container Logs"]
        LOKI["Loki Log Aggregator (:3100)"]
        GRAFANA["Grafana Dashboard (:3000)"]

        WHS -->|/metrics| PROM
        WRK -.->|JSON Logs| PROMTAIL
        IB1 -.->|JSON Logs| PROMTAIL
        PROMTAIL --> LOKI
        PROM --> GRAFANA
        LOKI --> GRAFANA
    end

    WRK -->|Send Generated Media| TGAPI
```

---

## 2. Bot Modular Architecture & Class Composition

Every bot instance is composed of reusable modules via the `ModularBotBuilder` pattern and configured by instance YAML descriptors.

```mermaid
classDiagram
    class BotInstanceConfig {
        +String bot_id
        +String token_env
        +Dict constants
        +List~Preset~ presets
    }

    class ModularBotBuilder {
        +with_module(BaseModule)
        +with_presets(PresetRepository)
        +with_fsm_storage(Storage)
        +build() Dispatcher
    }

    class BaseBotModule {
        <<abstract>>
        +register_handlers(Router)
        +setup_middlewares()
    }

    class ImageGenModule {
        +handle_prompt_message()
        +handle_image_input()
        +handle_aspect_ratio_selection()
    }

    class MonetizationModule {
        +check_credits()
        +handle_buy_command()
        +process_pre_checkout_query()
        +handle_successful_payment()
    }

    class PresetsModule {
        +show_preset_catalog()
        +apply_preset()
        +resolve_prompt_template()
    }

    class AdminControlModule {
        +show_dashboard()
        +manage_presets()
        +broadcast_message()
        +adjust_credits()
    }

    class PresetRepository {
        +load_from_yaml()
        +load_from_db()
        +get_preset(id)
    }

    ModularBotBuilder o-- BotInstanceConfig
    ModularBotBuilder *-- BaseBotModule
    BaseBotModule <|-- ImageGenModule
    BaseBotModule <|-- MonetizationModule
    BaseBotModule <|-- PresetsModule
    BaseBotModule <|-- AdminControlModule
    PresetsModule --> PresetRepository
```

---

## 3. Request & AI Generation Lifecycle

Detailed end-to-end sequence of a user submitting an image generation prompt, credit validation, background queueing, worker execution, fallback resolution, and media delivery.

```mermaid
sequenceDiagram
    autonumber
    actor User as Telegram User
    participant Bot as Bot Instance (Handler)
    participant DB as Supabase / DB
    participant Queue as Redis Queue / Broker
    participant Worker as AI Worker Pool
    participant Engine as Unified AI Generator
    participant Telegram as Telegram Bot API

    User->>Bot: Sends Prompt + Image / Preset Selection
    Bot->>DB: Check Daily Free Credits / Star Balance
    alt Insufficient Balance
        DB-->>Bot: Balance = 0 (Free credits exhausted)
        Bot-->>User: 💳 "Insufficient Credits — Use /buy to top up"
    else Has Sufficient Balance
        DB-->>Bot: Balance OK
        Bot->>DB: Deduct Credit (Pending / Reserved)
        Bot->>Telegram: Send "⏳ Generating your art..." (status msg)
        Bot->>Queue: Enqueue Task (prompt, model, aspect_ratio, chat_id)
        
        Queue->>Worker: Dequeue Job Payload
        Worker->>Engine: Generate Image Request
        
        alt Primary API (aimage_generation)
            Engine->>Engine: Execute LiteLLM aimage_generation()
        else Fallback API (Multimodal Chat / Gemini Vision)
            Engine->>Engine: Fallback to acompletion() with binary bytes
        end

        Engine-->>Worker: Return image_url or image_bytes (BufferedInputFile)
        Worker->>Telegram: send_photo(chat_id, photo, caption)
        Telegram-->>User: Delivers Generated Image
        Worker->>DB: Record Transaction / Analytics Event
        Worker->>Telegram: delete_message(status msg)
    end
```

---

## 4. Telegram Stars (XTR) Monetization & Credit Engine

The monetization model incorporates daily replenishing credits, package purchases using Telegram's native Stars currency (`XTR`), pre-checkout query validations, and idempotent balance updates.

```mermaid
flowchart TD
    Start([User sends command / generation request]) --> CheckFree{Has claimable<br/>daily credits?}
    
    CheckFree -->|Yes: Last claim < 24h| AddDaily[Grant daily_free_credits<br/>Update last_claimed_at in DB]
    CheckFree -->|No| CheckBalance{Current Balance > 0?}
    AddDaily --> CheckBalance
    
    CheckBalance -->|Yes| ExecGen[Execute Generation<br/>Cost: -1 credit]
    
    CheckBalance -->|No| PromptBuy[Show Star Package Catalog<br/>/buy]
    
    PromptBuy --> SelectPkg[User Selects Package<br/>e.g. 50 Stars = 50 Credits]
    SelectPkg --> SendInv[Bot sends send_invoice<br/>Currency: XTR]
    
    SendInv --> TGPayment[User Pays in Telegram UI]
    TGPayment --> PreCheck[Telegram sends PreCheckoutQuery]
    
    PreCheck --> Validate[Bot validates product payload & user ID]
    Validate -->|Valid| OK[Answer PreCheckoutQuery: OK=True]
    Validate -->|Invalid| Reject[Answer PreCheckoutQuery: OK=False]
    
    OK --> SuccPay[Telegram sends SuccessfulPayment]
    SuccPay --> CreditAdd[DB Transaction: Credits added<br/>Log Event to database & Prometheus]
    CreditAdd --> ConfMsg[Send Receipt & Updated Balance to User]
```

---

## 5. Observability & Telemetry Pipeline

How metrics and logs flow from containers to Prometheus, Promtail, Loki, and Grafana.

```mermaid
flowchart LR
    subgraph Apps["Application Containers"]
        B["Bots (image_bot, admin_bot)"]
        W["AI Worker (worker.py)"]
        S["Webhook Server (server.py)"]
    end

    subgraph TelemetryScrape["Metrics & Log Collection"]
        PRM["Prometheus Server<br/>(:9090)"]
        PTL["Promtail Agent<br/>(Docker log socket)"]
    end

    subgraph StorageEngine["Telemetry Storage"]
        TSDB[("Prometheus TSDB")]
        LOKI[("Loki Log Engine<br/>(:3100)")]
    end

    subgraph Visualization["Visualization & Alerting"]
        GRAF["Grafana Dashboard<br/>(:3000)"]
    end

    S -->|Exposes /metrics on :8000| PRM
    B -->|Structured JSON stdout| PTL
    W -->|Structured JSON stdout| PTL
    S -->|Structured JSON stdout| PTL

    PRM --> TSDB
    PTL --> LOKI
    
    TSDB --> GRAF
    LOKI --> GRAF
```

---

## 6. Deployment & Multi-Stack Infrastructure Topology

Independent Docker Compose stacks and GitHub Actions CI/CD workflows coordinate deployments without cross-service downtime.

```mermaid
flowchart TB
    subgraph CICD["🚀 GitHub Actions Split CI/CD"]
        CI["ci.yml<br/>(Pytest & YAML validation)"]
        DB_CD["deploy-database.yml<br/>(Migrations)"]
        BOT_CD["deploy-bots.yml<br/>(Bot Containers & Gateway)"]
        MON_CD["deploy-monitoring.yml<br/>(Grafana / Loki / Prom)"]
    end

    subgraph DockerBridge["Shared Docker Bridge: telegram_net"]
        subgraph AppStack["Stack 1: docker-compose.yml"]
            Redis["telegram_redis:6379"]
            Webhook["telegram_webhook_server:8000"]
            Worker["telegram_ai_worker"]
            Bot1["telegram_image_bot_1"]
            Admin["telegram_admin_bot"]
        end

        subgraph MonStack["Stack 2: docker-compose.monitoring.yml"]
            Prometheus["telegram_prometheus:9090"]
            Grafana["telegram_grafana:3000"]
            Loki["telegram_loki:3100"]
            Promtail["telegram_promtail"]
        end

        subgraph DBStack["Stack 3: docker-compose.supabase.yml"]
            Postgres["supabase_db:5432"]
            PostgREST["supabase_rest:8001"]
            Studio["supabase_studio:8082"]
        end
    end

    BOT_CD -.->|Deploys| AppStack
    MON_CD -.->|Deploys| MonStack
    DB_CD -.->|Deploys| DBStack
```
