from bs4 import BeautifulSoup
import requests
import re
import sqlite3
import spacy

# --- New Code: Load spaCy Model Globally ---
# This loads the model once when the script starts, which is much more efficient.
# It will download the model if you don't have it installed.
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    print("Downloading spaCy model 'en_core_web_lg'...")
    print("This may take a minute and only needs to run once.")
    spacy.cli.download("en_core_web_lg")
    nlp = spacy.load("en_core_web_lg")

# Regex to find course codes (e.g., CEE 1234, MATH 2425)
# This is often more reliable than just spaCy's POS tagging for this specific format
COURSE_RE = re.compile(r'([A-Z]{2,4})\s(\d{4})')

# --- New Code: Requisite Extraction Function ---
# --- New Code: Requisite Extraction Function (Modified) ---
# --- New Code: Requisite Extraction Function (State Machine) ---
def extract_requisites(description_text):
    """
    Uses spaCy to parse the *entire requisite block* (not just the last line)
    and uses a state machine to categorize courses.
    """
    prereqs = set()
    coreqs = set()

    # --- Step 1: Find the start of the entire requisite block ---
    lower_text = description_text.lower()
    
    # Find the first occurrence of any requisite keyword
    indices = [
        lower_text.find("prerequisite"),
        lower_text.find("corequisite"),
        lower_text.find("concurrent")
    ]
    
    # Filter out -1 (not found)
    valid_indices = [idx for idx in indices if idx != -1]
    
    if not valid_indices:
        # No requisite keywords found at all in the description
        return {"prereqs": prereqs, "coreqs": coreqs}
    
    # Get the index of the first keyword
    start_index = min(valid_indices)
    
    # Extract the entire block of text from that point forward
    req_block_text = description_text[start_index:]
    # --- End Step 1 ---

    # --- Step 2: Process this block with spaCy ---
    doc = nlp(req_block_text)
    
    # --- Step 3: Track the "state" as we read sentences ---
    # 0 = prerequisite mode (default)
    # 1 = corequisite mode
    current_mode = 0 
    
    # Set default mode based on the *first* keyword found
    first_keyword = lower_text[start_index:start_index+20]
    if "corequisite" in first_keyword or "concurrent" in first_keyword:
        current_mode = 1
    
    for sent in doc.sents:
        sent_text = sent.text.lower()
        
        # Check for keywords to *change* the state
        # (This handles "Prerequisite... Corequisite...")
        if "corequisite" in sent_text or "concurrent" in sent_text:
            current_mode = 1 # Now we are in coreq mode
        elif "prerequisite" in sent_text:
            current_mode = 0 # Now we are in prereq mode
            
        # Find all course codes in this sentence
        found_codes = COURSE_RE.findall(sent.text)
        if not found_codes:
            continue
            
        formatted_codes = {f"{dept} {num}" for dept, num in found_codes}

        # Apply codes based on the current_mode
        if current_mode == 1:
            coreqs.update(formatted_codes)
        else:
            prereqs.update(formatted_codes)

    return {"prereqs": prereqs, "coreqs": coreqs}

def find_data(html_content):
    """
    Find the (Course_Num, Course_Name) and (Prerequisites, Corequisites)
    Returned as list_of_titles and list_of_reqs respectively
    """
    # print(html_content)
    soup = BeautifulSoup(html_content, 'html.parser')
    titles_of_courses = soup.find_all(class_="courseblocktitle")

    """
    Find the Course Numbers and Names of all Classes in the chosen department
    """
    list_of_titles = []

    for i in titles_of_courses:
        # Split only on the first period
        delimited_list = i.text.split(".", 1)
        
        try:
            # Check for valid course num
            course_num_str = re.findall(r'\d+', delimited_list[0])[0]
            if int(course_num_str) > 5000:
                break  # Stop if we hit grad-level courses
                
            # [0] is "CSE 1320", [1] is "    Introduction to Programming    (3-2) 3"
            course_id = delimited_list[0].strip()
            
            # Clean the course name
            # "    Introduction to Programming    (3-2) 3"
            # Strip whitespace and remove the credit hours at the end
            course_name = re.sub(r'\s+\(.*\)\s*\d*$', '', delimited_list[1]).strip()
            
            list_of_titles.append([course_id, course_name])

        except (IndexError, ValueError):
            # Skip invalid formats (e.g., a title block without a period or number)
            continue

    """
    Find the Pre-Requisites and Co-requisites of a Class
    """
    list_of_reqs = []
    list_of_desc = []
    
    # Get descriptions, but only for the courses we've already processed
    desc_of_courses = soup.find_all(class_="courseblockdesc")[:len(list_of_titles)]
    
    for desc_html in desc_of_courses:
        desc_text = desc_html.text
        list_of_desc.append(desc_text)
        
        # --- Updated Code: Call the new spaCy function ---
        reqs = extract_requisites(desc_text)
        list_of_reqs.append(reqs)

    # TODO
    # IF THE Department from Prerequisite is not the same as the current department then grab the data for that department and add on the prerequisite
    # (This logic is complex and would require a recursive scraper)
    
    return list_of_titles, list_of_reqs, list_of_desc

