from pathlib import Path
import sys

from parse_transcript import extract_all_courses  # import from sibling file


DEFAULT_PDF = Path(__file__).resolve().parents[2] / 'data' / 'sample_transcript.pdf'


def main() -> None:
    pdf_path = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else DEFAULT_PDF
    courses = extract_all_courses(str(pdf_path))

    print(f"\nTranscript: {pdf_path}")
    print("Completed courses found:")
    for course in courses:
        print(course)


if __name__ == '__main__':
    main()
