import argparse
import os
import sys
import time

import google.generativeai as genai


DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_PROMPT = (
    "Summarise this PDF in 3 to 5 sentences, then list 3 key points as bullet points."
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Small test script for Gemini PDF summarisation."
    )
    parser.add_argument("pdf_path", help="Path to the PDF file to summarise.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Gemini model to use. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Custom prompt for the summarisation request.",
    )
    return parser.parse_args()


def wait_for_file_processing(uploaded_file, timeout_seconds=60):
    start_time = time.time()

    while True:
        current_file = genai.get_file(uploaded_file.name)
        state = getattr(current_file, "state", None)
        state_name = getattr(state, "name", "UNKNOWN")

        if state_name != "PROCESSING":
            return current_file

        if time.time() - start_time > timeout_seconds:
            raise TimeoutError("Timed out waiting for Gemini to finish processing the PDF.")

        time.sleep(2)


def main():
    args = parse_args()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Set GEMINI_API_KEY or GOOGLE_API_KEY before running this script.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.pdf_path):
        print(f"PDF file not found: {args.pdf_path}", file=sys.stderr)
        sys.exit(1)

    genai.configure(api_key=api_key)

    print(f"Uploading PDF: {args.pdf_path}")
    uploaded_file = genai.upload_file(path=args.pdf_path)
    uploaded_file = wait_for_file_processing(uploaded_file)

    state_name = getattr(getattr(uploaded_file, "state", None), "name", "UNKNOWN")
    if state_name == "FAILED":
        print("Gemini failed to process the PDF.", file=sys.stderr)
        sys.exit(1)

    model = genai.GenerativeModel(args.model)
    response = model.generate_content([uploaded_file, args.prompt])

    print("\n=== Summary ===\n")
    print(response.text.strip())


if __name__ == "__main__":
    main()
