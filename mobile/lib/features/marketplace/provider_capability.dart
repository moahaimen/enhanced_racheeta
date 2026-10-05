/// Capability codes of the marketplace (`ROLE_CAPABILITIES` in the backend). Hints from `/me` for
/// showing screens; the backend still requires a VERIFIED provider profile to browse and a company
/// profile for the company workspace, and enforces ownership on every call.
const marketplaceBrowseCapability = 'marketplace.view_targeted_products';
const marketplaceCompanyCapability = 'marketplace.manage_own_products';
