from django.db import models


class OrganizationType(models.TextChoices):
    HOSPITAL = "HOSPITAL", "Hospital"
    MEDICAL_CENTER = "MEDICAL_CENTER", "Medical center"
    CLINIC = "CLINIC", "Clinic"
    PHARMACY = "PHARMACY", "Pharmacy"
    LABORATORY = "LABORATORY", "Laboratory"
    BEAUTY_CENTER = "BEAUTY_CENTER", "Beauty center"
    MEDICAL_COMPANY = "MEDICAL_COMPANY", "Medical company"
    HEALTHCARE_INSTITUTION = "HEALTHCARE_INSTITUTION", "Healthcare institution"
    UNIVERSITY = "UNIVERSITY", "University / college"
    RECRUITMENT_AGENCY = "RECRUITMENT_AGENCY", "Recruitment agency"
    OTHER = "OTHER", "Other approved healthcare organisation"


class VerificationStatus(models.TextChoices):
    UNVERIFIED = "UNVERIFIED", "Unverified"
    PENDING = "PENDING", "Pending review"
    VERIFIED = "VERIFIED", "Verified"
    REJECTED = "REJECTED", "Rejected"
    SUSPENDED = "SUSPENDED", "Suspended"


class RecruitmentStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    SUSPENDED = "SUSPENDED", "Suspended"


class MemberRole(models.TextChoices):
    OWNER = "OWNER", "Owner"
    RECRUITER = "RECRUITER", "Recruiter"
    VIEWER = "VIEWER", "Viewer"


class MemberStatus(models.TextChoices):
    ACTIVE = "ACTIVE", "Active"
    ENDED = "ENDED", "Ended"


class Profession(models.TextChoices):
    DOCTOR = "DOCTOR", "Physician"
    DENTIST = "DENTIST", "Dentist"
    PHARMACIST = "PHARMACIST", "Pharmacist"
    NURSE = "NURSE", "Nurse"
    MIDWIFE = "MIDWIFE", "Midwife"
    LAB_TECHNICIAN = "LAB_TECHNICIAN", "Laboratory technician"
    RADIOLOGY_TECHNICIAN = "RADIOLOGY_TECHNICIAN", "Radiology technician"
    ANESTHESIA_TECHNICIAN = "ANESTHESIA_TECHNICIAN", "Anaesthesia technician"
    PHYSIOTHERAPIST = "PHYSIOTHERAPIST", "Physiotherapist"
    NUTRITIONIST = "NUTRITIONIST", "Nutritionist"
    PSYCHOLOGIST = "PSYCHOLOGIST", "Psychologist"
    MEDICAL_ASSISTANT = "MEDICAL_ASSISTANT", "Medical assistant"
    ADMINISTRATIVE = "ADMINISTRATIVE", "Administrative / reception"
    OTHER = "OTHER", "Other healthcare profession"


class Degree(models.TextChoices):
    DIPLOMA = "DIPLOMA", "Diploma"
    BACHELOR = "BACHELOR", "Bachelor"
    HIGHER_DIPLOMA = "HIGHER_DIPLOMA", "Higher diploma"
    MASTER = "MASTER", "Master"
    PHD = "PHD", "PhD"
    BOARD = "BOARD", "Board certification"
    OTHER = "OTHER", "Other"


DEGREE_RANK = {
    Degree.DIPLOMA: 1,
    Degree.OTHER: 1,
    Degree.BACHELOR: 2,
    Degree.HIGHER_DIPLOMA: 3,
    Degree.MASTER: 4,
    Degree.BOARD: 5,
    Degree.PHD: 5,
}


class EmploymentType(models.TextChoices):
    FULL_TIME = "FULL_TIME", "Full time"
    PART_TIME = "PART_TIME", "Part time"
    CONTRACT = "CONTRACT", "Contract"
    TEMPORARY = "TEMPORARY", "Temporary"
    INTERNSHIP = "INTERNSHIP", "Internship / residency"
    LOCUM = "LOCUM", "Locum"


