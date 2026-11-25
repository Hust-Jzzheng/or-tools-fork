// Copyright 2026 Google LLC
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "ortools/sat/sat_solver_clause_cleanup.h"

#include <algorithm>
#include <random>
#include <set>
#include <utility>
#include <vector>

#include "gtest/gtest.h"

namespace operations_research {
namespace sat {
namespace {

struct TestClauseInfo {
  int lbd;
  double activity;
};
using TestEntry = std::pair<int, TestClauseInfo>;

bool IsWorse(const TestEntry& a, const TestEntry& b, bool lbd_ordering) {
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
}

std::set<int> OldSortAndExpandSelection(std::vector<TestEntry> entries,
                                        int num_kept_clauses,
                                        bool lbd_ordering) {
  std::sort(entries.begin(), entries.end(),
            [lbd_ordering](const TestEntry& a, const TestEntry& b) {
              return IsWorse(a, b, lbd_ordering);
            });
  int num_deleted_clauses =
      static_cast<int>(entries.size()) - num_kept_clauses;
  if (num_kept_clauses > 0) {
    while (num_deleted_clauses > 0) {
      const TestClauseInfo& a = entries[num_deleted_clauses].second;
      const TestClauseInfo& b = entries[num_deleted_clauses - 1].second;
      if (a.activity != b.activity || a.lbd != b.lbd) break;
      --num_deleted_clauses;
      ++num_kept_clauses;
    }
  }

  std::set<int> deleted_ids;
  for (int i = 0; i < num_deleted_clauses; ++i) {
    deleted_ids.insert(entries[i].first);
  }
  return deleted_ids;
}

std::set<int> SelectionBasedSelection(std::vector<TestEntry> entries,
                                      int num_kept_clauses,
                                      bool lbd_ordering) {
  const int num_deleted_clauses = internal::SelectLearnedClausesToDelete(
      &entries, num_kept_clauses, lbd_ordering);
  std::set<int> deleted_ids;
  for (int i = 0; i < num_deleted_clauses; ++i) {
    deleted_ids.insert(entries[i].first);
  }
  return deleted_ids;
}

TEST(SatSolverClauseCleanupTest, MatchesSortAndExpandOnRandomInputs) {
  std::mt19937_64 rng(1234567);
  for (int trial = 0; trial < 20000; ++trial) {
    const int num_entries = static_cast<int>(rng() % 200);
    std::vector<TestEntry> entries;
    entries.reserve(num_entries);
    for (int i = 0; i < num_entries; ++i) {
      // Small domains deliberately create many ties at the boundary.
      entries.push_back({i, {static_cast<int>(rng() % 12),
                             static_cast<double>(rng() % 9) / 3.0}});
    }
    const int num_kept_clauses =
        num_entries == 0 ? 0 : static_cast<int>(rng() % (num_entries + 1));
    for (const bool lbd_ordering : {false, true}) {
      EXPECT_EQ(OldSortAndExpandSelection(entries, num_kept_clauses,
                                          lbd_ordering),
                SelectionBasedSelection(entries, num_kept_clauses,
                                        lbd_ordering))
          << "trial=" << trial << " entries=" << num_entries
          << " keep=" << num_kept_clauses
          << " lbd_ordering=" << lbd_ordering;
    }
  }
}

TEST(SatSolverClauseCleanupTest, PreservesBoundaryTieAndCornerCases) {
  std::vector<TestEntry> all_tied = {
      {0, {3, 1.0}}, {1, {3, 1.0}}, {2, {3, 1.0}}, {3, {3, 1.0}}};
  EXPECT_EQ(internal::SelectLearnedClausesToDelete(&all_tied, 2, true), 0);

  std::vector<TestEntry> keep_none = {
      {0, {3, 1.0}}, {1, {3, 1.0}}, {2, {3, 1.0}}, {3, {3, 1.0}}};
  EXPECT_EQ(internal::SelectLearnedClausesToDelete(&keep_none, 0, true), 4);

  std::vector<TestEntry> keep_all = {
      {0, {3, 1.0}}, {1, {2, 2.0}}, {2, {1, 3.0}}, {3, {4, 0.5}}};
  EXPECT_EQ(internal::SelectLearnedClausesToDelete(&keep_all, 4, false), 0);
}

}  // namespace
}  // namespace sat
}  // namespace operations_research
