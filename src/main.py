import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from extractor import llm_extractor, rule_extractor
from matcher.catalog_matcher import match_with_catalog
from output.exporter import export_results
from parser.pdf_parser import parse_pdf
from parser.word_parser import parse_word
from utils.logger import setup_logger

load_dotenv()
logger = setup_logger()


def parse_file(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in (".doc", ".docx"):
        return parse_word(path)
    if ext == ".pdf":
        return parse_pdf(path)
    raise ValueError(f"Unsupported format: {ext}")


def extract_positions(text: str, use_llm: bool) -> list:
    if use_llm:
        return llm_extractor.extract_positions(text)
    logger.info("Using rule-based extractor (no LLM)")
    return rule_extractor.extract_positions(text)


def main():
    parser = argparse.ArgumentParser(description="Lighting procurement parser")
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--catalog", "-c", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Extract positions with regex heuristics instead of OpenAI",
    )
    args = parser.parse_args()

    if args.debug:
        logger.setLevel(logging.DEBUG)

    use_llm = not args.no_llm and bool(os.getenv("OPENAI_API_KEY"))
    if not use_llm and not args.no_llm:
        logger.warning("OPENAI_API_KEY not set, falling back to rule-based extraction")

    logger.info("Parsing document...")
    text = parse_file(args.input)
    logger.info("Extracted %s chars", len(text))

    logger.info("Extracting positions...")
    positions = extract_positions(text, use_llm=use_llm)
    logger.info("Found %s positions", len(positions))

    if not positions:
        logger.warning("No positions found")
        return

    logger.info("Matching with catalog...")
    results = match_with_catalog(args.catalog, positions)

    logger.info("Exporting results...")
    export_results(results, args.output)
    logger.info("Done! Saved to %s", args.output)


if __name__ == "__main__":
    main()
