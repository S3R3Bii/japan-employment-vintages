import copy, sys, unittest, tempfile, zipfile
from fractions import Fraction as Q
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from analyze import growth, certified_sign, certified_alert, previous_year, sign
from build_inputs import validate_projection, period_from_label, decode_book


class GrowthTests(unittest.TestCase):
    def test_zero_change(self):
        self.assertEqual(growth(100, 100)[0], 0)

    def test_positive(self):
        self.assertEqual(growth(101, 100)[0], Q(1, 100))

    def test_negative(self):
        self.assertEqual(growth(99, 100)[0], -Q(1, 100))

    def test_zero_denominator(self):
        self.assertRaises(AssertionError, growth, 100, 0)

    def test_zero_numerator(self):
        self.assertRaises(AssertionError, growth, 0, 100)

    def test_rounding_enclosure(self):
        self.assertEqual(growth(100, 100)[1:], (Q(-2, 201), Q(2, 199)))

    def test_rounding_positive(self):
        self.assertEqual(certified_sign(*growth(102, 100)[1:]), "positive")

    def test_rounding_negative(self):
        self.assertEqual(certified_sign(*growth(98, 100)[1:]), "negative")

    def test_closed_zero_boundary(self):
        self.assertEqual(certified_sign(*growth(101, 100)[1:]), "ambiguous")

    def test_closed_negative_zero_boundary(self):
        self.assertEqual(certified_sign(*growth(99, 100)[1:]), "ambiguous")

    def test_exact_positive_cutoff(self):
        self.assertEqual(certified_alert(Q(1, 100), Q(2, 100), Q(1, 100)), "alert")

    def test_exact_negative_cutoff(self):
        self.assertEqual(certified_alert(Q(-2, 100), Q(-1, 100), Q(1, 100)), "alert")

    def test_inside_cutoff(self):
        self.assertEqual(certified_alert(Q(-1, 200), Q(1, 200), Q(1, 100)), "no_alert")

    def test_touch_cutoff(self):
        self.assertEqual(certified_alert(0, Q(1, 100), Q(1, 100)), "ambiguous")

    def test_span_both_cutoffs(self):
        self.assertEqual(certified_alert(Q(-2, 100), Q(2, 100), Q(1, 100)), "ambiguous")

    def test_invalid_interval(self):
        self.assertRaises(AssertionError, certified_sign, 1, -1)

    def test_leap_year_lag(self):
        self.assertEqual(previous_year("2020-02"), "2019-02")

    def test_december_lag(self):
        self.assertEqual(previous_year("2021-12"), "2020-12")

    def test_invalid_month(self):
        self.assertRaises(AssertionError, previous_year, "2020-13")

    def test_mixing_changes_direction(self):
        self.assertLess(growth(101, 103)[0], 0)
        self.assertGreater(growth(101, 100)[0], 0)

    def test_count_scale_preserves_point_but_narrows_rounding(self):
        small = growth(103, 100)
        large = growth(1030, 1000)
        self.assertEqual(small[0], large[0])
        self.assertGreater(large[1], small[1])
        self.assertLess(large[2], small[2])


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            dict(
                vintage=v,
                region=g,
                period=f"{y}-{m:02}",
                concept="employed_persons",
                sex="total",
                adjustment="original",
                unit="ten_thousand_persons",
                native_type="n",
                formula="false",
                value_token="100",
            )
            for v in ["pre2022", "current"]
            for g in ["Southern-Kanto", "Kinki"]
            for y in range(2016, 2022)
            for m in range(1, 13)
        ]

    def test_full_fixed_cohort(self):
        self.assertEqual(validate_projection(self.rows)["source_count_cells"], 288)

    def test_missing_is_not_zero(self):
        self.rows.pop()
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_conflicting_duplicate(self):
        self.rows[-1] = dict(self.rows[0], value_token="101")
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_zero_unavailable(self):
        self.rows[0]["value_token"] = "0"
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_wrong_unit(self):
        self.rows[0]["unit"] = "persons"
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_employee_not_employed(self):
        self.rows[0]["concept"] = "employees"
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_wrong_sex(self):
        self.rows[0]["sex"] = "male"
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_seasonal_adjustment(self):
        self.rows[0]["adjustment"] = "seasonal"
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_formula_not_value(self):
        self.rows[0]["formula"] = "true"
        self.assertRaises(AssertionError, validate_projection, self.rows)

    def test_era_transition(self):
        self.assertEqual(period_from_label("令和元年 5月", "May", (2019, 4)), (2019, 5))

    def test_heisei(self):
        self.assertEqual(
            period_from_label("平成28年 1月", "Jan.", (2015, 12)), (2016, 1)
        )

    def test_gregorian_anchor(self):
        self.assertEqual(period_from_label(" 2020 2", "Feb.", (2020, 1)), (2020, 2))

    def test_english_month_conflict(self):
        self.assertRaises(
            AssertionError, period_from_label, "平成28年 1月", "Feb.", (2015, 12)
        )

    def test_gap_rejected(self):
        self.assertRaises(AssertionError, period_from_label, "3", "Mar.", (2020, 1))

    def test_phonetic_annotation_is_not_visible_text(self):
        ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / "authored.xlsx"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr(
                    "xl/sharedStrings.xml",
                    f'<sst xmlns="{ns}"><si><t>平成28年 1月</t><rPh sb="0" eb="2"><t>ヘイセイ</t></rPh></si></sst>',
                )
                z.writestr(
                    "xl/workbook.xml",
                    f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="fixture" sheetId="1" r:id="r1"/></sheets></workbook>',
                )
                z.writestr(
                    "xl/_rels/workbook.xml.rels",
                    '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>',
                )
                z.writestr(
                    "xl/worksheets/sheet1.xml",
                    f'<worksheet xmlns="{ns}"><sheetData><row r="1"><c r="B1" t="s"><v>0</v></c><c r="F1"><v>100</v></c></row></sheetData></worksheet>',
                )
            cells = decode_book(p, "fixture")
            self.assertEqual(cells["B1"]["text"], "平成28年 1月")
            self.assertEqual(cells["F1"]["raw_token"], "100")


if __name__ == "__main__":
    unittest.main()
