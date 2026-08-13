# -*- coding: utf-8 -*-

from __future__ import annotations

from SRC.models.mahal import Mahal


class MahalValidator:

    def validate(self, mahals: list[Mahal]) -> bool:

        mahal_count = 0
        missing_mahal_no = 0
        missing_mahal_name = 0
        negative_area = 0
        duplicate_mahal_no = 0
        missing_level = 0
        missing_building = 0
        invalid_mahal_count = 0

        mahal_no_counts: dict[str, int] = {}

        for mahal in mahals:

            number = self._normalize_text(getattr(mahal, "mahal_no", None))

            if number is None:
                continue

            mahal_no_counts[number] = mahal_no_counts.get(number, 0) + 1

        for mahal in mahals:

            mahal_count += 1

            mahal_no = self._normalize_text(getattr(mahal, "mahal_no", None))
            mahal_name = self._normalize_text(getattr(mahal, "mahal_name", None))
            level_name = self._normalize_text(getattr(mahal, "level_name", None))
            building_name = self._normalize_text(getattr(mahal, "building_name", None))

            if mahal_no is None:
                missing_mahal_no += 1

            if mahal_name is None:
                missing_mahal_name += 1

            if level_name is None:
                missing_level += 1

            if building_name is None:
                missing_building += 1

            area = getattr(mahal, "expected_area", None)
            area_negative = (area is not None) and self._is_negative_number(area)

            if area_negative:
                negative_area += 1

            has_duplicate_no = (
                mahal_no is not None
                and mahal_no_counts.get(mahal_no, 0) > 1
            )

            if has_duplicate_no:
                duplicate_mahal_no += 1

            mahal_is_valid = (
                mahal_no is not None
                and mahal_name is not None
                and (not area_negative)
                and (not has_duplicate_no)
            )

            mahal.is_valid = mahal_is_valid

            if not mahal_is_valid:
                invalid_mahal_count += 1

        passed = (
            mahal_count > 0
            and missing_mahal_no == 0
            and missing_mahal_name == 0
            and negative_area == 0
            and duplicate_mahal_no == 0
        )

        print("MAHAL VALIDATOR")
        print()
        print(f"Mahal Count : {mahal_count}")
        print()
        print(f"Missing Mahal No : {missing_mahal_no}")
        print()
        print(f"Missing Mahal Name : {missing_mahal_name}")
        print()
        print(f"Negative Area : {negative_area}")
        print()
        print(f"Duplicate Mahal No : {duplicate_mahal_no}")
        print()
        print(f"Missing Level : {missing_level}")
        print()
        print(f"Missing Building : {missing_building}")
        print()
        print(f"Invalid Mahal Count : {invalid_mahal_count}")
        print()
        print(f"PASS / FAIL : {'PASS' if passed else 'FAIL'}")

        return passed

    # -------------------------------------------------

    @staticmethod
    def _normalize_text(value) -> str | None:

        if value is None:
            return None

        text = str(value).strip()

        if text == "":
            return None

        return text

    # -------------------------------------------------

    @staticmethod
    def _is_negative_number(value) -> bool:

        try:
            return float(value) < 0.0
        except (TypeError, ValueError):
            return False
