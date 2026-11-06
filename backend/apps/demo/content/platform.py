"""LOCAL demo content for the platform-completion slice (docs/PLATFORM_COMPLETION_MATRIX.md).

Every person and organization is fictional. Accounts use the demo e-mail domain and the shared
local demo password (never printed or committed).
"""

# Practitioners registered with the NEW onboarding types (account_type set explicitly).
# key, display name, provider type, specialty slug, account type, governorate, city
TYPED_PROVIDERS = [
    ("dr-noor-dentist", "د. نور الحسني | Dr Noor Al-Hasani", "DOCTOR", "dentistry", "DENTIST",
     "baghdad", "baghdad"),
    ("mw-huda-midwife", "هدى الكرخي | Huda Al-Karkhi", "NURSE", "midwifery", "MIDWIFE",
     "baghdad", "baghdad"),
]  # fmt: skip

# A verified NON-HEALTHCARE employer (organization type BUSINESS) owned by an EMPLOYER account.
BUSINESS_EMPLOYER = {
    "owner_key": "employer-rafidain-tech",
    "owner_name": "سلام الربيعي | Salam Al-Rubaie",
    "name": "شركة الرافدين للحلول البرمجية | Rafidain Software Solutions",
    "description_ar": "شركة برمجيات توضيحية توظف في التقنية والمالية والمبيعات فقط.",
    "description_en": "Fictional software company hiring for technology, finance and sales only.",
}

# key suffix, title ar, title en, profession, degree, years, salary min, salary max
BUSINESS_JOBS = [
    ("dev", "مطور برمجيات ويب", "Web Software Developer", "SOFTWARE_DEVELOPER", "BACHELOR", 2,
     1500000, 2200000),
    ("acc", "محاسب", "Accountant", "ACCOUNTANT", "BACHELOR", 3, 1100000, 1500000),
    ("sales", "مندوب مبيعات حلول برمجية", "Software Sales Representative", "SALES", "BACHELOR", 1,
     900000, 1300000),
    ("hr", "أخصائي موارد بشرية", "HR Specialist", "HUMAN_RESOURCES", "BACHELOR", 2, 1000000,
     1400000),
]  # fmt: skip

# Candidates registered as JOB_SEEKER accounts.
# key, name, profession, title, degree, years
TYPED_SEEKERS = [
    ("seeker-biomed-ali", "علي الدليمي | Ali Al-Dulaimi", "BIOMEDICAL_ENGINEER",
     "مهندس طبي (أجهزة تصوير)", "BACHELOR", 4),
    ("seeker-sales-rana", "رنا العبيدي | Rana Al-Obaidi", "SALES", "مندوبة مبيعات", "BACHELOR", 3),
    ("seeker-hr-sama", "سما الجبوري | Sama Al-Jubouri", "HUMAN_RESOURCES",
     "أخصائية موارد بشرية", "BACHELOR", 5),
]  # fmt: skip

# Accounts that registered with a type but have not set up yet (they see the setup step).
# key, name, account type
SETUP_ACCOUNTS = [
    ("employer-setup-new", "مؤسسة قيد الإعداد | New employer (setup)", "EMPLOYER"),
    ("jobseeker-setup-new", "باحث عن عمل جديد | New job seeker (setup)", "JOB_SEEKER"),
]

# Applications to the business employer: candidate account key, job key suffix.
BUSINESS_APPLICATIONS = [
    ("seeker-it-mustafa", "dev"),
    ("seeker-accountant-haidar", "acc"),
    ("seeker-sales-rana", "sales"),
]

# Property inquiries: tag, base listing index, asker account key, share contact, outcome, message
# outcome: open | answered | closed | withdrawn
INQUIRIES = [
    ("sara-open", 0, "patient-sara", False, "open",
     "هل العيادة متاحة للإيجار من الشهر القادم؟ | Is the clinic available from next month?"),
    ("dalia-answered", 1, "dr-dalia-tamimi", True, "answered",
     "أرغب بمعاينة العقار هذا الأسبوع. | I would like to view the property this week."),
    ("ali-closed", 0, "patient-ali", False, "closed",
     "هل السعر قابل للتفاوض؟ | Is the price negotiable?"),
    ("fatima-withdrawn", 2, "patient-fatima", False, "withdrawn",
     "هل يوجد موقف سيارات؟ | Is there parking?"),
]  # fmt: skip

INQUIRY_ANSWER = "نعم، يمكن ترتيب موعد للمعاينة. | Yes, a viewing can be arranged."
