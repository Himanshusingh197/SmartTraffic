LANES = ["north", "south", "east", "west"]
MIN_GREEN = 15
MAX_GREEN = 60
YELLOW = 3
ALL_RED = 2
CYCLE_BUDGET = 120  # total green seconds available per cycle


def compute_timings(counts, min_green=MIN_GREEN, max_green=MAX_GREEN, cycle_budget=CYCLE_BUDGET):
    safe = {l: max(0, int(counts.get(l, 0))) for l in LANES}
    total = sum(safe.values())

    timings = {}
    if total == 0:
        for l in LANES:
            timings[l] = {"count": 0, "green": min_green, "yellow": YELLOW, "all_red": ALL_RED}
    else:
        for l in LANES:
            share = (safe[l] / total) * cycle_budget
            green = int(round(max(min_green, min(max_green, share))))
            timings[l] = {"count": safe[l], "green": green, "yellow": YELLOW, "all_red": ALL_RED}

    cycle_total = sum(t["green"] + t["yellow"] + t["all_red"] for t in timings.values())
    return {"timings": timings, "total_vehicles": total, "cycle_total": cycle_total}