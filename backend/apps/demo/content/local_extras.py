"""LOCAL-ONLY demo extras (docs/DEMO_DATA.md §Local workspace demo). Seeded only by
`seed_local_demo` on the guarded disposable database — never by the staging seed.

Every person, business, product and price is FICTIONAL. Product descriptions make no medical
claims. Payments are demo records only: nothing is charged and no card data exists anywhere.
"""

# Business classification of the base demo companies (key -> BusinessType).
COMPANY_BUSINESS_TYPES = {
    "dijla-pharma": "PHARMACEUTICAL_COMPANY",
    "rafidain-pharma": "PHARMACEUTICAL_COMPANY",
    "babylon-medicines": "PHARMACEUTICAL_COMPANY",
    "nineveh-pharma": "PHARMACEUTICAL_COMPANY",
    "gulf-pharma": "PHARMACEUTICAL_COMPANY",
    "kurdistan-medicines": "PHARMA_DISTRIBUTOR",
    "sharq-devices": "EQUIPMENT_SUPPLIER",
    "iraq-monitor": "EQUIPMENT_SUPPLIER",
    "rafidain-labtech": "EQUIPMENT_SUPPLIER",
    "modern-furniture": "EQUIPMENT_SUPPLIER",
    "roya-imaging": "EQUIPMENT_SUPPLIER",
    "rehab-mobility": "ASSISTIVE_DEVICE_STORE",
    "aman-consumables": "MEDICAL_SUPPLIES_OFFICE",
}

# key, name_ar, name_en, business type, verification status, account active, governorate, city
EXTRA_COMPANIES = [
    (
        "nakhla-dental-supply",
        "مكتب النخلة لمستلزمات الأسنان",
        "Nakhla Dental Supply Office",
        "MEDICAL_SUPPLIES_OFFICE",
        "VERIFIED",
        True,
        "baghdad",
        "baghdad",
    ),
    (
        "ibn-sina-scientific",
        "المكتب العلمي ابن سينا",
        "Ibn Sina Scientific Office",
        "SCIENTIFIC_OFFICE",
        "VERIFIED",
        True,
        "baghdad",
        "baghdad",
    ),
    (
        "furat-trading-suspended",
        "شركة الفرات التجارية (معلّقة)",
        "Furat Trading Co. (suspended)",
        "EQUIPMENT_SUPPLIER",
        "VERIFIED",
        False,  # suspended account: its campaigns and products must disappear
        "babil",
        None,
    ),
    (
        "noor-rejected-supplies",
        "مستلزمات النور (مرفوضة)",
        "Noor Supplies (verification rejected)",
        "MEDICAL_SUPPLIES_OFFICE",
        "REJECTED",
        True,
        "basra",
        None,
    ),
    (
        "tigris-pending-supplies",
        "مستلزمات دجلة (قيد التحقق)",
        "Tigris Supplies (pending verification)",
        "MEDICAL_SUPPLIES_OFFICE",
        "PENDING",
        True,
        "baghdad",
        "baghdad",
    ),
]

# slug, name_ar, name_en, consumer_allowed, audience [(provider_type, specialty slug or None)]
EXTRA_CATEGORIES = [
    (
        "demo-dental-equipment",
        "معدات طب الأسنان",
        "Dental equipment",
        False,
        [("DOCTOR", "dentistry"), ("MEDICAL_CENTER", "dentistry")],
    ),
    (
        "demo-pharmacy-supplies",
        "مستلزمات الصيدليات",
        "Pharmacy supplies",
        False,
        [("PHARMACY", None)],
    ),
    (
        "demo-aesthetic-equipment",
        "معدات مراكز التجميل",
        "Aesthetic clinic equipment",
        False,
        [("BEAUTY_CENTER", None)],
    ),
    (
        "demo-mobility-aids",
        "وسائل المساعدة على الحركة",
        "Mobility aids",
        True,
        [("THERAPIST", None), ("HOSPITAL", None), ("MEDICAL_CENTER", None)],
    ),
    (
        "demo-home-monitoring",
        "أجهزة القياس المنزلية",
        "Home monitoring devices",
        True,
        [("DOCTOR", None), ("NURSE", None)],
    ),
]

