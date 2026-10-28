"""Fictional patients and the shared texts for reviews, notes and chats."""

# key, arabic name, language
PATIENTS = [
    ("patient-sara", "سارة محمود", "ar"),
    ("patient-ali", "علي حسين", "ar"),
    ("patient-fatima", "فاطمة الزهراء", "ar"),
    ("patient-omar", "عمر خالد", "en"),
    ("patient-zainab", "زينب كاظم", "ar"),
    ("patient-hassan", "حسن العلي", "ar"),
]

PATIENT_NOTES = [
    "أرغب بمتابعة دورية ونتائج تحاليل سابقة سأحضرها معي.",
    "زيارة أولى، أرجو توفير وقت كافٍ للاستفسارات.",
    "متابعة بعد العلاج السابق.",
    "",
]

# rating -> comments (neutral, specific, respectful; none makes a medical claim)
REVIEW_COMMENTS = {
    5: [
        "تعامل راقٍ ووقت كافٍ للشرح، أنصح بالزيارة.",
        "التزام بالموعد وشرح واضح لكل خطوة.",
        "عيادة نظيفة وطاقم متعاون جداً.",
    ],
    4: [
        "تجربة جيدة وشرح مفهوم، الانتظار كان قصيراً.",
        "طبيب محترف، تمنيت مدة جلسة أطول قليلاً.",
        "خدمة جيدة وأسعار مناسبة.",
    ],
    3: ["الخدمة مقبولة لكن الانتظار طال عن الموعد.", "الشرح كان مختصراً، وبقية الأمور جيدة."],
}
# provider key -> ratings of its completed, reviewed visits (variety on purpose: means 3.8–4.9)
REVIEW_PLAN = {
    "dr-karim-saadi": [5, 5, 4, 5],
    "dr-noor-hamdani": [4, 5, 4],
    "dr-huda-rubaie": [4, 4, 5, 3],
    "dr-mariam-zubaidi": [5, 5, 5, 4],
    "dr-rana-obaidi": [4, 4, 3, 5],
    "dr-sarmad-azzawi": [5, 4, 5],
    "dr-haider-moussawi": [4, 5, 4, 4],
    "dr-sura-kubaisi": [5, 5, 4],
    "dr-firas-anbari": [4, 3, 4],
    "dr-dalia-tamimi": [5, 4, 5, 5],
    "dr-amal-khazraji": [5, 5, 4, 5],
    "dr-reem-ani": [4, 4, 3],
    "th-layla-nuaimi": [5, 5, 4],
    "nr-hanan-saidi": [5, 4, 5],
    # facilities are bookable and reviewed too, so facility dashboards are not empty
    "dijla-hospital": [5, 4, 4],
    "rafidain-womens-children": [5, 5, 4],
    "fayhaa-center": [4, 3, 4, 5],
    "nakheel-dental": [5, 4, 5],
    "baghdad-imaging": [4, 4, 5],
    "noor-eye-center": [5, 4],
}

# (patient key, provider key, [(side, text)])
CHATS = [
    (
        "patient-sara",
        "dr-mariam-zubaidi",
        [
            ("patient", "السلام عليكم دكتورة، هل يمكن إحضار سجل اللقاحات في الموعد؟"),
            ("provider", "وعليكم السلام، نعم يرجى إحضاره مع آخر تقرير نمو."),
            ("patient", "شكراً جزيلاً، سنكون هناك قبل الموعد بعشر دقائق."),
            ("provider", "بانتظاركم، لا تنسوا بطاقة الطفل."),
        ],
    ),
    (
        "patient-ali",
        "dr-karim-saadi",
        [
            ("patient", "دكتور، هل أحتاج الصيام قبل تخطيط القلب؟"),
            ("provider", "لا حاجة للصيام، فقط ارتدِ ملابس مريحة."),
            ("patient", "ممتاز، شكراً لك."),
            ("provider", "أهلاً بك، نراك في الموعد."),
        ],
    ),
    (
        "patient-fatima",
        "dr-amal-khazraji",
        [
            ("patient", "مرحباً دكتورة، أرغب بتأجيل الموعد ساعة إن أمكن."),
            ("provider", "مرحباً، الموعد التالي متاح بعد ساعة، سأثبته لك."),
            ("patient", "ممتن لتعاونك."),
        ],
    ),
    (
        "patient-omar",
        "dr-sarmad-azzawi",
        [
            ("patient", "Hello doctor, could I bring my previous glasses prescription?"),
            ("provider", "Of course, please bring it with you to the appointment."),
            ("patient", "Great, thank you."),
            ("provider", "You're welcome, see you soon."),
        ],
    ),
    (
        "patient-zainab",
        "th-layla-nuaimi",
        [
            ("patient", "هل ألبس ملابس رياضية في جلسة العلاج الطبيعي؟"),
            ("provider", "نعم يفضّل ذلك وحذاء مريح."),
            ("patient", "تمام شكراً."),
        ],
    ),
]

# provider key -> offers (title_ar, title_en, discount_fraction, days_valid)
OFFERS = {
    "dr-dalia-tamimi": [
        ("خصم على فحص الأسنان والتنظيف", "Discount on dental check-up & cleaning", 0.2, 30)
    ],
    "dr-mariam-zubaidi": [
        (
            "متابعة النمو واللقاحات بسعر مخفض",
            "Reduced-price growth & vaccination follow-up",
            0.15,
            21,
        )
    ],
    "dr-sarmad-azzawi": [
        ("فحص العيون الشامل — عرض الشهر", "Comprehensive eye exam — monthly offer", 0.15, 30)
    ],
    "th-layla-nuaimi": [
        ("باقة تقييم حركي أولي مخفضة", "Reduced initial movement assessment", 0.1, 45)
    ],
    "dr-reem-ani": [("فحص دوري شامل بسعر خاص", "Routine health check at a special price", 0.2, 14)],
}
