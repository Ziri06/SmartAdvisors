#!/usr/bin/env python3
"""
UTA Catalog Course Scraper
===========================
Generates a degree plan CSV from UTA's online catalog.

Usage:
    python3 server/app/scripts/scrape_uta_catalog.py CSE
    python3 server/app/scripts/scrape_uta_catalog.py EE
    python3 server/app/scripts/scrape_uta_catalog.py MAE

Output:
    server/data/<DEPT> Degree Plan CSV.csv

After running:
    1. Open the output CSV
    2. Mark elective courses by changing 'required' to 'elective' in the Requirement column
    3. Reload the database:
       python3 server/app/scripts/load_degree_plan.py
"""

import sys
import os
import re
import csv
import urllib.request
import html


def fetch_page(url):
    """Fetch a URL and return the HTML as a string."""
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) SmartAdvisors/1.0'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='replace')


def parse_prerequisites(desc_text):
    """Extract prerequisite course codes from a course description."""
    prereqs = []

    # Match patterns like "Prerequisite: CSE 1310 and CSE 2315" or "Prerequisites: MATH 1426"
    prereq_match = re.search(
        r'[Pp]rerequisites?[:\s]+(.+?)(?:\.|$)',
        desc_text,
        re.IGNORECASE
    )
    if prereq_match:
        prereq_text = prereq_match.group(1)
        # Extract course codes (DEPT NNNN pattern)
        codes = re.findall(r'([A-Z]{2,4}\s*\d{4})', prereq_text)
        prereqs = [c.strip() for c in codes]

    return prereqs


def parse_corequisites(desc_text):
    """Extract corequisite course codes from a course description."""
    coreqs = []

    coreq_match = re.search(
        r'[Cc]orequisites?[:\s]+(.+?)(?:\.|$)',
        desc_text,
        re.IGNORECASE
    )
    if coreq_match:
        coreq_text = coreq_match.group(1)
        codes = re.findall(r'([A-Z]{2,4}\s*\d{4})', coreq_text)
        coreqs = [c.strip() for c in codes]

    return coreqs


def scrape_catalog(dept_code):
    """
    Scrape UTA catalog course descriptions for a department.
    Returns a list of dicts with keys: code, name, prereqs, coreqs.
    """
    dept_lower = dept_code.lower()
    url = f'https://catalog.uta.edu/coursedescriptions/{dept_lower}/'
    print(f"Fetching: {url}")

    try:
        page_html = fetch_page(url)
    except Exception as e:
        print(f"Error fetching catalog: {e}")
        print(f"Try opening the URL manually: {url}")
        sys.exit(1)

    courses = []

    # UTA catalog uses <div class="courseblock"> for each course
    # Course title is in <p class="courseblocktitle">
    # Description is in <p class="courseblockdesc">
    course_blocks = re.findall(
        r'class="courseblocktitle[^"]*"[^>]*>(.*?)</p>.*?'
        r'(?:class="courseblockdesc[^"]*"[^>]*>(.*?)</p>)?',
        page_html,
        re.DOTALL
    )

    if not course_blocks:
        # Alternative pattern: some catalog pages use different markup
        course_blocks = re.findall(
            r'<strong>([A-Z]{2,4}\s+\d{4})[.\s]+(.*?)</strong>.*?'
            r'(?:<p[^>]*>(.*?)</p>)?',
            page_html,
            re.DOTALL
        )
        if course_blocks:
            for code_raw, name_raw, desc_raw in course_blocks:
                code = html.unescape(re.sub(r'<[^>]+>', '', code_raw)).strip()
                # Normalize non-breaking spaces
                code = code.replace('\xa0', ' ').replace('&nbsp;', ' ')
                name = html.unescape(re.sub(r'<[^>]+>', '', name_raw)).strip()
                desc = html.unescape(re.sub(r'<[^>]+>', '', desc_raw or '')).strip()

                prereqs = parse_prerequisites(desc)
                coreqs = parse_corequisites(desc)

                courses.append({
                    'code': code,
                    'name': name,
                    'prereqs': prereqs,
                    'coreqs': coreqs,
                })
            return courses

    for title_html, desc_html in course_blocks:
        # Clean HTML tags
        title_text = html.unescape(re.sub(r'<[^>]+>', '', title_html)).strip()
        desc_text = html.unescape(re.sub(r'<[^>]+>', '', desc_html or '')).strip()

        # Normalize non-breaking spaces
        title_text = title_text.replace('\xa0', ' ').replace('&nbsp;', ' ')
        desc_text = desc_text.replace('\xa0', ' ').replace('&nbsp;', ' ')

        # Extract course code and name from title
        # Patterns: "CSE 1310. Introduction to Computers..." or "CSE 1310 - Introduction..."
        title_match = re.match(
            r'([A-Z]{2,4}\s+\d{4})\s*[.\-\s]+\s*(.+?)(?:\s*\(\d+.*\))?$',
            title_text
        )
        if not title_match:
            # Try without name separator
            title_match = re.match(r'([A-Z]{2,4}\s+\d{4})\s+(.*)', title_text)

        if not title_match:
            continue

        code = title_match.group(1).strip()
        name = title_match.group(2).strip()
        # Remove trailing credit hours like "(3 semester credit hours)"
        name = re.sub(r'\s*\(\d+\s*(semester\s+)?credit\s+hours?\)', '', name, flags=re.IGNORECASE).strip()
        # Remove trailing period
        name = name.rstrip('.')

        prereqs = parse_prerequisites(desc_text)
        coreqs = parse_corequisites(desc_text)

        courses.append({
            'code': code,
            'name': name,
            'prereqs': prereqs,
            'coreqs': coreqs,
        })

    return courses


