/// Recruiter access is an employer MEMBERSHIP, not a `/me` capability, so it is decided by the
/// server's dashboard index (`GET /dashboards/` lists `recruiter`); the backend still authorizes
/// every recruiter call from the membership.
const recruiterDashboardKey = 'recruiter';
