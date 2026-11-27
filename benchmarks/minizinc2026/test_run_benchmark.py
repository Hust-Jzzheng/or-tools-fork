"""Unit tests for MiniZinc benchmark output classification."""

import unittest

from run_benchmark import classify


class ClassifyTest(unittest.TestCase):
    def test_intermediate_solution_without_terminal_marker_is_feasible(self):
        output = "A = [1, 2, 1];\n----------\n%%%mzn-stat: nSolutions=1"
        self.assertEqual(classify(output, return_code=0, timed_out=False),
                         ("FEASIBLE", True))

    def test_solution_then_unknown_marker_is_feasible(self):
        output = "x = 1;\n----------\n=====UNKNOWN====="
        self.assertEqual(classify(output, return_code=0, timed_out=False),
                         ("FEASIBLE", True))

    def test_timeout_with_incumbent_preserves_timeout_status(self):
        output = "x = 1;\n----------"
        self.assertEqual(classify(output, return_code=124, timed_out=True),
                         ("TIMEOUT", True))

    def test_optimal_marker(self):
        self.assertEqual(classify("x = 1;\n----------\n=====OPTIMAL=====",
                                  return_code=0, timed_out=False),
                         ("OPTIMAL", True))

    def test_satisfiable_marker(self):
        self.assertEqual(classify("x = 1;\n=====SATISFIABLE=====",
                                  return_code=0, timed_out=False),
                         ("FEASIBLE", True))

    def test_unsatisfiable_marker(self):
        self.assertEqual(classify("=====UNSATISFIABLE=====",
                                  return_code=0, timed_out=False),
                         ("UNSAT", False))

    def test_unknown_without_solution(self):
        self.assertEqual(classify("=====UNKNOWN=====",
                                  return_code=0, timed_out=False),
                         ("UNKNOWN", False))

    def test_error_with_partial_solution_is_still_error(self):
        output = "x = 1;\n----------\n=====ERROR====="
        self.assertEqual(classify(output, return_code=1, timed_out=False),
                         ("ERROR", True))


if __name__ == "__main__":
    unittest.main()
