"""Generate deterministic Shopify-shaped fixtures for offline demos (India peer set)."""



from __future__ import annotations



import argparse

import hashlib

import json

import random

from datetime import datetime, timedelta, timezone

from pathlib import Path





def stable_id(*parts: object) -> int:

    h = hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()

    return int(h[:12], 16)





FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"



# (title, product_type, tags, base_price) — INR-like units for peer realism.

PRODUCT_SEEDS = {

    "minimalist": [

        ("Niacinamide 10% Face Serum", "Skin Care", ["niacinamide", "serum", "bestseller"], 569.0),

        ("Salicylic Acid 2% Face Serum", "Skin Care", ["salicylic", "acne", "serum"], 499.0),

        ("Vitamin C 10% Face Serum", "Skin Care", ["vitamin c", "brightening"], 599.0),

        ("SPF 50 Sunscreen", "Skin Care", ["spf", "sunscreen", "bestseller"], 449.0),

        ("Hyaluronic Acid 2% Face Serum", "Skin Care", ["hyaluronic", "hydration"], 479.0),

        ("Retinol 0.3% Face Serum", "Skin Care", ["retinol", "anti-aging"], 699.0),

        ("Glycolic Acid 8% Exfoliating Liquid", "Skin Care", ["glycolic", "aha", "exfoliant"], 549.0),

        ("Ceramide Barrier Repair Moisturizer", "Skin Care", ["ceramide", "moisturizer"], 529.0),

    ],

    "pilgrim": [

        ("10% Niacinamide Face Serum", "Serum", ["niacinamide", "acne marks"], 450.0),

        ("10% Vitamin C Face Serum", "Serum", ["vitamin c", "brightening"], 520.0),

        ("Korean Rice Water Hydra Glow Moisturizer", "Moisturizer", ["ceramide", "hydration"], 480.0),

        ("Retinol & Vitamin C Night Cream", "Cream", ["retinol", "vitamin c"], 650.0),

        ("SPF 50 Sunscreen Serum", "Sun Care", ["spf", "sunscreen"], 399.0),

        ("Salicylic Acid & Green Tea Face Wash", "Cleanser", ["salicylic", "bha"], 350.0),

    ],

    "myglamm": [

        ("LIT Vitamin C Face Serum", "Skin Care", ["vitamin c", "brightening"], 499.0),

        ("Manish Malhotra Sandalwood SPF 25", "Skin Care", ["spf", "sunscreen"], 799.0),

        ("POSE HD Niacinamide Primer", "Skin Care", ["niacinamide"], 599.0),

        ("YOUTHfull Hyaluronic Sleeping Mask", "Skin Care", ["hyaluronic", "peptide"], 449.0),

        ("WIPEOUT Salicylic Acid Cleanser", "Cleanser", ["salicylic", "acne"], 349.0),

    ],

    "mamaearth": [

        ("Ubtan Face Serum with Vitamin C", "Skin Care", ["vitamin c", "brightening"], 399.0),

        ("Tea Tree Spot Gel Face Serum", "Skin Care", ["salicylic", "acne"], 449.0),

        ("Skin Illuminate Face Serum", "Skin Care", ["niacinamide"], 379.0),

        ("Ultra Light Indian Sunscreen SPF 50", "Sun Care", ["spf", "sunscreen"], 499.0),

        ("Retinol Face Serum", "Skin Care", ["retinol"], 599.0),

        ("Vitamin C Daily Glow Face Cream", "Skin Care", ["vitamin c"], 349.0),

    ],

    "bellavita": [

        ("Glowner Vitamin C Face Wash", "Skin Care", ["vitamin c"], 249.0),

        ("C-Glow Face Serum", "Skin Care", ["vitamin c", "brightening"], 399.0),

        ("Exfoliating Coffee Body Scrub", "Body Care", ["aha"], 299.0),

        ("Aqua Glow Hydrating Moisturizer", "Skin Care", ["hyaluronic"], 349.0),

        ("SPF 50 Sunscreen Gel", "Sun Care", ["spf", "sunscreen"], 379.0),

    ],

    "foxtale": [

        ("8% Glycolic Acid Toner", "Skin Care", ["glycolic", "aha"], 399.0),

        ("Ceramide Barrier Repair Moisturizer", "Skin Care", ["ceramide"], 449.0),

        ("SPF 70 Sunscreen", "Sun Care", ["spf", "sunscreen"], 499.0),

        ("Niacinamide 10% Serum", "Serum", ["niacinamide"], 429.0),

        ("Salicylic Acid 2% Face Wash", "Cleanser", ["salicylic"], 349.0),

    ],

    "deconstruct": [

        ("Beginner's Exfoliating Serum — AHA 10%", "Serum", ["aha", "glycolic"], 549.0),

        ("Salicylic Acid 2% Face Serum", "Serum", ["salicylic", "bha"], 499.0),

        ("Beginner's Retinol 0.2% Face Serum", "Serum", ["retinol"], 629.0),

        ("Vitamin C 10% Face Serum", "Serum", ["vitamin c"], 579.0),

        ("Niacinamide 5% + Hyaluronic Acid 1%", "Serum", ["niacinamide", "hyaluronic"], 519.0),

    ],

}





