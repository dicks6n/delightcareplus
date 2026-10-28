"""
The shop's supplement line-up, loaded by `python manage.py setup_shop`.

Products are shown under the France / Japan / USA collections only; supplier brand
names never appear on the site. Prices marked `estimate=True` are starting points:
check them (and the label details) in Seller Center → Products before selling.

Each product also describes its infographic (the main photo):
    callouts: three (icon, title, text) cards beside the pack
    badges:   three (icon, text) benefits along the bottom
Icons are names from catalog.imaging.ICONS.
"""

SAFETY = ("Food supplement. Not a substitute for a varied, balanced diet. Do not exceed the stated dose. "
          "Keep out of reach of children. If you are pregnant, breastfeeding, taking medication or under medical "
          "care, ask your doctor or pharmacist before use.")

PRODUCTS = [
    # ------------------------------------------------------------------ France collection
    {
        "name": "Advanced Collagen + Hyaluronic Acid & Vitamin C", "brand": "France", "category": "Collagen",
        "form": "capsules", "size": "120 capsules", "price": 4500, "estimate": True, "sku": "FR-COLHA-120",
        "concerns": ["Fine lines", "Dryness", "Hair & nails", "Joints"], "best": True, "featured": True,
        "short": "Collagen with hyaluronic acid and vitamin C for skin, hair, nails and joints.",
        "benefits": "Supports skin elasticity and hydration\nHelps strengthen hair and nails\nSupports joint comfort",
        "ingredients": "Collagen, hyaluronic acid, vitamin C. See the label for exact amounts.",
        "callouts": [
            ("dna", "Collagen", "The main structural protein in skin, hair, nails and joints."),
            ("droplet", "Hyaluronic Acid", "Holds water in the skin for a plump, supple look."),
            ("lemon", "Vitamin C", "Contributes to normal collagen formation for the skin."),
        ],
        "badges": [("sparkles", "Skin glow"), ("gem", "Hair & nails"), ("bone", "Joint comfort")],
    },
    {
        "name": "14-in-1 Multi Collagen Complex", "brand": "France", "category": "Collagen",
        "form": "capsules", "size": "Capsules", "price": 4800, "estimate": True, "sku": "FR-COL14",
        "concerns": ["Fine lines", "Hair & nails", "Joints"], "new": True,
        "short": "Collagen types I, II, III, V and X with biotin, keratin and hyaluronic acid.",
        "benefits": "Five types of collagen in one capsule\nBiotin and keratin for hair and nails\nHyaluronic acid for skin moisture",
        "ingredients": "Collagen types I, II, III, V and X, biotin, keratin, hyaluronic acid. See the label for exact amounts.",
        "callouts": [
            ("dna", "5 Collagen Types", "Types I, II, III, V and X — for skin, joints and connective tissue."),
            ("gem", "Biotin + Keratin", "Biotin contributes to normal hair and skin."),
            ("droplet", "Hyaluronic Acid", "Helps skin hold moisture."),
        ],
        "badges": [("sparkles", "Skin"), ("gem", "Hair & nails"), ("bone", "Joints")],
    },
    {
        "name": "Glutathione Radiance Blend with Vitamin C & Mulberry", "brand": "France", "category": "Skin, Hair & Nails",
        "form": "capsules", "size": "120 capsules", "price": 4500, "estimate": True, "sku": "FR-GLUT-120",
        "concerns": ["Dull skin", "Dark spots"], "best": True,
        "short": "Antioxidant glutathione with vitamin C and mulberry for radiant-looking skin.",
        "benefits": "Antioxidant support from within\nVitamin C helps protect cells from oxidative stress\nFor a more even, radiant-looking complexion",
        "ingredients": "Glutathione, vitamin C, mulberry extract. See the label for exact amounts.",
        "callouts": [
            ("shield", "Glutathione", "An antioxidant the body makes naturally, found in every cell."),
            ("lemon", "Vitamin C", "Contributes to the protection of cells from oxidative stress."),
            ("leaf", "Mulberry Extract", "A plant extract often used in skin-radiance formulas."),
        ],
        "badges": [("sparkles", "Radiant look"), ("shield", "Antioxidant"), ("sun", "Daily glow routine")],
    },
    {
        "name": "Berberine", "brand": "France", "category": "Weight Management",
        "form": "capsules", "size": "Capsules", "price": 5999, "sku": "FR-BERB",
        "concerns": ["Weight", "Digestion"],
        "short": "Plant compound from barberry, popular for metabolic and digestive wellness.",
        "benefits": "Traditionally used for metabolic wellness\nSupports a healthy-weight routine\nPlant-derived compound",
        "ingredients": "Berberine (from Berberis species). See the label for exact amounts.",
        "warning": "Not suitable during pregnancy or breastfeeding. If you take medicine for blood sugar or any other condition, "
                   "talk to your doctor first.",
        "callouts": [
            ("mortar", "Berberine", "A natural compound found in barberry and other plants."),
            ("seedling", "Metabolic Support", "Widely used in routines for healthy metabolism."),
            ("scale", "Weight Routine", "Works best alongside a balanced diet and activity."),
        ],
        "badges": [("scale", "Healthy weight routine"), ("seedling", "Digestion"), ("bolt", "Metabolism")],
    },
    {
        "name": "Vitamin K2 + D3 (1,000 IU / 45 mcg)", "brand": "France", "category": "Joint & Bone",
        "form": "capsules", "size": "Capsules", "price": 5999, "sku": "FR-K2D3",
        "concerns": ["Joints", "Immunity"],
        "short": "Vitamin D3 1,000 IU with vitamin K2 45 mcg for bones and immunity.",
        "benefits": "Vitamin D contributes to normal bones and teeth\nVitamin K contributes to normal bones\nVitamin D supports normal immune function",
        "ingredients": "Vitamin D3 (1,000 IU), vitamin K2 (45 mcg) per serving. See the label for the full list.",
        "warning": "If you take blood-thinning medicine (such as warfarin), talk to your doctor before taking vitamin K.",
        "callouts": [
            ("sun", "Vitamin D3 · 1,000 IU", "Contributes to normal bones, teeth and immune function."),
            ("bone", "Vitamin K2 · 45 mcg", "Contributes to the maintenance of normal bones."),
            ("check", "Better Together", "D3 helps absorb calcium; K2 helps put it in bones."),
        ],
        "badges": [("bone", "Strong bones"), ("shield", "Immunity"), ("sun", "Sunshine vitamin")],
    },
    {
        "name": "Calcium, Magnesium & Zinc", "brand": "France", "category": "Joint & Bone",
        "form": "tablets", "size": "Tablets", "price": 4950, "sku": "FR-CAMGZN",
        "concerns": ["Joints", "Immunity", "Sleep"],
        "short": "Three essential minerals for bones, muscles and immunity.",
        "benefits": "Calcium is needed for normal bones\nMagnesium contributes to normal muscle function\nZinc contributes to normal immune function",
        "ingredients": "Calcium, magnesium, zinc. See the label for exact amounts.",
        "callouts": [
            ("bone", "Calcium", "Needed for the maintenance of normal bones and teeth."),
            ("moon", "Magnesium", "Contributes to normal muscle function and reduces tiredness."),
            ("shield", "Zinc", "Contributes to the normal function of the immune system."),
        ],
        "badges": [("bone", "Bones & teeth"), ("run", "Muscles"), ("shield", "Immunity")],
    },
    {
        "name": "Omega-3 Fish Oil 1000 mg", "brand": "France", "category": "Heart Health",
        "form": "capsules", "size": "90 softgels", "price": 3200, "estimate": True, "sku": "FR-OM3-90",
        "concerns": ["Heart health", "Focus & memory"], "best": True,
        "short": "1000 mg fish oil per softgel with 300 mg omega-3 (EPA and DHA).",
        "benefits": "EPA and DHA contribute to normal heart function\nDHA supports normal brain function and vision\nEasy-to-swallow softgels",
        "ingredients": "Fish oil 1000 mg, providing 300 mg omega-3 fatty acids (EPA and DHA) per softgel.",
        "warning": "Contains fish. If you take blood-thinning medicine, talk to your doctor first.",
        "callouts": [
            ("fish", "1000 mg Fish Oil", "Per softgel, providing 300 mg omega-3."),
            ("heart", "EPA + DHA", "Contribute to the normal function of the heart."),
            ("brain", "DHA", "Supports normal brain function and normal vision."),
        ],
        "badges": [("heart", "Heart"), ("brain", "Brain"), ("eye", "Vision")],
    },
    {
        "name": "Maca Complex", "brand": "France", "category": "Men's Health",
        "form": "capsules", "size": "Capsules", "price": 3500, "estimate": True, "sku": "FR-MACA",
        "concerns": ["Energy"],
        "short": "Peruvian maca root, traditionally used for energy and vitality.",
        "benefits": "Traditionally used for energy and stamina\nPlant-based root extract\nFor men and women",
        "ingredients": "Maca root extract (Lepidium meyenii). See the label for exact amounts.",
        "callouts": [
            ("mortar", "Maca Root", "A root from the Peruvian Andes, used for centuries."),
            ("bolt", "Energy & Stamina", "Traditionally taken for energy and vitality."),
            ("care", "For Him & Her", "Popular in both men's and women's wellness routines."),
        ],
        "badges": [("bolt", "Energy"), ("run", "Stamina"), ("leaf", "Plant-based")],
    },
    {
        "name": "NMN Capsules", "brand": "France", "category": "Energy & Vitality",
        "form": "capsules", "size": "Capsules", "price": 6500, "estimate": True, "sku": "FR-NMN",
        "concerns": ["Energy", "Fine lines"], "new": True,
        "short": "Nicotinamide mononucleotide (NMN) for healthy-ageing routines.",
        "benefits": "A building block of NAD+, used in cell energy\nPopular in healthy-ageing routines\nOne small capsule",
        "ingredients": "Nicotinamide mononucleotide (NMN). See the label for exact amounts.",
        "callouts": [
            ("atom", "NMN", "A natural molecule the body turns into NAD+."),
            ("bolt", "Cell Energy", "NAD+ is involved in how cells make energy."),
            ("hourglass", "Healthy Ageing", "A favourite in longevity-focused routines."),
        ],
        "badges": [("bolt", "Energy"), ("hourglass", "Healthy ageing"), ("atom", "Cellular wellness")],
    },
    {
        "name": "Turmeric Curcumin", "brand": "France", "category": "Joint & Bone",
        "form": "capsules", "size": "Capsules", "price": 3200, "estimate": True, "sku": "FR-TURM",
        "concerns": ["Joints", "Immunity"],
        "short": "Golden turmeric root with curcumin for joint comfort and antioxidant support.",
        "benefits": "Traditionally used for joint comfort\nAntioxidant plant compound\nGolden root used for centuries",
        "ingredients": "Turmeric root extract (curcumin). See the label for exact amounts.",
        "warning": "If you take blood-thinning medicine or have gallbladder problems, talk to your doctor first.",
        "callouts": [
            ("mortar", "Turmeric Root", "The golden spice used in traditional wellness for centuries."),
            ("shield", "Curcumin", "The main active compound in turmeric, an antioxidant."),
            ("bone", "Joint Comfort", "A popular choice for active, everyday joint support."),
        ],
        "badges": [("bone", "Joints"), ("shield", "Antioxidant"), ("run", "Active life")],
    },
    {
        "name": "Ashwagandha", "brand": "France", "category": "Sleep & Stress",
        "form": "capsules", "size": "Capsules", "price": 3200, "estimate": True, "sku": "FR-ASHW",
        "concerns": ["Stress", "Sleep"],
        "short": "Ayurvedic herb traditionally used to help the body handle stress.",
        "benefits": "Traditionally used to support calm\nHelps you unwind for better sleep\nAdaptogenic herb",
        "ingredients": "Ashwagandha root extract (Withania somnifera). See the label for exact amounts.",
        "warning": "Not suitable during pregnancy. If you have a thyroid condition or take sedatives, talk to your doctor first.",
        "callouts": [
            ("leaf", "Ashwagandha Root", "An adaptogen from Ayurvedic tradition."),
            ("moon", "Calm & Balance", "Traditionally used to help the body cope with stress."),
            ("bed", "Rest", "A calm mind makes it easier to switch off at night."),
        ],
        "badges": [("moon", "Calm"), ("bed", "Better rest"), ("brain", "Focus")],
    },
    {
        "name": "Saw Palmetto Prostate Support", "brand": "France", "category": "Men's Health",
        "form": "capsules", "size": "Capsules", "price": 3500, "estimate": True, "sku": "FR-SAWP",
        "concerns": [],
        "short": "Saw palmetto berry extract, traditionally used for men's prostate wellness.",
        "benefits": "Traditionally used for prostate wellness\nSupports normal urinary comfort in men\nPlant extract",
        "ingredients": "Saw palmetto berry extract (Serenoa repens). See the label for exact amounts.",
        "warning": "For adult men. See a doctor about any urinary symptoms before using supplements.",
        "callouts": [
            ("mortar", "Saw Palmetto", "Extract of the berries of a small palm tree."),
            ("mars", "Men's Wellness", "Traditionally used to support the prostate."),
            ("check", "Daily Routine", "One of the most popular men's herbal supplements."),
        ],
        "badges": [("mars", "Prostate wellness"), ("droplet", "Urinary comfort"), ("leaf", "Plant extract")],
    },
    {
        "name": "CoQ10", "brand": "France", "category": "Heart Health",
        "form": "capsules", "size": "Capsules", "price": 4200, "estimate": True, "sku": "FR-COQ10",
        "concerns": ["Heart health", "Energy"],
        "short": "Coenzyme Q10 for cell energy and heart wellness.",
        "benefits": "Involved in how cells produce energy\nHighest in hard-working organs like the heart\nLevels fall with age",
        "ingredients": "Coenzyme Q10. See the label for exact amounts.",
        "warning": "If you take blood-thinning or blood-pressure medicine, talk to your doctor first.",
        "callouts": [
            ("atom", "Coenzyme Q10", "A vitamin-like compound found in every cell."),
            ("bolt", "Cell Energy", "Part of the process cells use to make energy."),
            ("heart", "Heart Wellness", "Found in high amounts in the heart muscle."),
        ],
        "badges": [("heart", "Heart"), ("bolt", "Energy"), ("hourglass", "Healthy ageing")],
    },
    {
        "name": "Glucosamine & Chondroitin", "brand": "France", "category": "Joint & Bone",
        "form": "tablets", "size": "Tablets", "price": 3800, "estimate": True, "sku": "FR-GLUCH",
        "concerns": ["Joints"],
        "short": "Two building blocks of cartilage for everyday joint comfort.",
        "benefits": "Glucosamine and chondroitin are found in cartilage\nPopular for active and ageing joints\nTake daily for best results",
        "ingredients": "Glucosamine, chondroitin. See the label for exact amounts.",
        "warning": "Glucosamine is often made from shellfish — not suitable if you have a shellfish allergy unless the label says otherwise.",
        "callouts": [
            ("bone", "Glucosamine", "A natural part of healthy cartilage."),
            ("dna", "Chondroitin", "Helps give cartilage its cushioning."),
            ("run", "Keep Moving", "Made for active people and ageing joints."),
        ],
        "badges": [("bone", "Joints"), ("run", "Mobility"), ("care", "Everyday comfort")],
    },

    # ------------------------------------------------------------------ USA collection
    {
        "name": "Liver Protection — Milk Thistle & Dandelion Root", "brand": "USA", "category": "Liver Health",
        "form": "capsules", "size": "120 vegetable capsules", "price": 3500, "estimate": True, "sku": "US-LIVER-120",
        "concerns": ["Liver detox", "Digestion", "Dull skin"], "best": True, "featured": True,
        "short": "Milk thistle and dandelion root in vegetable capsules. Soy-free and GMO-free.",
        "benefits": "Milk thistle is traditionally used to support the liver\nDandelion root supports digestion\nSoy-free, GMO-free vegetable capsules",
        "ingredients": "Milk thistle extract (silymarin), dandelion root extract (Taraxacum officinale). Vegetable capsule. "
                       "See the label for exact amounts.",
        "warning": "If you have a liver condition or allergy to plants in the daisy family, talk to your doctor first.",
        "callouts": [
            ("leaf", "Milk Thistle", "Rich in silymarin, a plant antioxidant traditionally used for the liver."),
            ("mortar", "Dandelion Root", "A traditional herb used to support digestion and bile flow."),
            ("check", "Soy-free · GMO-free", "120 vegetable capsules, as stated on the label."),
        ],
        "badges": [("leaf", "Liver support"), ("seedling", "Digestion"), ("bolt", "Daily wellness")],
    },
]

# Sample products that the real line-up above replaces
REPLACED_SAMPLES = ["Collagen Beauty Capsules", "Liver Detox Milk Thistle", "Omega-3 Fish Oil 1000mg",
                    "Glucosamine Joint Support"]
