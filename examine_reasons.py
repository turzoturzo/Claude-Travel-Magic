
import csv
from collections import Counter

file_path = "feedback - Sheet1 (1).csv"

print("Examples of Misclassified Flight Marketing:")
print("-" * 50)
with open(file_path, mode='r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    count = 0
    for row in reader:
        category = row.get('category', '').strip()
        feedback = row.get('Matt Feedback', '').strip().lower()
        reasons = row.get('reasons', '').strip()
        subject = row.get('subject', '').strip()
        
        if category == 'FLIGHT_CONFIRMATION' and ('marketing' in feedback or 'not confirmation' in feedback):
            print(f"Subject: {subject}")
            print(f"Feedback: {feedback}")
            print(f"Reasons: {reasons}")
            print("-" * 20)
            count += 1
            if count >= 10:
                break