# key, company key, category slug, title_ar, title_en, price, sale channel, restricted, stock
EXTRA_PRODUCTS = [
    (
        "dental-chair",
        "nakhla-dental-supply",
        "demo-dental-equipment",
        "كرسي أسنان كهربائي",
        "Electric dental chair",
        "9500000",
        "B2B",
        False,
        None,
    ),
    (
        "dental-scaler",
        "nakhla-dental-supply",
        "demo-dental-equipment",
        "جهاز تنظيف الجير بالموجات",
        "Ultrasonic scaler",
        "750000",
        "B2B",
        False,
        None,
    ),
    (
        "pharmacy-fridge",
        "ibn-sina-scientific",
        "demo-pharmacy-supplies",
        "ثلاجة أدوية للصيدليات",
        "Pharmacy medicine refrigerator",
        "2400000",
        "B2B",
        False,
        None,
    ),
    (
        "dispensing-trays",
        "ibn-sina-scientific",
        "demo-pharmacy-supplies",
        "صواني صرف الأدوية",
        "Dispensing trays (set)",
        "45000",
        "B2B",
        False,
        None,
    ),
    (
        "restricted-antibiotic",
        "dijla-pharma",
        "demo-generic-medicines",
        "مضاد حيوي بوصفة طبية (توضيحي)",
        "Prescription antibiotic (demo, restricted)",
        "12000",
        "B2B",
        True,
        None,
    ),
    (
        "wheelchair",
        "rehab-mobility",
        "demo-mobility-aids",
        "كرسي متحرك قابل للطي",
        "Folding wheelchair",
        "185000",
        "BOTH",
        False,
        6,
    ),
    (
        "walker",
        "rehab-mobility",
        "demo-mobility-aids",
        "مشاية بعجلات",
        "Wheeled walker",
        "65000",
        "B2C",
        False,
        10,
    ),
    (
        "crutches",
        "rehab-mobility",
        "demo-mobility-aids",
        "عكازات ألمنيوم (زوج)",
        "Aluminium crutches (pair)",
        "30000",
        "B2C",
        False,
        15,
    ),
    (
        "shower-chair",
        "rehab-mobility",
        "demo-mobility-aids",
        "كرسي استحمام",
        "Shower chair",
        "40000",
        "B2C",
        False,
        0,
    ),
    (
        "bp-monitor",
        "aman-consumables",
        "demo-home-monitoring",
        "جهاز ضغط منزلي",
        "Home blood-pressure monitor",
        "55000",
        "BOTH",
        False,
        12,
    ),
    (
        "pulse-oximeter",
        "aman-consumables",
        "demo-home-monitoring",
        "مقياس الأكسجين",
        "Fingertip pulse oximeter",
        "25000",
        "B2C",
        False,
        20,
    ),
    (
        "suspended-monitor",
        "furat-trading-suspended",
        "demo-home-monitoring",
        "شاشة مراقبة",
        "Patient monitor",
        "900000",
        "BOTH",
        False,
        4,
    ),
    (
        "pending-gloves",
        "tigris-pending-supplies",
        "demo-home-monitoring",
        "قفازات فحص",
        "Examination gloves",
        "8000",
        "B2C",
        False,
        100,
    ),
    (
        "quad-cane",
        "rehab-mobility",
        "demo-mobility-aids",
        "عصا رباعية القاعدة",
        "Quad-base walking cane",
        "28000",
        "B2C",
        False,
        2,
    ),
    (
        "skin-analyzer",
        "sharq-devices",
        "demo-aesthetic-equipment",
        "جهاز تحليل البشرة",
        "Skin analysis device",
        "3200000",
        "B2B",
        False,
        None,
    ),
    (
        "rejected-gauze",
        "noor-rejected-supplies",
        "demo-home-monitoring",
        "شاش طبي",
        "Medical gauze pack",
        "3000",
        "B2C",
        False,
        50,
    ),
]

