from datasets import load_dataset
from collections import Counter

print("Downloading dataset...")
dataset = load_dataset("deepset/prompt-injections")

print("\n--- Dataset Structure ---")
print(dataset)

print("\n--- First 3 examples ---")
for i in range(3):
    example = dataset["train"][i]
    print(f"\n[{i+1}] Label: {'INJECTION' if example['label'] == 1 else 'CLEAN'}")
    print(f"     Text: {example['text'][:100]}...")

print("\n--- Label Distribution ---")
labels = [x["label"] for x in dataset["train"]]
counts = Counter(labels)
print(f"Clean inputs:      {counts[0]}")
print(f"Injections:        {counts[1]}")
print(f"Total examples:    {len(labels)}")