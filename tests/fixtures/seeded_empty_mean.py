"""Seeded logic bug. The AST analyzer has no rule for this.

mean([]) raises ZeroDivisionError. tools/code_analyzer.py does not report it.
"""


def mean(values):
    return sum(values) / len(values)