# key, company key, product key, status, payment status, start offset days, length days,
# target provider types, target specialty slugs
CAMPAIGNS = [
    (
        "dental-live",
        "nakhla-dental-supply",
        "dental-chair",
        "ACTIVE",
        "VERIFIED",
        -3,
        30,
        [],
        ["dentistry"],
    ),
    (
        "pharmacy-live",
        "ibn-sina-scientific",
        "pharmacy-fridge",
        "ACTIVE",
        "VERIFIED",
        -2,
        20,
        ["PHARMACY"],
        [],
    ),
    ("rehab-live", "rehab-mobility", "wheelchair", "ACTIVE", "VERIFIED", -1, 25, ["THERAPIST"], []),
    ("expired", "nakhla-dental-supply", "dental-scaler", "ACTIVE", "VERIFIED", -40, 10, [], []),
    ("rejected", "ibn-sina-scientific", "dispensing-trays", "REJECTED", "REJECTED", 2, 10, [], []),
    ("pending", "aman-consumables", "bp-monitor", "PENDING_PAYMENT", "PENDING", 3, 14, [], []),
    (
        "suspended",
        "furat-trading-suspended",
        "suspended-monitor",
        "ACTIVE",
        "VERIFIED",
        -1,
        20,
        [],
        [],
    ),
    (
        "beauty-live",
        "sharq-devices",
        "skin-analyzer",
        "ACTIVE",
        "VERIFIED",
        -1,
        20,
        ["BEAUTY_CENTER"],
        [],
    ),
]

# key, full name, account type, contrast flag ("pending" | "suspended" | "inactive" | "unverified")
CONTRAST_PROVIDERS = [
    (
        "dr-pending-samer",
        "د. سامر الحلي | Dr. Samer Al-Hilli (pending)",
        "DOCTOR",
        "dentistry",
        "PENDING",
    ),
    (
        "dr-suspended-kamal",
        "د. كمال الربيعي | Dr. Kamal Al-Rubaie (suspended)",
        "DOCTOR",
        "general-medicine",
        "SUSPENDED",
    ),
]

# key, full name, flag
CONTRAST_PATIENTS = [
    ("patient-suspended", "مريض معلّق | Suspended patient", "inactive"),
    ("patient-unverified", "مريض غير مؤكد البريد | Unverified-email patient", "unverified"),
]

# Staff (personal accounts) and their organization roles:
# key, full name, [(org kind, org key, role, active)]
STAFF = [
    (
        "staff-nakheel-manager",
        "مديرة مركز النخيل | Nakheel center manager",
        [("facility", "nakheel-dental", "MANAGER", True)],
    ),
    (
        "staff-dijla-reception",
        "موظف استقبال دجلة | Dijla reception",
        [("facility", "dijla-hospital", "STAFF", True)],
    ),
    (
        "staff-dijla-viewer",
        "مراجع دجلة (قراءة فقط) | Dijla viewer",
        [("facility", "dijla-hospital", "VIEWER", True)],
    ),
    (
        "staff-rehab-store",
        "مدير متجر التأهيل | Rehab store manager",
        [("company", "rehab-mobility", "MANAGER", True)],
    ),
    (
        "staff-multi-org",
        "موظف متعدد الجهات | Multi-org staff",
        [
            ("facility", "fayhaa-center", "STAFF", True),
            ("company", "rehab-mobility", "VIEWER", True),
        ],
    ),
    ("staff-ended", "موظف سابق | Former staff", [("facility", "dijla-hospital", "STAFF", False)]),
]

# key, full name, employer key (EmployerMembership RECRUITER)
RECRUITERS = [("recruiter-dijla", "مسؤولة توظيف دجلة | Dijla recruiter", "dijla-hospital")]

