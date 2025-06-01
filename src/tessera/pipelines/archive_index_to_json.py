import pandas as pd
import re


def archive_index_text(input_path: str) -> str:
    with open(input_path, "r", encoding="utf-8") as file:
        text = file.read()

    return text


def archive_index_df(archive_index_text: str) -> pd.DataFrame:
    records = []
    # Split the text into blocks based on double newlines
    blocks = archive_index_text.split("\n\n")

    for block in blocks:
        block = block.strip()
        # Assume each record block has at least two lines
        lines = block.split("\n")
        if len(lines) < 2:
            continue

        # --- First line parsing: description and year ---
        # Expected pattern: "Dispensation ... , 1772"
        first_line = lines[0].strip()
        year_match = re.search(r",\s*(\d{4})\s*$", first_line)
        if not year_match:
            continue  # Skip if pattern not found
        year = int(year_match.group(1))
        # Description is the text before the comma and year.
        description = first_line[: year_match.start()].strip()

        # --- Second line parsing: author, document number, and pages ---
        # Join all subsequent lines (in case the details span more than one line).
        second_line = " ".join(lines[1:]).strip()
        details_match = re.search(
            r"Author:\s*(.*?)\.\s*Original document number:\s*(\d+)\.\s*Pages:\s*(\d+)",
            second_line,
        )
        if not details_match:
            continue  # Skip if the details pattern is not found

        author = details_match.group(1).strip()
        document_number = int(details_match.group(2))
        pages = int(details_match.group(3))

        # Build record dictionary
        record = {
            "description": description,
            "year": year,
            "author": author,
            "document_number": document_number,
            "pages": pages,
        }
        records.append(record)

    df = pd.DataFrame(records)
    return df


def archive_index_to_json(archive_index_df: pd.DataFrame, output_path: str) -> None:
    archive_index_df.to_json(
        output_path, orient="records", lines=True, force_ascii=False
    )
