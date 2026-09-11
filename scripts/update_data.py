import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("update_data")

if __name__ == "__main__":
    from app import seed

    n = seed.update_from_web(scrape_profiles=True)
    print(f"OK : {n} joueurs en base")