def find_prereqs(prerequisites, main_course_department, safe_table_name, cur):
    """
    Recursively finds and inserts prerequisite courses from other departments.
    
    :param prerequisites: A set of prerequisite course IDs, e.g., {'MATH 1426', 'PHYS 1443'}
    :param main_course_department: The department of the course we're checking, e.g., "CE"
    :param safe_table_name: The name of the SQL table to insert into.
    :param cur: The active database cursor.
    """
    
    # Use the same INSERT OR REPLACE strategy as insert_courses
    sql_insert = f"""
        INSERT OR REPLACE INTO {safe_table_name} 
        (Course_Num, Course_Name, Pre_Requisites, Co_Requisites, Description)
        VALUES (?, ?, ?, ?, ?)
    """
    
    if not prerequisites:
        return  # Base case: no prerequisites

    # Loop through each prerequisite course ID in the set
    for prereq_course_id in prerequisites:
        # prereq_course_id is a string, e.g., "MATH 1426"
        
        # Check if this prerequisite is in a different department
        if main_course_department not in str(prereq_course_id):
            try:
                prereq_dept = prereq_course_id.split(" ")[0] # e.g., "MATH"

                # --- VITAL CHECK: PREVENT INFINITE RECURSION ---
                # Check if we have *already* inserted this course.
                cur.execute(f"SELECT 1 FROM {safe_table_name} WHERE Course_Num = ?", (prereq_course_id,))
                if cur.fetchone():
                    # If it exists, we're done. Skip to the next prerequisite.
                    continue 
                
                # --- We don't have it. Scrape the new department. ---
                print(f"--- Finding prereq: {prereq_course_id} from {prereq_dept} department...")
                html = get_html_content(prereq_dept)
                if not html:
                    print(f"Warning: Could not fetch {prereq_dept}. Skipping {prereq_course_id}.")
                    continue # Skip this prerequisite

                # Parse the *entire* department page
                new_titles, new_preqs, new_descs = find_data(html)
                
                # Find the specific course we're looking for
                found_course = False
                for k in range(len(new_titles)):
                    
                    clean_title_from_scrape = new_titles[k][0].replace('\u00A0', ' ').strip()
                    
                    # If we find the matching course (e.g., "MATH 1426")
                    if prereq_course_id == clean_title_from_scrape:
                        found_course = True
                        
                        # Get its data and prereqs
                        prereqs_for_this_prereq_set = new_preqs[k]["prereqs"]
                        coreqs_for_this_prereq_set = new_preqs[k]["coreqs"]
                        
                        prereqs_str = ', '.join(prereqs_for_this_prereq_set)
                        coreqs_str = ', '.join(coreqs_for_this_prereq_set)
                        
                        data_tuple_for_prereq = (
                            new_titles[k][0],      # Course_Num
                            new_titles[k][1],      # Course_Name
                            prereqs_str,           # Pre_Requisites 
                            coreqs_str,            # Co_Requisites 
                            str(new_descs[k]).strip() # Description
                        )
                        
                        # --- 1. Insert this prerequisite course (e.g., "MATH 1426") ---
                        try:
                            cur.execute(sql_insert, data_tuple_for_prereq)
                        except Exception as e:
                            print(f"Error inserting prereq {data_tuple_for_prereq[0]}: {e}")

                        # --- 2. NOW, recursively find *its* prerequisites ---
                        all_prereqs_for_prereq = prereqs_for_this_prereq_set.union(coreqs_for_this_prereq_set)
                        if all_prereqs_for_prereq:
                            # The 'department' for this recursive call is "MATH" (prereq_dept)
                            find_prereqs(all_prereqs_for_prereq, prereq_dept, safe_table_name, cur)
                        
                        # We found our course, so break from the inner 'for k' loop
                        break 
                
                if not found_course:
                    print(f"Warning: Could not find {prereq_course_id} on {prereq_dept} page.")
                    
            except Exception as e:
                print(f"Recursive scrape error on {prereq_course_id}: {e}")
                continue # Continue to the next prereq in the 'for' loop

    # This function does not need to return anything.
    # Its only job is to find and insert.
    return
            

