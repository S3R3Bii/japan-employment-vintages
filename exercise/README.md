# Implement a count-version guard

A dashboard receives a current count and a same-month prior-year count. Implement a function that returns exact year-on-year growth and a conservative rounding enclosure only when geography, employment concept, sex, adjustment, native unit and dataset version match. A missing or conflicting identity must return an unavailable reason. Do not silently interpret a revised employment count as a vacancy or an employees-only count.

Use the three authored examples in ../examples. Their counts of 101 and 100 are invented fixture values, not Japanese statistics. The coherent pair returns 1/100 growth with a rounding-ambiguous sign. The mixed-version pair must be unavailable, even though a calculator can divide the numbers.

Check an exact threshold boundary, missing version, different region, wrong lag, zero/missing count and a floating-point value. Explain why the rounding enclosure does not cover sampling uncertainty. Then compare your function with ../src/cli.py and the finite CLI fixtures. A matching version string is a declared input contract; this reference guard cannot authenticate a publisher or establish compatibility across separately labeled files.

Run `python src/cli.py examples/current-authored.json examples/lag-authored.json` from the repository root, then substitute examples/lag-mixed-authored.json. No network, account or key is needed. The implementation exercise is offline learning code, with no deployed service or measured user benefit.