# key, name, profession, title, degree, years
EXTRA_SEEKERS = [
    (
        "seeker-it-mustafa",
        "مصطفى الكعبي | Mustafa Al-Kaabi",
        "SOFTWARE_DEVELOPER",
        "مطور برمجيات أنظمة صحية",
        "BACHELOR",
        3,
    ),
    (
        "seeker-cyber-zahra",
        "زهراء الموسوي | Zahraa Al-Mousawi",
        "CYBERSECURITY",
        "أخصائية أمن معلومات",
        "MASTER",
        5,
    ),
    (
        "seeker-accountant-haidar",
        "حيدر الشمري | Haidar Al-Shammari",
        "ACCOUNTANT",
        "محاسب مؤسسات صحية",
        "BACHELOR",
        7,
    ),
]

# account key -> preference changes (anything not listed keeps the defaults)
PREFERENCES = {
    "dr-dalia-tamimi": {"offers_and_news": True, "real_estate_promotions": True},
    "dr-mustafa-saffar": {"show_sponsored_products": False},
    "dr-karim-saadi": {"real_estate_promotions": False, "offers_and_news": False},
    "amal-pharmacy": {"real_estate_promotions": True, "offers_and_news": True},
    "nakheel-dental": {"real_estate_promotions": True, "offers_and_news": True},
    "th-layla-nuaimi": {"offers_and_news": True},
}

# tag, patient key, product key, quantity, payment method, steps after placing
ORDERS = [
    ("sara-wheelchair", "patient-sara", "wheelchair", 1, "CASH_ON_DELIVERY", []),
    ("sara-walker", "patient-sara", "walker", 1, "CASH_ON_DELIVERY", ["CONFIRMED"]),
    ("ali-bp", "patient-ali", "bp-monitor", 1, "MANUAL_TRANSFER", ["CONFIRMED", "paid", "SHIPPED"]),
    (
        "fatima-crutches",
        "patient-fatima",
        "crutches",
        2,
        "CASH_ON_DELIVERY",
        ["CONFIRMED", "SHIPPED", "DELIVERED"],
    ),
    ("omar-oximeter", "patient-omar", "pulse-oximeter", 1, "CASH_ON_DELIVERY", ["buyer-cancel"]),
]

# tag, requester provider key, product key, quantity, outcome ("REQUESTED"|"QUOTED"|"ACCEPTED")
QUOTES = [
    ("dalia-chair", "dr-dalia-tamimi", "dental-chair", 1, "QUOTED", "9200000"),
    ("nakheel-scaler", "nakheel-dental", "dental-scaler", 3, "REQUESTED", None),
    ("amal-fridge", "amal-pharmacy", "pharmacy-fridge", 1, "ACCEPTED", "2300000"),
]

# tag, listing index (base estate.LISTINGS), target provider types, days, outcome
PROMOTIONS = [
    ("clinic-floor", 0, ["PHARMACY", "MEDICAL_CENTER", "DOCTOR"], 21, "ACTIVE"),
    ("pharmacy-shop", 1, ["PHARMACY"], 14, "REQUESTED"),
    ("old-villa", 2, [], 7, "REJECTED"),
]


# A beauty center (facility) with its own services, offer, staff and preferences.
# key, ptype, name_ar, name_en, gov, city, services [(ar, en, price, minutes)]
EXTRA_FACILITIES = [
    (
        "lamsa-beauty",
        "BEAUTY_CENTER",
        "مركز لمسة للتجميل",
        "Lamsa Beauty Center",
        "baghdad",
        "baghdad",
        [
            ("جلسة تنظيف بشرة", "Facial cleansing session", "45000", 60),
            ("استشارة عناية بالبشرة", "Skin-care consultation", "25000", 30),
            ("جلسة ترطيب", "Hydration session", "35000", 45),
        ],
    ),
]
EXTRA_FACILITY_OFFERS = [("lamsa-beauty", "عرض جلسة تنظيف", "Facial session offer", "0.2", 20)]
EXTRA_STAFF = [
    (
        "staff-lamsa-reception",
        "موظفة استقبال لمسة | Lamsa reception",
        [("facility", "lamsa-beauty", "STAFF", True)],
    ),
]
EXTRA_PREFERENCES = {"lamsa-beauty": {"offers_and_news": True, "real_estate_promotions": False}}
