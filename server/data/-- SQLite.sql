-- CREATE TABLE CE_CLASSES AS 
SELECT a.* 
FROM allgrades AS a 
WHERE subject_id='CE' AND (course_number BETWEEN 1000 AND 5000) AND (year=2023 or year=2024) AND (section_number LIKE '0_1' or (course_number='4310' or course_number='4320')));
