"""Iraq reference data used by migration 0002. Edit only via a new migration."""

# (slug, name_en, name_ar, [(city_slug, city_en, city_ar), ...])
IRAQ_GOVERNORATES = [
    (
        "baghdad",
        "Baghdad",
        "بغداد",
        [
            ("baghdad", "Baghdad", "بغداد"),
            ("mahmudiyah", "Mahmudiyah", "المحمودية"),
            ("abu-ghraib", "Abu Ghraib", "أبو غريب"),
        ],
    ),
    (
        "basra",
        "Basra",
        "البصرة",
        [
            ("basra", "Basra", "البصرة"),
            ("zubair", "Az Zubayr", "الزبير"),
            ("umm-qasr", "Umm Qasr", "أم قصر"),
        ],
    ),
    (
        "nineveh",
        "Nineveh",
        "نينوى",
        [
            ("mosul", "Mosul", "الموصل"),
            ("tal-afar", "Tal Afar", "تلعفر"),
            ("sinjar", "Sinjar", "سنجار"),
        ],
    ),
    (
        "erbil",
        "Erbil",
        "أربيل",
        [
            ("erbil", "Erbil", "أربيل"),
            ("soran", "Soran", "سوران"),
            ("shaqlawa", "Shaqlawa", "شقلاوة"),
        ],
    ),
    (
        "sulaymaniyah",
        "Sulaymaniyah",
        "السليمانية",
        [
            ("sulaymaniyah", "Sulaymaniyah", "السليمانية"),
            ("ranya", "Ranya", "رانية"),
            ("kalar", "Kalar", "كلار"),
        ],
    ),
    (
        "duhok",
        "Duhok",
        "دهوك",
        [
            ("duhok", "Duhok", "دهوك"),
            ("zakho", "Zakho", "زاخو"),
            ("amadiya", "Amadiya", "العمادية"),
        ],
    ),
    ("kirkuk", "Kirkuk", "كركوك", [("kirkuk", "Kirkuk", "كركوك"), ("hawija", "Hawija", "الحويجة")]),
    (
        "diyala",
        "Diyala",
        "ديالى",
        [
            ("baqubah", "Baqubah", "بعقوبة"),
            ("khanaqin", "Khanaqin", "خانقين"),
            ("muqdadiyah", "Al Muqdadiyah", "المقدادية"),
        ],
    ),
    (
        "anbar",
        "Anbar",
        "الأنبار",
        [
            ("ramadi", "Ramadi", "الرمادي"),
            ("fallujah", "Fallujah", "الفلوجة"),
            ("hit", "Hit", "هيت"),
        ],
    ),
    (
        "babil",
        "Babil",
        "بابل",
        [("hillah", "Hillah", "الحلة"), ("musayyib", "Al Musayyib", "المسيب")],
    ),
    (
        "karbala",
        "Karbala",
        "كربلاء",
        [("karbala", "Karbala", "كربلاء"), ("ain-al-tamur", "Ain al-Tamur", "عين التمر")],
    ),
    ("najaf", "Najaf", "النجف", [("najaf", "Najaf", "النجف"), ("kufa", "Kufa", "الكوفة")]),
    ("wasit", "Wasit", "واسط", [("kut", "Kut", "الكوت"), ("al-hay", "Al Hay", "الحي")]),
    (
        "maysan",
        "Maysan",
        "ميسان",
        [("amarah", "Amarah", "العمارة"), ("majar-al-kabir", "Al Majar al-Kabir", "المجر الكبير")],
    ),
    (
        "dhi-qar",
        "Dhi Qar",
        "ذي قار",
        [("nasiriyah", "Nasiriyah", "الناصرية"), ("shatrah", "Shatrah", "الشطرة")],
    ),
    (
        "muthanna",
        "Muthanna",
        "المثنى",
        [("samawah", "Samawah", "السماوة"), ("rumaitha", "Rumaitha", "الرميثة")],
    ),
    (
        "qadisiyyah",
        "Al-Qadisiyyah",
        "القادسية",
        [("diwaniyah", "Diwaniyah", "الديوانية"), ("afak", "Afak", "عفك")],
    ),
    (
        "saladin",
        "Saladin",
        "صلاح الدين",
        [
            ("tikrit", "Tikrit", "تكريت"),
            ("samarra", "Samarra", "سامراء"),
            ("baiji", "Baiji", "بيجي"),
        ],
    ),
    ("halabja", "Halabja", "حلبجة", [("halabja", "Halabja", "حلبجة")]),
]
