import csv
import os
import random
from datetime import date, timedelta

random.seed(11)
os.makedirs("data", exist_ok=True)

first = ["Acme", "Nova", "Orbit", "Zenith", "Lumen", "Bright", "Vertex", "Pioneer",
         "Summit", "Apex", "Cobalt", "Delta", "Echo", "Falcon", "Granite"]
second = ["Logistics", "Retail", "Health", "Foods", "Studio", "Labs", "Systems",
          "Motors", "Finance", "Textiles", "Energy", "Media", "Pharma", "Realty"]
people = ["Priya Nair", "Arjun Rao", "Meera Shah", "Kabir Sen", "Sana Iqbal", "Dev Patel",
          "Ishita Roy", "Rohan Gupta", "Ananya Das", "Vikram Singh", "Neha Kapoor", "Aman Verma"]
owners = ["Rahul", "Sneha", "Karan", "Divya"]
regions = ["North", "South", "East", "West"]
stages = ["Lead", "Qualified", "Demo", "Proposal", "Negotiation", "Won", "Lost"]
weights = [15, 20, 20, 20, 10, 10, 5]

names = set()
while len(names) < 60:
    names.add(f"{random.choice(first)} {random.choice(second)}")
names = sorted(names)

today = date.today()
rows = []
for name in names:
    amount = random.choice([150000, 300000, 450000, 800000, 1200000, 2000000])
    amount = int(round(amount * random.uniform(0.7, 1.3), -4))
    last = (today - timedelta(days=random.randint(0, 45))).isoformat()
    rows.append([name, random.choice(people), random.choices(stages, weights)[0],
                 amount, last, random.choice(owners), random.choice(regions)])

# A few imperfect rows, like real exports have.
for k in random.sample(range(len(rows)), 3):
    rows[k][4] = ""
rows.append(["", "Unknown Person", "Lead", 100000, today.isoformat(), "Rahul", "North"])
rows.append(["", "Another Person", "Demo", 250000, today.isoformat(), "Sneha", "East"])

with open("data/sample_deals.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Account Name", "Primary Contact", "Pipeline Stage",
                "Amount (INR)", "Last Contacted", "Owner", "Region"])
    w.writerows(rows)
print("Wrote", len(rows), "rows to data/sample_deals.csv")