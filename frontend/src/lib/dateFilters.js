export const DATE_FILTERS = ["all", "waiting", "confirmed", "completed", "cancelled"];

const GROUPS = {
  waiting: ["INVITATION_SENT", "DATE_ACTIVITY_SELECTED", "LOCATION_PROPOSED", "TAXI_REQUESTED", "PICKUP_ADDRESS_PENDING", "PICKUP_ADDRESS_SELECTED", "escrow"],
  confirmed: ["DATE_CONFIRMED", "accepted", "confirmed"],
  completed: ["DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING", "COMPLETED", "COMPLETED_AUTO", "released"],
  cancelled: ["CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED", "cancelled", "declined"],
};

export const DATE_TABS = ["requests", "mine", "confirmed", "review", "cancelled", "past"];
const REVIEW = ["REPORTED", "UNDER_ADMIN_REVIEW"];
// booked dates keep their status while a report is open — treat them as REPORTED for tabs
export const bookingStatus = (b) => (b.report && (b.report.status || "open") === "open" ? "REPORTED" : b.status);
export const tabOf = (status, incoming) => {
  if (GROUPS.cancelled.includes(status)) return "cancelled";
  if (REVIEW.includes(status)) return "review";
  if (GROUPS.completed.includes(status)) return "past";
  if (GROUPS.confirmed.includes(status)) return "confirmed";
  return incoming ? "requests" : "mine";
};
export const countByTab = (items) =>
  Object.fromEntries(DATE_TABS.map(k => [k, items.filter(x => tabOf(x.status, x.inc) === k).length]));

export const matchesFilter = (status, f) => f === "all" || (GROUPS[f] || []).includes(status);
export const countByFilter = (statuses) =>
  Object.fromEntries(DATE_FILTERS.map(f => [f, statuses.filter(s => matchesFilter(s, f)).length]));
