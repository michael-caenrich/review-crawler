"""First-pass hazard classification for AliExpress 1/2-star reviews using DeepSeek-V4-Flash."""

import os
import time
import pathlib

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from cli_utils import colorize, format_elapsed, pick_file, classify_batch, save_progress
from config import (
    ALIEXPRESS_REVIEWS_PATH,
    ALIEXPRESS_LABELED_PATH,
    PROMPT_HAZARD,
    MODELS,
)

MODEL = MODELS["DeepInfra"]["DeepSeek-V4-Flash"]
BASE_URL = MODELS["DeepInfra"]["base_url"]
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY_G2")
BATCH_SIZE = 40
TEST_LIMIT: int | None = None  # set to None for full run


def load_reviews(file_path: pathlib.Path) -> list[dict[str, str | int]] | None:
    """Load raw reviews CSV file."""
    reviews = pd.read_csv(file_path)  # type: ignore
    reviews = reviews.to_dict(orient="records")  # type: ignore
    return reviews


def save_hazard_reviews(labeled_path: pathlib.Path) -> None:
    """Read all CSV files, extract '1' reviews, and write to CSV."""
    print(f"\n{colorize('[INFO]')} Extracting hazard reviews from all labeled files...")
    all_hazard = []

    for file in labeled_path.glob("*_labeled.csv"):
        df = pd.read_csv(file)  # type: ignore

        if df["hazard_label_classified"].isna().any():  # type: ignore
            print(f"{colorize('[WARNING]')} {file.name} has unlabeled rows — skipping incomplete file.")
            continue

        df_hazard = df[df["hazard_label_classified"] == 1]  # type: ignore
        print(f"{colorize('[INFO]')} {file.name}: {len(df_hazard)} hazard reviews found.")
        all_hazard.append(df_hazard)

    if not all_hazard:
        print(f"{colorize('[WARNING]')} No labeled files ready — skipping final output.")
        return

    df_final = pd.concat(all_hazard)
    df_final["hazard_label_classified"] = df_final["hazard_label_classified"].astype(int)
    final_path = labeled_path / "aliexpress_us_hazard_reviews_classified.csv"
    df_final.to_csv(final_path, index=False)
    print(f"{colorize('[DONE]')} Saved {len(df_final)} total hazard reviews → {final_path.name}")


def main() -> None:
    """Run first-pass classification and export hazard candidates to CSV."""
    print(f"{colorize('[INFO]')} Starting hazard classification pipeline...")
    selected_files = pick_file(ALIEXPRESS_REVIEWS_PATH, "*.csv")

    start = time.time()
    for file in selected_files:
        name = file.stem.replace("_raw", "_labeled")
        labeled_path = ALIEXPRESS_LABELED_PATH / (name + ".csv")

        print(f"\n{colorize('[INFO]')} Processing {file.name}...")
        file_start = time.time()
        reviews = load_reviews(file)
        if reviews is None:
            continue

        if labeled_path.exists():
            labeled_df = pd.read_csv(labeled_path)  # type: ignore
            labeled_df = labeled_df.dropna(subset=["hazard_label_classified"])  # type: ignore
            labeled_df.to_csv(labeled_path, index=False)
            already_done = len(labeled_df)
        else:
            already_done = 0

        unlabeled = reviews[already_done:]

        if TEST_LIMIT:
            unlabeled = unlabeled[:TEST_LIMIT]
        total = len(unlabeled)

        if already_done > 0:
            print(
                f"{colorize('[INFO]')} {len(reviews)} reviews loaded — {already_done} already classified, "
                  f"{total} to classify{f' (TEST_LIMIT={TEST_LIMIT})' if TEST_LIMIT else ''}."
            )

        for i in range(0, total, BATCH_SIZE):
            batch = unlabeled[i:i + BATCH_SIZE]
            labels = classify_batch(batch, PROMPT_HAZARD, MODEL, DEEPINFRA_API_KEY, BASE_URL)
            save_progress(batch, labels, labeled_path, "hazard_label_classified")
            print(f"{colorize('[INFO]')} Batch {i // BATCH_SIZE + 1}/{-(-total // BATCH_SIZE)} ({i + len(batch)}/{total})")

        elapsed = int(time.time() - file_start)
        print(f"{colorize('[INFO]')} Time: {format_elapsed(elapsed)}")

    if input("\nGenerate hazard reviews output now? (y/n): ").strip().lower() == "y":
        save_hazard_reviews(ALIEXPRESS_LABELED_PATH)

    elapsed = int(time.time() - start)
    print(f"{colorize('[INFO]')} Total time: {format_elapsed(elapsed)}")


if __name__ == "__main__":
    main()
