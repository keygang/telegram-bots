import logging
from datetime import UTC, datetime
from typing import Any

from platform_core.config import settings
from platform_core.db.models import (
    AnalyticsEvent,
    BotBreakdownMetric,
    BotEvent,
    ButtonClickMetric,
    CommandMetric,
    ErrorBreakdownMetric,
    GenerationLog,
    MessageBreakdownMetric,
    MetricsSummary,
    ModelBreakdownMetric,
    RecentEventMetric,
    StarTransaction,
    UserBalance,
    UserProfile,
)
from supabase import Client, create_client

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


class SupabaseManager:
    """
    Asynchronous Repository Manager for Supabase (PostgreSQL) with automatic
    in-memory fallback when credentials are not configured.
    """

    def __init__(self):
        self.client: Client | None = None
        self._in_memory_users: dict[int, UserProfile] = {}
        self._in_memory_balances: dict[int, UserBalance] = {}
        self._in_memory_transactions: list[StarTransaction] = []
        self._in_memory_events: list[BotEvent] = []
        self._in_memory_analytics_events: list[AnalyticsEvent] = []
        self._in_memory_generations: list[GenerationLog] = []

        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            is_placeholder_url = (
                "localhost" in settings.SUPABASE_URL or "your-project" in settings.SUPABASE_URL
            )
            is_placeholder_key = (
                "your-self-hosted" in settings.SUPABASE_KEY
                or "your-supabase" in settings.SUPABASE_KEY
            )
            if is_placeholder_url and is_placeholder_key:
                logger.info(
                    f"Supabase credentials appear to be placeholder defaults ({settings.SUPABASE_URL}). Using in-memory store."
                )
            else:
                try:
                    self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                    logger.info(
                        f"Successfully initialized Supabase PostgreSQL client ({settings.SUPABASE_URL})."
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to connect to Supabase ({settings.SUPABASE_URL}): {e}. Falling back to in-memory store."
                    )

    # --- USER PROFILE OPERATIONS ---

    async def sync_user(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> UserProfile:
        now = utc_now()
        if self.client:
            try:
                data: dict[str, Any] = {
                    "telegram_id": telegram_id,
                    "username": username,
                    "first_name": first_name,
                    "last_name": last_name,
                    "last_active_at": now.isoformat(),
                }
                if language_code is not None:
                    data["language_code"] = language_code

                res = self.client.table("users").upsert(data).execute()
                if res.data:
                    return UserProfile(**res.data[0])
            except Exception as e:
                logger.error(f"Supabase sync_user error: {e}")

        # In-memory fallback
        if telegram_id not in self._in_memory_users:
            profile = UserProfile(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                language_code=language_code,
                created_at=now,
                last_active_at=now,
            )
            self._in_memory_users[telegram_id] = profile
        else:
            profile = self._in_memory_users[telegram_id]
            profile.username = username
            profile.first_name = first_name
            profile.last_name = last_name
            if language_code is not None:
                profile.language_code = language_code
            profile.last_active_at = now
        return profile

    async def update_user_language(
        self, telegram_id: int, language_code: str
    ) -> UserProfile | None:
        """Updates user's language setting persistently."""
        if self.client:
            try:
                res = (
                    self.client.table("users")
                    .update({"language_code": language_code})
                    .eq("telegram_id", telegram_id)
                    .execute()
                )
                if res.data:
                    return UserProfile(**res.data[0])
            except Exception as e:
                logger.error(f"Supabase update_user_language error: {e}")

        # In-memory fallback
        if telegram_id in self._in_memory_users:
            self._in_memory_users[telegram_id].language_code = language_code
            return self._in_memory_users[telegram_id]
        else:
            profile = UserProfile(telegram_id=telegram_id, language_code=language_code)
            self._in_memory_users[telegram_id] = profile
            return profile

    async def update_user_model(self, telegram_id: int, model_name: str) -> UserProfile | None:
        """Updates user's selected AI model preference persistently."""
        if self.client:
            try:
                res = (
                    self.client.table("users")
                    .update({"selected_model": model_name})
                    .eq("telegram_id", telegram_id)
                    .execute()
                )
                if res.data:
                    return UserProfile(**res.data[0])
            except Exception as e:
                logger.error(f"Supabase update_user_model error: {e}")

        # In-memory fallback
        if telegram_id in self._in_memory_users:
            self._in_memory_users[telegram_id].selected_model = model_name
            return self._in_memory_users[telegram_id]
        else:
            profile = UserProfile(telegram_id=telegram_id, selected_model=model_name)
            self._in_memory_users[telegram_id] = profile
            return profile

    # --- CREDIT & MONETIZATION BALANCE OPERATIONS ---

    async def get_user_balance(self, user_id: int) -> UserBalance:
        now = utc_now()
        if self.client:
            try:
                res = (
                    self.client.table("user_balances").select("*").eq("user_id", user_id).execute()
                )
                if res.data:
                    balance = UserBalance(**res.data[0])
                    # Check daily free credit reset
                    if balance.free_credits_reset_at.date() < now.date():
                        balance.credits_remaining = max(
                            balance.credits_remaining, settings.FREE_DAILY_CREDITS
                        )
                        balance.free_credits_reset_at = now
                        self.client.table("user_balances").update(
                            {
                                "credits_remaining": balance.credits_remaining,
                                "free_credits_reset_at": now.isoformat(),
                            }
                        ).eq("user_id", user_id).execute()
                    return balance
                else:
                    new_balance = UserBalance(
                        user_id=user_id, credits_remaining=settings.FREE_DAILY_CREDITS
                    )
                    self.client.table("user_balances").insert(
                        new_balance.model_dump(mode="json")
                    ).execute()
                    return new_balance
            except Exception as e:
                logger.error(f"Supabase get_user_balance error: {e}")

        # In-memory fallback
        if user_id not in self._in_memory_balances:
            self._in_memory_balances[user_id] = UserBalance(
                user_id=user_id, credits_remaining=settings.FREE_DAILY_CREDITS
            )
        balance = self._in_memory_balances[user_id]
        if balance.free_credits_reset_at.date() < now.date():
            balance.credits_remaining = max(balance.credits_remaining, settings.FREE_DAILY_CREDITS)
            balance.free_credits_reset_at = now
        return balance

    async def deduct_user_credit(self, user_id: int, amount: int = 1) -> bool:
        balance = await self.get_user_balance(user_id)
        if balance.credits_remaining < amount:
            return False

        balance.credits_remaining -= amount
        if self.client:
            try:
                self.client.table("user_balances").update(
                    {"credits_remaining": balance.credits_remaining}
                ).eq("user_id", user_id).execute()
            except Exception as e:
                logger.error(f"Supabase deduct_user_credit error: {e}")
        return True

    async def add_user_credits(
        self,
        user_id: int,
        bot_id: str,
        stars_paid: int,
        credits_to_add: int,
        telegram_charge_id: str,
    ) -> UserBalance:
        balance = await self.get_user_balance(user_id)
        balance.credits_remaining += credits_to_add
        balance.total_stars_spent += stars_paid

        transaction = StarTransaction(
            user_id=user_id,
            bot_id=bot_id,
            stars_amount=stars_paid,
            credits_added=credits_to_add,
            telegram_payment_charge_id=telegram_charge_id,
        )

        if self.client:
            try:
                self.client.table("user_balances").update(
                    {
                        "credits_remaining": balance.credits_remaining,
                        "total_stars_spent": balance.total_stars_spent,
                    }
                ).eq("user_id", user_id).execute()

                self.client.table("star_transactions").insert(
                    transaction.model_dump(mode="json")
                ).execute()
            except Exception as e:
                logger.error(f"Supabase add_user_credits error: {e}")
        else:
            self._in_memory_transactions.append(transaction)

        return balance

    # --- POSTHOG-STYLE ANALYTICS EVENTS ---

    async def track_event(self, event: AnalyticsEvent) -> None:
        """
        Record a PostHog-style AnalyticsEvent into PostgreSQL 'events' table
        (or in-memory store if DB is offline).
        """
        if not settings.METRICS_ENABLED:
            return

        if self.client:
            try:
                self.client.table("events").insert(event.model_dump(mode="json")).execute()
                return
            except Exception as e:
                # Fallback to legacy bot_events table if events table is not yet migrated
                try:
                    user_id_int = int(event.distinct_id) if event.distinct_id.isdigit() else 0
                    self.client.table("bot_events").insert(
                        {
                            "bot_id": event.bot_id,
                            "user_id": user_id_int,
                            "event_type": event.properties.get("event_type", event.event),
                            "event_name": event.event,
                            "duration_ms": event.duration_ms,
                            "metadata": event.properties,
                        }
                    ).execute()
                    return
                except Exception as fallback_err:
                    logger.error(f"Supabase track_event error: {e} (fallback: {fallback_err})")

        self._in_memory_analytics_events.append(event)
        # Also sync to _in_memory_events for backwards compatibility
        user_id_int = int(event.distinct_id) if event.distinct_id.isdigit() else 0
        self._in_memory_events.append(
            BotEvent(
                id=event.id,
                bot_id=event.bot_id,
                user_id=user_id_int,
                event_type=event.properties.get("event_type", "custom"),
                event_name=event.event,
                duration_ms=event.duration_ms,
                metadata=event.properties,
                created_at=event.timestamp,
            )
        )

    async def track_events_batch(self, events: list[AnalyticsEvent]) -> None:
        """Record multiple events in a single batch insert."""
        if not settings.METRICS_ENABLED or not events:
            return

        if self.client:
            try:
                payload = [e.model_dump(mode="json") for e in events]
                self.client.table("events").insert(payload).execute()
                return
            except Exception as e:
                logger.error(f"Supabase track_events_batch error: {e}")

        for e in events:
            await self.track_event(e)

    async def query_events(
        self,
        event: str | None = None,
        distinct_id: str | None = None,
        bot_id: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
        property_filters: dict[str, Any] | None = None,
    ) -> list[AnalyticsEvent]:
        """
        Query PostHog-style events with optional filtering on event type, user, bot,
        time window, and JSONB properties.
        """
        if self.client:
            try:
                q = self.client.table("events").select("*")
                if event:
                    q = q.eq("event", event)
                if distinct_id:
                    q = q.eq("distinct_id", str(distinct_id))
                if bot_id:
                    q = q.eq("bot_id", bot_id)
                if status:
                    q = q.eq("status", status)
                if since:
                    q = q.gte("timestamp", since.isoformat())
                if property_filters:
                    for k, v in property_filters.items():
                        q = q.eq(f"properties->>{k}", str(v))
                q = q.order("timestamp", desc=True).limit(limit)
                res = q.execute()
                return [AnalyticsEvent(**item) for item in res.data] if res.data else []
            except Exception as e:
                logger.error(f"Supabase query_events error: {e}")

        # In-memory query filtering
        filtered = list(self._in_memory_analytics_events)
        if event:
            filtered = [e for e in filtered if e.event == event]
        if distinct_id:
            filtered = [e for e in filtered if e.distinct_id == str(distinct_id)]
        if bot_id:
            filtered = [e for e in filtered if e.bot_id == bot_id]
        if status:
            filtered = [e for e in filtered if e.status == status]
        if since:
            filtered = [e for e in filtered if e.timestamp >= since]
        if property_filters:
            filtered = [
                e
                for e in filtered
                if all(e.properties.get(k) == v for k, v in property_filters.items())
            ]
        filtered.sort(key=lambda x: x.timestamp, reverse=True)
        return filtered[:limit]

    # --- LEGACY METRICS & TELEMETRY EVENTS ---

    async def record_event(self, event: BotEvent) -> None:
        if not settings.METRICS_ENABLED:
            return

        analytics_event = AnalyticsEvent.from_bot_event(event)
        self._in_memory_analytics_events.append(analytics_event)
        self._in_memory_events.append(event)

        if self.client:
            try:
                self.client.table("bot_events").insert(event.model_dump(mode="json")).execute()
                return
            except Exception as e:
                logger.error(f"Supabase record_event error: {e}")

    # --- GENERATION LOGGING ---

    async def log_generation(self, log: GenerationLog) -> None:
        if self.client:
            try:
                self.client.table("generation_logs").insert(log.model_dump(mode="json")).execute()
                return
            except Exception as e:
                logger.error(f"Supabase log_generation error: {e}")

        self._in_memory_generations.append(log)

    # --- ANALYTICS SUMMARY REPORTING ---

    async def get_metrics_summary(self, bot_id: str | None = None) -> MetricsSummary:
        if self.client:
            try:
                events_query = self.client.table("bot_events").select("*")
                if bot_id:
                    events_query = events_query.eq("bot_id", bot_id)
                events_res = events_query.execute()
                events = [BotEvent(**e) for e in events_res.data] if events_res.data else []

                generations_query = self.client.table("generation_logs").select("*")
                if bot_id:
                    generations_query = generations_query.eq("bot_id", bot_id)
                generations_res = generations_query.execute()
                generations = (
                    [GenerationLog(**g) for g in generations_res.data]
                    if generations_res.data
                    else []
                )

                transactions_query = self.client.table("star_transactions").select("*")
                if bot_id:
                    transactions_query = transactions_query.eq("bot_id", bot_id)
                transactions_res = transactions_query.execute()
                transactions = (
                    [StarTransaction(**t) for t in transactions_res.data]
                    if transactions_res.data
                    else []
                )

                return self._compute_metrics_summary(events, generations, transactions)
            except Exception as e:
                logger.error(f"Supabase get_metrics_summary error: {e}")

        return self._compute_metrics_summary(
            self._in_memory_events
            if not bot_id
            else [e for e in self._in_memory_events if e.bot_id == bot_id],
            self._in_memory_generations
            if not bot_id
            else [g for g in self._in_memory_generations if g.bot_id == bot_id],
            self._in_memory_transactions
            if not bot_id
            else [t for t in self._in_memory_transactions if t.bot_id == bot_id],
        )

    async def get_button_click_metrics(
        self, bot_id: str | None = None, limit: int = 20
    ) -> list[ButtonClickMetric]:
        summary = await self.get_metrics_summary(bot_id=bot_id)
        return summary.top_buttons[:limit]

    async def get_command_metrics(
        self, bot_id: str | None = None, limit: int = 20
    ) -> list[CommandMetric]:
        summary = await self.get_metrics_summary(bot_id=bot_id)
        return summary.top_commands[:limit]

    async def get_bot_breakdown(self) -> list[BotBreakdownMetric]:
        summary = await self.get_metrics_summary()
        return summary.bots_breakdown

    async def get_messages_sent_metrics(
        self, bot_id: str | None = None, limit: int = 20
    ) -> list[MessageBreakdownMetric]:
        summary = await self.get_metrics_summary(bot_id=bot_id)
        return summary.messages_breakdown[:limit]

    async def get_errors_metrics(
        self, bot_id: str | None = None, limit: int = 20
    ) -> list[ErrorBreakdownMetric]:
        summary = await self.get_metrics_summary(bot_id=bot_id)
        return summary.errors_breakdown[:limit]

    async def get_recent_events_metrics(
        self, bot_id: str | None = None, limit: int = 20
    ) -> list[RecentEventMetric]:
        summary = await self.get_metrics_summary(bot_id=bot_id)
        return summary.recent_events[:limit]

    def _compute_metrics_summary(
        self,
        events: list[BotEvent],
        generations: list[GenerationLog],
        transactions: list[StarTransaction],
    ) -> MetricsSummary:
        unique_users = len(
            {e.user_id for e in events if e.user_id} | {g.user_id for g in generations if g.user_id}
        )
        click_count = sum(1 for e in events if e.event_type == "click")
        command_count = sum(1 for e in events if e.event_type == "command")
        total_generations = len(generations)
        successful_generations = sum(1 for g in generations if g.status == "success")
        failed_generations = sum(1 for g in generations if g.status == "failed")
        total_stars = sum(t.stars_amount for t in transactions)

        # Messages Sent Breakdown
        msg_stats: dict[str, dict[str, Any]] = {}
        error_stats: dict[str, dict[str, Any]] = {}
        total_messages_sent = 0
        total_errors = 0

        for e in events:
            # Check for message_sent events
            if e.event_type == "message_sent" or (
                e.event_name and e.event_name.startswith("message_sent:")
            ):
                total_messages_sent += 1
                m_type = e.metadata.get("message_type", "text") if e.metadata else "text"
                if m_type not in msg_stats:
                    msg_stats[m_type] = {"count": 0, "users": set(), "lengths": []}
                msg_stats[m_type]["count"] += 1
                if e.user_id:
                    msg_stats[m_type]["users"].add(e.user_id)
                t_len = e.metadata.get("text_length") if e.metadata else None
                if t_len:
                    msg_stats[m_type]["lengths"].append(t_len)

            # Check for error events
            if (
                e.event_type == "error"
                or (e.event_name and e.event_name.startswith("error:"))
                or e.metadata.get("status") == "error"
            ):
                total_errors += 1
                err_type = (
                    e.metadata.get("error_type", e.event_name or "UnknownError")
                    if e.metadata
                    else (e.event_name or "UnknownError")
                )
                if err_type not in error_stats:
                    error_stats[err_type] = {
                        "count": 0,
                        "users": set(),
                        "last_msg": e.metadata.get("error_message", "") if e.metadata else "",
                    }
                error_stats[err_type]["count"] += 1
                if e.user_id:
                    error_stats[err_type]["users"].add(e.user_id)
                if e.metadata and e.metadata.get("error_message"):
                    error_stats[err_type]["last_msg"] = e.metadata["error_message"]

        messages_breakdown = [
            MessageBreakdownMetric(
                type=m_type,
                count=data["count"],
                unique_users=len(data["users"]),
                avg_chars=int(sum(data["lengths"]) / len(data["lengths"]))
                if data["lengths"]
                else 0,
            )
            for m_type, data in sorted(msg_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        errors_breakdown = [
            ErrorBreakdownMetric(
                error_type=err_type,
                count=data["count"],
                unique_users=len(data["users"]),
                last_message=data["last_msg"],
            )
            for err_type, data in sorted(
                error_stats.items(), key=lambda x: x[1]["count"], reverse=True
            )
        ]

        # Top Presets
        preset_counts: dict[str, int] = {}
        for g in generations:
            if g.preset_id:
                preset_counts[g.preset_id] = preset_counts.get(g.preset_id, 0) + 1
        top_presets = sorted(preset_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Top Button Clicks Breakdown
        button_stats: dict[str, dict[str, Any]] = {}
        for e in events:
            if e.event_type == "click":
                name = e.event_name or "unknown_button"
                if name not in button_stats:
                    button_stats[name] = {"count": 0, "users": set(), "durations": []}
                button_stats[name]["count"] += 1
                if e.user_id:
                    button_stats[name]["users"].add(e.user_id)
                if e.duration_ms is not None:
                    button_stats[name]["durations"].append(e.duration_ms)

        top_buttons = [
            ButtonClickMetric(
                name=name,
                count=data["count"],
                unique_users=len(data["users"]),
                avg_duration_ms=int(sum(data["durations"]) / len(data["durations"]))
                if data["durations"]
                else 0,
            )
            for name, data in sorted(
                button_stats.items(), key=lambda x: x[1]["count"], reverse=True
            )
        ]

        # Top Commands Breakdown
        cmd_stats: dict[str, dict[str, Any]] = {}
        for e in events:
            if e.event_type == "command":
                name = e.event_name or "unknown_command"
                if name not in cmd_stats:
                    cmd_stats[name] = {"count": 0, "users": set(), "durations": []}
                cmd_stats[name]["count"] += 1
                if e.user_id:
                    cmd_stats[name]["users"].add(e.user_id)
                if e.duration_ms is not None:
                    cmd_stats[name]["durations"].append(e.duration_ms)

        top_commands = [
            CommandMetric(
                name=name,
                count=data["count"],
                unique_users=len(data["users"]),
                avg_duration_ms=int(sum(data["durations"]) / len(data["durations"]))
                if data["durations"]
                else 0,
            )
            for name, data in sorted(cmd_stats.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        # Per-Bot Breakdown
        all_bot_ids = (
            {e.bot_id for e in events}
            | {g.bot_id for g in generations}
            | {t.bot_id for t in transactions}
        )
        bots_breakdown = []
        for b_id in sorted(all_bot_ids):
            b_events = [e for e in events if e.bot_id == b_id]
            b_gens = [g for g in generations if g.bot_id == b_id]
            b_trans = [t for t in transactions if t.bot_id == b_id]
            b_users = len(
                {e.user_id for e in b_events if e.user_id}
                | {g.user_id for g in b_gens if g.user_id}
            )
            bots_breakdown.append(
                BotBreakdownMetric(
                    bot_id=b_id,
                    users=b_users,
                    clicks=sum(1 for e in b_events if e.event_type == "click"),
                    commands=sum(1 for e in b_events if e.event_type == "command"),
                    generations=len(b_gens),
                    messages_sent=sum(
                        1
                        for e in b_events
                        if e.event_type == "message_sent"
                        or (e.event_name and e.event_name.startswith("message_sent:"))
                    ),
                    stars=sum(t.stars_amount for t in b_trans),
                    events=len(b_events),
                )
            )

        # Models Breakdown
        model_stats: dict[str, dict[str, Any]] = {}
        for g in generations:
            m_name = g.model_name or "default"
            if m_name not in model_stats:
                model_stats[m_name] = {"total": 0, "success": 0, "failed": 0, "durations": []}
            model_stats[m_name]["total"] += 1
            if g.status == "success":
                model_stats[m_name]["success"] += 1
            elif g.status == "failed":
                model_stats[m_name]["failed"] += 1
            if g.duration_ms:
                model_stats[m_name]["durations"].append(g.duration_ms)

        models_breakdown = [
            ModelBreakdownMetric(
                model_name=m_name,
                total=data["total"],
                success=data["success"],
                failed=data["failed"],
                avg_duration_ms=int(sum(data["durations"]) / len(data["durations"]))
                if data["durations"]
                else 0,
            )
            for m_name, data in sorted(
                model_stats.items(), key=lambda x: x[1]["total"], reverse=True
            )
        ]

        # Recent Events Feed
        recent_events = [
            RecentEventMetric(
                event=e.event_name or e.event_type,
                bot_id=e.bot_id,
                user_id=e.user_id,
                duration_ms=e.duration_ms,
                created_at=e.created_at.strftime("%H:%M:%S") if e.created_at else "",
            )
            for e in sorted(events, key=lambda x: x.created_at, reverse=True)[:15]
        ]

        return MetricsSummary(
            total_users=unique_users,
            total_events=len(events),
            total_commands=command_count,
            total_button_clicks=click_count,
            total_generations=total_generations,
            successful_generations=successful_generations,
            failed_generations=failed_generations,
            total_messages_sent=total_messages_sent,
            total_errors=total_errors,
            total_stars_earned=total_stars,
            top_presets=top_presets,
            top_buttons=top_buttons,
            top_commands=top_commands,
            bots_breakdown=bots_breakdown,
            models_breakdown=models_breakdown,
            messages_breakdown=messages_breakdown,
            errors_breakdown=errors_breakdown,
            recent_events=recent_events,
        )

    # Legacy alias
    def _compute_metrics_dict(
        self,
        events: list[BotEvent],
        generations: list[GenerationLog],
        transactions: list[StarTransaction],
    ) -> MetricsSummary:
        return self._compute_metrics_summary(events, generations, transactions)


# Global database manager instance
db = SupabaseManager()
