import json

with open("candidates.jsonl", "r", encoding="utf-8") as fin, \
     open("first100.jsonl", "w", encoding="utf-8") as fout:

    for i, line in enumerate(fin):
        if i >= 100:
            break

        obj = json.loads(line)
        fout.write(json.dumps(obj) + "\n")

print("Saved first 100 records.")