BLOG_SEEDS = {

    "minimalist": [

        ("New Multi-Repair serum clinical data", "Published tolerability results for the 15% active blend."),

        ("Trust Circle rewards refresh", "Loyalty tiers updated for repeat skincare buyers."),

    ],

    "pilgrim": [

        ("Building Lifelong Skin Health", "Education-led post on early skincare habits."),

        ("K-beauty ritual deep dive", "Layering guide for serums and SPF."),

    ],

    "mamaearth": [

        ("Goodness Insider: plastic positive", "Brand impact update for Earth Month."),

        ("Ingredient spotlight: Vitamin C", "Why stable vitamin C matters in serums."),

    ],

    "foxtale": [

        ("Foxtale Labs: barrier science", "Why ceramides anchor the new moisturizer."),

    ],

}





def _build_products(slug: str, round_num: int) -> dict:

    random.Random(hash((slug, round_num)) & 0xFFFFFFFF)

    base = PRODUCT_SEEDS[slug]



    products = []

    base_published = datetime(2024, 1, 1, tzinfo=timezone.utc)



    rounds_base = list(enumerate(base))

    if round_num >= 2 and len(rounds_base) > 4:

        rounds_base = rounds_base[:-1]



    for i, (title, ptype, tags, price) in rounds_base:

        price_final = price

        available = True

        if round_num >= 2:

            if i % 5 == 0:

                price_final = round(price * 0.88, 2)

                tags = list(tags) + ["sale"]

            elif i % 7 == 3:

                price_final = round(price * 1.07, 2)

            if i % 6 == 2:

                available = False



        pid = 1_000_000 + stable_id(slug, title) % 9_000_000

        handle = title.lower().replace(" ", "-").replace("(", "").replace(")", "").replace(",", "").replace("%", "")

        variants = [

            {

                "id": pid * 10 + k,

                "price": f"{price_final:.2f}",

                "available": available and (k != 0 or round_num < 2 or i % 6 != 2),

            }

            for k in range(3)

        ]

        products.append(

            {

                "id": pid,

                "title": title,

                "handle": handle,

                "product_type": ptype,

                "vendor": slug,

                "tags": tags,

                "published_at": (base_published + timedelta(days=i * 5)).isoformat(),

                "updated_at": (base_published + timedelta(days=i * 5 + round_num * 30)).isoformat(),

                "images": [{"src": f"https://picsum.photos/seed/{slug}-{i}-{round_num}/600/600"}],

                "variants": variants,

            }

        )



    if round_num >= 2:

        extras = {

            "minimalist": [

                ("Azelaic Acid 10% Face Serum", "Skin Care", ["launch", "azelaic"], 589.0),

                ("Tranexamic 3% Face Serum", "Skin Care", ["launch", "tranexamic"], 584.0, 649.0),

            ],

            "pilgrim": [("Launch: Peptide Eye Serum", "Serum", ["launch", "peptide"], 550.0)],

            "myglamm": [("Super Serum SPF 50 Launch", "Sun Care", ["launch", "spf", "vitamin c"], 699.0)],

            "mamaearth": [("Onion Hair Serum — cross-sell", "Hair Care", ["launch"], 399.0)],

            "bellavita": [("Vitamin C + Niacinamide Body Lotion", "Body Care", ["launch", "vitamin c", "niacinamide"], 329.0)],

            "foxtale": [("Mandelic Acid 5% Serum", "Serum", ["launch", "aha"], 459.0)],

            "deconstruct": [("Kojic Acid + Alpha Arbutin Serum", "Serum", ["launch", "kojic"], 599.0)],

        }

        for j, row in enumerate(extras.get(slug, [])):
            if len(row) == 5:
                title, ptype, tags, price, compare_at = row
            else:
                title, ptype, tags, price = row
                compare_at = None

            pid = 2_000_000 + stable_id(slug, title, round_num) % 7_000_000

            handle = title.lower().replace(" ", "-").replace("(", "").replace(")", "")

            def _extra_variant(k: int) -> dict:
                v: dict = {"id": pid * 10 + k, "price": f"{price:.2f}", "available": True}
                if compare_at is not None:
                    v["compare_at_price"] = f"{compare_at:.2f}"
                return v

            products.append(

                {

                    "id": pid,

                    "title": title,

                    "handle": handle,

                    "product_type": ptype,

                    "vendor": slug,

                    "tags": tags,

                    "published_at": datetime.now(timezone.utc).isoformat(),

                    "updated_at": datetime.now(timezone.utc).isoformat(),

                    "images": [{"src": f"https://picsum.photos/seed/{slug}-new-{j}/600/600"}],

                    "variants": [_extra_variant(k) for k in range(2)],

                }

            )



    return {"products": products}