def insert_courses(html_content, department):
    
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../data/classes.db')
    
    db = sqlite3.connect(db_path)
    cur = db.cursor()
    
    list_of_titles, list_of_preqs, description = find_data(html_content)
    
    print(f"Found {len(list_of_titles)} titles.")
    print(f"Found {len(list_of_preqs)} requisite lists.")
    print(f"Found {len(description)} descriptions.")

    # Sanitize department name for table name (basic)
    safe_table_name = re.sub(r'[^a-zA-Z0-9_]', '', f"ClassesFor{department}")

    # Creates the Classes Table if not already present
    try:
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {safe_table_name}(
                                        Course_Num VARCHAR(10) NOT NULL PRIMARY KEY, 
                                        Course_Name VARCHAR(100) NOT NULL, 
                                        Pre_Requisites VARCHAR(200),
                                        Co_Requisites VARCHAR(200),
                                        Description VARCHAR(1000)
                                        )""")
    except Exception as e:
        print(f"Error creating table: {e}")
        db.close()
        return

    sql_insert = f"""
        INSERT OR REPLACE INTO {safe_table_name} 
        (Course_Num, Course_Name, Pre_Requisites,Co_Requisites, Description)
        VALUES (?, ?, ?, ?, ?)
    """
    i = 0
    while i < len(list_of_titles):
        prereqs_set = list_of_preqs[i]["prereqs"] # Get the set
        coreqs_set = list_of_preqs[i]["coreqs"]   # Get the set
        
        prereqs_str = ', '.join([str(item) for item in prereqs_set])
        coreqs_str = ', '.join([str(item) for item in coreqs_set])
        
        # --- This is the Depth-First Search part ---
        # 1. First, find and insert all prerequisites for this course
        # We combine prereqs and coreqs to process them all
        all_reqs_set = prereqs_set.union(coreqs_set)
        
        # Call the recursive function. It doesn't return anything.
        find_prereqs(all_reqs_set, department, safe_table_name, cur)
        
        # 2. Now that all prerequisites are in the DB, insert the main course
        data = (
            list_of_titles[i][0],         # Course_Num
            list_of_titles[i][1],         # Course_Name
            str(prereqs_str),             # Pre_Requisites 
            str(coreqs_str),              # Co_Requisites 
            str(description[i]).strip()   # Description
        )
        try:
            cur.execute(sql_insert, data)
            i += 1
        except Exception as e:
            print(f"Error inserting {data[0]}: {e}")
            i += 1 # Increment to avoid an infinite loop on a failing row

    db.commit()
    db.close()
    print(f"Successfully processed and saved data for {department} to {db_path}")
def get_html_content(department):
    department = department.lower()
    website = f"https://catalog.uta.edu/coursedescriptions/{department}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}

    print(f"Requesting data from {website}...")
    try:
        response = requests.get(website, headers=headers)
        response.raise_for_status()  # Will raise an error for bad responses (404, 500, etc.)
        print("Success.")
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return None

# --- Main execution ---
department = "CSE" # Example department

"""
Insert the into the database for any department
"""
html = get_html_content(department)
if html:
    insert_courses(html, department)