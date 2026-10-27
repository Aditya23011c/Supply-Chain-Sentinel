"""Generates a believable, deterministic mock orders dataset (run once)."""
import json, random
from datetime import date, timedelta
random.seed(7)
customers = [("Reliance Retail", "A"), ("Tata Motors", "A"), ("Apollo Hospitals", "A"),
             ("Croma", "B"), ("Bharat Forge", "B"), ("Havells India", "B"),
             ("Local Distributor Pune", "C"), ("Lucknow Electronics Hub", "C")]
products = [("Industrial Sensor Module", "electronic-components", 100),
            ("Motor Controller Board", "electronic-components", 100),
            ("LED Driver Chip Pack", "electronic-components", 100),
            ("Steel Fasteners Lot", "hardware", 40)]
locations = ["Mumbai"] * 16 + ["Chennai"] * 10 + ["Kolkata"] * 6 + ["Delhi"] * 4
today = date(2026, 10, 10)
orders = []
for i, loc in enumerate(locations, 1):
    cust, tier = random.choice(customers)
    prod, cat, unit = random.choice(products)
    qty = random.choice([200, 500, 800, 1200, 2000])
    orders.append({
        "order_id": f"ORD-{1000+i}", "customer": cust, "customer_tier": tier,
        "product": prod, "category": cat, "quantity": qty,
        "baseline_unit_cost": unit, "order_value": qty * unit * 1.4,
        "due_date": (today + timedelta(days=random.randint(3, 25))).isoformat(),
        "route_node": loc, "sla_penalty_pct": random.choice([0, 2, 5, 8]),
    })
json.dump(orders, open("data/orders_inventory.json", "w"), indent=2)
print(len(orders), "orders written")