def _build_blog(slug: str, round_num: int) -> dict:

    entries = []

    posts = list(BLOG_SEEDS.get(slug, []))

    if round_num >= 2:

        fresh = {

            "minimalist": ("SPF reformulation statement", "Transparent note on filter upgrade for 2026 batch."),

            "pilgrim": ("New store opening — Mumbai", "Retail expansion for try-before-buy."),

            "mamaearth": ("Plastic Positive milestone", "Recycled plastic offset update."),

            "foxtale": ("Foxtale x creator collab", "Limited kit with SPF + serum."),

        }

        if slug in fresh:

            posts.append(fresh[slug])



    now = datetime.now(timezone.utc)

    for i, (title, summary) in enumerate(posts):

        published = now - timedelta(days=(len(posts) - i) * 14 - (0 if round_num == 1 else -3))

        entries.append(

            {

                "id": f"{slug}-post-{i}",

                "url": f"https://example.com/{slug}/blog/{i}",

                "title": title,

                "summary": summary,

                "published_at": published.isoformat(),

            }

        )

    return {"entries": entries}





def main() -> None:

    parser = argparse.ArgumentParser()

    parser.add_argument("--round", type=int, default=1, choices=[1, 2])

    args = parser.parse_args()



    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    for slug in PRODUCT_SEEDS:

        products_path = FIXTURES_DIR / f"{slug}_products.json"

        products_path.write_text(json.dumps(_build_products(slug, args.round), indent=2), encoding="utf-8")

        print(f"wrote {products_path.name}")

        blog = _build_blog(slug, args.round)

        if blog["entries"]:

            blog_path = FIXTURES_DIR / f"{slug}_blog.json"

            blog_path.write_text(json.dumps(blog, indent=2), encoding="utf-8")

            print(f"wrote {blog_path.name}")



    print(f"\nFixtures written for round {args.round} at {FIXTURES_DIR}")





if __name__ == "__main__":

    main()