def format_list(items):
    """Format a list of items for CSV output."""
    if not items:
        return '[None]'
    if len(items) == 1:
        return items[0]
    return ', '.join(items)


def write_csv(courses, dept_code, output_path):
    """Write courses to a CSV file in the degree plan format."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Formal Name', 'Course Name', 'Prerequisites', 'Corequisites', 'Requirement'])

        for course in courses:
            writer.writerow([
                course['code'],
                course['name'],
                format_list(course['prereqs']),
                format_list(course['coreqs']),
                'required',  # Default — user should manually mark electives
            ])

    print(f"\nWrote {len(courses)} courses to: {output_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scrape_uta_catalog.py <DEPT>")
        print("Example: python3 scrape_uta_catalog.py CSE")
        print("         python3 scrape_uta_catalog.py EE")
        print("         python3 scrape_uta_catalog.py MAE")
        sys.exit(1)

    dept_code = sys.argv[1].upper()

    # Determine output path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
    data_dir = os.path.join(server_root, 'data')

    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)

    output_path = os.path.join(data_dir, f'{dept_code} Degree Plan CSV.csv')

    # Scrape the catalog
    courses = scrape_catalog(dept_code)

    if not courses:
        print(f"No courses found for department '{dept_code}'.")
        print(f"Check if the URL is correct: https://catalog.uta.edu/coursedescriptions/{dept_code.lower()}/")
        sys.exit(1)

    # Filter to only courses from the target department
    dept_courses = [c for c in courses if c['code'].startswith(dept_code)]
    other_courses = [c for c in courses if not c['code'].startswith(dept_code)]

    if other_courses:
        print(f"\nNote: Found {len(other_courses)} courses from other departments (skipped):")
        for c in other_courses[:5]:
            print(f"  - {c['code']}: {c['name']}")
        if len(other_courses) > 5:
            print(f"  ... and {len(other_courses) - 5} more")

    # Write CSV
    write_csv(dept_courses, dept_code, output_path)

    # Print next steps
    print(f"\n--- NEXT STEPS ---")
    print(f"1. Open the CSV file: {output_path}")
    print(f"2. Review courses and mark electives:")
    print(f"   - Change 'required' to 'elective' in the Requirement column for elective courses")
    print(f"   - Add general education courses (MATH, PHYS, ENGL, etc.) that are part of the degree plan")
    print(f"   - Add placeholder rows for elective slots (e.g., '{dept_code} 43XX, {dept_code} Technical Elective (1), [None], [None], required')")
    print(f"3. Reload the database:")
    print(f"   python3 server/app/scripts/load_degree_plan.py")
    print(f"4. Add '{dept_code}' to DEPT_TO_CSV in load_degree_plan.py if not already there")


if __name__ == '__main__':
    main()
