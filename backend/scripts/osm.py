"""
Counts the most frequent key=value tag combinations across an entire
.osm.pbf file, with percentages — no assumption about which keys matter,
just the raw, empirical top tags for this region.
"""

import osmium
from collections import Counter

PBF_PATH = "scripts/kansai-latest.osm.pbf"  # pas dit pad aan naar waar jouw bestand staat
TOP_N = 500


class AllTagsCounter(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.counts = Counter()
        self.total_tagged_elements = 0

    def _count(self, tags):
        if len(tags) == 0:
            return
        self.total_tagged_elements += 1
        for tag in tags:
            self.counts[(tag.k, tag.v)] += 1

    def node(self, n):
        self._count(n.tags)

    def way(self, w):
        self._count(w.tags)

    def relation(self, r):
        self._count(r.tags)


print(f"Reading {PBF_PATH} ... (this may take a few minutes for a regional extract)")
handler = AllTagsCounter()
handler.apply_file(PBF_PATH)

total_tag_instances = sum(handler.counts.values())
print(f"\nTotal tagged elements seen: {handler.total_tagged_elements:,}")
print(f"Total individual tag instances: {total_tag_instances:,}\n")

print(f"Top {TOP_N} most common key=value tags:\n")
for (key, value), count in handler.counts.most_common(TOP_N):
    percentage = (count / total_tag_instances) * 100
    print(f"  {key}={value}: {count:,} ({percentage:.3f}%)")