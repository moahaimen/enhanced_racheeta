import { apiRequest } from '../client'
import type {
  AdminDashboard,
  DashboardIndex,
  DoctorDashboard,
  FacilityDashboard,
  MedicalCompanyDashboard,
  PatientDashboard,
  RecruiterDashboard,
} from '../dashboards.types'

const BASE = '/api/v1/dashboards'

// Read-only and parameterless: ownership is decided by the server from the signed-in account.
export const getIndex = (signal?: AbortSignal) => apiRequest<DashboardIndex>(`${BASE}/`, { signal })
export const getPatient = (signal?: AbortSignal) => apiRequest<PatientDashboard>(`${BASE}/patient`, { signal })
export const getDoctor = (signal?: AbortSignal) => apiRequest<DoctorDashboard>(`${BASE}/doctor`, { signal })
export const getFacility = (signal?: AbortSignal) => apiRequest<FacilityDashboard>(`${BASE}/facility`, { signal })
export const getCompany = (signal?: AbortSignal) =>
  apiRequest<MedicalCompanyDashboard>(`${BASE}/company`, { signal })
export const getRecruiter = (signal?: AbortSignal) =>
  apiRequest<RecruiterDashboard>(`${BASE}/recruiter`, { signal })
export const getAdmin = (signal?: AbortSignal) => apiRequest<AdminDashboard>(`${BASE}/admin`, { signal })
