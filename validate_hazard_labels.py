"""Second-pass hazard validation for AliExpress 1/2-star reviews using a stronger model."""

import os
import time
import pathlib

import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from cli_utils import colorize, format_elapsed, classify_batch, save_progress
from config import (
    ALIEXPRESS_LABELED_PATH,
    ALIEXPRESS_OUTPUT_PATH,
    PROMPT_HAZARD,
    MODELS,
)

MODEL = MODELS["DeepInfra"]["DeepSeek-V4-Pro"]
BASE_URL = MODELS["DeepInfra"]["base_url"]
DEEPINFRA_API_KEY = os.getenv("DEEPINFRA_API_KEY")
BATCH_SIZE = 20
TEST_LIMIT: int | None = None  # set to None for full run
PROMPT = PROMPT_HAZARD


def load_reviews(file_path: pathlib.Path) -> list[dict[str, str | int]] | None:
    """Load CSV with classified reviews."""
    if not file_path.exists():
        print(f"{colorize('[WARNING]')} File {file_path.name} not found")
        return None
    reviews = pd.read_csv(file_path)  # type: ignore
    return reviews.to_dict(orient="records")  # type: ignore


def main() -> None:
    """Run second-pass validation and export confirmed hazard reviews to Excel."""
    print(f"\n{colorize('[INFO]')} Starting hazard validation...\n")
    classified_path = ALIEXPRESS_LABELED_PATH / "aliexpress_us_hazard_reviews_classified.csv"
    validated_path = ALIEXPRESS_LABELED_PATH / "aliexpress_us_hazard_reviews_validated.csv"
    final_path = ALIEXPRESS_OUTPUT_PATH / "aliexpress_us_hazard_reviews_final.xlsx"

    reviews = load_reviews(classified_path)
    if reviews is None:
        return

    if validated_path.exists():
        df_validated = pd.read_csv(validated_path)  # type: ignore
        df_validated = df_validated.dropna(subset=["hazard_label_validated"])  # type: ignore
        df_validated.to_csv(validated_path, index=False)
        already_done = len(df_validated)
    else:
        already_done = 0

    unlabeled = reviews[already_done:]

    if TEST_LIMIT:
        unlabeled = unlabeled[:TEST_LIMIT]
    total = len(unlabeled)

    if already_done > 0:
        print(
            f"{colorize('[INFO]')} {len(reviews)} reviews loaded — {already_done} already validated, "
            f"{total} to validate{f' (TEST_LIMIT={TEST_LIMIT})' if TEST_LIMIT else ''}."
        )

    start = time.time()
    for i in range(0, total, BATCH_SIZE):
        batch = unlabeled[i: i + BATCH_SIZE]
        labels = classify_batch(batch, PROMPT, MODEL, DEEPINFRA_API_KEY, base_url=BASE_URL)
        save_progress(batch, labels, validated_path, "hazard_label_validated")
        print(f"{colorize('[INFO]')} Batch {(i // BATCH_SIZE) + 1}/{-(-total // BATCH_SIZE)} ({i + len(batch)}/{total})")

    df = pd.read_csv(validated_path)  # type: ignore
    if df["hazard_label_validated"].isna().any():  # type: ignore
        print(f"{colorize('[WARNING]')} Unlabeled rows found — re-run to classify them.")
        return
    df["hazard_label_validated"] = df["hazard_label_validated"].astype(int)  # type: ignore
    df.to_csv(validated_path, index=False)  # type: ignore

    if input("\nGenerate final output now? (y/n): ").strip().lower() != "y":
        return

    df["hazard_label_validated"] = (  # type: ignore
        (df["hazard_label_classified"] == 1) | (df["hazard_label_validated"] == 1)
    ).astype(int)
    df_final = df[df["hazard_label_validated"] == 1]  # type: ignore
    df_final.to_excel(final_path, index=False)
    print(f"\n{colorize('[DONE]')} Saved {len(df_final)} confirmed hazard reviews (union of classified and validated)")

    elapsed = int(time.time() - start)
    print(f"{colorize('[INFO]')} Total time: {format_elapsed(elapsed)}")


if __name__ == "__main__":
    main()