class WorkMode(models.TextChoices):
    ON_SITE = "ON_SITE", "On site"
    REMOTE = "REMOTE", "Remote"
    HYBRID = "HYBRID", "Hybrid"


class ShiftType(models.TextChoices):
    DAY = "DAY", "Day"
    NIGHT = "NIGHT", "Night"
    ROTATING = "ROTATING", "Rotating"
    FLEXIBLE = "FLEXIBLE", "Flexible"
    ON_CALL = "ON_CALL", "On call"


class Availability(models.TextChoices):
    IMMEDIATE = "IMMEDIATE", "Immediately"
    WITHIN_MONTH = "WITHIN_MONTH", "Within a month"
    WITHIN_3_MONTHS = "WITHIN_3_MONTHS", "Within three months"
    NOT_AVAILABLE = "NOT_AVAILABLE", "Not currently available"


class LanguageLevel(models.TextChoices):
    BASIC = "BASIC", "Basic"
    INTERMEDIATE = "INTERMEDIATE", "Intermediate"
    ADVANCED = "ADVANCED", "Advanced"
    NATIVE = "NATIVE", "Native"


class CredentialKind(models.TextChoices):
    LICENSE = "LICENSE", "Professional licence"
    CERTIFICATION = "CERTIFICATION", "Training / certification"


class JobStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    PENDING_ADMIN_REVIEW = "PENDING_ADMIN_REVIEW", "Pending administrator review"
    PUBLISHED = "PUBLISHED", "Published"
    CLOSED = "CLOSED", "Closed"
    EXPIRED = "EXPIRED", "Expired"
    REJECTED = "REJECTED", "Rejected"
    SUSPENDED = "SUSPENDED", "Suspended"
    ARCHIVED = "ARCHIVED", "Archived"


class ApplicationStatus(models.TextChoices):
    SUBMITTED = "SUBMITTED", "Submitted"
    REVIEWING = "REVIEWING", "Reviewing"
    SHORTLISTED = "SHORTLISTED", "Shortlisted"
    INTERVIEW = "INTERVIEW", "Interview"
    ACCEPTED = "ACCEPTED", "Accepted"
    REJECTED = "REJECTED", "Rejected"
    WITHDRAWN = "WITHDRAWN", "Withdrawn"


ACTIVE_APPLICATION_STATUSES = ("SUBMITTED", "REVIEWING", "SHORTLISTED", "INTERVIEW", "ACCEPTED")
SEEKER_WITHDRAWABLE = ("SUBMITTED", "REVIEWING", "SHORTLISTED", "INTERVIEW")
TERMINAL_APPLICATION_STATUSES = ("ACCEPTED", "REJECTED", "WITHDRAWN")
# An invitation that still represents live outreach: waiting for an answer, or
# accepted but not yet turned into an application. Both block a duplicate.
ACTIVE_INVITATION_STATUSES = ("PENDING", "ACCEPTED")
# employer transitions: from -> allowed to
EMPLOYER_APPLICATION_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "SUBMITTED": ("REVIEWING", "SHORTLISTED", "REJECTED"),
    "REVIEWING": ("SHORTLISTED", "REJECTED"),
    "SHORTLISTED": ("INTERVIEW", "REJECTED", "ACCEPTED"),
    "INTERVIEW": ("ACCEPTED", "REJECTED"),
}


class InvitationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    EXPIRED = "EXPIRED", "Expired"
    CANCELLED = "CANCELLED", "Cancelled"


class InterviewMode(models.TextChoices):
    IN_PERSON = "IN_PERSON", "In person"
    ONLINE = "ONLINE", "Online (details shared inside Racheeta)"


class InterviewStatus(models.TextChoices):
    PROPOSED = "PROPOSED", "Proposed"
    ACCEPTED = "ACCEPTED", "Accepted"
    DECLINED = "DECLINED", "Declined"
    CANCELLED = "CANCELLED", "Cancelled"


class MessageSide(models.TextChoices):
    EMPLOYER = "EMPLOYER", "Employer"
    CANDIDATE = "CANDIDATE", "Candidate"
