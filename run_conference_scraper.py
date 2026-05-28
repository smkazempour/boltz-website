"""
Finance Conference Scraper
--------------------------
Scrapes the SSRN finance conference list, extracts structured info via OpenAI,
and saves outputs (xlsx, csv, html) to OUTPUT_DIR.

Environment variables:
  OPENAI_API_KEY  - Your OpenAI API key (required)
  OUTPUT_DIR      - Directory to write output files (default: current directory)
  OPENAI_MODEL    - Model to use (default: gpt-4o-mini)
"""

import os
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from bs4 import BeautifulSoup
from openai import OpenAI
from tqdm import tqdm

OUTPUT_DIR = os.environ.get("OUTPUT_DIR", ".")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")


def get_driver():
    options = Options()
    options.add_argument("-headless")
    return webdriver.Firefox(options=options)


def scrape_conference_page():
    print("Scraping SSRN conference page...")
    driver = get_driver()
    driver.get(
        "https://www.ssrn.com/index.cfm/en/janda/professional-announcements/"
        "?annsNet=203#AnnType_2"
    )
    source = driver.page_source
    driver.quit()

    html_path = os.path.join(OUTPUT_DIR, "ssrn_conference_list.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(source)

    return source


def parse_conference_links(source):
    soup = BeautifulSoup(source, "html.parser")
    headings = soup.find_all("h2")

    current_header = next_header = None
    for i, h in enumerate(headings):
        text = h.get_text().lower()
        if "call" in text and "paper" in text and "conference" in text:
            current_header = h.decode()
            next_header = headings[i + 1].decode()
            break

    if current_header is None:
        raise ValueError("Could not locate the 'Call for Papers: Conferences' section on SSRN.")

    section_html = source.split(current_header)[1].split(next_header)[0]
    section = BeautifulSoup(section_html, "html.parser")
    conf_links = section.find_all("a", href=True)

    links = [c["href"] for c in conf_links]
    conf_names = [c.text for c in conf_links]
    print(f"Found {len(links)} conference links.")
    return links, conf_names


def fetch_conference_texts(links):
    print("Fetching individual conference pages...")
    driver = get_driver()
    texts = []

    for link in tqdm(links):
        text = ""
        for attempt in range(1, 4):
            try:
                driver.get(link)
                soup = BeautifulSoup(driver.page_source, "html.parser")
                articles = soup.find_all("article")
                if articles:
                    text = articles[0].get_text()
                break
            except KeyboardInterrupt:
                driver.quit()
                raise
            except Exception as e:
                if attempt == 3:
                    print(f"\nFailed after 3 attempts: {link}\n  {e}")
        texts.append(text)

    driver.quit()
    return texts


def analyze_with_openai(client, announcement_text):
    prompt = f"""The following is the text of a call for papers for an academic finance conference. \
Please extract the following information: Conference name, date, topics of interest, location, \
paper submission deadline, submission fee. Please respond in the following format:

Conference name: [insert name here]
Start Date: [insert the conference start date in YYYY-mm-dd format here]
End Date: [insert the conference end date in YYYY-mm-dd format here]
Topics of interest: [insert topics of interest here]
Location: [insert location here]
Deadline: [insert paper submission deadline in YYYY-mm-dd format here]
Submission fee: [insert submission fee and currency here]

If you cannot find any of the required information, please fill the field with "N/A".

The text of the announcement follows.

{announcement_text}
"""
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model=OPENAI_MODEL,
    )
    return response.choices[0].message.content.split("\n")


def process_with_openai(texts):
    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY environment variable is not set.")

    print("Extracting structured data via OpenAI...")
    client = OpenAI(api_key=OPENAI_API_KEY)
    results = []

    for text in tqdm(texts):
        for attempt in range(1, 6):
            try:
                r = analyze_with_openai(client, text)
                results.append(r)
                break
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"\nAttempt {attempt} failed: {e}")
                if attempt < 5:
                    time.sleep(2 ** attempt)
                else:
                    print("Max retries reached; recording N/A.")
                    results.append(["Conference name: N/A", "Start Date: N/A", "End Date: N/A",
                                    "Topics of interest: N/A", "Location: N/A",
                                    "Deadline: N/A", "Submission fee: N/A"])
    return results


def build_dataframe(results):
    columns = ["Conference", "Deadline", "Start", "End", "Location", "Submission fee", "Topics of interest"]
    rows = []
    for r in results:
        # Pad in case the model returned fewer lines than expected
        r = r + [""] * 8
        try:
            values = [
                r[0].strip().split(":", 1)[-1].strip(),
                r[5].strip().split(":", 1)[-1].strip(),
                r[1].strip().split(":", 1)[-1].strip(),
                r[2].strip().split(":", 1)[-1].strip(),
                r[4].strip().split(":", 1)[-1].strip(),
                r[6].strip().split(":", 1)[-1].strip(),
                r[3].strip().split(":", 1)[-1].strip(),
            ]
        except Exception:
            values = ["N/A"] * 7
        rows.append(dict(zip(columns, values)))
    return pd.DataFrame.from_records(rows)


def save_outputs(df):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    xlsx_path = os.path.join(OUTPUT_DIR, "conference_list.xlsx")
    df.to_excel(xlsx_path, index=False)
    print(f"Saved: {xlsx_path}")

    csv_path = os.path.join(OUTPUT_DIR, "conference_list.csv")
    df.to_csv(csv_path, index=False)
    print(f"Saved: {csv_path}")

    html_table = df[["Conference", "Deadline", "Start"]].to_html(
        index=False, classes="conf-table", border=0, escape=True
    )
    updated = pd.Timestamp.now().strftime("%B %d, %Y")
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Finance Conference List</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
    h1 {{ font-size: 1.6em; }}
    p.updated {{ color: #777; font-size: 0.85em; margin-top: -10px; }}
    .conf-table {{ border-collapse: collapse; width: 100%; }}
    .conf-table th {{ background: #2c5f8a; color: #fff; padding: 10px 12px; text-align: left; }}
    .conf-table td {{ border: 1px solid #ddd; padding: 8px 12px; }}
    .conf-table tr:nth-child(even) {{ background: #f5f5f5; }}
    .conf-table tr:hover {{ background: #e8f0fe; }}
  </style>
</head>
<body>
  <h1>Finance Conference List</h1>
  <p class="updated">Last updated: {updated}</p>
  {html_table}
</body>
</html>"""

    html_path = os.path.join(OUTPUT_DIR, "conference_list.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Saved: {html_path}")


def main():
    source = scrape_conference_page()
    links, _ = parse_conference_links(source)
    texts = fetch_conference_texts(links)
    results = process_with_openai(texts)
    df = build_dataframe(results)
    save_outputs(df)
    print("Done.")


if __name__ == "__main__":
    main()
