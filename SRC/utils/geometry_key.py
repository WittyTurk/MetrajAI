# -*- coding: utf-8 -*-

from __future__ import annotations


class GeometryKey:

    DEFAULT_PRECISION = 6

    @staticmethod
    def point(point_or_x, y=None, precision=DEFAULT_PRECISION):

        if y is None:
            x = point_or_x.x
            y = point_or_x.y
        else:
            x = point_or_x

        if precision is None:
            return (x, y)

        return (
            round(x, precision),
            round(y, precision)
        )

    @staticmethod
    def segment(start, end, thickness=None, precision=DEFAULT_PRECISION):

        start_key = GeometryKey.point(start, precision=precision)
        end_key = GeometryKey.point(end, precision=precision)

        key = start_key + end_key

        if thickness is not None:
            key = key + (thickness,)

        return key
