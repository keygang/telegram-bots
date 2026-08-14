import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from supabase import create_client, Client
from platform_core.config import settings
from platform_core.db.models import UserProfile, UserBalance, StarTransaction, BotEvent, GenerationLog

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SupabaseManager:
    """
    Asynchronous Repository Manager for Supabase (PostgreSQL) with automatic
    in-memory fallback when credentials are not configured.
    """

    def __init__(self):
        self.client: Optional[Client] = None
        self._in_memory_users: Dict[int, UserProfile] = {}
        self._in_memory_balances: Dict[int, UserBalance] = {}
        self._in_memory_transactions: List[StarTransaction] = []
        self._in_memory_events: List[BotEvent] = []
        self._in_memory_generations: List[GenerationLog] = []

        if settings.SUPABASE_URL and settings.SUPABASE_KEY:
            is_placeholder_url = "localhost" in settings.SUPABASE_URL or "your-project" in settings.SUPABASE_URL
            is_placeholder_key = "your-self-hosted" in settings.SUPABASE_KEY or "your-supabase" in settings.SUPABASE_KEY
            if is_placeholder_url and is_placeholder_key:
                logger.info(f"Supabase credentials appear to be placeholder defaults ({settings.SUPABASE_URL}). Using in-memory store.")
            else:
                try:
                    self.client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                    logger.info(f"Successfully initialized Supabase PostgreSQL client ({settings.SUPABASE_URL}).")
                except Exception as e:
                    logger.warning(f"Failed to connect to Supabase ({settings.SUPABASE_URL}): {e}. Falling back to in-memory store.")

    # --- USER PROFILE OPERATIONS ---

    async def sync_user(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        language_code: Optional[str] = None
    ) -> UserProfile:
        now = utc_now()
        if self.client:
            try:
                data: Dict[str, Any] = {
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

    async def update_user_language(self, telegram_id: int, language_code: str) -> Optional[UserProfile]:
        """Updates user's language setting persistently."""
        if self.client:
            try:
                res = self.client.table("users").update({"language_code": language_code}).eq("telegram_id", telegram_id).execute()
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

    # --- CREDIT & MONETIZATION BALANCE OPERATIONS ---

    async def get_user_balance(self, user_id: int) -> UserBalance:
        now = utc_now()
        if self.client:
            try:
                res = self.client.table("user_balances").select("*").eq("user_id", user_id).execute()
                if res.data:
                    balance = UserBalance(**res.data[0])
                    # Check daily free credit reset
                    if balance.free_credits_reset_at.date() < now.date():
                        balance.credits_remaining = max(balance.credits_remaining, settings.FREE_DAILY_CREDITS)
                        balance.free_credits_reset_at = now
                        self.client.table("user_balances").update({
                            "credits_remaining": balance.credits_remaining,
                            "free_credits_reset_at": now.isoformat()
                        }).eq("user_id", user_id).execute()
                    return balance
                else:
                    new_balance = UserBalance(user_id=user_id, credits_remaining=settings.FREE_DAILY_CREDITS)
                    self.client.table("user_balances").insert(new_balance.model_dump(mode="json")).execute()
                    return new_balance
            except Exception as e:
                logger.error(f"Supabase get_user_balance error: {e}")

        # In-memory fallback
        if user_id not in self._in_memory_balances:
            self._in_memory_balances[user_id] = UserBalance(user_id=user_id, credits_remaining=settings.FREE_DAILY_CREDITS)
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
                self.client.table("user_balances").update({
                    "credits_remaining": balance.credits_remaining
                }).eq("user_id", user_id).execute()
            except Exception as e:
                logger.error(f"Supabase deduct_user_credit error: {e}")
        return True

    async def add_user_credits(self, user_id: int, bot_id: str, stars_paid: int, credits_to_add: int, telegram_charge_id: str) -> UserBalance:
        balance = await self.get_user_balance(user_id)
        balance.credits_remaining += credits_to_add
        balance.total_stars_spent += stars_paid

        transaction = StarTransaction(
            user_id=user_id,
            bot_id=bot_id,
            stars_amount=stars_paid,
            credits_added=credits_to_add,
            telegram_payment_charge_id=telegram_charge_id
        )

        if self.client:
            try:
                self.client.table("user_balances").update({
                    "credits_remaining": balance.credits_remaining,
                    "total_stars_spent": balance.total_stars_spent
                }).eq("user_id", user_id).execute()

                self.client.table("star_transactions").insert(transaction.model_dump(mode="json")).execute()
            except Exception as e:
                logger.error(f"Supabase add_user_credits error: {e}")
        else:
            self._in_memory_transactions.append(transaction)

        return balance

    # --- METRICS & TELEMETRY EVENTS ---

    async def record_event(self, event: BotEvent) -> None:
        if not settings.METRICS_ENABLED:
            return

        if self.client:
            try:
                self.client.table("bot_events").insert(event.model_dump(mode="json")).execute()
                return
            except Exception as e:
                logger.error(f"Supabase record_event error: {e}")

        self._in_memory_events.append(event)

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

    async def get_metrics_summary(self, bot_id: Optional[str] = None) -> Dict[str, Any]:
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
                generations = [GenerationLog(**g) for g in generations_res.data] if generations_res.data else []

                transactions_query = self.client.table("star_transactions").select("*")
                if bot_id:
                    transactions_query = transactions_query.eq("bot_id", bot_id)
                transactions_res = transactions_query.execute()
                transactions = [StarTransaction(**t) for t in transactions_res.data] if transactions_res.data else []

                return self._compute_metrics_dict(events, generations, transactions)
            except Exception as e:
                logger.error(f"Supabase get_metrics_summary error: {e}")

        return self._compute_metrics_dict(
            self._in_memory_events if not bot_id else [e for e in self._in_memory_events if e.bot_id == bot_id],
            self._in_memory_generations if not bot_id else [g for g in self._in_memory_generations if g.bot_id == bot_id],
            self._in_memory_transactions if not bot_id else [t for t in self._in_memory_transactions if t.bot_id == bot_id],
        )

    def _compute_metrics_dict(
        self,
        events: List[BotEvent],
        generations: List[GenerationLog],
        transactions: List[StarTransaction]
    ) -> Dict[str, Any]:
        unique_users = len({e.user_id for e in events} | {g.user_id for g in generations})
        click_count = sum(1 for e in events if e.event_type == "click")
        command_count = sum(1 for e in events if e.event_type == "command")
        total_generations = len(generations)
        successful_generations = sum(1 for g in generations if g.status == "success")
        total_stars = sum(t.stars_amount for t in transactions)

        preset_counts: Dict[str, int] = {}
        for g in generations:
            if g.preset_id:
                preset_counts[g.preset_id] = preset_counts.get(g.preset_id, 0) + 1

        top_presets = sorted(preset_counts.items(), key=lambda x: x[1], reverse=True)[:5]

        return {
            "total_users": unique_users,
            "total_commands": command_count,
            "total_button_clicks": click_count,
            "total_generations": total_generations,
            "successful_generations": successful_generations,
            "total_stars_earned": total_stars,
            "top_presets": top_presets,
        }


# Global database manager instance
db = SupabaseManager()
