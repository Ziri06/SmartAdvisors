from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage # Import for type hinting
import os
import tempfile
import sys
import traceback
import json

from app.models import Professor

from .scripts.recommendation_engine import (
    get_department_courses,
    filter_eligible_courses_unique,
    get_professor_offerings_for_course,
    normalize_code
)
from .scripts.parse_transcript import extract_all_courses

api_bp = Blueprint('api', __name__, url_prefix='/api')

# --- IMPROVED SCORING ALGORITHM ---
def calculate_match_score(professor_obj, user_prefs):
    """
    Sophisticated scoring based on Rating, Difficulty, and Tags.
    """
    if not professor_obj:
        return 0.0
    
    # 1. BASELINE: Start with the Quality Rating (0 - 5)
    try:
        base_score = float(professor_obj.rating) if professor_obj.rating else 2.5
    except:
        base_score = 2.5
        
    score = base_score
    
    # Get Data safely
    try:
        difficulty = float(professor_obj.difficulty) if professor_obj.difficulty else 3.0
    except:
        difficulty = 3.0

    try:
        tags_str = str(professor_obj.tags).lower() if professor_obj.tags else ""
    except:
        tags_str = ""
    
    # --- 2. LOGIC APPLICATION ---

    # A. EASY GRADER LOGIC
    if user_prefs.get('extraCredit'):
        if "extra credit" in tags_str:
            score += 1.0

    if user_prefs.get('easyGrader') or user_prefs.get('clearGrading'):
        # Bonus for low difficulty (1.0 difficulty = +2.0 boost)
        difficulty_bonus = (5.0 - difficulty) * 0.5 
        score += difficulty_bonus
        
        if any(t in tags_str for t in ['easy grader', 'clear grading', 'graded by few things']):
            score += 1.0
        if any(t in tags_str for t in ['tough grader', 'hard grader']):
            score -= 1.5

    # B. TEACHING QUALITY
    if user_prefs.get('caring') or user_prefs.get('goodFeedback'):
        if any(t in tags_str for t in ['caring', 'respected', 'inspirational', 'accessible', 'good feedback']):
            score += 1.2
    
    # C. LEARNING STYLE
    if user_prefs.get('lectureHeavy'):
        if "amazing lectures" in tags_str:
            score += 1.5
        elif "lecture heavy" in tags_str:
            score += 0.5 
    
    if user_prefs.get('groupProjects'):
        if "group projects" in tags_str:
            score += 1.0
    else:
        # User dislikes groups (default assumption)
        if "group projects" in tags_str:
            score -= 0.5

    # D. "DEAL BREAKERS"
    if not user_prefs.get('testHeavy'):
        if any(t in tags_str for t in ['test heavy', 'tests are tough']):
            score -= 1.5 

    if not user_prefs.get('homeworkHeavy'):
        if any(t in tags_str for t in ['lots of homework', 'so many papers']):
            score -= 1.0

    if not user_prefs.get('strictAttendance'):
        if any(t in tags_str for t in ['attendance mandatory', 'skip class']):
            score -= 1.0

    if not user_prefs.get('popQuizzes'):
        if "pop quizzes" in tags_str:
            score -= 2.0 

    return round(score, 1)


@api_bp.route('/parse-transcript', methods=['POST'])
def parse_transcript():
    print("\n=== PARSE TRANSCRIPT ROUTE CALLED ===", file=sys.stderr)
    try:
        if 'transcript' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        # Explicit type hint removes the red line in IDE
        file: FileStorage = request.files['transcript']
        
        if not file or file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        temp_dir = tempfile.gettempdir()
        # Safe handling of filename
        fname = secure_filename(file.filename or "temp.pdf")
        temp_path = os.path.join(temp_dir, fname)
        file.save(temp_path)
        
        courses = extract_all_courses(temp_path)
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        return jsonify({'success': True, 'courses': courses}), 200
        
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500


