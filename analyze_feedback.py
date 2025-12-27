
import csv
from collections import Counter

file_path = "feedback - Sheet1 (1).csv"
feedback_counter = Counter()
errors = []

try:
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            feedback = row.get('Matt Feedback', '').strip()
            category = row.get('category', '').strip()
            subject = row.get('subject', '').strip()
            
            if feedback:
                feedback_counter[feedback] += 1
                # If feedback sounds like a correction or comment
                if feedback.lower() not in ['true', 'false', 'ok']:
                    errors.append({
                        'subject': subject,
                        'current_category': category,
                        'feedback': feedback
                    })

    print(f"Total rows with feedback: {sum(feedback_counter.values())}")
    print("\nFeedback Frequency:")
    for fb, count in feedback_counter.most_common(20):
        print(f" - {fb}: {count}")

    print("\nDetailed Feedback Examples:")
    for err in errors[:30]:
        print(f"Subject: {err['subject']}\nCategory: {err['current_category']}\nFeedback: {err['feedback']}\n---")

except Exception as e:
    print(f"Error: {e}")
