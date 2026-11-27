#ifndef OR_TOOLS_SAT_SAT_SOLVER_CLAUSE_CLEANUP_H_
#define OR_TOOLS_SAT_SAT_SOLVER_CLAUSE_CLEANUP_H_

#include <algorithm>
#include <vector>

namespace operations_research {
namespace sat {
namespace internal {

// Returns the number of entries to delete and moves them to the beginning of
// `entries`. The ranking follows the existing clause-cleanup policy. Entries
// tied with the first kept entry are retained, matching the deletion-set
// semantics of sort-and-expand.
//
// This only selects the deletion boundary; it does not sort either partition.
// The caller must not rely on the order in which deleted clauses are visited.
template <typename Entry>
int SelectLearnedClausesToDelete(std::vector<Entry>* entries,
                                 int num_kept_clauses,
                                 bool lbd_ordering) {
  const int num_entries = static_cast<int>(entries->size());
  int num_deleted_clauses = num_entries - num_kept_clauses;
  if (num_deleted_clauses <= 0 || num_deleted_clauses >= num_entries) {
    return num_deleted_clauses;
  }

  // The comparator orders clauses from least useful to most useful. Clauses
  // with identical (LBD, activity) values are equivalent.
  const auto is_worse = [lbd_ordering](const Entry& a, const Entry& b) {
    if (lbd_ordering) {
      if (a.second.lbd != b.second.lbd) {
        return a.second.lbd > b.second.lbd;
      }
      return a.second.activity < b.second.activity;
    }
    if (a.second.activity != b.second.activity) {
      return a.second.activity < b.second.activity;
    }
    return a.second.lbd > b.second.lbd;
  };

  // We only need the deletion threshold, not a complete ordering of all
  // clauses. Select the first clause that would be kept by a full sort.
  const auto nth = entries->begin() + num_deleted_clauses;
  std::nth_element(entries->begin(), nth, entries->end(), is_worse);
  const int threshold_lbd = nth->second.lbd;
  const double threshold_activity = nth->second.activity;

  // Preserve the entire boundary tie group. This is important because the
  // original clauses_info map is pointer-keyed and its iteration order is not
  // deterministic.
  const auto strictly_worse_than_threshold =
      [lbd_ordering, threshold_lbd, threshold_activity](const Entry& entry) {
        if (lbd_ordering) {
          if (entry.second.lbd != threshold_lbd) {
            return entry.second.lbd > threshold_lbd;
          }
          return entry.second.activity < threshold_activity;
        }
        if (entry.second.activity != threshold_activity) {
          return entry.second.activity < threshold_activity;
        }
        return entry.second.lbd > threshold_lbd;
      };
  // nth_element guarantees that no element after nth is strictly worse
  // than the threshold, so partitioning the prefix is sufficient.
  const auto first_kept = std::partition(
      entries->begin(), nth, strictly_worse_than_threshold);
  return static_cast<int>(first_kept - entries->begin());
}

}  // namespace internal
}  // namespace sat
}  // namespace operations_research

#endif  // OR_TOOLS_SAT_SAT_SOLVER_CLAUSE_CLEANUP_H_