@api_bp.route('/recommendations', methods=['POST'])
def get_recommendations():
    print("\n=== RECOMMENDATIONS ROUTE CALLED ===", file=sys.stderr)
    
    try:
        department = request.form.get('department')
        if not department:
            return jsonify({'error': 'Department required'}), 400

        # 1. GET COMPLETED COURSES
        completed_courses = []
        
        # Safe .get() with default string '[]' fixes the red line risk
        raw_courses = request.form.get('completed_courses', '[]')
        
        try:
            if raw_courses and raw_courses != 'undefined':
                completed_courses = json.loads(raw_courses)
        except:
            print("Error parsing completed_courses JSON", file=sys.stderr)
        
        # Fallback: Parse file if list is missing
        if not completed_courses and 'transcript' in request.files:
            file: FileStorage = request.files['transcript']
            if file and file.filename:
                temp_dir = tempfile.gettempdir()
                fname = secure_filename(file.filename)
                temp_path = os.path.join(temp_dir, fname)
                file.save(temp_path)
                completed_courses = extract_all_courses(temp_path)
                if os.path.exists(temp_path): os.remove(temp_path)

        # 2. GET PREFERENCES
        user_prefs = {}
        try:
            raw_prefs = request.form.get('preferences', '{}')
            user_prefs = json.loads(raw_prefs)
        except:
            pass

        # 3. LOGIC ENGINE
        all_courses = get_department_courses(department)
        eligible = filter_eligible_courses_unique(all_courses, completed_courses)
        
        result = []
        for code, course in eligible.items():
            offerings = get_professor_offerings_for_course(code)
            
            professors_list = []
            seen = set()
            
            for offer in offerings:
                for prof_name in offer['instructors']:
                    
                    # CLEANUP: Skip "Staff" or "TBA" placeholders
                    if not prof_name or prof_name.lower() in ['staff', 'tba', 'unknown']:
                        continue

                    if prof_name not in seen:
                        seen.add(prof_name)
                        
                        try:
                            # --- ROBUST NAME MATCHING ---
                            db_prof = Professor.query.filter(Professor.name.ilike(prof_name)).first()
                            
                            # Swap Check: "Smith, John" -> "John Smith"
                            if not db_prof and ',' in prof_name:
                                parts = prof_name.split(',')
                                if len(parts) >= 2:
                                    swapped = f"{parts[1].strip()} {parts[0].strip()}"
                                    db_prof = Professor.query.filter(Professor.name.ilike(swapped)).first()
                            
                            # Fuzzy Last Name Check
                            if not db_prof:
                                parts = prof_name.replace(',', '').split()
                                if len(parts) > 0:
                                    last_name = parts[0] if ',' in prof_name else parts[-1]
                                    db_prof = Professor.query.filter(Professor.name.ilike(f"%{last_name}%")).first()

                            # CALCULATE SCORE
                            match_score = calculate_match_score(db_prof, user_prefs)
                            
                            # GET DATA (Safe defaults)
                            final_rating = 0.0
                            if db_prof and db_prof.rating is not None: 
                                try: final_rating = float(db_prof.rating)
                                except: final_rating = 0.0
                            else:
                                try: final_rating = round(float(offer.get('course_gpa', 0) or 0), 1)
                                except: final_rating = 0.0
                            
                            final_tags = []
                            if db_prof and db_prof.tags:
                                final_tags = str(db_prof.tags).split(',')

                            final_difficulty = "Moderate"
                            if db_prof and db_prof.difficulty:
                                try:
                                    diff_val = float(db_prof.difficulty)
                                    if diff_val < 2.5: final_difficulty = "Easy"
                                    elif diff_val > 3.8: final_difficulty = "Hard"
                                except: pass

                            professors_list.append({
                                'id': str(len(professors_list)),
                                'name': prof_name,
                                'rating': final_rating,
                                'difficulty': final_difficulty,
                                'matchScore': match_score,
                                'schedule': f"{offer.get('year','')} {offer.get('semester','')}".strip(),
                                'tags': final_tags,
                                'reviewCount': 0, 'classSize': 'Unknown', 'assessmentType': 'Unknown', 'attendance': 'Unknown'
                            })
                        except Exception as inner_e:
                            print(f"Skipping prof {prof_name}: {inner_e}", file=sys.stderr)
                            continue
            
            # Sort by Match Score (Highest First)
            professors_list.sort(key=lambda x: x['matchScore'], reverse=True)
            
            coreqs = course.get('Co_Requisites', '').strip()
            entry = {
                'courseCode': code,
                'courseName': course['Course_Name'],
                'creditHours': course.get('Credit_Hours', 3),
                'corequisites': coreqs if coreqs and coreqs.lower() != 'none' else '',
                'professors': professors_list
            }
            # Tag with requirement type for partitioning
            entry['_requirement'] = course.get('Requirement', 'required')
            result.append(entry)

        # Partition into required vs elective
        required = []
        electives = []
        for r in result:
            req_type = r.pop('_requirement', 'required')
            if req_type == 'elective':
                electives.append(r)
            else:
                required.append(r)

        # Calculate progress stats
        normalized_completed = set(normalize_code(c) for c in completed_courses)

        # Required: count completed vs total (exclude XX placeholders)
        required_courses = [c for c in all_courses if c.get('Requirement', 'required') == 'required' and 'XX' not in c['Course_Num']]
        total_required = len(required_courses)
        total_required_hours = sum(c.get('Credit_Hours', 3) for c in required_courses)
        completed_required = [c for c in required_courses if normalize_code(c['Course_Num']) in normalized_completed]
        completed_required_count = len(completed_required)
        completed_required_hours = sum(c.get('Credit_Hours', 3) for c in completed_required)

        # Electives: count technical elective slots (XX entries, excluding gen-ed like HIST/LPC/CA)
        gen_ed_prefixes = ('HIST', 'LPC', 'CA', 'POLS', 'ENGL', 'UNIV')
        elective_slots = [c for c in all_courses if 'XX' in c['Course_Num'] and not c['Course_Num'].startswith(gen_ed_prefixes)]
        total_elective_slots = len(elective_slots)
        elective_courses = [c for c in all_courses if c.get('Requirement', 'required') == 'elective']
        completed_electives = [c for c in elective_courses if normalize_code(c['Course_Num']) in normalized_completed]
        completed_elective_count = len(completed_electives)
        completed_elective_hours = sum(c.get('Credit_Hours', 3) for c in completed_electives)
        total_elective_hours = sum(c.get('Credit_Hours', 3) for c in elective_slots)
        remaining_elective_slots = max(0, total_elective_slots - completed_elective_count)

        return jsonify({
            'success': True,
            'recommendations': required,
            'electiveRecommendations': electives,
            'stats': {
                'totalRequiredCourses': total_required,
                'totalRequiredHours': total_required_hours,
                'completedRequiredCourses': completed_required_count,
                'completedRequiredHours': completed_required_hours,
                'totalElectiveSlots': total_elective_slots,
                'totalElectiveHours': total_elective_hours,
                'completedElectives': completed_elective_count,
                'completedElectiveHours': completed_elective_hours,
                'remainingElectiveSlots': remaining_elective_slots,
            }
        }), 200
        
    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        return jsonify({'error': str(e)}), 500