import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app import seed
from app.config import DAILY_SCRAPE_HOUR, DAILY_SCRAPE_MINUTE

logger = logging.getLogger("fifa.scheduler")

scheduler = BackgroundScheduler()


def run_daily_update():
    logger.info("Daily data update started at 22:00.")
    try:
        n = seed.update_from_web(scrape_profiles=True)
        logger.info("Daily update finished: %s players.", n)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Daily update failed: %s", exc)


def start_scheduler():
    if scheduler.get_jobs():
        return
    scheduler.add_job(
        run_daily_update,
        CronTrigger(hour=DAILY_SCRAPE_HOUR, minute=DAILY_SCRAPE_MINUTE),
        id="daily_scrape",
        misfire_grace_time=3600,
        coalesce=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: daily scrape at %02d:%02d.",
        DAILY_SCRAPE_HOUR,
        DAILY_SCRAPE_MINUTE,
    )