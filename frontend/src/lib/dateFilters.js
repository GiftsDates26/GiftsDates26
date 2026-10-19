export const DATE_FILTERS = ["all", "waiting", "confirmed", "completed", "cancelled"];

const GROUPS = {
  waiting: ["INVITATION_SENT", "DATE_ACTIVITY_SELECTED", "LOCATION_PROPOSED", "TAXI_REQUESTED", "PICKUP_ADDRESS_PENDING", "PICKUP_ADDRESS_SELECTED", "escrow"],
  confirmed: ["DATE_CONFIRMED", "accepted", "confirmed"],
  completed: ["DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING", "COMPLETED", "COMPLETED_AUTO", "released"],
  cancelled: ["CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED", "cancelled", "declined"],
};

export const matchesFilter = (status, f) => f === "all" || (GROUPS[f] || []).includes(status);
export const countByFilter = (statuses) =>
  Object.fromEntries(DATE_FILTERS.map(f => [f, statuses.filter(s => matchesFilter(s, f)).length]));
