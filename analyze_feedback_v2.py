
import csv
from collections import Counter

file_path = "feedback - Sheet1 (1).csv"
category_errors = {} # category -> {feedback_msg: count}
total_per_category = Counter()

with open(file_path, mode='r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        category = row.get('category', '').strip()
        feedback = row.get('Matt Feedback', '').strip()
        
        total_per_category[category] += 1
        
        if feedback and feedback.lower() not in ['true', 'false', 'ok']:
            if category not in category_errors:
                category_errors[category] = Counter()
            category_errors[category][feedback] += 1

print(f"{'Category':<25} | {'Total':<5} | {'Feedback Count':<15} | {'Top Feedback Labels'}")
print("-" * 80)
for cat, count in total_per_category.most_common():
    fb_dict = category_errors.get(cat, Counter())
    fb_total = sum(fb_dict.values())
    top_fb = ", ".join([f"{k} ({v})" for k, v in fb_dict.most_common(3)])
    print(f"{cat:<25} | {count:<5} | {fb_total:<15} | {top_fb}")
